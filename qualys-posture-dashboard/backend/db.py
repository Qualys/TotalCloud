"""SQLite schema + access for the posture dashboard.

Two fact tables keep a rolling 30-day daily history:

  posture_daily     — per (date, account, csp, control) pass/fail counts (Controls view + count trend)
  resource_findings — per (date, account, csp, control, resource) rows (Resource view)

Resource identity follows the LIVE CloudView shape: there is NO arn; a resource is keyed by
(accountId, resourceType, resourceId, region). We also store Qualys's own per-finding lifecycle
(firstEvaluated / lastEvaluated / dateFixed / dateReopen / prevResult) so the Resource view can
flag NEW / FIXED / REOPENED from a single Refresh — not only from accumulated local snapshots.

Writes are an idempotent per-day replace (re-refreshing "today" overwrites today's rows), then a
prune of anything older than RETENTION_DAYS.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import crypto_store

RETENTION_DAYS = 30
_DATA_DIR = Path(__file__).resolve().parent / "data"
_LOCK = threading.Lock()


def _db_path() -> Path:
    d = Path(os.environ.get("QPD_DATA_DIR", str(_DATA_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d / "posture.db"


@contextmanager
def connect():
    conn = sqlite3.connect(_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS posture_daily (
                date         TEXT NOT NULL,
                account      TEXT NOT NULL,
                csp          TEXT NOT NULL,
                control_id   TEXT NOT NULL,
                control_name TEXT,
                criticality  TEXT,
                service      TEXT,
                policies     TEXT,          -- JSON array of Qualys policyNames the control belongs to
                passed       INTEGER NOT NULL DEFAULT 0,
                failed       INTEGER NOT NULL DEFAULT 0,
                total        INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (date, account, csp, control_id)
            );

            CREATE TABLE IF NOT EXISTS resource_findings (
                date            TEXT NOT NULL,
                account         TEXT NOT NULL,
                csp             TEXT NOT NULL,
                control_id      TEXT NOT NULL,
                resource_id     TEXT NOT NULL,
                resource_type   TEXT NOT NULL DEFAULT '',
                region          TEXT NOT NULL DEFAULT '',
                criticality     TEXT,
                result          TEXT,
                first_evaluated TEXT,
                last_evaluated  TEXT,
                date_fixed      TEXT,
                date_reopen     TEXT,
                prev_result     TEXT,
                evidence_json   TEXT,
                tags_json       TEXT,          -- JSON array of provider tags [{key, value}, …] (AWS cloudTags)
                qualys_tags_json TEXT,         -- JSON array of Qualys asset tag NAMES (resource-inventory API)
                PRIMARY KEY (date, account, csp, control_id, resource_type, resource_id, region)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            -- Connector account_id → display name (alias), captured at sync time so the UI can show
            -- "acme-prod (123456789012)" instead of a bare number. Additive; safe to add anytime.
            CREATE TABLE IF NOT EXISTS accounts (
                account TEXT NOT NULL,
                csp     TEXT NOT NULL,
                name    TEXT,
                PRIMARY KEY (account, csp)
            );

            -- Per-control remediation guidance (manual / CLI / build-time / rationale / references),
            -- captured from the control-metadata API at sync time. Shown in the drawers on all screens.
            CREATE TABLE IF NOT EXISTS control_meta (
                csp         TEXT NOT NULL,
                control_id  TEXT NOT NULL,
                remediation TEXT,       -- JSON: {manual, cli, buildtime, rationale, specification, references}
                PRIMARY KEY (csp, control_id)
            );

            CREATE INDEX IF NOT EXISTS idx_posture_date ON posture_daily(date);
            CREATE INDEX IF NOT EXISTS idx_res_date ON resource_findings(date);
            CREATE INDEX IF NOT EXISTS idx_posture_control ON posture_daily(control_id);
            CREATE INDEX IF NOT EXISTS idx_res_type ON resource_findings(date, resource_type);
            CREATE INDEX IF NOT EXISTS idx_res_region ON resource_findings(date, region);
            """
        )
        # Additive migrations for DBs created before a column existed (idempotent).
        _add_column(c, "posture_daily", "policies", "TEXT")
        _add_column(c, "resource_findings", "tags_json", "TEXT")
        _add_column(c, "resource_findings", "qualys_tags_json", "TEXT")
        # Lifecycle columns behind the NEW/EXISTING/FIXED/REOPENED status. Present in the
        # CREATE above for fresh DBs; added here for a DB created by a build that predated
        # them, so upgrading over an existing posture.db doesn't hit "no such column".
        _add_column(c, "resource_findings", "date_fixed", "TEXT")
        _add_column(c, "resource_findings", "date_reopen", "TEXT")
        _add_column(c, "resource_findings", "prev_result", "TEXT")


def _add_column(c, table: str, column: str, decl: str) -> None:
    cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


# ── settings / creds ─────────────────────────────────────────────────────────
_SECRET_KEYS = {"qualys_password"}


