# Azure → Qualys Tenant Connector

A Python CLI that discovers every active subscription in an Azure tenant and automatically creates a Qualys cloud connector for each one. Supports **Azure Government** and **Azure Commercial** clouds, all 14 Qualys platforms, and full lifecycle management (create, list, status, disable orphans, restore, delete).

---

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Configuration](#configuration)
  - [Azure Section](#azure-section)
  - [Qualys Section](#qualys-section)
  - [Qualys Platforms](#qualys-platforms)
- [CLI Reference](#cli-reference)
  - [Global Flags](#global-flags)
  - [create](#create)
  - [list](#list)
  - [status](#status)
  - [list-mgs](#list-mgs)
  - [delete](#delete)
  - [restore-orphans](#restore-orphans)
- [Orphan Detection](#orphan-detection)
- [Output Files](#output-files)
- [Security Notes](#security-notes)

---

## How It Works

```
Azure Tenant
    └── Management Groups (tree)
            └── Subscriptions  ──►  Qualys Azure Connector (1 per subscription)
```

1. Authenticates to Azure using a Service Principal
2. Walks the Management Group hierarchy under `rootMg` (or the entire tenant if not set)
3. Collects all active subscriptions
4. For each subscription, calls the Qualys Connectors API to create an `AzureAssetDataConnector`
5. Skips subscriptions that already have a connector (idempotent)
6. Optionally resolves/creates Qualys tags and applies them to connectors and discovered assets
7. Fetches live connector state after creation and saves everything to CSV

---

## Prerequisites

| Requirement | Detail |
|---|---|
| Python | 3.10 or later |
| Azure Service Principal | See permissions below |
| Qualys account | Connectors module enabled on your platform |

### Azure SP permissions

The Service Principal needs read access to Management Groups and their subscriptions.

**Recommended — custom role at tenant root MG scope:**

```json
{
  "roleName": "QualysOrgConnector",
  "actions": [
    "Microsoft.Management/managementGroups/read",
    "Microsoft.Management/managementGroups/subscriptions/read"
  ]
}
```

Assign this role at `/providers/Microsoft.Management/managementGroups/<tenant-root-id>`.

**Fallback — subscription-level Reader:**

If the SP only has `Reader` on individual subscriptions, the script falls back to the Azure Subscriptions API automatically. Management group info will not be shown, but connector creation works normally.

---

## Setup

```bash
git clone <repo-url>
cd azure-gov-tenant-connector

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your config
cp config.example.json config.json
# Edit config.json with your credentials and settings
```

---

## Configuration

All runtime settings live in `config.json`. The only CLI arguments are `--config`, `--output-dir`, and subcommand-specific flags (see [CLI Reference](#cli-reference)).

> **Security:** `config.json` contains credentials. Never commit it to version control. It is included in `.gitignore` by default, and the script will warn you at startup if it detects the file is not gitignored.

### Minimal config (required fields only)

```json
{
  "azure": {
    "tenantId":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "clientId":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "clientSecret": "your-sp-client-secret"
  },
  "qualys": {
    "username": "your-qualys-username",
    "password": "your-qualys-password",
    "platform": "US2"
  }
}
```

### Full config with all options

```json
{
  "azure": {
    "tenantId":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "clientId":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "clientSecret": "your-sp-client-secret",
    "rootMg":       "MyRootMG"
  },
  "qualys": {
    "username":       "your-qualys-username",
    "password":       "your-qualys-password",
    "platform":       "US2",
    "appType":        "cspm",
    "activation":     ["VM", "PC"],
    "runFrequency":   1440,
    "isGovCloud":     false,
    "disableOrphans": false,
    "connectorTags":  ["azure-commercial", "production"],
    "assetTags":      ["azure-asset", "cloud-discovery"]
  }
}
```

### Azure Section

| Field | Required | Default | Description |
|---|---|---|---|
| `tenantId` | **Yes** | — | Azure tenant (directory) ID |
| `clientId` | **Yes** | — | Service Principal application (client) ID |
| `clientSecret` | **Yes** | — | Service Principal secret value |
| `rootMg` | No | `null` | Management Group name to scope discovery. `null` = entire tenant. Run `list-mgs` to find available names. |

### Qualys Section

| Field | Required | Default | Description |
|---|---|---|---|
| `username` | **Yes** | — | Qualys login username |
| `password` | **Yes** | — | Qualys login password |
| `platform` | **Yes** | — | Qualys platform key (e.g. `"US2"`) or a full base URL. See [Qualys Platforms](#qualys-platforms). |
| `appType` | No | `"cspm"` | Connector type. `"cspm"` enables Cloud Security Assessment; `"asset-inventory"` enables asset discovery only. |
| `activation` | No | `[]` (none) | List of Qualys modules to activate. Valid values: `VM` (Vulnerability Management), `PC` (Policy Compliance), `SCA` (Security Configuration Assessment), `CERTVIEW`. **Note:** `PC` and `SCA` are mutually exclusive — choose one. |
| `runFrequency` | No | `1440` | How often Qualys syncs the connector, in minutes. Default is 1440 (24 hours). |
| `isGovCloud` | No | `true` | `true` = Azure Government (`login.microsoftonline.us`). `false` = Azure Commercial (`login.microsoftonline.com`). |
| `disableOrphans` | No | `false` | When `true`, connectors for subscriptions no longer in scope are automatically disabled on each `create` run. See [Orphan Detection](#orphan-detection). |
| `connectorTags` | No | `[]` | Tag names to apply to the **connector object** in Qualys. Tags are created automatically if they don't exist. |
| `assetTags` | No | `[]` | Tag names to apply to **assets discovered** by the connector. |

### Qualys Platforms

| Key | Region | API Base URL |
|---|---|---|
| `US1` | United States 1 | `qualysapi.qualys.com` |
| `US2` | United States 2 | `qualysapi.qg2.apps.qualys.com` |
| `US3` | United States 3 | `qualysapi.qg3.apps.qualys.com` |
| `US4` | United States 4 | `qualysapi.qg4.apps.qualys.com` |
| `GOV1` | US Government | `qualysapi.gov1.qualys.us` |
| `EU1` | Europe 1 | `qualysapi.qualys.eu` |
| `EU2` | Europe 2 | `qualysapi.qg2.apps.qualys.eu` |
| `EU3` | Europe 3 | `qualysapi.qg3.apps.qualys.it` |
| `IN1` | India | `qualysapi.qg1.apps.qualys.in` |
| `CA1` | Canada | `qualysapi.qg1.apps.qualys.ca` |
| `AE1` | UAE | `qualysapi.qg1.apps.qualys.ae` |
| `UK1` | United Kingdom | `qualysapi.qg1.apps.qualys.co.uk` |
| `AU1` | Australia | `qualysapi.qg1.apps.qualys.com.au` |
| `KSA1` | Saudi Arabia | `qualysapi.qg1.apps.qualysksa.com` |

**Custom platform:** Set `platform` to a full URL to use a private or non-standard endpoint:

```json
"platform": "https://qualysapi.internal.example.com"
```

Not sure which platform you're on? Log in to the Qualys UI and check the URL in your browser, or visit [qualys.com/platform-identification](https://www.qualys.com/platform-identification/).

---

## CLI Reference

```
python main.py [--config FILE] [--output-dir DIR] <command> [options]
```

### Global Flags

| Flag | Default | Description |
|---|---|---|
| `--config FILE` | `config.json` | Path to your config file |
| `--output-dir DIR` | `.` (current directory) | Directory where all CSVs and logs are written. Created automatically if it doesn't exist. Useful for organising runs by date or environment. |

---

### `create`

Discovers Azure subscriptions and creates a Qualys connector for each one.

```bash
python main.py create [--dry-run] [--parallel N]
```

| Flag | Default | Description |
|---|---|---|
| `--dry-run` | off | Enumerate Azure subscriptions only. No Qualys API calls are made. Useful for previewing scope before a live run. |
| `--parallel N` | `1` | Number of concurrent connector creation threads. Default is 1 (sequential). Submissions are always paced 2 seconds apart regardless of parallelism to avoid Qualys rate limits. |

**Behaviour:**
- Skips subscriptions that already have a connector (idempotent — safe to re-run)
- If `disableOrphans: true`, runs orphan detection **before** creating new connectors
- Fetches live connector state after creation and saves to CSV

**Examples:**

```bash
# Preview what would be created
python main.py create --dry-run

# Live run, sequential
python main.py create

# Live run, 3 concurrent threads
python main.py create --parallel 3

# Separate output per environment
python main.py --config config-prod.json --output-dir runs/prod create
python main.py --config config-dev.json  --output-dir runs/dev  create
```

**Sample output:**

```
  #    Subscription ID                        Connector Name                             MG
  ─────────────────────────────────────────────────────────────────────────────────────────
  1    aaa-bbb-ccc-ddd-...                    My Production Sub                          prod-mg
  2    eee-fff-ggg-hhh-...                    Dev Environment                            dev-mg

=================================================================
  Summary — 2026-05-18 16:30 UTC
=================================================================
  Total          : 2
  Created        : 2
  Already existed: 0
  Failed         : 0

  Created:
    ✓ [657901] My Production Sub (aaa-bbb-ccc-ddd-...)
    ✓ [657902] Dev Environment (eee-fff-ggg-hhh-...)
=================================================================
```

---

### `list`

Lists all Azure connectors currently in Qualys with their live state.

```bash
python main.py list [--subscription ID]
```

| Flag | Default | Description |
|---|---|---|
| `--subscription ID` | (all) | Filter results to connectors whose subscription ID contains this string (substring match) |

**Example:**

```bash
# List all
python main.py list

# Filter to a specific subscription
python main.py list --subscription aaa-bbb-ccc
```

**Sample output:**

```
  ID         Name                          Subscription ID                        State             Disabled
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────
  657901     My Production Sub             aaa-bbb-ccc-ddd-...                    FINISHED_SUCCESS  false
  657902     Dev Environment               eee-fff-ggg-hhh-...                    QUEUED            false

  Total: 2 connector(s)
```

**Connector states:**

| State | Meaning |
|---|---|
| `QUEUED` | Connector created, waiting for first sync |
| `PROCESSING` | Sync in progress |
| `FINISHED_SUCCESS` | Last sync completed successfully |
| `FINISHED_ERRORS` | Last sync completed with errors |

---

### `status`

Shows detailed live state for one or more specific connectors.

```bash
python main.py status --ids <ID> [<ID> ...]
```

**Example:**

```bash
python main.py status --ids 657901 657902
```

**Sample output:**

```
  Connector 657901:
    State          : FINISHED_SUCCESS
    Last Synced    : 2026-05-18T16:45:00Z
    Assets Created : 42
    Assets Updated : 0
    Assets Deleted : 0
    Error          : (none)
    Disabled       : false
    Run Frequency  : 1440 min
```

---

### `list-mgs`

Prints the Management Group hierarchy for your tenant as a tree. Use this to find the right value for `azure.rootMg` in your config.

```bash
python main.py list-mgs
```

**Sample output:**

```
  Management Group hierarchy — tenant abc123:

  └── Tenant Root Group  [abc123]
      ├── Production  [prod-mg]
      │   ├── sub-prod-1
      │   └── sub-prod-2
      └── QA  [qa-mg]
          └── sub-qa-1

  Tip: set azure.rootMg in config.json to the name in brackets to scope connector creation.
```

The name in `[brackets]` is what you put in `azure.rootMg`.

---

### `delete`

Permanently deletes one or more Qualys connectors by ID. This cannot be undone.

```bash
python main.py delete --ids <ID> [<ID> ...]
```

**Example:**

```bash
python main.py delete --ids 657901 657902
```

**Sample output:**

```
  Deleting 2 connector(s) …

  ✓  [657901]  deleted
  ✓  [657902]  deleted

  Summary: 2 deleted, 0 failed
```

---

### `restore-orphans`

Re-enables connectors that were previously disabled by this script (via `disableOrphans`) if their Azure subscription is now active again in the current scope.

```bash
python main.py restore-orphans
```

This reads `connector_orphans_*.csv` history, discovers the current active Azure subscriptions, and re-enables any connector whose subscription is now back in scope. See [Orphan Detection](#orphan-detection) for the full explanation.

---

## Orphan Detection

### What is an orphan?

An orphan is a Qualys connector whose Azure subscription is **no longer in scope** — because the subscription was deleted, moved out of the managed Management Group, or you narrowed `azure.rootMg` in your config.

Without cleanup, orphaned connectors keep running sync jobs in Qualys against subscriptions that are no longer managed, consuming resources and polluting your asset inventory.

### How it works

Enable with `"disableOrphans": true` in config. On every `create` run, **before** creating new connectors, the script:

1. Reads all `connector_state_*.csv` files to identify the set of connectors **this script created** (by connector ID)
2. Fetches the current list of connectors from Qualys
3. Filters to only script-managed connectors (all others are untouched)
4. Disables any script-managed connector whose subscription is not in the current Azure scope

```
Script-managed connector IDs (from CSV history)
    ∩  connectors whose subscription is not in current Azure scope
    ∩  connectors that are not already disabled
    →  these are disabled
```

### What it does NOT touch

- Connectors created outside this script (e.g. manually, by another tool)
- Connectors that are already disabled
- Connectors in Qualys for other cloud types (AWS, GCP)

### Safety guard

If no `connector_state_*.csv` history exists (first run on a new machine, or files were deleted), orphan detection **skips entirely** with a warning:

```
WARNING: Orphan detection requested but no CSV history found.
Skipping to avoid touching connectors created outside this script.
Run 'create' at least once so the script has a baseline.
```

This prevents the script from accidentally disabling connectors it didn't create.

### Restoring orphans

If a subscription comes back (or you expand `rootMg`), restore its connector:

```bash
python main.py restore-orphans
```

The script cross-references the `connector_orphans_*.csv` disable history against the current active Azure subscriptions and re-enables matching connectors. A `connector_restore_*.csv` is written with the results.

### Example walkthrough

```
Step 1: rootMg = null (entire tenant, 5 subscriptions)
        → create runs: connectors A B C D E created

Step 2: rootMg = "QA"  (2 subscriptions: D, E)
        disableOrphans = true
        → create runs:
            orphan check: A, B, C are no longer in scope → DISABLED
            D, E already exist → skipped
        → connector_orphans_<ts>.csv written

Step 3: rootMg = null (5 subscriptions again)
        → restore-orphans:
            reads orphan CSV: A, B, C were disabled
            checks Azure: A, B, C subscriptions are active again
            → A, B, C RE-ENABLED
        → connector_restore_<ts>.csv written
```

---

## Output Files

All files are written to `--output-dir` (default: current directory). Logs go in `<output-dir>/logs/`.

| File | Created by | Contents |
|---|---|---|
| `connector_state_<ts>.csv` | `create` | Full record of every subscription processed: connector ID, status, and live state snapshot (connectorState, lastSyncedOn, asset counts) |
| `connector_orphans_<ts>.csv` | `create` (with disableOrphans) | Record of connectors disabled by orphan detection |
| `connector_restore_<ts>.csv` | `restore-orphans` | Record of connectors re-enabled |
| `connector_delete_<ts>.csv` | `delete` | Audit log of manual deletions |
| `logs/run_<ts>.log` | all commands | Full timestamped log of every API call and decision |

### `connector_state_*.csv` columns

| Column | Description |
|---|---|
| `timestamp` | UTC time of the run |
| `tenant_id` | Azure tenant ID |
| `app_type` | `cspm` or `asset-inventory` |
| `dry_run` | `true` or `false` |
| `subscription_id` | Azure subscription ID |
| `subscription_name` | Subscription display name |
| `management_group` | Parent MG name |
| `connector_name` | Name given to the Qualys connector |
| `connector_id` | Qualys connector ID |
| `status` | `created`, `skipped`, `failed`, or `dry_run` |
| `note` | Error message (if failed) or `already_exists` (if skipped) |
| `connector_state` | Live state from Qualys (e.g. `FINISHED_SUCCESS`) |
| `last_synced_on` | Timestamp of last successful sync |
| `total_assets_created` | Assets added in last sync |
| `total_assets_updated` | Assets updated in last sync |
| `total_assets_deleted` | Assets removed in last sync |
| `connector_error` | Error detail from Qualys (if any) |
| `disabled` | Whether the connector is disabled in Qualys |
| `run_frequency` | Configured sync interval (minutes) |

---

## Security Notes

| Topic | Guidance |
|---|---|
| `config.json` | Contains Azure SP secret and Qualys credentials. Never commit to version control. The script warns at startup if the file is not gitignored. |
| SP Secret rotation | The SP secret is stored as `authenticationKey` inside each Qualys connector's `authRecord`. If you rotate the secret, update `config.json` **and** update existing connectors in Qualys (or delete and re-create them). |
| Qualys credentials | Transmitted over HTTPS (Basic Auth). Use a Qualys service account with the minimum role needed to manage connectors. |
| Least privilege | The Azure SP only needs read access to Management Groups and Subscriptions — no write access to Azure resources. |
| Output files | `connector_state_*.csv` files contain subscription IDs and connector IDs but no secrets. They are safe to retain for audit purposes. |

---

## Project Structure

```
azure-gov-tenant-connector/
├── main.py              # CLI entry point — all commands, config loading, CSV output
├── azure_client.py      # Azure MG/subscription discovery (Gov + Commercial)
├── qualys_client.py     # Qualys Connectors API client (create, search, update, delete)
├── config.json          # Your credentials and settings (gitignored)
├── config.example.json  # Full schema reference with all fields and defaults
├── requirements.txt     # Python dependencies
├── .gitignore           # Excludes config.json, CSVs, logs, .venv
├── logs/                # Per-run log files
├── connector_state_*.csv
├── connector_orphans_*.csv
├── connector_restore_*.csv
└── connector_delete_*.csv
```

---

## Frequently Asked Questions

**What happens if I run `create` twice?**

Nothing bad. The script checks whether a connector already exists for each subscription before creating one. Duplicates are skipped and reported as `Already existed` in the summary. It is safe to run on a schedule.

**Can I use a different config file per environment?**

Yes. Use `--config`:

```bash
python main.py --config config-gov-prod.json create
python main.py --config config-commercial-dev.json create
```

**Can I scope to a specific MG without changing the config?**

No — the scope is controlled by `azure.rootMg` in the config file. Use separate config files for different scopes.

**What if a subscription has no display name?**

The connector name falls back to `azure-sub-<subscription-id>`.

**What is the connector name length limit?**

Qualys enforces a 255-character limit. The script automatically truncates names that exceed this.

**My run was interrupted mid-way. What do I do?**

Re-run `create`. Connectors already created will be skipped (idempotent). The run will pick up where it left off effectively.

**I deleted `connector_state_*.csv` files. Will orphan detection break?**

It will skip orphan detection and print a warning (the safety guard). Run `create` once normally to rebuild the history, then orphan detection will work on the next run.
