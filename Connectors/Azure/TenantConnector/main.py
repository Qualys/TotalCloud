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
    APP_TYPE_CONFIG,
    ConnectorResult,
    QualysClient,
    VALID_ACTIVATION_MODULES,
    resolve_connector_name,
    resolve_platform_url,
)

_LOG_FMT  = "%(asctime)s  %(levelname)-7s  %(message)s"
_LOG_DATE = "%Y-%m-%d %H:%M:%S"

_APP_TYPE_MAP = {
    "asset-inventory": "AI",
    "cspm":            "CSA",
}

_DELETE_PATH = "/qps/rest/3.0/delete/am/azureassetdataconnector"


# ── logging ───────────────────────────────────────────────────────────────────

def _setup_logging(output_dir: Path) -> Path:
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
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

    raw_app_type = q.get("appType", "cspm").lower()
    if raw_app_type not in _APP_TYPE_MAP:
        log.error("Config qualys.appType must be one of: %s", list(_APP_TYPE_MAP))
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

    run_frequency = int(q.get("runFrequency", 1440))
    if run_frequency < 1:
        log.error("Config qualys.runFrequency must be >= 1 minute")
        sys.exit(1)

    return {
        "username":        q["username"],
        "password":        q["password"],
        "base_url":        base_url,
        "platform_label":  platform_val.upper() if not platform_val.startswith("http") else "custom",
        "app_type_label":  raw_app_type,
        "app_type_key":    _APP_TYPE_MAP[raw_app_type],
        "activation":      activation,
        "run_frequency":   run_frequency,
        "is_gov_cloud":    bool(q.get("isGovCloud", True)),
        "disable_orphans": bool(q.get("disableOrphans", False)),
        "connector_tags":  q.get("connectorTags") or [],
        "asset_tags":      q.get("assetTags") or [],
    }


def _qualys_client(qs: dict) -> QualysClient:
    return QualysClient(
        username=qs["username"],
        password=qs["password"],
        base_url=qs["base_url"],
    )