def set_setting(key: str, value: str) -> None:
    stored = crypto_store.encrypt(value) if key in _SECRET_KEYS else value
    with connect() as c:
        c.execute("INSERT INTO settings(key, value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, stored))


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with connect() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    return crypto_store.decrypt(row["value"]) if key in _SECRET_KEYS else row["value"]


def save_creds(gateway_url: str, username: str, password: str) -> None:
    set_setting("qualys_gateway_url", gateway_url.strip())
    set_setting("qualys_username", username.strip())
    set_setting("qualys_password", password)


def get_creds() -> Optional[Dict[str, str]]:
    gw, user, pwd = get_setting("qualys_gateway_url"), get_setting("qualys_username"), get_setting("qualys_password")
    if not (gw and user and pwd):
        return None
    return {"gateway_url": gw, "username": user, "password": pwd}


def creds_set() -> bool:
    return get_creds() is not None


# ── daily replace + prune ────────────────────────────────────────────────────
def _upsert_posture(c, rows: Iterable[Dict], d: str) -> int:
    n = 0
    for r in rows:
        pols = r.get("policies")
        pols_json = pols if isinstance(pols, str) else json.dumps(pols or [])
        c.execute(
            """INSERT INTO posture_daily
               (date, account, csp, control_id, control_name, criticality, service, policies, passed, failed, total)
               VALUES (:date,:account,:csp,:control_id,:control_name,:criticality,:service,:policies,:passed,:failed,:total)
               ON CONFLICT(date, account, csp, control_id) DO UPDATE SET
                 control_name=excluded.control_name, criticality=excluded.criticality,
                 service=excluded.service, policies=excluded.policies,
                 passed=excluded.passed, failed=excluded.failed, total=excluded.total""",
            {"date": d, "account": r["account"], "csp": r["csp"], "control_id": r["control_id"],
             "control_name": r.get("control_name"), "criticality": r.get("criticality"),
             "service": r.get("service"), "policies": pols_json,
             "passed": r.get("passed", 0), "failed": r.get("failed", 0), "total": r.get("total", 0)})
        n += 1
    return n


def _upsert_resources(c, rows: Iterable[Dict], d: str) -> int:
    n = 0
    for r in rows:
        evidence = r.get("evidence_json")
        if not isinstance(evidence, str):
            evidence = json.dumps(evidence or [])
        tags = r.get("tags_json")
        if not isinstance(tags, str):
            tags = json.dumps(tags or [])
        qtags = r.get("qualys_tags_json")
        if not isinstance(qtags, str):
            qtags = json.dumps(qtags or [])
        c.execute(
            """INSERT INTO resource_findings
               (date, account, csp, control_id, resource_id, resource_type, region, criticality, result,
                first_evaluated, last_evaluated, date_fixed, date_reopen, prev_result, evidence_json,
                tags_json, qualys_tags_json)
               VALUES (:date,:account,:csp,:control_id,:resource_id,:resource_type,:region,:criticality,:result,
                :first_evaluated,:last_evaluated,:date_fixed,:date_reopen,:prev_result,:evidence_json,
                :tags_json,:qualys_tags_json)
               ON CONFLICT(date, account, csp, control_id, resource_type, resource_id, region) DO UPDATE SET
                 criticality=excluded.criticality, result=excluded.result,
                 first_evaluated=excluded.first_evaluated, last_evaluated=excluded.last_evaluated,
                 date_fixed=excluded.date_fixed, date_reopen=excluded.date_reopen,
                 prev_result=excluded.prev_result, evidence_json=excluded.evidence_json,
                 tags_json=excluded.tags_json, qualys_tags_json=excluded.qualys_tags_json""",
            {"date": d, "account": r["account"], "csp": r["csp"], "control_id": r["control_id"],
             "resource_id": r["resource_id"], "resource_type": r.get("resource_type", ""),
             "region": r.get("region", ""), "criticality": r.get("criticality"),
             "result": r.get("result", "FAIL"), "first_evaluated": r.get("first_evaluated"),
             "last_evaluated": r.get("last_evaluated"), "date_fixed": r.get("date_fixed"),
             "date_reopen": r.get("date_reopen"), "prev_result": r.get("prev_result"),
             "evidence_json": evidence, "tags_json": tags, "qualys_tags_json": qtags})
        n += 1
    return n


def replace_day(d: str, posture_rows: List[Dict], resource_rows: List[Dict]) -> Dict[str, int]:
    with connect() as c:
        c.execute("DELETE FROM posture_daily WHERE date=?", (d,))
        c.execute("DELETE FROM resource_findings WHERE date=?", (d,))
        p = _upsert_posture(c, posture_rows, d)
        r = _upsert_resources(c, resource_rows, d)
    return {"posture_rows": p, "resource_rows": r}


def write_account_posture(d: str, account: str, csp: str, posture_rows: List[Dict]) -> int:
    """Replace ONE account's control-posture slice for TODAY (leaves its resource_findings intact).
    The incremental sync calls this in a fast first pass so the Controls view lights up account by
    account within seconds — latest_date() flips to `d` after the first account writes."""
    with connect() as c:
        c.execute("DELETE FROM posture_daily WHERE date=? AND account=? AND csp=?", (d, account, csp))
        return _upsert_posture(c, posture_rows, d)


def write_account_resources(d: str, account: str, csp: str, resource_rows: List[Dict]) -> int:
    """Replace ONE account's resource-findings slice for TODAY (leaves its posture_daily intact).
    Called in the slower second pass; the Resource view fills in behind the Controls view."""
    with connect() as c:
        c.execute("DELETE FROM resource_findings WHERE date=? AND account=? AND csp=?", (d, account, csp))
        return _upsert_resources(c, resource_rows, d)


def prune(retention_days: int = RETENTION_DAYS) -> int:
    cutoff = (date.today() - timedelta(days=retention_days - 1)).isoformat()
    with connect() as c:
        d1 = c.execute("DELETE FROM posture_daily WHERE date < ?", (cutoff,)).rowcount
        d2 = c.execute("DELETE FROM resource_findings WHERE date < ?", (cutoff,)).rowcount
    return (d1 or 0) + (d2 or 0)


# ── lifecycle helpers ────────────────────────────────────────────────────────
def _to_date(v: Any) -> Optional[date]:
    """Parse a Qualys evaluationDates value (epoch ms/s int, or ISO string) → date."""
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            n = float(v)
            if n > 1e12:  # milliseconds
                n /= 1000.0
            return datetime.fromtimestamp(n, tz=timezone.utc).date()
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s).date()
    except (ValueError, OverflowError, OSError):
        return None


def _within_days(v: Any, days: int, ref: date) -> bool:
    d = _to_date(v)
    return d is not None and (ref - d).days <= days and d <= ref


# ── query helpers ────────────────────────────────────────────────────────────
def latest_date() -> Optional[str]:
    with connect() as c:
        row = c.execute("SELECT MAX(date) d FROM posture_daily").fetchone()
    return row["d"] if row and row["d"] else None


