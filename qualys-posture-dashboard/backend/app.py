"""Qualys Posture Dashboard — single-process local app.

FastAPI serves BOTH the JSON API (/api/*) and the pre-built React frontend (static). Run:

    python app.py                # serves API + frontend on http://localhost:8770
    python app.py --demo         # seed 30 days of sample data first (no live Qualys needed)
    python app.py --port 9000

All data lives in ./data/posture.db (SQLite). Credentials are encrypted at rest and never logged.
Nothing leaves the machine except the customer's own calls to their Qualys gateway.
"""

from __future__ import annotations

import argparse
import logging
import os
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import qualys
import scheduler as scheduler_mod
import sync as sync_mod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("app")

# Persistent rotating log file (so failures are diagnosable regardless of how the app was started).
# Lives next to the DB in the data dir; controlled by QPD_DATA_DIR.
try:
    from logging.handlers import RotatingFileHandler
    _LOG_DIR = Path(os.environ.get("QPD_DATA_DIR", str(Path(__file__).resolve().parent / "data")))
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _fh = RotatingFileHandler(_LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(_fh)
except Exception as _e:  # noqa: BLE001 — logging must never block startup
    logger.warning("Could not attach file log: %s", _e)

app = FastAPI(title="Qualys Posture Dashboard", version="1.0.0")

# CORS only helps the Vite dev server (:5173). In the shipped single-process mode the frontend is
# same-origin, so this is a no-op there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    if os.environ.get("QPD_DEMO", "").strip() in ("1", "true", "yes"):
        import seed
        res = seed.seed()
        logger.info("demo seed: %s", res)
    scheduler_mod.start()   # in-app auto-refresh scheduler (no-op unless a schedule is enabled)


# ── global error handler: log the traceback, return a clean JSON error ────────
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal error — see app.log for details."}, status_code=500)


# ── models ───────────────────────────────────────────────────────────────────
class Creds(BaseModel):
    gateway_url: str
    username: str
    password: str


# ── credential + status ──────────────────────────────────────────────────────
@app.post("/api/creds")
def save_creds(body: Creds):
    """Validate by minting a JWT, then persist (encrypted). Never logs the password."""
    try:
        gw, jwt = qualys.mint_jwt(body.gateway_url, body.username, body.password)
    except qualys.QualysError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.save_creds(gw, body.username, body.password)
    # kick off the first refresh in the background so setup → data is one step
    threading.Thread(target=_safe_sync, daemon=True).start()
    return {"ok": True, "gateway": gw, "first_sync": "started"}


def _safe_sync() -> None:
    try:
        sync_mod.run_sync()
    except Exception as e:  # noqa: BLE001
        logger.warning("background sync failed: %s", e)


@app.get("/api/status")
def status():
    creds = db.creds_set()
    return {
        "creds_set": creds,
        "gateway_url": db.get_setting("qualys_gateway_url") if creds else None,
        "username": db.get_setting("qualys_username") if creds else None,
        "last_sync": db.get_setting("last_sync"),
        "last_sync_accounts": db.get_setting("last_sync_accounts"),
        "demo_mode": db.get_setting("demo_mode") == "1",
        "latest_snapshot": db.latest_date(),
        "accounts": db.distinct_accounts(),
        "dates": db.available_dates(),   # snapshot dates for the time-travel "As of" picker
        "syncing": sync_mod.is_running(),
        "sync_progress": sync_mod.sync_state().get("progress"),
    }


@app.post("/api/sync")
def trigger_sync():
    """Refresh now (user-driven). Runs in the background; poll /api/status or /api/sync/state."""
    if not db.creds_set():
        raise HTTPException(status_code=400, detail="No Qualys credentials configured.")
    if sync_mod.is_running():
        return {"ok": True, "already_running": True}
    threading.Thread(target=_safe_sync, daemon=True).start()
    return {"ok": True, "started": True}


@app.get("/api/sync/state")
def sync_state():
    return sync_mod.sync_state()


class Schedule(BaseModel):
    enabled: bool = False
    mode: str = "daily"        # "daily" | "interval"
    time: str = "06:00"        # HH:MM (daily)
    hours: int = 6             # interval hours


@app.get("/api/schedule")
def get_schedule():
    return scheduler_mod.get_schedule()


@app.post("/api/schedule")
def set_schedule(body: Schedule):
    """Save the in-app auto-refresh schedule (persisted; applied by the background scheduler)."""
    return scheduler_mod.set_schedule(body.model_dump())


# ── data views ───────────────────────────────────────────────────────────────
@app.get("/api/facets")
def facets(cloud: str = "", as_of: str = ""):
    """Option lists for the filter rail (values present in the snapshot). Counts are computed
    client-side from the loaded rows so they react to the active filters."""
    return {
        "dates": db.available_dates(),
        "services": db.distinct_services(cloud, as_of),
        "resource_types": db.distinct_resource_types(cloud, as_of),
        "regions": db.distinct_regions(cloud, as_of),
        "policies": db.distinct_policies(cloud, as_of),
        "accounts": db.distinct_accounts(),
    }


@app.get("/api/controls")
def controls(cloud: str = "", account: str = "", severity: str = "", service: str = "",
             policy: str = "", q: str = "", as_of: str = ""):
    return {"latest": db.latest_date(), "as_of": db._resolve_date(as_of),
            "controls": db.controls_view(cloud, account, severity, service, policy, q, as_of)}


@app.get("/api/resources")
def resources(cloud: str = "", account: str = "", severity: str = "", service: str = "",
              rtype: str = "", region: str = "", status: str = "", policy: str = "",
              result: str = "", q: str = "", as_of: str = ""):
    rv = db.resource_view(cloud, account, severity, service, rtype, region, status, policy, result, q, as_of)
    return {"latest": db.latest_date(), "as_of": db._resolve_date(as_of),
            "resources": rv["resources"], "stats": rv["stats"]}


@app.get("/api/control-resources")
def control_resources(control: str, csp: str = "", cloud: str = "", account: str = "", as_of: str = ""):
    """Resources failing a single control — powers the Controls-view CID drill-down."""
    if not control:
        raise HTTPException(status_code=400, detail="control is required")
    return db.control_failing_resources(control, csp, cloud, account, as_of)


@app.get("/api/control-remediation")
def control_remediation(control: str, csp: str):
    """Remediation guidance for a control (manual / CLI / build-time / rationale / references).
    Powers the 'Remediation' panel in the drawers on all screens."""
    return db.get_control_remediation(control, csp)


@app.get("/api/remediation-map")
def remediation_map():
    """{"CSP:cid": manual remediation} for all controls — feeds the inline Remediation column."""
    return db.manual_remediation_map()


@app.get("/api/resource-controls")
def resource_controls(account: str, csp: str, resource_type: str = "", resource_id: str = "",
                      region: str = "", as_of: str = ""):
    """Failing controls for one resource — powers the Resource-view drawer (lazy-loaded on expand)."""
    return db.resource_controls(account, csp, resource_type, resource_id, region, as_of)


@app.get("/api/findings")
def findings(cloud: str = "", account: str = "", severity: str = "", service: str = "",
             policy: str = "", rtype: str = "", region: str = "", result: str = "fail",
             status: str = "", q: str = "", as_of: str = ""):
    fv = db.findings_view(cloud, account, severity, service, policy, rtype, region, result, status, q, as_of)
    return {"latest": db.latest_date(), "as_of": db._resolve_date(as_of),
            "findings": fv["findings"], "total": fv["total"],
            "status_counts": fv.get("status_counts")}


@app.get("/api/finding-evidence")
def finding_evidence(control: str, account: str, csp: str, resource_type: str = "",
                     resource_id: str = "", region: str = "", as_of: str = ""):
    """Full evidence for one finding (control × resource) — Findings-view drawer, lazy-loaded."""
    return db.finding_evidence(control, account, csp, resource_type, resource_id, region, as_of)


@app.get("/api/export.xlsx")
def export_xlsx(view: str = "findings", cloud: str = "", account: str = "", severity: str = "",
                service: str = "", policy: str = "", rtype: str = "", region: str = "",
                status: str = "", result: str = "", q: str = "", as_of: str = ""):
    """Excel export of a view for the current filter set, with a **Manual remediation** column.

    Declared before the SPA catch-all below so it is not swallowed by it."""
    try:
        import xlsx_export   # imported lazily so a stale venv fails here, with a clear message
        data, filename = xlsx_export.build(view, {
            "cloud": cloud, "account": account, "severity": severity, "service": service,
            "policy": policy, "rtype": rtype, "region": region, "status": status,
            "result": result, "q": q, "as_of": as_of,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError:
        raise HTTPException(status_code=500,
                            detail="openpyxl is not installed — restart the app (run.py installs it).")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/trend")
def trend(cloud: str = "", account: str = "", severity: str = "", service: str = "",
          policy: str = "", days: int = 0):
    return {"trend": db.overall_trend(cloud, account, severity, service, policy, days)}


# ── static frontend (mounted last so /api/* wins) ────────────────────────────
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # SPA fallback: serve index.html for any non-API route.
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))
else:
    @app.get("/")
    def no_dist():
        return JSONResponse(
            {"message": "Frontend not built. Run `npm ci && npm run build` in ./frontend, "
                        "or use run.sh. API is available under /api/*."},
            status_code=200,
        )


def main():
    parser = argparse.ArgumentParser(description="Qualys Posture Dashboard")
    parser.add_argument("--port", type=int, default=int(os.environ.get("QPD_PORT", "8770")))
    parser.add_argument("--host", default=os.environ.get("QPD_HOST", "127.0.0.1"))
    parser.add_argument("--demo", action="store_true", help="seed 30 days of sample data")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    db.init_db()
    if args.demo:
        import seed
        logger.info("demo seed: %s", seed.seed())

    url = f"http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    logger.info("Serving on %s", url)

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
