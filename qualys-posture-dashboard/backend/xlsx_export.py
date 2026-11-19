"""Excel (.xlsx) export for the three dashboard views.

Same rows the on-screen table shows for the current filter set, plus one extra column —
**Manual remediation** — carrying Qualys's manual remediation text for the control (HTML stripped).

  * Controls  → one row per control          → manual remediation of that control
  * Findings  → one row per control×resource → manual remediation of that control
  * Resources → one row per resource         → the manual remediation of *every* control that
                resource fails, joined into that single cell ("CID — text", severity-ordered).

Findings and Resources carry TWO separate tag columns — deliberately not merged:

  * **Cloud tags**  — the provider's own resource tags ("key=value; key=value"), from `cloudTags`
                      on the evaluations response.
  * **Qualys tags** — Qualys's own asset tag names, from the resource-inventory API.

They come from different endpoints and mean different things, so a resource can carry either, both,
or neither; an empty cell is normal.

Server-side (rather than in the browser) so the remediation join is one cached DB pass instead of
one HTTP round-trip per distinct control.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, List, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import db

VIEWS = ("controls", "resources", "findings")

# Excel rejects most C0 control characters in a cell, and caps a cell at 32,767 characters.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_CELL = 32000
_SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}

_HEADER_FILL = PatternFill("solid", fgColor="0E2A47")
_HEADER_FONT = Font(bold=True, color="FFFFFF")

# Per-view column widths (the remediation column is always last and gets REM_WIDTH).
_REM_WIDTH = 90
_TAGS_WIDTH = 45
_DEFAULT_WIDTH = 18


def _clean(v) -> str:
    """HTML → plain text, strip Excel-illegal control chars, truncate to the cell cap."""
    if v is None:
        return ""
    s = db.strip_html(v) if isinstance(v, str) else str(v)
    s = _CTRL_RE.sub(" ", s).strip()
    if len(s) > _MAX_CELL:
        s = s[: _MAX_CELL - 1] + "…"
    return s


def _safe(v):
    """Numbers pass through; text that Excel would read as a formula is prefixed with an
    apostrophe-free zero-width guard (a leading space) so nothing is auto-evaluated."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = _clean(v)
    return " " + s if s[:1] in ("=", "+", "-", "@") else s


class _Remediation:
    """(csp, control_id) → manual remediation text, memoised for the life of one export."""

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], str] = {}

    def manual(self, control_id, csp) -> str:
        key = (str(csp or "").upper(), str(control_id))
        if key not in self._cache:
            rem = db.get_control_remediation(key[1], key[0]) or {}
            self._cache[key] = _clean(rem.get("manual") or "")
        return self._cache[key]


# ── per-view row builders ────────────────────────────────────────────────────
def _controls_rows(f: Dict, rem: _Remediation):
    header = ["Control ID", "Control", "Cloud", "Severity", "Service", "Policies", "Accounts",
              "Passed", "Failed", "Total", "% Fail", "Manual remediation"]
    rows = []
    for r in db.controls_view(f["cloud"], f["account"], f["severity"], f["service"], f["policy"],
                              f["q"], f["as_of"]):
        total = r["total"] or 0
        pct = round(100 * (r["failed"] or 0) / total) if total else 0
        rows.append([r["control_id"], r["control_name"], r["csp"], r["criticality"], r["service"],
                     ", ".join(r.get("policies") or []), r["accounts"], r["passed"], r["failed"],
                     total, f"{pct}%", rem.manual(r["control_id"], r["csp"])])
    return header, rows


def _findings_rows(f: Dict, rem: _Remediation):
    header = ["Control ID", "Control", "Severity", "Service", "Policies", "Resource ID", "Type",
              "Region", "Cloud", "Account", "Account name", "Result", "Status", "First evaluated",
              "Last evaluated", "Fixed date", "Evidence (summary)", "Cloud tags", "Qualys tags",
              "Manual remediation"]
    fv = db.findings_view(f["cloud"], f["account"], f["severity"], f["service"], f["policy"],
                          f["rtype"], f["region"], f["result"] or "fail", f["status"], f["q"],
                          f["as_of"])
    rows = []
    for r in fv["findings"]:
        rows.append([r["control_id"], r["control_name"], r["criticality"], r["service"],
                     ", ".join(r.get("policies") or []), r["resource_id"], r["resource_type"],
                     r["region"], r["csp"], r["account"], r["account_name"], r["result"],
                     r["status"], r["first_evaluated"], r["last_evaluated"], r.get("date_fixed"),
                     r["evidence_summary"], r.get("tags", ""), r.get("qualys_tags", ""),
                     rem.manual(r["control_id"], r["csp"])])
    return header, rows


