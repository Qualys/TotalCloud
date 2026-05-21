#!/usr/bin/env python3
"""
Azure → Qualys Tenant Connector

Sub-commands:
  create          Discover subscriptions and create a Qualys connector per subscription
  list            List all Azure connectors currently in Qualys
  status          Show live state for specific connector ID(s)
  list-mgs        Show management group hierarchy (to choose azure.rootMg in config)
  delete          Delete one or more Qualys connectors by ID
  restore-orphans Re-enable connectors that were previously disabled by this script

All run settings live in config.json. Only --config FILE and subcommand flags are CLI args.
See config.example.json for the full schema.
"""

import argparse
import csv
import json
import logging
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from azure_client import (
    build_credential,
    discover_subscriptions,
    get_mg_hierarchy,
    list_management_groups,
)
from qualys_client import (
    ConnectorResult,
    QualysClient,
    VALID_ACTIVATION_MODULES,
    resolve_connector_name,
    resolve_platform_url,
)

_LOG_FMT  = "%(asctime)s  %(levelname)-7s  %(message)s"
_LOG_DATE = "%Y-%m-%d %H:%M:%S"

_DELETE_PATH = "/qps/rest/3.0/delete/am/azureassetdataconnector"


# ── logging ───────────────────────────────────────────────────────────────────