def upsert_account_names(accounts: Iterable[Dict[str, str]]) -> None:
    """Persist connector account_id → display name so the UI can show the alias. Called each sync."""
    with connect() as c:
        for a in accounts:
            aid, csp, name = a.get("id"), a.get("csp"), a.get("name")
            if not aid or not csp:
                continue
            c.execute("INSERT INTO accounts(account, csp, name) VALUES(?,?,?) "
                      "ON CONFLICT(account, csp) DO UPDATE SET name=excluded.name",
                      (aid, csp, name or None))


def account_name_map() -> Dict[tuple, str]:
    with connect() as c:
        rows = c.execute("SELECT account, csp, name FROM accounts WHERE name IS NOT NULL").fetchall()
    return {(r["account"], r["csp"]): r["name"] for r in rows}


# ── control remediation guidance ──────────────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
             "&#39;": "'", "&#x27;": "'", "&apos;": "'"}


def strip_html(v) -> str:
    """Qualys remediation/rationale fields are HTML. Flatten to readable plain text: block/list tags
    become line breaks + bullets, other tags are dropped, entities decoded."""
    if not v:
        return ""
    s = str(v)
    s = re.sub(r"(?i)<\s*(br|/p|/div|/h[1-6])\s*/?>", "\n", s)
    s = re.sub(r"(?i)<\s*li[^>]*>", "\n• ", s)
    s = _TAG_RE.sub("", s)
    for a, b in _ENTITIES.items():
        s = s.replace(a, b)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def upsert_control_meta(csp: str, index: Dict[str, Dict]) -> None:
    """Store per-control remediation guidance from the control catalog (index: cid → meta dict)."""
    with connect() as c:
        for cid, m in index.items():
            rem = {
                "manual": strip_html(m.get("manual_remediation")),
                "cli": strip_html(m.get("cli_remediation")),
                "buildtime": strip_html(m.get("buildtime_remediation")),
                "rationale": strip_html(m.get("rationale")),
                "specification": strip_html(m.get("specification")),
                "references": strip_html(m.get("references")),
            }
            if not any(rem.values()):
                continue
            c.execute("INSERT INTO control_meta(csp, control_id, remediation) VALUES(?,?,?) "
                      "ON CONFLICT(csp, control_id) DO UPDATE SET remediation=excluded.remediation",
                      (csp.upper(), str(cid), json.dumps(rem)))


def get_control_remediation(control_id: str, csp: str) -> Dict:
    with connect() as c:
        row = c.execute("SELECT remediation FROM control_meta WHERE csp=? AND control_id=?",
                        (csp.upper(), str(control_id))).fetchone()
    if not row or not row["remediation"]:
        return {"manual": "", "cli": "", "buildtime": "", "rationale": "", "specification": "", "references": ""}
    try:
        return json.loads(row["remediation"])
    except (ValueError, TypeError):
        return {"manual": "", "cli": "", "buildtime": "", "rationale": "", "specification": "", "references": ""}


def manual_remediation_map() -> Dict[str, str]:
    """{"CSP:control_id": manual remediation text} for every control we have metadata for.

    Powers the inline Remediation COLUMN in the tables: one small fetch on load beats one request
    per expanded row, and the tables need the text for rows the user never expands (CSV export)."""
    out: Dict[str, str] = {}
    with connect() as c:
        rows = c.execute("SELECT csp, control_id, remediation FROM control_meta").fetchall()
    for r in rows:
        try:
            rem = json.loads(r["remediation"]) if r["remediation"] else {}
        except (ValueError, TypeError):
            continue
        text = (rem or {}).get("manual") or ""
        if text:
            out[f'{r["csp"]}:{r["control_id"]}'] = text
    return out


def distinct_accounts() -> List[Dict[str, str]]:
    """Accounts present in the snapshots, enriched with their connector alias (name) when known."""
    names = account_name_map()
    with connect() as c:
        rows = c.execute("SELECT DISTINCT account, csp FROM posture_daily ORDER BY csp, account").fetchall()
    return [{"account": r["account"], "csp": r["csp"], "name": names.get((r["account"], r["csp"]))}
            for r in rows]


def available_dates() -> List[str]:
    """Snapshot dates present (newest first) — feeds the time-travel 'As of' picker."""
    with connect() as c:
        rows = c.execute("SELECT DISTINCT date FROM posture_daily ORDER BY date DESC").fetchall()
    return [r["date"] for r in rows]


def _resolve_date(as_of: str = "") -> Optional[str]:
    """Pick the snapshot date to read: the requested `as_of` if it exists, else the latest."""
    if as_of:
        with connect() as c:
            row = c.execute("SELECT 1 FROM posture_daily WHERE date=? LIMIT 1", (as_of,)).fetchone()
        if row:
            return as_of
    return latest_date()


def distinct_services(cloud: str = "", as_of: str = "") -> List[str]:
    d = _resolve_date(as_of)
    if not d:
        return []
    params: List[Any] = [d]
    extra = ""
    if cloud:
        extra = " AND csp = ?"; params.append(cloud.upper())
    with connect() as c:
        rows = c.execute(f"SELECT DISTINCT service FROM posture_daily WHERE date=? AND service IS NOT NULL "
                         f"AND service != ''{extra} ORDER BY service", params).fetchall()
    return [r["service"] for r in rows]


def distinct_resource_types(cloud: str = "", as_of: str = "") -> List[str]:
    d = _resolve_date(as_of)
    if not d:
        return []
    params: List[Any] = [d]
    extra = ""
    if cloud:
        extra = " AND csp = ?"; params.append(cloud.upper())
    with connect() as c:
        rows = c.execute(f"SELECT DISTINCT resource_type FROM resource_findings WHERE date=? "
                         f"AND resource_type != ''{extra} ORDER BY resource_type", params).fetchall()
    return [r["resource_type"] for r in rows]


