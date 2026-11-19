"""In-app auto-refresh scheduler (no OS cron needed, no external deps).

A daemon thread checks every 30s whether a scheduled refresh is due and, if so, runs `sync.run_sync()`.
The schedule is persisted in the settings table so it survives restarts:

  {"enabled": bool, "mode": "daily"|"interval", "time": "HH:MM", "hours": int}

- daily    → run once a day at `time` (24h local). Catches up if the machine was off at that time.
- interval → run every `hours` hours.

Last-run markers (`schedule_last_run` = date, `schedule_last_ts` = epoch) prevent double-runs across
restarts.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime

import db
import sync

_stop = threading.Event()
_thread: threading.Thread | None = None
DEFAULT = {"enabled": False, "mode": "daily", "time": "06:00", "hours": 6}


def get_schedule() -> dict:
    cfg = dict(DEFAULT)
    raw = db.get_setting("schedule")
    if raw:
        try:
            cfg.update({k: v for k, v in json.loads(raw).items() if k in DEFAULT})
        except (ValueError, TypeError):
            pass
    return cfg


def set_schedule(patch: dict) -> dict:
    merged = get_schedule()
    for k in DEFAULT:
        if k in patch:
            merged[k] = patch[k]
    db.set_setting("schedule", json.dumps(merged))
    return merged


def _due_daily(cfg: dict, now: datetime) -> bool:
    try:
        hh, mm = (cfg.get("time") or "06:00").split(":")
        hh, mm = int(hh), int(mm)
    except (ValueError, TypeError):
        hh, mm = 6, 0
    scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now < scheduled:
        return False
    return db.get_setting("schedule_last_run") != now.date().isoformat()


def _due_interval(cfg: dict, now: datetime) -> bool:
    hrs = max(1, int(cfg.get("hours") or 6))
    last = db.get_setting("schedule_last_ts")
    if not last:
        return True
    try:
        return (time.time() - float(last)) >= hrs * 3600
    except (ValueError, TypeError):
        return True


def _run(now: datetime) -> None:
    db.set_setting("schedule_last_run", now.date().isoformat())
    db.set_setting("schedule_last_ts", str(time.time()))
    try:
        sync.run_sync()
    except Exception:  # noqa: BLE001  — never let a scheduled run crash the thread
        pass


def _loop() -> None:
    while not _stop.wait(30):
        try:
            cfg = get_schedule()
            if not cfg.get("enabled") or not db.creds_set() or sync.is_running():
                continue
            now = datetime.now()
            due = _due_interval(cfg, now) if cfg.get("mode") == "interval" else _due_daily(cfg, now)
            if due:
                _run(now)
        except Exception:  # noqa: BLE001
            pass


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="qpd-scheduler")
    _thread.start()
