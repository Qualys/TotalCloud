"""run_sync(): pull a fresh posture snapshot for TODAY and store it (idempotent).

Flow
----
1. Load creds → mint a gateway JWT.
2. Enumerate cloud accounts (paged per-CSP connector lists). CSPM only — no Kubernetes/KSPM.
3. Per (account, csp): fetch the control catalog + the account's paged posture; for every FAILING
   control, fetch its paged resources (result FAIL, plus recently-fixed PASS rows for the lifecycle
   stats). Parse against the LIVE CloudView shapes (no arn; evaluationDates captured).
4. replace_day() writes TODAY's rows, then prune >30 days.

User-driven (the Refresh button). A CSP whose controls/posture endpoint errors is skipped, not
fatal. A module lock makes overlapping refreshes safe.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, date
from typing import Callable, Dict, List, Optional

import db
import qualys

logger = logging.getLogger("sync")

_SYNC_LOCK = threading.Lock()
_STATE: Dict[str, object] = {"running": False, "progress": "", "started_at": None, "error": None}

# Full pass+fail coverage: fetch resources for EVERY control that has any (total>0), not just
# failing ones. The cap is a runaway backstop far above the real per-CSP control count (~500).
MAX_CONTROLS_FOR_RESOURCES = 3000
KUBERNETES = qualys.KUBERNETES


def sync_state() -> Dict[str, object]:
    return dict(_STATE)


def is_running() -> bool:
    return bool(_STATE.get("running"))


def _set(progress: str) -> None:
    _STATE["progress"] = progress
    logger.info("sync: %s", progress)


def run_sync(progress_cb: Optional[Callable[[str], None]] = None) -> Dict:
    if not _SYNC_LOCK.acquire(blocking=False):
        return {"ok": False, "skipped": True, "reason": "A refresh is already in progress."}
    _STATE.update({"running": True, "progress": "starting", "started_at": datetime.now().isoformat(), "error": None})

    def report(msg: str) -> None:
        _set(msg)
        if progress_cb:
            progress_cb(msg)

    try:
        creds = db.get_creds()
        if not creds:
            raise qualys.QualysError("No Qualys credentials configured.")
        report("Authenticating with Qualys gateway…")
        gw, jwt = qualys.mint_jwt(creds["gateway_url"], creds["username"], creds["password"])

        report("Enumerating cloud accounts…")
        accounts = qualys.enumerate_accounts(gw, jwt)
        # CSPM-only: we deliberately do NOT append the synthetic KUBERNETES account — this dashboard
        # covers cloud posture (AWS/Azure/GCP CSPM) only. The kspm_* helpers stay in qualys.py unused.
        db.upsert_account_names(accounts)  # capture id→alias so the UI can show "name (account-id)"

        snapshot_date = date.today().isoformat()
        db.set_setting("last_sync_accounts", str(len(accounts)))
        db.set_setting("demo_mode", "0")

        # Two-pass incremental sync so the dashboard renders partial data as the sweep progresses
        # (the frontend polls /api/controls + /api/resources while syncing).
        #
        #   Pass 1 (fast — one paged call per account): write each account's CONTROL posture the
        #   moment it's fetched → the Controls view lights up account by account within seconds.
        #   Pass 2 (slow — one call per control WITH resources): fetch + write each account's
        #   resources (both PASS and FAIL) → the Resource view fills in behind.
        total_p = total_r = 0
        control_idx_cache: Dict[str, Dict] = {}
        scanned_by_acct: List[tuple] = []  # (csp, account_id, [(control_id, criticality), ...])
        n = len(accounts)

        for i, acct in enumerate(accounts, 1):
            csp, account_id = acct["csp"], acct["id"]
            report(f"Posture [{i}/{n}] {csp} · {account_id}")
            prows, scanned = _collect_posture(gw, jwt, csp, account_id, control_idx_cache)
            if prows:
                total_p += db.write_account_posture(snapshot_date, account_id, csp, prows)
                db.set_setting("last_sync", datetime.now().isoformat())
            if scanned:
                scanned_by_acct.append((csp, account_id, scanned))

        m = len(scanned_by_acct)
        for j, (csp, account_id, scanned) in enumerate(scanned_by_acct, 1):
            report(f"Resources [{j}/{m}] {csp} · {account_id}")
            rrows = _collect_resources(gw, jwt, csp, account_id, scanned)
            # Always write (even empty) so a re-refresh clears stale resources for this account.
            total_r += db.write_account_resources(snapshot_date, account_id, csp, rrows)
            db.set_setting("last_sync", datetime.now().isoformat())

        # Pass 3 — Qualys's OWN asset tags. They live on the resource-INVENTORY API (the evaluations
        # response carries only the provider's cloudTags), which is keyed by resource TYPE and spans
        # all accounts — so it runs once per CSP, after pass 2 has written the rows whose resource
        # types tell us which inventory endpoints to call. Best-effort: failures leave tags blank.
        for csp in sorted({c for c, _a, _s in scanned_by_acct}):
            _attach_qualys_tags(gw, jwt, csp, snapshot_date, report)

        pruned = db.prune()
        db.set_setting("last_sync", datetime.now().isoformat())

        summary = {"ok": True, "date": snapshot_date, "accounts": n,
                   "posture_rows": total_p, "resource_rows": total_r, "pruned": pruned}
        report("Done")
        return summary
    except Exception as e:  # noqa: BLE001
        _STATE["error"] = str(e)
        raise
    finally:
        _STATE["running"] = False
        _SYNC_LOCK.release()


def _attach_qualys_tags(gw: str, jwt: str, csp: str, snapshot_date: str, report) -> int:
    """Pass 3 — join inventory-sourced tags (Qualys asset tags, plus cloud tags for the resource
    types the evaluations response omits them for) onto this snapshot's rows, one call per
    resource type. The type list comes from the rows pass 2 just wrote (the inventory endpoint uses
    the same enum, e.g. SNS_TOPIC, that the evaluation payload reports). Types with no inventory
    endpoint answer 400 and are skipped."""
    types = db.distinct_resource_types_for_csp(csp, snapshot_date)
    tagged = 0
    for k, rtype in enumerate(types, 1):
        report(f"Qualys tags · {csp} [{k}/{len(types)}]")
        try:
            mapping = qualys.resource_inventory_tags(gw, jwt, csp, rtype)
            if mapping:
                tagged += db.update_inventory_tags(snapshot_date, csp, rtype, mapping)
        except Exception as e:  # noqa: BLE001
            logger.info("qualys-tag pass skipped %s/%s: %s", csp, rtype, e)
    logger.info("qualys tags: %s → %d rows tagged across %d types", csp, tagged, len(types))
    return tagged


def _collect_posture(gw: str, jwt: str, csp: str, account_id: str,
                     control_idx_cache: Dict[str, Dict]):
    """Pass 1 — fetch ONE account's control posture (fast). Returns (posture_rows, scanned) where
    `scanned` is a list of (control_id, criticality) to fetch resources for in pass 2 — EVERY control
    with resources (total>0), so the Resource view gets both passing and failing resources. Returns
    ([], []) on a posture error so the caller can skip the account without aborting the sweep."""
    posture_rows: List[Dict] = []
    scanned: List[tuple] = []

    if csp not in control_idx_cache:
        control_idx_cache[csp] = qualys.cspm_control_index(gw, jwt, csp)
        db.upsert_control_meta(csp, control_idx_cache[csp])  # capture remediation guidance
    catalog = control_idx_cache[csp]
    try:
        evals = qualys.cspm_posture(gw, jwt, csp, account_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("posture fetch failed for %s/%s: %s — skipping account", csp, account_id, e)
        return [], []

    for raw_ev in evals:
        ev = qualys.parse_posture_eval(raw_ev)
        cid = ev["control_id"]
        if not cid:
            continue
        meta = catalog.get(cid, {})
        criticality = meta.get("criticality") or ev["criticality"]
        posture_rows.append({
            "account": account_id, "csp": csp, "control_id": cid,
            "control_name": meta.get("control_name") or ev["control_name"] or f"Control {cid}",
            "criticality": criticality, "service": meta.get("service") or ev["service"],
            "policies": meta.get("policies") or [],
            "passed": ev["passed"], "failed": ev["failed"], "total": ev["total"],
        })
        if ev["total"] > 0 and len(scanned) < MAX_CONTROLS_FOR_RESOURCES:
            scanned.append((cid, criticality))
    return posture_rows, scanned


def _collect_resources(gw: str, jwt: str, csp: str, account_id: str, scanned: List[tuple]):
    """Pass 2 — fetch resources for ONE account's scanned controls (slow: one call per control).
    Stores BOTH passing and failing resources for full pass/fail coverage. Cloud tags ride along
    here; Qualys's own asset tags are a separate source and get attached in pass 3."""
    resource_rows: List[Dict] = []
    for cid, criticality in scanned:
        try:
            raw_resources = qualys.cspm_posture_resources(gw, jwt, csp, account_id, cid)
        except Exception as e:  # noqa: BLE001
            logger.warning("resource fetch failed %s/%s/%s: %s", csp, account_id, cid, e)
            raw_resources = []
        for raw_res in raw_resources:
            res = qualys.parse_resource(raw_res)
            resource_rows.append({
                "account": account_id, "csp": csp, "control_id": cid,
                "resource_id": res["resource_id"] or f"{res['resource_type']}:{account_id}",
                "resource_type": res["resource_type"], "region": res["region"],
                "criticality": criticality, "result": res["result"] or "FAIL",
                "first_evaluated": res["first_evaluated"], "last_evaluated": res["last_evaluated"],
                "date_fixed": res["date_fixed"], "date_reopen": res["date_reopen"],
                "prev_result": res["prev_result"],
                "evidence_json": res["evidences"],
                "tags_json": res["tags"],          # cloud provider tags (cloudTags)
            })
    return resource_rows