def distinct_policies(cloud: str = "", as_of: str = "") -> List[str]:
    """Distinct Qualys policy/framework names present in the snapshot (unnested from the per-control
    policies JSON via json_each). Feeds the Policy quick-filter."""
    d = _resolve_date(as_of)
    if not d:
        return []
    params: List[Any] = [d]
    extra = ""
    if cloud:
        extra = " AND pd.csp = ?"; params.append(cloud.upper())
    with connect() as c:
        try:
            rows = c.execute(
                f"""SELECT DISTINCT je.value v
                    FROM posture_daily pd, json_each(pd.policies) je
                    WHERE pd.date=? AND pd.policies IS NOT NULL{extra}
                    ORDER BY je.value""", params).fetchall()
        except sqlite3.OperationalError:
            return []
    return [r["v"] for r in rows if r["v"]]


def distinct_regions(cloud: str = "", as_of: str = "") -> List[str]:
    d = _resolve_date(as_of)
    if not d:
        return []
    params: List[Any] = [d]
    extra = ""
    if cloud:
        extra = " AND csp = ?"; params.append(cloud.upper())
    with connect() as c:
        rows = c.execute(f"SELECT DISTINCT region FROM resource_findings WHERE date=? AND region != ''{extra} "
                         f"ORDER BY region", params).fetchall()
    return [r["region"] for r in rows]


def update_inventory_tags(d: str, csp: str, resource_type: str, mapping: Dict[tuple, Dict]) -> int:
    """Attach inventory-sourced tags to already-written resource rows (pass 3 of the sync).

    Qualys asset tags always win (that column has no other source). Cloud tags are only written
    where the evaluations response gave us NONE — the evaluations `cloudTags` stay authoritative
    when present, and inventory fills the types it omits.

    Keyed on (date, csp, ACCOUNT, resource_type, resource_id). The account is part of the key
    because IAM ids are bare names that repeat across accounts."""
    if not mapping:
        return 0
    with connect() as c:
        cur = c.executemany(
            """UPDATE resource_findings
                  SET qualys_tags_json = ?,
                      tags_json = CASE WHEN tags_json IS NULL OR tags_json IN ('', '[]')
                                       THEN ? ELSE tags_json END
               WHERE date=? AND csp=? AND account=? AND resource_type=? AND resource_id=?""",
            [(json.dumps(v.get("qualys") or []), json.dumps(v.get("cloud") or []),
              d, csp.upper(), acct, resource_type, rid)
             for (acct, rid), v in mapping.items()])
        return cur.rowcount or 0


def distinct_resource_types_for_csp(csp: str, d: str) -> List[str]:
    """Resource types present for one CSP on a snapshot date — drives the Qualys-tag inventory pass
    (one call per type). Falls back to the whole table before the day's rows exist."""
    with connect() as c:
        rows = c.execute(
            """SELECT DISTINCT resource_type FROM resource_findings
               WHERE csp=? AND resource_type<>'' AND (date=? OR ?='')
               ORDER BY resource_type""", (csp.upper(), d, d)).fetchall()
        if not rows:
            rows = c.execute(
                """SELECT DISTINCT resource_type FROM resource_findings
                   WHERE csp=? AND resource_type<>'' ORDER BY resource_type""",
                (csp.upper(),)).fetchall()
    return [r["resource_type"] for r in rows]


def _facet_clause(prefix: str, cloud: str, account: str, severity: str, params: List[Any],
                  service: str = "", service_prefix: Optional[str] = None) -> str:
    where = []
    if cloud:
        where.append(f"{prefix}csp = ?"); params.append(cloud.upper())
    if account:
        where.append(f"{prefix}account = ?"); params.append(account)
    if severity:
        where.append(f"UPPER({prefix}criticality) = ?"); params.append(severity.upper())
    if service:
        sp = service_prefix if service_prefix is not None else prefix
        where.append(f"{sp}service = ?"); params.append(service)
    return (" AND " + " AND ".join(where)) if where else ""


def _policy_clause(policy: str, params: List[Any], col: str = "policies") -> str:
    """Match rows whose policies JSON contains the exact policy name (quoted so 'CIS' doesn't match
    'CIS Amazon…')."""
    if not policy:
        return ""
    params.append(f'%{json.dumps(policy)}%')   # e.g. %"CIS Amazon Web Services…"%
    return f" AND {col} LIKE ?"


def controls_view(cloud: str = "", account: str = "", severity: str = "", service: str = "",
                  policy: str = "", q: str = "", as_of: str = "") -> List[Dict]:
    d = _resolve_date(as_of)
    if not d:
        return []
    params: List[Any] = [d]
    clause = _facet_clause("", cloud, account, severity, params, service)
    clause += _policy_clause(policy, params)
    if q:
        clause += " AND (control_name LIKE ? OR control_id LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    with connect() as c:
        rows = c.execute(
            f"""SELECT control_id, csp, MAX(control_name) control_name, MAX(criticality) criticality,
                       MAX(service) service, MAX(policies) policies, SUM(passed) passed, SUM(failed) failed,
                       SUM(total) total, COUNT(DISTINCT account) accounts
                FROM posture_daily WHERE date = ?{clause}
                GROUP BY control_id, csp ORDER BY SUM(failed) DESC""", params).fetchall()
        # Trend line: same facets EXCEPT the date pin (we want the whole history), across all dates.
        tparams: List[Any] = []
        tclause = _facet_clause("", cloud, account, severity, tparams, service)
        tclause += _policy_clause(policy, tparams)
        if q:
            tclause += " AND (control_name LIKE ? OR control_id LIKE ?)"
            tparams += [f"%{q}%", f"%{q}%"]
        trows = c.execute(
            f"""SELECT control_id, csp, date, SUM(failed) failed, SUM(passed) passed
                FROM posture_daily WHERE 1=1{tclause}
                GROUP BY control_id, csp, date ORDER BY date""", tparams).fetchall()
    trend: Dict[tuple, List[Dict]] = {}
    for t in trows:
        trend.setdefault((t["control_id"], t["csp"]), []).append(
            {"date": t["date"], "failed": t["failed"], "passed": t["passed"]})
    return [{
        "control_id": r["control_id"], "csp": r["csp"], "control_name": r["control_name"],
        "criticality": r["criticality"], "service": r["service"], "passed": r["passed"],
        "failed": r["failed"], "total": r["total"], "accounts": r["accounts"],
        "policies": _loads_list(r["policies"]),
        "trend": trend.get((r["control_id"], r["csp"]), []),
    } for r in rows]