def _setup_logging(output_dir: Path, verbose: bool = False) -> Path:
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FMT, datefmt="%H:%M:%S"))
    root.addHandler(console)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATE))
    root.addHandler(fh)

    # Silence chatty Azure SDK HTTP transport logs
    for noisy in ("azure.core.pipeline.policies.http_logging_policy",
                  "azure.identity", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log_path


log = logging.getLogger(__name__)


# ── config loading ────────────────────────────────────────────────────────────

def _check_config_gitignored(config_path: str) -> None:
    """Warn if config.json is not gitignored (it contains credentials)."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", config_path],
            capture_output=True, timeout=3,
        )
        if result.returncode == 1:
            # returncode 0 = ignored, 1 = not ignored, 128 = not in a git repo
            log.warning(
                "SECURITY WARNING: %s is NOT gitignored — it contains credentials. "
                "Add it to .gitignore before committing.",
                config_path,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # git not available


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        log.error("Config file not found: %s", path)
        log.error("Copy config.example.json → config.json and fill in your values.")
        sys.exit(1)
    with p.open() as fh:
        try:
            cfg = json.load(fh)
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON in %s: %s", path, exc)
            sys.exit(1)
    for section in ("azure", "qualys"):
        if section not in cfg:
            log.error("Config missing required section '%s'", section)
            sys.exit(1)
    _check_config_gitignored(path)
    return cfg


def _azure_creds(cfg: dict) -> tuple[str, str, str]:
    az = cfg["azure"]
    missing = [k for k in ("tenantId", "clientId", "clientSecret") if not az.get(k)]
    if missing:
        log.error("Config azure section missing required keys: %s", missing)
        sys.exit(1)
    return az["tenantId"], az["clientId"], az["clientSecret"]


def _qualys_settings(cfg: dict) -> dict:
    q = cfg["qualys"]
    missing = [k for k in ("username", "password") if not q.get(k)]
    if missing:
        log.error("Config qualys section missing required keys: %s", missing)
        sys.exit(1)

    platform_val = q.get("platform") or q.get("baseUrl") or "US2"
    try:
        base_url = resolve_platform_url(platform_val)
    except ValueError as exc:
        log.error("%s", exc)
        sys.exit(1)

    activation = q.get("activation") or []
    invalid = [m for m in activation if m not in VALID_ACTIVATION_MODULES]
    if invalid:
        log.error(
            "Config qualys.activation contains unknown module(s): %s  (valid: %s)",
            invalid, VALID_ACTIVATION_MODULES,
        )
        sys.exit(1)

    if "PC" in activation and "SCA" in activation:
        log.error("Config qualys.activation: PC and SCA cannot be activated together — choose one.")
        sys.exit(1)

    _VALID_FREQUENCIES = {60, 120, 180, 240, 360, 480, 720, 1440}
    run_frequency = int(q.get("runFrequency", 1440))
    if run_frequency not in _VALID_FREQUENCIES:
        log.error(
            "Config qualys.runFrequency=%d is invalid. Allowed values: %s",
            run_frequency, sorted(_VALID_FREQUENCIES),
        )
        sys.exit(1)

    perimeter_scan = bool(q.get("perimeterScan", False))
    scan_config    = q.get("perimeterScanConfig") or None

    _APP_TYPE_MAP = {
        "asset-inventory": ["AI"],
        "cspm":            ["AI", "CI", "CSA"],
    }
    raw_app_type = (q.get("appType") or "").strip().lower()
    if raw_app_type not in _APP_TYPE_MAP:
        log.error(
            "Config qualys.appType=%r is invalid. Allowed values: %s",
            raw_app_type, list(_APP_TYPE_MAP),
        )
        sys.exit(1)
    app_modules = _APP_TYPE_MAP[raw_app_type]

    if perimeter_scan and "VM" not in activation:
        log.error("Config: perimeterScan=true requires \"VM\" in qualys.activation.")
        sys.exit(1)

    if perimeter_scan and scan_config:
        _VALID_DAYS       = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"}
        _VALID_RECURRENCE = {"WEEKLY", "MONTHLY"}

        # optionProfileId — required positive integer
        opid = scan_config.get("optionProfileId")
        if not opid or not isinstance(opid, int) or opid <= 0:
            log.error("perimeterScanConfig.optionProfileId must be a positive integer (got %r).", opid)
            sys.exit(1)

        # recurrence
        recurrence = (scan_config.get("recurrence") or "").upper()
        if recurrence not in _VALID_RECURRENCE:
            log.error(
                "perimeterScanConfig.recurrence=%r is invalid. Allowed: %s",
                recurrence, sorted(_VALID_RECURRENCE),
            )
            sys.exit(1)

        # daysOfWeek — required for WEEKLY
        days = scan_config.get("daysOfWeek") or []
        bad_days = [d for d in days if d not in _VALID_DAYS]
        if bad_days:
            log.error("perimeterScanConfig.daysOfWeek contains invalid values: %s  (valid: %s)",
                      bad_days, sorted(_VALID_DAYS))
            sys.exit(1)
        if recurrence == "WEEKLY" and not days:
            log.error("perimeterScanConfig.daysOfWeek is required when recurrence=WEEKLY.")
            sys.exit(1)

        # startDate — required, MM/DD/YYYY
        import re as _re
        start_date = scan_config.get("startDate") or ""
        if not _re.fullmatch(r"\d{2}/\d{2}/\d{4}", start_date):
            log.error("perimeterScanConfig.startDate=%r must be in MM/DD/YYYY format.", start_date)
            sys.exit(1)

        # startTime — required, HH:MM
        start_time = scan_config.get("startTime") or ""
        if not _re.fullmatch(r"\d{2}:\d{2}", start_time):
            log.error("perimeterScanConfig.startTime=%r must be in HH:MM format.", start_time)
            sys.exit(1)

        # timezone — required
        if not (scan_config.get("timezone") or "").strip():
            log.error("perimeterScanConfig.timezone is required.")
            sys.exit(1)

    return {
        "username":        q["username"],
        "password":        q["password"],
        "base_url":        base_url,
        "platform_label":  platform_val.upper() if not platform_val.startswith("http") else "custom",
        "activation":      activation,
        "run_frequency":   run_frequency,
        "is_gov_cloud":    bool(q.get("isGovCloud", True)),
        "disable_orphans": bool(q.get("disableOrphans", False)),
        "connector_tags":  q.get("connectorTags") or [],
        "name_prefix":     q.get("connectorNamePrefix") or "",
        "name_suffix":     q.get("connectorNameSuffix") or "",
        "perimeter_scan":  perimeter_scan,
        "scan_config":     scan_config,
        "app_modules":     app_modules,
    }


def _qualys_client(qs: dict) -> QualysClient:
    return QualysClient(
        username=qs["username"],
        password=qs["password"],
        base_url=qs["base_url"],
    )


# ── CSV ──────────────────────────────────────────────────────────────────────

_CSV_FILE = "connectors.csv"
_CSV_FIELDS = [
    "subscription_id", "subscription_name", "management_group",
    "connector_id", "connector_name", "tenant_id", "app_type", "dry_run",
    "created_at", "last_updated_at", "last_action", "current_status", "note",
    "connector_state", "last_synced_on",
    "total_assets_created", "total_assets_updated", "total_assets_deleted",
    "connector_error", "disabled", "run_frequency",
]


def _load_connector_csv(output_dir: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Load connectors.csv. Returns (by_sub, by_id) — both dicts share the same row objects.
    """
    by_sub: dict[str, dict] = {}
    by_id:  dict[str, dict] = {}
    path = output_dir / _CSV_FILE
    if not path.exists():
        return by_sub, by_id
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            sub_id = row.get("subscription_id", "")
            cid    = row.get("connector_id", "")
            if sub_id:
                by_sub[sub_id] = row
            if cid:
                by_id[cid] = row
    log.info("Loaded %d row(s) from %s", len(by_sub), path)
    return by_sub, by_id


def _write_connector_csv(by_sub: dict[str, dict], by_id: dict[str, dict], output_dir: Path) -> Path:
    path = output_dir / _CSV_FILE
    seen: set[int] = set()
    rows: list[dict] = []
    for row in list(by_sub.values()) + list(by_id.values()):
        if id(row) not in seen:
            seen.add(id(row))
            rows.append(row)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in _CSV_FIELDS})
    return path