# ── CSV / summary ─────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _save_csv(
    results: list[ConnectorResult],
    tenant_id: str,
    app_type_label: str,
    dry_run: bool,
    output_dir: Path,
    states: Optional[dict[str, dict]] = None,
) -> Path:
    filename = output_dir / f"connector_state_{_ts()}.csv"
    fieldnames = [
        "timestamp", "tenant_id", "app_type", "dry_run",
        "subscription_id", "subscription_name", "management_group",
        "connector_name", "connector_id", "status", "note",
        "connector_state", "last_synced_on",
        "total_assets_created", "total_assets_updated", "total_assets_deleted",
        "connector_error", "disabled", "run_frequency",
    ]
    now = datetime.now(timezone.utc).isoformat()
    states = states or {}
    with open(filename, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            st = states.get(r.connector_id or "", {})
            writer.writerow({
                "timestamp":            now,
                "tenant_id":            tenant_id,
                "app_type":             app_type_label,
                "dry_run":              str(dry_run).lower(),
                "subscription_id":      r.subscription_id,
                "subscription_name":    r.subscription_name,
                "management_group":     r.management_group,
                "connector_name":       r.connector_name,
                "connector_id":         r.connector_id or "",
                "status":               r.status,
                "note":                 r.note or "",
                "connector_state":      st.get("connector_state", ""),
                "last_synced_on":       st.get("last_synced_on", ""),
                "total_assets_created": st.get("total_assets_created", ""),
                "total_assets_updated": st.get("total_assets_updated", ""),
                "total_assets_deleted": st.get("total_assets_deleted", ""),
                "connector_error":      st.get("connector_error", ""),
                "disabled":             st.get("disabled", ""),
                "run_frequency":        st.get("run_frequency", ""),
            })
    return filename


def _save_orphan_csv(orphans: list[dict], output_dir: Path) -> Path:
    filename = output_dir / f"connector_orphans_{_ts()}.csv"
    fieldnames = ["timestamp", "connector_id", "connector_name", "subscription_id", "result", "note"]
    now = datetime.now(timezone.utc).isoformat()
    with open(filename, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for o in orphans:
            writer.writerow({
                "timestamp":       now,
                "connector_id":    o["id"],
                "connector_name":  o["name"],
                "subscription_id": o["subscriptionId"],
                "result":          o["result"],
                "note":            o.get("note", ""),
            })
    return filename


def _print_summary(results: list[ConnectorResult]) -> None:
    created = [r for r in results if r.status == "created"]
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
        print(f"  Already existed: {len(skipped)}")
        print(f"  Failed         : {len(failed)}")

    for label, bucket, icon in [
        ("Created", created, "✓"),
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


# ── CSV history ───────────────────────────────────────────────────────────────

def _scan_state_csvs(*dirs: Path) -> set[str]:
    """
    Scan connector_state_*.csv files in the given directories.
    Returns the set of connector IDs with status=='created'.
    """
    managed: set[str] = set()
    seen_files: set[Path] = set()
    for d in dirs:
        for path in sorted(d.glob("connector_state_*.csv")):
            if path in seen_files:
                continue
            seen_files.add(path)
            try:
                with path.open(newline="") as fh:
                    for row in csv.DictReader(fh):
                        if row.get("status") == "created" and row.get("connector_id"):
                            managed.add(row["connector_id"])
            except Exception as exc:
                log.warning("Could not read CSV %s: %s", path, exc)
    log.info("CSV history: %d script-managed connector ID(s) found across %d file(s)",
             len(managed), len(seen_files))
    return managed


def _load_managed_connector_ids(output_dir: Path) -> set[str]:
    """Collect previously created connector IDs from all known CSV locations."""
    dirs = {output_dir, Path(".")}
    return _scan_state_csvs(*dirs)


def _load_disabled_connectors(output_dir: Path) -> dict[str, str]:
    """
    Read connector_orphans_*.csv files and return {connector_id: subscription_id}
    for connectors that were disabled by this script (result == 'disabled').
    """
    result: dict[str, str] = {}
    seen: set[Path] = set()
    for d in {output_dir, Path(".")}:
        for path in sorted(d.glob("connector_orphans_*.csv")):
            if path in seen:
                continue
            seen.add(path)
            try:
                with path.open(newline="") as fh:
                    for row in csv.DictReader(fh):
                        if row.get("result") == "disabled" and row.get("connector_id"):
                            result[row["connector_id"]] = row.get("subscription_id", "")
            except Exception as exc:
                log.warning("Could not read orphan CSV %s: %s", path, exc)
    log.info("Orphan CSV history: %d previously disabled connector(s) found", len(result))
    return result


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

    app_modules = APP_TYPE_CONFIG.get(qs["app_type_key"], APP_TYPE_CONFIG["CSA"])

    log.info("=" * 60)
    log.info("Azure Tenant Connector")
    log.info("Tenant        : %s", tenant_id)
    log.info("SP            : %s", client_id)
    log.info("Qualys        : %s  (%s)", qs["platform_label"], qs["base_url"])
    log.info("App-type      : %s  →  appInfos=%s", qs["app_type_label"], app_modules)
    log.info("Activation    : %s", qs["activation"] if qs["activation"] else "(none)")
    log.info("Run frequency : %d min", qs["run_frequency"])
    log.info("Gov cloud     : %s", qs["is_gov_cloud"])
    log.info("Scope         : %s", f"MG '{root_mg}' (+ children)" if root_mg else "entire tenant")
    log.info("Orphan check  : %s", qs["disable_orphans"])
    log.info("Connector tags: %s", qs["connector_tags"] or "(none)")
    log.info("Asset tags    : %s", qs["asset_tags"] or "(none)")
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
        name   = resolve_connector_name(sub.get("displayName"), sub_id)
        mg     = sub.get("managementGroupName", "")
        print(f"  {idx:<4} {sub_id:<38} {name:<42} {mg}")
    print()

    if dry_run:
        results = [
            ConnectorResult(
                subscription_id=sub["subscriptionId"],
                subscription_name=sub.get("displayName", sub["subscriptionId"]),
                connector_name=resolve_connector_name(sub.get("displayName"), sub["subscriptionId"]),
                management_group=sub.get("managementGroupName", ""),
                success=True,
                status="dry_run",
            )
            for sub in subscriptions
        ]
        _print_summary(results)
        csv_path = _save_csv(results, tenant_id, qs["app_type_label"], dry_run=True, output_dir=output_dir)
        log.info("DRY RUN — CSV saved: %s", csv_path)
        return 0

    client = _qualys_client(qs)

    connector_tag_ids: list[int] = []
    asset_tag_ids: list[int] = []
    if qs["connector_tags"]:
        connector_tag_ids = client.resolve_tag_names(qs["connector_tags"])
    if qs["asset_tags"]:
        asset_tag_ids = client.resolve_tag_names(qs["asset_tags"])

    # Drift detection — scoped strictly to connectors this script previously created
    if qs["disable_orphans"]:
        managed_ids = _load_managed_connector_ids(output_dir)
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
                orphan_csv = _save_orphan_csv(orphans, output_dir)
                dis  = sum(1 for o in orphans if o["result"] == "disabled")
                fail = len(orphans) - dis
                log.info("Orphans: %d disabled, %d failed  →  %s", dis, fail, orphan_csv)
                print("\n  Orphan connectors (subscription no longer active):")
                for o in orphans:
                    icon = "✓" if o["result"] == "disabled" else "✗"
                    print(f"    {icon} [{o['id']}] {o['name']} (sub={o['subscriptionId']}) — {o['result']}")

    results = client.create_connectors_bulk(
        subscriptions=subscriptions,
        directory_id=tenant_id,
        application_id=client_id,
        authentication_key=client_secret,
        is_gov_cloud=qs["is_gov_cloud"],
        app_type=qs["app_type_key"],
        activation_modules=qs["activation"],
        run_frequency=qs["run_frequency"],
        connector_tag_ids=connector_tag_ids,
        asset_tag_ids=asset_tag_ids,
        parallel=parallel,
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

    csv_path = _save_csv(results, tenant_id, qs["app_type_label"], dry_run=False,
                         output_dir=output_dir, states=states)
    log.info("State CSV saved: %s", csv_path)
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
    ids    = args.ids
    total  = len(ids)
    failed = 0

    log.info("Qualys platform: %s  (%s)", qs["platform_label"], qs["base_url"])
    print(f"\n  Deleting {total} connector(s) …\n")
    rows = []
    for cid in ids:
        ok, msg = _delete_one(client, cid)
        icon = "✓" if ok else "✗"
        print(f"  {icon}  [{cid}]  {msg}")
        rows.append({"connector_id": cid, "status": "deleted" if ok else "failed", "note": msg})
        if not ok:
            failed += 1

    filename = output_dir / f"connector_delete_{_ts()}.csv"
    with open(filename, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["timestamp", "connector_id", "status", "note"])
        writer.writeheader()
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            writer.writerow({"timestamp": now, **row})

    print(f"\n  Summary: {total - failed} deleted, {failed} failed")
    log.info("Delete log saved: %s", filename)
    return 1 if failed else 0


# ── restore-orphans ───────────────────────────────────────────────────────────

def cmd_restore_orphans(args: argparse.Namespace) -> int:
    """
    Re-enable connectors that were previously disabled by this script (tracked in
    connector_orphans_*.csv) if their Azure subscription is now active again.
    """
    cfg = load_config(args.config)
    qs  = _qualys_settings(cfg)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    disabled = _load_disabled_connectors(output_dir)
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
    rows = []
    failed = 0
    for cid, sub_id in to_restore.items():
        ok, msg = client.enable_connector(cid)
        icon = "✓" if ok else "✗"
        print(f"  {icon}  [{cid}]  sub={sub_id}  {msg}")
        rows.append({"connector_id": cid, "subscription_id": sub_id,
                     "result": "enabled" if ok else "failed", "note": msg})
        if not ok:
            failed += 1

    filename = output_dir / f"connector_restore_{_ts()}.csv"
    with open(filename, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["timestamp", "connector_id", "subscription_id", "result", "note"])
        writer.writeheader()
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            writer.writerow({"timestamp": now, **row})

    ok_count = len(to_restore) - failed
    print(f"\n  Summary: {ok_count} enabled, {failed} failed")
    log.info("Restore log saved: %s", filename)
    return 1 if failed else 0


# ── CLI wiring ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Azure → Qualys tenant connector  (all settings in config.json)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    p_create = sub.add_parser("create", help="Discover subscriptions and create connectors")
    p_create.add_argument("--dry-run", action="store_true",
                          help="Enumerate Azure subscriptions only; skip all Qualys API calls")
    p_create.add_argument("--parallel", type=int, default=1, metavar="N",
                          help="Number of concurrent connector creation threads (default: 1)")

    # list
    p_list = sub.add_parser("list", help="List all Azure connectors in Qualys")
    p_list.add_argument("--subscription", metavar="ID",
                        help="Filter by subscription ID (substring match)")

    # status
    p_status = sub.add_parser("status", help="Show live state for one or more connector IDs")
    p_status.add_argument("--ids", metavar="ID", nargs="+", required=True,
                          help="One or more Qualys connector IDs")

    # list-mgs
    sub.add_parser("list-mgs", help="Print MG hierarchy — use to pick azure.rootMg in config")

    # delete
    p_delete = sub.add_parser("delete", help="Delete one or more connectors by Qualys ID")
    p_delete.add_argument("--ids", metavar="ID", nargs="+", required=True,
                          help="One or more Qualys connector IDs to delete")

    # restore-orphans
    sub.add_parser("restore-orphans",
                   help="Re-enable previously disabled connectors whose subscriptions are now active")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = _setup_logging(output_dir)
    log.info("Log file: %s", log_path)

    dispatch = {
        "create":          cmd_create,
        "list":            cmd_list,
        "status":          cmd_status,
        "list-mgs":        cmd_list_mgs,
        "delete":          cmd_delete,
        "restore-orphans": cmd_restore_orphans,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