def format_qualys_tags(v) -> str:
    """JSON array of Qualys asset tag names → "name; name". '' when the resource has none."""
    return "; ".join(str(t) for t in _loads_list(v) if t)


def format_tags(v) -> str:
    """JSON tag array → "key=value; key=value" (stable order). '' when untagged."""
    out = []
    for t in _loads_list(v):
        if isinstance(t, dict):
            k, val = t.get("key"), t.get("value")
            if k:
                out.append(f"{k}={val}" if val not in (None, "") else str(k))
        elif t:
            out.append(str(t))
    return "; ".join(out)


def _loads_list(v) -> List:
    try:
        out = json.loads(v) if v else []
        return out if isinstance(out, list) else []
    except (ValueError, TypeError):
        return []


# Qualys CloudView CSPM criticality has only three levels: HIGH / MEDIUM / LOW.
_SEVS = ["HIGH", "MEDIUM", "LOW"]


def _sev_rank(crit: str) -> int:
    """Index into _SEVS (0 = CRITICAL, most severe). Unknown → past the end so it sorts last."""
    try:
        return _SEVS.index((crit or "").upper())
    except ValueError:
        return len(_SEVS)


def resource_view(cloud: str = "", account: str = "", severity: str = "", service: str = "",
                  rtype: str = "", region: str = "", status: str = "", policy: str = "",
                  result: str = "", q: str = "", as_of: str = "") -> Dict:
    """Snapshot pivot: each resource → its controls (both PASS and FAIL), with NEW / REOPENED flags,
    first/last-seen and top severity from Qualys's evaluationDates. A resource's overall `result` is
    FAIL if it fails any control, else PASS. `result` (fail/pass) and `status` (NEW/REOPENED/EXISTING)
    filter the table after the pivot; the stat cards describe the full facet set. `as_of` time-travels
    to an earlier snapshot day. Failing-control detail is kept for the drawer; passing controls are
    only counted (keeps the payload bounded)."""
    d = _resolve_date(as_of)
    if not d:
        return {"resources": [], "stats": {}}
    ref = _to_date(d) or date.today()
    params: List[Any] = [d]
    clause = _facet_clause("rf.", cloud, account, severity, params, service, service_prefix="pd.")
    if rtype:
        clause += " AND rf.resource_type = ?"; params.append(rtype)
    if region:
        clause += " AND rf.region = ?"; params.append(region)
    clause += _policy_clause(policy, params, col="pd.policies")
    if q:
        clause += " AND (rf.resource_id LIKE ? OR rf.tags_json LIKE ? OR rf.qualys_tags_json LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    with connect() as c:
        rows = c.execute(
            f"""SELECT rf.account, rf.csp, rf.control_id, rf.resource_id, rf.resource_type, rf.region,
                       rf.criticality, rf.result, rf.first_evaluated, rf.last_evaluated,
                       rf.date_fixed, rf.date_reopen, rf.prev_result, rf.evidence_json, rf.tags_json,
                       rf.qualys_tags_json, pd.control_name, pd.service, pd.policies
                FROM resource_findings rf
                LEFT JOIN posture_daily pd
                  ON pd.date=rf.date AND pd.account=rf.account AND pd.csp=rf.csp AND pd.control_id=rf.control_id
                WHERE rf.date = ?{clause}
                ORDER BY rf.resource_id""", params).fetchall()

    names = account_name_map()
    pivot: Dict[str, Dict] = {}
    fixed_30d = 0
    for r in rows:
        res = (r["result"] or "FAIL").upper()
        is_fail = res == "FAIL"
        if bool(r["date_fixed"]) and res == "PASS" and _within_days(r["date_fixed"], RETENTION_DAYS, ref):
            fixed_30d += 1
        uid = f'{r["account"]}|{r["csp"]}|{r["resource_type"]}|{r["resource_id"]}|{r["region"]}'
        entry = pivot.get(uid)
        if not entry:
            entry = {
                "uid": uid, "resource_id": r["resource_id"], "resource_type": r["resource_type"],
                "region": r["region"] or None, "csp": r["csp"], "account": r["account"],
                "account_name": names.get((r["account"], r["csp"])),
                "controls": [], "pass_controls": 0, "severity_mix": {s: 0 for s in _SEVS},
                "services": set(), "policies": set(), "first_seen": None, "last_seen": None,
                "date_fixed": None, "date_reopen": None, "is_new": False, "is_reopened": False,
                "tags": "", "qualys_tags": "",
            }
            pivot[uid] = entry
        if r["service"]:
            entry["services"].add(r["service"])
        if not entry["tags"]:
            # Tags are a property of the resource, so any finding for it carries the same set —
            # take the first non-empty one we see. Cloud and Qualys tags are kept separate.
            entry["tags"] = format_tags(r["tags_json"])
        if not entry["qualys_tags"]:
            entry["qualys_tags"] = format_qualys_tags(r["qualys_tags_json"])
        for p in _loads_list(r["policies"]):
            entry["policies"].add(p)
        fe, le = _to_date(r["first_evaluated"]), _to_date(r["last_evaluated"])
        if fe and (entry["first_seen"] is None or fe.isoformat() < entry["first_seen"]):
            entry["first_seen"] = fe.isoformat()
        if le and (entry["last_seen"] is None or le.isoformat() > entry["last_seen"]):
            entry["last_seen"] = le.isoformat()
        df, dr = _to_date(r["date_fixed"]), _to_date(r["date_reopen"])
        if df and (entry["date_fixed"] is None or df.isoformat() > entry["date_fixed"]):
            entry["date_fixed"] = df.isoformat()
        if dr and (entry["date_reopen"] is None or dr.isoformat() > entry["date_reopen"]):
            entry["date_reopen"] = dr.isoformat()
        if not is_fail:
            entry["pass_controls"] += 1
            continue  # passing controls are counted, not detailed (keeps payload bounded)
        # Failing control → keep full detail for the drawer + severity/lifecycle rollups.
        crit = (r["criticality"] or "MEDIUM").upper()
        entry["severity_mix"][crit] = entry["severity_mix"].get(crit, 0) + 1
        is_new = _within_days(r["first_evaluated"], RETENTION_DAYS, ref)
        is_reopened = bool(r["date_reopen"])
        if is_new:
            entry["is_new"] = True
        if is_reopened:
            entry["is_reopened"] = True
        try:
            evidence = json.loads(r["evidence_json"]) if r["evidence_json"] else []
        except (ValueError, TypeError):
            evidence = []
        entry["controls"].append({
            "control_id": r["control_id"], "control_name": r["control_name"] or f'Control {r["control_id"]}',
            "criticality": crit, "evidence": evidence,
            "first_evaluated": r["first_evaluated"], "last_evaluated": r["last_evaluated"],
            "date_reopen": r["date_reopen"], "prev_result": r["prev_result"],
            "is_new": is_new, "is_reopened": is_reopened,
        })
    out = list(pivot.values())
    for e in out:
        e["failing_controls"] = len(e["controls"])
        e["passing_controls"] = e["pass_controls"]
        e["total_controls"] = e["failing_controls"] + e["passing_controls"]
        e["result"] = "FAIL" if e["failing_controls"] > 0 else "PASS"
        e["services"] = sorted(e["services"])
        e["policies"] = sorted(e["policies"])
        # Top severity = the most-severe criticality among this resource's FAILING controls (— if none).
        present = [s for s in _SEVS if e["severity_mix"].get(s)]
        e["top_severity"] = present[0] if present else None
        # Lifecycle, same precedence as the Findings view but at resource granularity: a resource is
        # FIXED only when the WHOLE resource is passing now (no failing controls) and it carries a
        # dateFixed inside the window. Otherwise the failing-control flags drive REOPENED / NEW.
        if e["result"] == "PASS" and e["date_fixed"] and _within_days(e["date_fixed"], RETENTION_DAYS, ref):
            e["status"] = "FIXED"
        elif e["is_reopened"]:
            e["status"] = "REOPENED"
        elif e["is_new"]:
            e["status"] = "NEW"
        else:
            e["status"] = "EXISTING"
        # One-line evidence preview from the most-severe failing control (no need to expand).
        first_ctrl = min(e["controls"], key=lambda c: _sev_rank(c["criticality"])) if e["controls"] else None
        # The most-severe failing control — lets the UI show that control's remediation inline
        # (the Excel export still lists every failing control's steps).
        e["top_control_id"] = (first_ctrl or {}).get("control_id")
        e["top_control_name"] = (first_ctrl or {}).get("control_name")
        ev = (first_ctrl or {}).get("evidence") or []
        e["evidence_summary"] = "; ".join(f'{x.get("settingName")}: {x.get("actualValue")}'
                                          for x in ev[:2] if x.get("settingName")) or None
        # Drop the heavy per-control detail (with evidence) from the LIST payload (34MB→~3MB). The
        # drawer lazy-loads a resource's failing controls via /api/resource-controls on expand.
        e.pop("controls", None)
    # Distinct-RESOURCE counts (a resource is counted once).
    failing = [e for e in out if e["failing_controls"] > 0]
    stats = {"failing_resources": len(failing),
             "passing_resources": sum(1 for e in out if e["failing_controls"] == 0),
             "total_resources": len(out),
             "new_30d": sum(1 for e in failing if e["is_new"]),
             "reopened": sum(1 for e in failing if e["is_reopened"]),
             "fixed_30d": fixed_30d,
             "fixed_resources": sum(1 for e in out if e["status"] == "FIXED")}
    if result:
        want_fail = result.lower() == "fail"
        out = [e for e in out if (e["failing_controls"] > 0) == want_fail]
    if status:
        out = [e for e in out if e["status"] == status.upper()]
    # Failing resources first (most failures on top), then passing.
    out.sort(key=lambda e: (e["failing_controls"], e["is_new"]), reverse=True)
    return {"resources": out, "stats": stats}