def _upsert_create_results(
    results: list[ConnectorResult],
    tenant_id: str,
    label: str,
    dry_run: bool,
    output_dir: Path,
    states: Optional[dict[str, dict]] = None,
) -> Path:
    by_sub, by_id = _load_connector_csv(output_dir)
    now    = datetime.now(timezone.utc).isoformat()
    states = states or {}

    for r in results:
        st       = states.get(r.connector_id or "", {})
        existing = by_sub.get(r.subscription_id, {})

        if r.status in ("created", "updated"):
            current_status = "active"
        elif r.status == "skipped":
            current_status = existing.get("current_status") or "active"
        elif r.status == "dry_run":
            current_status = "dry_run"
        else:
            current_status = "failed"

        row: dict = {
            "subscription_id":      r.subscription_id,
            "subscription_name":    r.subscription_name,
            "management_group":     r.management_group,
            "connector_id":         r.connector_id or existing.get("connector_id", ""),
            "connector_name":       r.connector_name,
            "tenant_id":            tenant_id,
            "app_type":             label,
            "dry_run":              str(dry_run).lower(),
            "created_at":           existing.get("created_at") or now,
            "last_updated_at":      now,
            "last_action":          r.status,
            "current_status":       current_status,
            "note":                 r.note or "",
            "connector_state":      st.get("connector_state",       existing.get("connector_state", "")),
            "last_synced_on":       st.get("last_synced_on",        existing.get("last_synced_on", "")),
            "total_assets_created": st.get("total_assets_created",  existing.get("total_assets_created", "")),
            "total_assets_updated": st.get("total_assets_updated",  existing.get("total_assets_updated", "")),
            "total_assets_deleted": st.get("total_assets_deleted",  existing.get("total_assets_deleted", "")),
            "connector_error":      st.get("connector_error",       existing.get("connector_error", "")),
            "disabled":             st.get("disabled",              existing.get("disabled", "")),
            "run_frequency":        st.get("run_frequency",         existing.get("run_frequency", "")),
        }
        by_sub[r.subscription_id] = row
        if row["connector_id"]:
            by_id[row["connector_id"]] = row

    return _write_connector_csv(by_sub, by_id, output_dir)


def _apply_action(
    connector_id: str,
    action: str,
    current_status: str,
    note: str,
    by_sub: dict[str, dict],
    by_id:  dict[str, dict],
) -> None:
    """Update an existing row, or create a minimal one if the connector isn't in history."""
    now = datetime.now(timezone.utc).isoformat()
    row = by_id.get(connector_id)
    if row is None:
        row = {"connector_id": connector_id, "created_at": ""}
        by_id[connector_id] = row
        sub_id = row.get("subscription_id", "")
        if sub_id:
            by_sub[sub_id] = row
    row["last_updated_at"] = now
    row["last_action"]     = action
    row["current_status"]  = current_status
    row["note"]            = note
    if action in ("disabled", "orphan_disable"):
        row["disabled"] = "true"
    elif action in ("enabled", "created"):
        row["disabled"] = "false"