def _resource_uid(account, csp, rtype, rid, region) -> str:
    return f"{account}|{csp}|{rtype}|{rid}|{region}"


def _resources_rows(f: Dict, rem: _Remediation):
    header = ["Resource ID", "Account", "Account name", "Type", "Region", "Cloud", "Result",
              "Status", "Top severity", "Failing controls", "Passing controls", "Services",
              "Policies", "First evaluated", "Last evaluated", "Date fixed", "Date reopened",
              "Evidence", "Cloud tags", "Qualys tags", "Manual remediation"]
    rv = db.resource_view(f["cloud"], f["account"], f["severity"], f["service"], f["rtype"],
                          f["region"], f["status"], f["policy"], f["result"], f["q"], f["as_of"])

    # A resource fails many controls, so its remediation cell is the union of those controls'
    # manual steps. One extra flat pass over the same snapshot gives us the control list per
    # resource without a per-resource query.
    per_resource: Dict[str, List[Dict]] = {}
    fails = db.findings_view(f["cloud"], f["account"], f["severity"], f["service"], f["policy"],
                             f["rtype"], f["region"], "fail", "", f["q"], f["as_of"])["findings"]
    for r in fails:
        uid = _resource_uid(r["account"], r["csp"], r["resource_type"], r["resource_id"], r["region"])
        per_resource.setdefault(uid, []).append(r)

    rows = []
    for e in rv["resources"]:
        uid = _resource_uid(e["account"], e["csp"], e["resource_type"], e["resource_id"], e["region"])
        hits = sorted(per_resource.get(uid, []),
                      key=lambda c: (_SEV_ORDER.get(c["criticality"], 9), str(c["control_id"])))
        blocks = []
        for c in hits:
            text = rem.manual(c["control_id"], c["csp"])
            if text:
                blocks.append(f'[{c["control_id"]}] {c["control_name"]} — {text}')
        rows.append([e["resource_id"], e["account"], e["account_name"], e["resource_type"],
                     e["region"], e["csp"], e["result"], e["status"], e["top_severity"],
                     e["failing_controls"], e["passing_controls"], ", ".join(e.get("services") or []),
                     ", ".join(e.get("policies") or []), e["first_seen"], e["last_seen"],
                     e["date_fixed"], e["date_reopen"], e["evidence_summary"], e.get("tags", ""),
                     e.get("qualys_tags", ""), "\n\n".join(blocks)])
    return header, rows


_BUILDERS = {"controls": _controls_rows, "resources": _resources_rows, "findings": _findings_rows}


# ── workbook ─────────────────────────────────────────────────────────────────
def build(view: str, filters: Dict) -> Tuple[bytes, str]:
    """Render one view to .xlsx bytes. Returns (bytes, suggested filename)."""
    view = (view or "findings").lower()
    if view not in _BUILDERS:
        raise ValueError(f"unknown view '{view}' (expected one of {', '.join(VIEWS)})")
    f = {k: (filters.get(k) or "") for k in
         ("cloud", "account", "severity", "service", "policy", "rtype", "region", "status",
          "result", "q", "as_of")}

    header, rows = _BUILDERS[view](f, _Remediation())

    wb = Workbook()
    ws = wb.active
    ws.title = view.capitalize()
    ws.append(header)
    for r in rows:
        ws.append([_safe(v) for v in r])

    rem_col = len(header)
    for i, name in enumerate(header, start=1):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = (
            _REM_WIDTH if i == rem_col else _TAGS_WIDTH if name in ("Cloud tags", "Qualys tags")
            else max(_DEFAULT_WIDTH, min(48, len(name) + 4)))
        cell = ws.cell(row=1, column=i)
        cell.fill, cell.font = _HEADER_FILL, _HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    for row in ws.iter_rows(min_row=2, min_col=rem_col, max_col=rem_col):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{len(rows) + 1}"

    buf = BytesIO()
    wb.save(buf)
    as_of = f["as_of"] or db.latest_date() or "snapshot"
    return buf.getvalue(), f"qualys-{view}-{as_of}.xlsx"