def findings_view(cloud: str = "", account: str = "", severity: str = "", service: str = "",
                  policy: str = "", rtype: str = "", region: str = "", result: str = "fail",
                  status: str = "", q: str = "", as_of: str = "", limit: int = 200000) -> Dict:
    """FLAT findings — one row per (control × resource) evaluation, NOT grouped. This is the
    remediation-plan view: every failing check spelled out individually. Defaults to result=FAIL.
    Honors the same facets as the other views. `limit` is a safety backstop far above the real
    finding count; full evidence is lazy-loaded per row so the list payload stays small."""
    d = _resolve_date(as_of)
    if not d:
        return {"findings": [], "total": 0}
    ref = _to_date(d) or date.today()
    params: List[Any] = [d]
    clause = _facet_clause("rf.", cloud, account, severity, params, service, service_prefix="pd.")
    if rtype:
        clause += " AND rf.resource_type = ?"; params.append(rtype)
    if region:
        clause += " AND rf.region = ?"; params.append(region)
    clause += _policy_clause(policy, params, col="pd.policies")
    if q:
        clause += (" AND (rf.resource_id LIKE ? OR pd.control_name LIKE ? OR rf.control_id LIKE ?"
                   " OR rf.tags_json LIKE ? OR rf.qualys_tags_json LIKE ?)")
        params += [f"%{q}%"] * 5
    # `clause`/`params` are now the FACET base (no result/status filter) — reused for the lifecycle
    # counts below. The result/status restriction is a paramless SQL fragment layered on top.
    rl = (result or "fail").lower()
    want_status = (status or "").upper()
    if want_status == "FIXED":
        # FIXED items are remediated → currently PASS with a dateFixed. They live outside the default
        # fail-only remediation plan, so selecting Status=Fixed overrides the result filter and pulls
        # the passing+fixed rows in (the per-row derivation below still gates on the 30-day window).
        rs_sql = " AND UPPER(COALESCE(rf.result,'FAIL'))='PASS' AND rf.date_fixed IS NOT NULL AND rf.date_fixed<>''"
    elif rl == "fail":
        rs_sql = " AND UPPER(COALESCE(rf.result,'FAIL'))='FAIL'"
    elif rl == "pass":
        rs_sql = " AND UPPER(COALESCE(rf.result,'FAIL'))='PASS'"
    else:
        rs_sql = ""
    join = ("""FROM resource_findings rf
               LEFT JOIN posture_daily pd
                 ON pd.date=rf.date AND pd.account=rf.account AND pd.csp=rf.csp AND pd.control_id=rf.control_id
               WHERE rf.date = ?""")
    names = account_name_map()
    with connect() as c:
        total = c.execute(f"SELECT COUNT(*) n {join}{clause}{rs_sql}", params).fetchone()["n"]
        rows = c.execute(
            f"""SELECT rf.account, rf.csp, rf.control_id, rf.resource_id, rf.resource_type, rf.region,
                       rf.criticality, rf.result, rf.first_evaluated, rf.last_evaluated, rf.date_fixed,
                       rf.date_reopen, rf.prev_result, rf.evidence_json, rf.tags_json,
                       rf.qualys_tags_json, pd.control_name, pd.service, pd.policies
                {join}{clause}{rs_sql}
                ORDER BY CAST(rf.control_id AS INTEGER), rf.control_id, rf.account, rf.resource_id
                LIMIT ?""", params + [limit]).fetchall()
        # Lifecycle counts across ALL results for the current facet set (ignores the result/status
        # filter) so the Status rail can show every state's true total — including FIXED, which the
        # default fail-only list never loads. Minimal columns; derived with the same rules as below.
        lc_rows = c.execute(
            f"""SELECT rf.result, rf.first_evaluated, rf.date_fixed, rf.date_reopen
                {join}{clause}""", params).fetchall()
    status_counts = {"NEW": 0, "EXISTING": 0, "FIXED": 0, "REOPENED": 0}
    for lr in lc_rows:
        lres = (lr["result"] or "FAIL").upper()
        if lres == "PASS":
            if lr["date_fixed"] and _within_days(lr["date_fixed"], RETENTION_DAYS, ref):
                status_counts["FIXED"] += 1
        elif lr["date_reopen"]:
            status_counts["REOPENED"] += 1
        elif _within_days(lr["first_evaluated"], RETENTION_DAYS, ref):
            status_counts["NEW"] += 1
        else:
            status_counts["EXISTING"] += 1
    out = []
    for r in rows:
        try:
            evidence = json.loads(r["evidence_json"]) if r["evidence_json"] else []
        except (ValueError, TypeError):
            evidence = []
        crit = (r["criticality"] or "MEDIUM").upper()
        res = (r["result"] or "FAIL").upper()
        # Lifecycle, VMDR-style. Precedence gates on the CURRENT result first:
        #   FIXED    — remediated now: PASS with a dateFixed inside the 30-day window
        #   REOPENED — was fixed, misconfigured again: FAIL with a dateReopen
        #   NEW      — first-ever detection inside the window: FAIL, recently first-seen
        #   EXISTING — still failing, seen before (the remainder)
        if res == "PASS" and r["date_fixed"] and _within_days(r["date_fixed"], RETENTION_DAYS, ref):
            st = "FIXED"
        elif res == "FAIL" and r["date_reopen"]:
            st = "REOPENED"
        elif res == "FAIL" and _within_days(r["first_evaluated"], RETENTION_DAYS, ref):
            st = "NEW"
        else:
            st = "EXISTING"
        if status and st != status.upper():
            continue
        # Full `evidence` is NOT inlined here (keeps the list payload small enough to lift the row
        # cap) — the drawer lazy-loads it via /api/finding-evidence. Only a one-line summary ships.
        ev_sum = "; ".join(f'{x.get("settingName")}: {x.get("actualValue")}'
                           for x in evidence[:2] if x.get("settingName")) or None
        out.append({
            "uid": f'{r["control_id"]}|{r["account"]}|{r["csp"]}|{r["resource_type"]}|{r["resource_id"]}|{r["region"]}',
            "control_id": r["control_id"], "control_name": r["control_name"] or f'Control {r["control_id"]}',
            "criticality": crit, "service": r["service"] or "", "policies": _loads_list(r["policies"]),
            "resource_id": r["resource_id"], "resource_type": r["resource_type"], "region": r["region"] or None,
            "csp": r["csp"], "account": r["account"], "account_name": names.get((r["account"], r["csp"])),
            "result": res, "status": st,
            "first_evaluated": r["first_evaluated"], "last_evaluated": r["last_evaluated"],
            "date_fixed": r["date_fixed"], "date_reopen": r["date_reopen"],
            "evidence_summary": ev_sum, "tags": format_tags(r["tags_json"]),
            "qualys_tags": format_qualys_tags(r["qualys_tags_json"]),
        })
    return {"findings": out, "total": total, "status_counts": status_counts}


