"""Demo seed — populate ~30 days of posture from the real-shaped fixtures in ./fixtures/.

Loads the fixture JSON (Spring-paged, live shapes) through the SAME qualys.parse_* helpers used on
the live path — so the demo exercises the real parsing (no arn, evaluationDates, pagination fields).

- Day 0 (today): the exact fixture-derived posture counts + failing/fixed resources (with
  evaluationDates → NEW / FIXED / REOPENED flags).
- Days -1..-29: synthesized posture_daily COUNTS only (older days slightly worse) so the 30-day
  count trend and sparklines have movement. Resources are stored only for the latest day (the
  Resource view is a current pivot).

Enable with `python app.py --demo` or `QPD_DEMO=1`.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import db
import qualys

FIX = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    p = FIX / name
    return json.loads(p.read_text()) if p.exists() else {}


def _paged_content(obj: dict, key: str = "content") -> List[dict]:
    return obj.get(key) or obj.get("content") or obj.get("data") or []


def _fixture_accounts() -> List[Dict]:
    manifest = _load("manifest.json")
    return manifest.get("accounts", [])


def _day0_rows() -> Tuple[List[Dict], List[Dict], Dict[str, List[str]]]:
    """Parse the fixtures into (posture_rows, resource_rows) for today, plus a
    control catalog map for prior-day synthesis. Uses qualys.parse_* (real code path)."""
    manifest = _load("manifest.json")
    posture_rows: List[Dict] = []
    resource_rows: List[Dict] = []
    csp_controls = manifest.get("csps", {})

    for acct in manifest.get("accounts", []):
        account_id, csp = acct["id"], acct["csp"]
        # control catalog for names/criticality/service
        catalog_raw = _paged_content(_load(f"controls_{csp.lower()}.json"), key="control")
        catalog = {str(c.get("cid")): {
            "control_name": c.get("controlName", ""), "criticality": (c.get("criticality") or "MEDIUM").upper(),
            "service": c.get("serviceType") or c.get("service") or "",
        } for c in catalog_raw}

        evals = _paged_content(_load(f"posture_{account_id}.json"))
        for raw_ev in evals:
            ev = qualys.parse_posture_eval(raw_ev)
            cid = ev["control_id"]
            if not cid:
                continue
            meta = catalog.get(cid, {})
            crit = meta.get("criticality") or ev["criticality"]
            posture_rows.append({
                "account": account_id, "csp": csp, "control_id": cid,
                "control_name": meta.get("control_name") or ev["control_name"] or f"Control {cid}",
                "criticality": crit, "service": meta.get("service") or ev["service"],
                "passed": ev["passed"], "failed": ev["failed"], "total": ev["total"],
            })
            if ev["failed"] > 0:
                raw_resources = _paged_content(_load(f"resources_{account_id}_{cid}.json"))
                for raw_res in raw_resources:
                    res = qualys.parse_resource(raw_res)
                    if res["result"] != "FAIL" and not res["date_fixed"]:
                        continue
                    resource_rows.append({
                        "account": account_id, "csp": csp, "control_id": cid,
                        "resource_id": res["resource_id"] or f"{res['resource_type']}:{account_id}",
                        "resource_type": res["resource_type"], "region": res["region"],
                        "criticality": crit, "result": res["result"] or "FAIL",
                        "first_evaluated": res["first_evaluated"], "last_evaluated": res["last_evaluated"],
                        "date_fixed": res["date_fixed"], "date_reopen": res["date_reopen"],
                        "prev_result": res["prev_result"], "evidence_json": res["evidences"],
                        "tags_json": res["tags"],
                        # Live syncs read Qualys tags from the inventory API; the fixtures inline
                        # them so demo mode exercises the same column.
                        "qualys_tags_json": [t.get("tagName") for t in (raw_res.get("qualysTags") or [])],
                    })
    return posture_rows, resource_rows, csp_controls


def seed(days: int = 30, force: bool = False) -> Dict:
    db.init_db()
    if not force and db.latest_date():
        return {"seeded": False, "reason": "data already present"}

    posture0, resources0, _ = _day0_rows()
    if not posture0:
        return {"seeded": False, "reason": "no fixtures found — run backend/fixtures/_generate.py"}

    # Remediation guidance for the demo controls (so --demo shows the same panels as live data).
    for csp in {a["csp"] for a in _load("manifest.json").get("accounts", [])}:
        catalog = _paged_content(_load(f"controls_{csp.lower()}.json"), key="control")
        db.upsert_control_meta(csp, {str(c.get("cid")): {
            "manual_remediation": c.get("manualRemediation", ""), "cli_remediation": c.get("cliRemediation", ""),
            "buildtime_remediation": c.get("buildTimeRemediation", ""), "rationale": c.get("rationale", ""),
            "references": c.get("references", ""), "specification": c.get("specification", ""),
        } for c in catalog})

    rnd = random.Random(42)
    today = date.today()
    total_p = total_r = 0

    for day_offset in range(days - 1, -1, -1):
        d = (today - timedelta(days=day_offset)).isoformat()
        if day_offset == 0:
            counts = db.replace_day(d, posture0, resources0)
        else:
            # older days: same controls, slightly MORE failures (posture improving toward today)
            drift = 1.0 + (day_offset / days) * 0.5
            rows = []
            for r in posture0:
                total = r["total"]
                failed = min(total, int(round(r["failed"] * drift * rnd.uniform(0.85, 1.15))))
                rows.append({**r, "failed": failed, "passed": total - failed})
            counts = db.replace_day(d, rows, [])
        total_p += counts["posture_rows"]
        total_r += counts["resource_rows"]

    db.set_setting("last_sync", datetime.now().isoformat())
    db.set_setting("last_sync_accounts", str(len(_fixture_accounts()) + 0))
    db.set_setting("demo_mode", "1")
    return {"seeded": True, "days": days, "posture_rows": total_p, "resource_rows": total_r,
            "accounts": len(_fixture_accounts())}