def _print_summary(results: list[ConnectorResult]) -> None:
    created = [r for r in results if r.status == "created"]
    updated = [r for r in results if r.status == "updated"]
    skipped = [r for r in results if r.status == "skipped"]
    dry     = [r for r in results if r.status == "dry_run"]
    failed  = [r for r in results if r.status == "failed"]

    print("\n" + "=" * 65)
    print(f"  Summary — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 65)
    print(f"  Total          : {len(results)}")
    if dry:
        print(f"  Dry-run (enum) : {len(dry)}")
    else:
        print(f"  Created        : {len(created)}")
        print(f"  Updated        : {len(updated)}")
        print(f"  Already existed: {len(skipped)}")
        print(f"  Failed         : {len(failed)}")

    for label, bucket, icon in [
        ("Created", created, "✓"),
        ("Updated", updated, "↺"),
        ("Skipped", skipped, "↷"),
        ("Dry-run", dry,     "○"),
        ("Failed",  failed,  "✗"),
    ]:
        if bucket:
            print(f"\n  {label}:")
            for r in bucket:
                cid = f"[{r.connector_id}] " if r.connector_id else ""
                err = f"  — {r.note}" if r.note and r.status == "failed" else ""
                print(f"    {icon} {cid}{r.connector_name} ({r.subscription_id}){err}")
    print("=" * 65)


def _get_managed_ids(by_id: dict[str, dict]) -> set[str]:
    """Connector IDs tracked by this script that have not been deleted."""
    return {cid for cid, row in by_id.items() if row.get("current_status") != "deleted" and cid}


def _get_disabled_map(by_id: dict[str, dict]) -> dict[str, str]:
    """Return {connector_id: subscription_id} for all disabled connectors."""
    return {
        cid: row.get("subscription_id", "")
        for cid, row in by_id.items()
        if row.get("current_status") == "disabled"
    }


# ── create ────────────────────────────────────────────────────────────────────

def cmd_create(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    qs  = _qualys_settings(cfg)
    dry_run    = args.dry_run
    parallel   = args.parallel
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tenant_id, client_id, client_secret = _azure_creds(cfg)
    root_mg = cfg["azure"].get("rootMg") or None

    log.info("=" * 60)
    log.info("Azure Tenant Connector")
    log.info("Tenant        : %s", tenant_id)
    log.info("SP            : %s", client_id)
    log.info("Qualys        : %s  (%s)", qs["platform_label"], qs["base_url"])
    log.info("Activation    : %s", qs["activation"] if qs["activation"] else "(none)")
    log.info("Run frequency : %d min", qs["run_frequency"])
    log.info("Gov cloud     : %s", qs["is_gov_cloud"])
    log.info("Scope         : %s", f"MG '{root_mg}' (+ children)" if root_mg else "entire tenant")
    log.info("Orphan check  : %s", qs["disable_orphans"])
    log.info("Connector tags: %s", qs["connector_tags"] or "(none)")
    log.info("Name prefix   : %s", qs["name_prefix"] or "(none)")
    log.info("Name suffix   : %s", qs["name_suffix"] or "(none)")
    log.info("Perimeter scan: %s", qs["perimeter_scan"])
    log.info("Parallel      : %d", parallel)
    log.info("Output dir    : %s", output_dir.resolve())
    log.info("Mode          : %s", "DRY RUN" if dry_run else "LIVE")
    log.info("=" * 60)

    tenant_info, management_groups, subscriptions = discover_subscriptions(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        root_management_group=root_mg,
        is_gov_cloud=qs["is_gov_cloud"],
    )

    log.info("MGs found            : %d", len(management_groups))
    log.info("Active subscriptions : %d", len(subscriptions))

    if not subscriptions:
        log.warning("No active subscriptions found. Check SP permissions or azure.rootMg in config.")
        return 0

    print(f"\n  {'#':<4} {'Subscription ID':<38} {'Connector Name':<42} MG")
    print("  " + "-" * 105)
    for idx, sub in enumerate(subscriptions, 1):
        sub_id = sub["subscriptionId"]
        name   = resolve_connector_name(sub.get("displayName"), sub_id, qs["name_prefix"], qs["name_suffix"])
        mg     = sub.get("managementGroupName", "")
        print(f"  {idx:<4} {sub_id:<38} {name:<42} {mg}")
    print()

    if dry_run:
        results = [
            ConnectorResult(
                subscription_id=sub["subscriptionId"],
                subscription_name=sub.get("displayName", sub["subscriptionId"]),
                connector_name=resolve_connector_name(sub.get("displayName"), sub["subscriptionId"], qs["name_prefix"], qs["name_suffix"]),
                management_group=sub.get("managementGroupName", ""),
                success=True,
                status="dry_run",
            )
            for sub in subscriptions
        ]
        _print_summary(results)
        csv_path = _upsert_create_results(results, tenant_id, qs["platform_label"],
                                          dry_run=True, output_dir=output_dir)
        log.info("DRY RUN — CSV updated: %s", csv_path)
        return 0

    client = _qualys_client(qs)

    log.info("Verifying Qualys credentials and Connectors module access …")
    ok, reason = client.verify_access()
    if not ok:
        log.error("Qualys access check failed: %s", reason)
        return 1
    log.info("Qualys access check passed.")

    connector_tag_ids: list[int] = []
    if qs["connector_tags"]:
        connector_tag_ids = client.resolve_tag_names(qs["connector_tags"])

    # Drift detection — scoped strictly to connectors this script previously created
    orphan_updates: list[tuple[str, str, str, str]] = []  # (id, action, status, note)
    if qs["disable_orphans"]:
        by_sub_pre, by_id_pre = _load_connector_csv(output_dir)
        managed_ids = _get_managed_ids(by_id_pre)
        if not managed_ids:
            log.warning(
                "Orphan detection requested (disableOrphans=true) but no CSV history found. "
                "Skipping to avoid touching connectors created outside this script. "
                "Run 'create' at least once so the script has a baseline."
            )
        else:
            active_sub_ids = {sub["subscriptionId"] for sub in subscriptions}
            log.info("Drift check — disabling script-managed connectors for subscriptions no longer in scope …")
            orphans = client.disable_orphan_connectors(active_sub_ids, managed_connector_ids=managed_ids)
            if orphans:
                dis  = sum(1 for o in orphans if o["result"] == "disabled")
                fail = len(orphans) - dis
                log.info("Orphans: %d disabled, %d failed", dis, fail)
                print("\n  Orphan connectors (subscription no longer active):")
                for o in orphans:
                    icon   = "✓" if o["result"] == "disabled" else "✗"
                    action = "orphan_disable" if o["result"] == "disabled" else "orphan_disable_failed"
                    status = "disabled"       if o["result"] == "disabled" else "active"
                    print(f"    {icon} [{o['id']}] {o['name']} (sub={o['subscriptionId']}) — {o['result']}")
                    orphan_updates.append((o["id"], action, status, o.get("note", "")))

    results = client.create_connectors_bulk(
        subscriptions=subscriptions,
        directory_id=tenant_id,
        application_id=client_id,
        authentication_key=client_secret,
        is_gov_cloud=qs["is_gov_cloud"],
        activation_modules=qs["activation"],
        run_frequency=qs["run_frequency"],
        connector_tag_ids=connector_tag_ids,
        parallel=parallel,
        name_prefix=qs["name_prefix"],
        name_suffix=qs["name_suffix"],
        perimeter_scan=qs["perimeter_scan"],
        scan_config=qs["scan_config"],
        app_modules=qs["app_modules"],
    )

    _print_summary(results)

    states: dict[str, dict] = {}
    ids_to_fetch = [r.connector_id for r in results if r.connector_id]
    if ids_to_fetch:
        log.info("Fetching live connector state for %d connector(s) …", len(ids_to_fetch))
        for cid in ids_to_fetch:
            st = client.get_connector_state(cid)
            if st:
                states[cid] = st
                log.info("  [%s] state=%s  lastSync=%s  assets_created=%s",
                         cid,
                         st.get("connector_state", "?"),
                         st.get("last_synced_on", "?"),
                         st.get("total_assets_created", "?"))

    csv_path = _upsert_create_results(results, tenant_id, qs["platform_label"],
                                      dry_run=False, output_dir=output_dir, states=states)
    # Apply any orphan disable updates into the same file
    if orphan_updates:
        by_sub, by_id = _load_connector_csv(output_dir)
        for cid, action, status, note in orphan_updates:
            _apply_action(cid, action, status, note, by_sub, by_id)
        _write_connector_csv(by_sub, by_id, output_dir)
    log.info("CSV updated: %s", csv_path)
    return 1 if any(r.status == "failed" for r in results) else 0


# ── list ──────────────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> int:
    cfg    = load_config(args.config)
    qs     = _qualys_settings(cfg)
    client = _qualys_client(qs)

    log.info("Qualys platform: %s  (%s)", qs["platform_label"], qs["base_url"])
    connectors = client.list_all_connectors()

    if not connectors:
        print("  No Azure connectors found.")
        return 0

    if args.subscription:
        connectors = [c for c in connectors if args.subscription in c["subscriptionId"]]
        log.info("Filtered to subscription containing '%s': %d result(s)", args.subscription, len(connectors))

    print(f"\n  {'ID':<10} {'Name':<46} {'Subscription ID':<38} {'State':<14} Disabled")
    print("  " + "-" * 120)
    for c in connectors:
        name = c["name"][:45]
        print(f"  {c['id']:<10} {name:<46} {c['subscriptionId']:<38} "
              f"{c.get('connectorState',''):<14} {str(c['disabled']).lower()}")
    print(f"\n  Total: {len(connectors)} connector(s)")
    return 0


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    cfg    = load_config(args.config)
    qs     = _qualys_settings(cfg)
    client = _qualys_client(qs)

    log.info("Qualys platform: %s  (%s)", qs["platform_label"], qs["base_url"])
    for cid in args.ids:
        st = client.get_connector_state(cid)
        if not st:
            print(f"\n  [{cid}] Not found or error.")
            continue
        print(f"\n  Connector {cid}:")
        print(f"    State          : {st.get('connector_state','')}")
        print(f"    Last Synced    : {st.get('last_synced_on','')}")
        print(f"    Assets Created : {st.get('total_assets_created','')}")
        print(f"    Assets Updated : {st.get('total_assets_updated','')}")
        print(f"    Assets Deleted : {st.get('total_assets_deleted','')}")
        err = st.get("connector_error", "")
        print(f"    Error          : {err or '(none)'}")
        print(f"    Disabled       : {st.get('disabled','')}")
        print(f"    Run Frequency  : {st.get('run_frequency','')} min")
    return 0


# ── list-mgs ──────────────────────────────────────────────────────────────────

def cmd_list_mgs(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    tenant_id, client_id, client_secret = _azure_creds(cfg)

    is_gov_cloud = bool(cfg["qualys"].get("isGovCloud", True))
    credential   = build_credential(tenant_id, client_id, client_secret, is_gov_cloud)
    all_mgs      = list_management_groups(credential, is_gov_cloud)

    if not all_mgs:
        log.warning("No management groups found. Check SP permissions.")
        return 1

    root_mg = all_mgs[0]["name"]
    log.info("Fetching MG hierarchy from root '%s' …", root_mg)
    hierarchy = get_mg_hierarchy(credential, root_mg, is_gov_cloud=is_gov_cloud)

    def _print_tree(node: dict, prefix: str = "", is_last: bool = True) -> None:
        ch    = "└── " if is_last else "├── "
        disp  = node["displayName"]
        name  = node["name"]
        label = f"{disp}  [{name}]" if disp != name else f"[{name}]"
        print(f"  {prefix}{ch}{label}")
        children     = node.get("children", [])
        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(children):
            _print_tree(child, child_prefix, is_last=(i == len(children) - 1))

    print(f"\n  Management Group hierarchy — tenant {tenant_id}:\n")
    _print_tree(hierarchy)
    print()
    print('  Tip: set azure.rootMg in config.json to the name in brackets to scope connector creation.')
    print()
    return 0


# ── delete ────────────────────────────────────────────────────────────────────

def _delete_one(client: QualysClient, connector_id: str) -> tuple[bool, str]:
    url = f"{client._base}{_DELETE_PATH}/{connector_id}"
    log.info("Deleting connector id=%s", connector_id)
    try:
        resp = client._session.post(url, data=b"", auth=client._auth, timeout=30)
        log.debug("  delete HTTP %d", resp.status_code)
        root = ET.fromstring(resp.text)
        if root.findtext("responseCode") == "SUCCESS":
            log.info("  ✓ Connector %s deleted", connector_id)
            return True, "deleted"
        err = root.findtext("responseErrorDetails/errorMessage") or f"HTTP {resp.status_code}"
        log.warning("  ✗ Failed to delete %s: %s", connector_id, err)
        return False, err
    except Exception as exc:
        log.warning("  ✗ Exception deleting %s: %s", connector_id, exc)
        return False, str(exc)


def cmd_delete(args: argparse.Namespace) -> int:
    cfg    = load_config(args.config)
    qs     = _qualys_settings(cfg)
    client = _qualys_client(qs)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        _, by_id = _load_connector_csv(output_dir)
        managed_ids = _get_managed_ids(by_id)
        if not managed_ids:
            log.error(
                "No connector IDs found in %s. "
                "Run 'create' first so the script has a record of what it created.",
                output_dir / _CSV_FILE,
            )
            return 1
        ids = sorted(managed_ids)
        log.info("--all: %d script-managed connector(s) found in CSV history", len(ids))
        print(f"\n  Found {len(ids)} script-managed connector(s) in CSV history:")
        for cid in ids:
            print(f"    {cid}")
        confirm = input("\n  Delete all of the above? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return 0
    elif args.ids:
        ids = args.ids
    else:
        log.error("Provide --ids <ID ...> or --all")
        return 1

    total  = len(ids)
    failed = 0

    log.info("Qualys platform: %s  (%s)", qs["platform_label"], qs["base_url"])
    print(f"\n  Deleting {total} connector(s) …\n")
    by_sub, by_id = _load_connector_csv(output_dir)
    for cid in ids:
        ok, msg = _delete_one(client, cid)
        icon = "✓" if ok else "✗"
        print(f"  {icon}  [{cid}]  {msg}")
        _apply_action(cid, "deleted" if ok else "delete_failed", "deleted" if ok else "active",
                      msg, by_sub, by_id)
        if not ok:
            failed += 1

    csv_path = _write_connector_csv(by_sub, by_id, output_dir)
    print(f"\n  Summary: {total - failed} deleted, {failed} failed")
    log.info("CSV updated: %s", csv_path)
    return 1 if failed else 0


# ── update ────────────────────────────────────────────────────────────────────

def cmd_update(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    qs  = _qualys_settings(cfg)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    by_sub, by_id = _load_connector_csv(output_dir)

    if args.all:
        managed_ids = _get_managed_ids(by_id)
        if not managed_ids:
            log.error(
                "No connector IDs found in %s. "
                "Run 'create' first so the script has a record of what it created.",
                output_dir / _CSV_FILE,
            )
            return 1
        ids = sorted(managed_ids)
        print(f"\n  Found {len(ids)} script-managed connector(s) in CSV history:")
        for cid in ids:
            row = by_id.get(cid, {})
            print(f"    {cid}  ({row.get('subscription_name', '')})")
        confirm = input("\n  Update all of the above? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return 0
    elif args.ids:
        ids = args.ids
    else:
        log.error("Provide --ids <ID ...> or --all")
        return 1

    tenant_id, client_id, client_secret = _azure_creds(cfg)
    client = _qualys_client(qs)

    connector_tag_ids: list[int] = []
    if qs["connector_tags"]:
        connector_tag_ids = client.resolve_tag_names(qs["connector_tags"])

    total  = len(ids)
    failed = 0

    log.info("Qualys platform: %s  (%s)", qs["platform_label"], qs["base_url"])
    log.info("Updating %d connector(s) …", total)
    print(f"\n  Updating {total} connector(s) …\n")

    for cid in ids:
        row    = by_id.get(cid, {})
        sub_id = row.get("subscription_id", "")
        disp   = row.get("subscription_name", "")
        mg     = row.get("management_group", "")

        if not sub_id:
            log.warning("  [%s] subscription_id not in CSV — skipping", cid)
            print(f"  ⚠  [{cid}]  subscription_id not in CSV, skipping")
            failed += 1
            continue

        conn_name = resolve_connector_name(disp, sub_id, qs["name_prefix"], qs["name_suffix"])
        result = client.update_connector(
            connector_id=cid,
            connector_name=conn_name,
            subscription_id=sub_id,
            subscription_name=disp or sub_id,
            management_group=mg,
            directory_id=tenant_id,
            application_id=client_id,
            authentication_key=client_secret,
            is_gov_cloud=qs["is_gov_cloud"],
            activation_modules=qs["activation"],
            run_frequency=qs["run_frequency"],
            connector_tag_ids=connector_tag_ids,
            perimeter_scan=qs["perimeter_scan"],
            scan_config=qs["scan_config"],
            app_modules=qs["app_modules"],
        )
        icon = "✓" if result.success else "✗"
        note = f"  — {result.note}" if result.note else ""
        print(f"  {icon}  [{cid}]  {conn_name}{note}")
        _apply_action(cid, result.status, "active" if result.success else "failed",
                      result.note or "", by_sub, by_id)
        if not result.success:
            failed += 1

    csv_path = _write_connector_csv(by_sub, by_id, output_dir)
    print(f"\n  Summary: {total - failed} updated, {failed} failed")
    log.info("CSV updated: %s", csv_path)
    return 1 if failed else 0


# ── disable ───────────────────────────────────────────────────────────────────

def cmd_disable(args: argparse.Namespace) -> int:
    cfg    = load_config(args.config)
    qs     = _qualys_settings(cfg)
    client = _qualys_client(qs)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        _, by_id = _load_connector_csv(output_dir)
        managed_ids = _get_managed_ids(by_id)
        if not managed_ids:
            log.error(
                "No connector IDs found in %s. "
                "Run 'create' first so the script has a record of what it created.",
                output_dir / _CSV_FILE,
            )
            return 1
        ids = sorted(managed_ids)
        log.info("--all: %d script-managed connector(s) found in CSV history", len(ids))
        print(f"\n  Found {len(ids)} script-managed connector(s) in CSV history:")
        for cid in ids:
            print(f"    {cid}")
        confirm = input("\n  Disable all of the above? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return 0
    elif args.ids:
        ids = args.ids
    else:
        log.error("Provide --ids <ID ...> or --all")
        return 1

    total  = len(ids)
    failed = 0

    log.info("Qualys platform: %s  (%s)", qs["platform_label"], qs["base_url"])
    print(f"\n  Disabling {total} connector(s) …\n")
    by_sub, by_id = _load_connector_csv(output_dir)
    for cid in ids:
        ok, msg = client.disable_connector(cid)
        icon = "✓" if ok else "✗"
        print(f"  {icon}  [{cid}]  {msg}")
        _apply_action(cid, "disabled" if ok else "disable_failed", "disabled" if ok else "active",
                      msg, by_sub, by_id)
        if not ok:
            failed += 1

    csv_path = _write_connector_csv(by_sub, by_id, output_dir)
    print(f"\n  Summary: {total - failed} disabled, {failed} failed")
    log.info("CSV updated: %s", csv_path)
    return 1 if failed else 0


# ── restore-orphans ───────────────────────────────────────────────────────────

def cmd_restore_orphans(args: argparse.Namespace) -> int:
    """
    Re-enable connectors that were previously disabled by this script if their
    Azure subscription is now active again.
    """
    cfg = load_config(args.config)
    qs  = _qualys_settings(cfg)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    by_sub, by_id = _load_connector_csv(output_dir)
    disabled = _get_disabled_map(by_id)
    if not disabled:
        log.info("No previously disabled connectors found in CSV history — nothing to restore.")
        return 0

    tenant_id, client_id, client_secret = _azure_creds(cfg)
    root_mg = cfg["azure"].get("rootMg") or None

    log.info("Discovering current active Azure subscriptions …")
    _, _, subscriptions = discover_subscriptions(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        root_management_group=root_mg,
        is_gov_cloud=qs["is_gov_cloud"],
    )
    active_sub_ids = {sub["subscriptionId"] for sub in subscriptions}

    to_restore = {cid: sub_id for cid, sub_id in disabled.items() if sub_id in active_sub_ids}
    if not to_restore:
        log.info("None of the %d previously disabled connector(s) have subscriptions that are now active.",
                 len(disabled))
        return 0

    log.info("Restoring %d connector(s) whose subscriptions are now active …", len(to_restore))
    client = _qualys_client(qs)
    print(f"\n  Restoring {len(to_restore)} connector(s) …\n")
    failed = 0
    for cid, sub_id in to_restore.items():
        ok, msg = client.enable_connector(cid)
        icon = "✓" if ok else "✗"
        print(f"  {icon}  [{cid}]  sub={sub_id}  {msg}")
        _apply_action(cid, "enabled" if ok else "enable_failed", "active" if ok else "disabled",
                      msg, by_sub, by_id)
        if not ok:
            failed += 1

    csv_path = _write_connector_csv(by_sub, by_id, output_dir)
    ok_count = len(to_restore) - failed
    print(f"\n  Summary: {ok_count} enabled, {failed} failed")
    log.info("CSV updated: %s", csv_path)
    return 1 if failed else 0


# ── CLI wiring ────────────────────────────────────────────────────────────────

def main():
    # Shared parent parser so --verbose/-v works after the subcommand too
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG logging (shows request/response XML)",
    )

    parser = argparse.ArgumentParser(
        description="Azure → Qualys tenant connector  (all settings in config.json)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_common],
    )
    parser.add_argument(
        "--config", default="config.json", metavar="FILE",
        help="Path to JSON config file (default: config.json)",
    )
    parser.add_argument(
        "--output-dir", default=".", metavar="DIR",
        help="Directory for CSVs and logs (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Discover subscriptions and create connectors",
                              parents=[_common])
    p_create.add_argument("--dry-run", action="store_true",
                          help="Enumerate Azure subscriptions only; skip all Qualys API calls")
    p_create.add_argument("--parallel", type=int, default=1, metavar="N",
                          help="Number of concurrent connector creation threads (default: 1)")

    # list
    p_list = sub.add_parser("list", help="List all Azure connectors in Qualys",
                            parents=[_common])
    p_list.add_argument("--subscription", metavar="ID",
                        help="Filter by subscription ID (substring match)")

    # status
    p_status = sub.add_parser("status", help="Show live state for one or more connector IDs",
                              parents=[_common])
    p_status.add_argument("--ids", metavar="ID", nargs="+", required=True,
                          help="One or more Qualys connector IDs")

    # list-mgs
    sub.add_parser("list-mgs", help="Print MG hierarchy — use to pick azure.rootMg in config",
                   parents=[_common])

    # delete
    p_delete = sub.add_parser("delete", help="Delete one or more connectors by Qualys ID",
                              parents=[_common])
    p_delete.add_argument("--ids", metavar="ID", nargs="+",
                          help="One or more Qualys connector IDs to delete")
    p_delete.add_argument("--all", action="store_true",
                          help="Delete all connectors previously created by this script (reads CSV history)")

    # update
    p_update = sub.add_parser("update", help="Update existing connectors (name, auth key, activation, frequency)",
                              parents=[_common])
    p_update.add_argument("--ids", metavar="ID", nargs="+",
                          help="One or more Qualys connector IDs to update")
    p_update.add_argument("--all", action="store_true",
                          help="Update all connectors previously created by this script (reads CSV history)")

    # disable
    p_disable = sub.add_parser("disable", help="Disable one or more connectors by Qualys ID",
                               parents=[_common])
    p_disable.add_argument("--ids", metavar="ID", nargs="+",
                           help="One or more Qualys connector IDs to disable")
    p_disable.add_argument("--all", action="store_true",
                           help="Disable all connectors previously created by this script (reads CSV history)")

    # restore-orphans
    sub.add_parser("restore-orphans",
                   help="Re-enable previously disabled connectors whose subscriptions are now active",
                   parents=[_common])

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = _setup_logging(output_dir, verbose=args.verbose)
    log.info("Log file: %s", log_path)

    dispatch = {
        "create":          cmd_create,
        "list":            cmd_list,
        "status":          cmd_status,
        "list-mgs":        cmd_list_mgs,
        "delete":          cmd_delete,
        "update":          cmd_update,
        "disable":         cmd_disable,
        "restore-orphans": cmd_restore_orphans,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