def finding_evidence(control_id: str, account: str, csp: str, resource_type: str, resource_id: str,
                     region: str = "", as_of: str = "") -> Dict:
    """Full evidence for ONE finding (control × resource) — lazy-loaded by the Findings drawer."""
    d = _resolve_date(as_of)
    if not d:
        return {"evidence": []}
    with connect() as c:
        row = c.execute(
            """SELECT evidence_json FROM resource_findings
               WHERE date=? AND control_id=? AND account=? AND csp=? AND resource_type=?
                 AND resource_id=? AND region=? LIMIT 1""",
            (d, control_id, account, csp, resource_type, resource_id, region)).fetchone()
    if not row:
        return {"evidence": []}
    try:
        return {"evidence": json.loads(row["evidence_json"]) if row["evidence_json"] else []}
    except (ValueError, TypeError):
        return {"evidence": []}


def resource_controls(account: str, csp: str, resource_type: str, resource_id: str, region: str = "",
                      as_of: str = "") -> Dict:
    """ALL controls (both PASS and FAIL, with evidence) for ONE resource — powers the Resource-view
    drawer, fetched lazily on expand so the list payload stays small. Failing controls sort first."""
    d = _resolve_date(as_of)
    if not d:
        return {"controls": []}
    with connect() as c:
        rows = c.execute(
            """SELECT rf.control_id, rf.criticality, rf.result, rf.first_evaluated, rf.last_evaluated,
                      rf.date_reopen, rf.prev_result, rf.evidence_json, rf.tags_json,
                      rf.qualys_tags_json, pd.control_name
               FROM resource_findings rf
               LEFT JOIN posture_daily pd
                 ON pd.date=rf.date AND pd.account=rf.account AND pd.csp=rf.csp AND pd.control_id=rf.control_id
               WHERE rf.date=? AND rf.account=? AND rf.csp=? AND rf.resource_type=? AND rf.resource_id=?
                 AND rf.region=?
               ORDER BY CASE WHEN UPPER(COALESCE(rf.result,'FAIL'))='FAIL' THEN 0 ELSE 1 END, rf.control_id""",
            (d, account, csp, resource_type, resource_id, region)).fetchall()
    ref = _to_date(d) or date.today()
    out = []
    for r in rows:
        try:
            evidence = json.loads(r["evidence_json"]) if r["evidence_json"] else []
        except (ValueError, TypeError):
            evidence = []
        out.append({
            "control_id": r["control_id"], "control_name": r["control_name"] or f'Control {r["control_id"]}',
            "criticality": (r["criticality"] or "MEDIUM").upper(),
            "result": (r["result"] or "FAIL").upper(), "evidence": evidence,
            "first_evaluated": r["first_evaluated"], "last_evaluated": r["last_evaluated"],
            "date_reopen": r["date_reopen"], "prev_result": r["prev_result"],
            "is_new": _within_days(r["first_evaluated"], RETENTION_DAYS, ref),
            "is_reopened": bool(r["date_reopen"]), "tags": format_tags(r["tags_json"]),
            "qualys_tags": format_qualys_tags(r["qualys_tags_json"]),
        })
    return {"controls": out}


def control_failing_resources(control_id: str, csp: str = "", cloud: str = "", account: str = "",
                              as_of: str = "", limit: int = 500) -> Dict:
    """Drill-down for one control: the individual resources FAILING it (Controls-view CID click).
    Joins posture_daily for the control name/service. Returns rows + a total count (rows may be
    capped at `limit`)."""
    d = _resolve_date(as_of)
    if not d:
        return {"resources": [], "total": 0, "control_name": None}
    names = account_name_map()
    params: List[Any] = [d, control_id]
    where = ""
    eff_cloud = csp or cloud
    if eff_cloud:
        where += " AND rf.csp = ?"; params.append(eff_cloud.upper())
    if account:
        where += " AND rf.account = ?"; params.append(account)
    with connect() as c:
        total = c.execute(
            f"""SELECT COUNT(*) n FROM resource_findings rf
                WHERE rf.date=? AND rf.control_id=? AND UPPER(COALESCE(rf.result,'FAIL'))='FAIL'{where}""",
            params).fetchone()["n"]
        rows = c.execute(
            f"""SELECT rf.account, rf.csp, rf.resource_id, rf.resource_type, rf.region, rf.criticality,
                       rf.first_evaluated, rf.last_evaluated, rf.date_reopen, rf.evidence_json,
                       rf.tags_json, rf.qualys_tags_json, pd.control_name, pd.service
                FROM resource_findings rf
                LEFT JOIN posture_daily pd
                  ON pd.date=rf.date AND pd.account=rf.account AND pd.csp=rf.csp AND pd.control_id=rf.control_id
                WHERE rf.date=? AND rf.control_id=? AND UPPER(COALESCE(rf.result,'FAIL'))='FAIL'{where}
                ORDER BY rf.account, rf.resource_id LIMIT ?""", params + [limit]).fetchall()
    ref = _to_date(d) or date.today()
    out = []
    control_name = None
    for r in rows:
        control_name = control_name or r["control_name"]
        try:
            evidence = json.loads(r["evidence_json"]) if r["evidence_json"] else []
        except (ValueError, TypeError):
            evidence = []
        out.append({
            "resource_id": r["resource_id"], "resource_type": r["resource_type"],
            "region": r["region"] or None, "csp": r["csp"], "account": r["account"],
            "account_name": names.get((r["account"], r["csp"])),
            "criticality": (r["criticality"] or "MEDIUM").upper(),
            "first_evaluated": r["first_evaluated"], "last_evaluated": r["last_evaluated"],
            "is_new": _within_days(r["first_evaluated"], RETENTION_DAYS, ref),
            "is_reopened": bool(r["date_reopen"]),
            "evidence": evidence, "tags": format_tags(r["tags_json"]),
            "qualys_tags": format_qualys_tags(r["qualys_tags_json"]),
        })
    return {"resources": out, "total": total, "control_name": control_name}


def overall_trend(cloud: str = "", account: str = "", severity: str = "", service: str = "",
                  policy: str = "", days: int = 0) -> List[Dict]:
    """Posture (controls) pass/fail time series, honoring the controls-level facets so the hero
    trend reacts to the active filters. Resource-only facets (rtype/region/status/result) don't
    apply to a controls-posture trend and are ignored by the caller."""
    params: List[Any] = []
    clause = _facet_clause("", cloud, account, severity, params, service)
    clause += _policy_clause(policy, params)
    if days and days > 0:
        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
        clause += " AND date >= ?"; params.append(cutoff)
    with connect() as c:
        rows = c.execute(
            f"""SELECT date, SUM(passed) passed, SUM(failed) failed
                FROM posture_daily WHERE 1=1{clause}
                GROUP BY date ORDER BY date""", params).fetchall()
    return [{"date": r["date"], "passed": r["passed"], "failed": r["failed"]} for r in rows]
