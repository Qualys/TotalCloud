# Qualys Posture Dashboard

A **local, single-tenant CSPM posture dashboard** for your Qualys account. You enter your Qualys
credentials once; it pulls your cloud-security posture across **all** your connected cloud accounts
(AWS / Azure / GCP), keeps a rolling **30-day daily history**, and presents it in three views.

> **Your data never leaves your machine.** The only outbound calls are from your machine to *your*
> Qualys gateway. Everything is stored in a local SQLite file, and your Qualys password is
> **encrypted at rest**. Nothing is sent to any third party.

---

## What you get

- **Controls view** — every CSPM control: severity, service, pass-vs-fail bar and %, failing/passing
  resource counts, and a 30-day trend sparkline. Click any control to drill into the resources
  failing it.
- **Resources view** — one row per cloud resource, with its overall PASS/FAIL result, top severity,
  failing/passing control counts, **NEW / EXISTING / FIXED / REOPENED** lifecycle status (from Qualys's
  own `evaluationDates`), and an expandable list of its failing + passing controls with evidence.
- **Findings view** — a flat, ungrouped remediation "plan": **one row per (control × resource)**, so
  you can work down the list of every failing check individually. Each finding carries the same
  **NEW / EXISTING / FIXED / REOPENED** lifecycle status, so you can filter to **Fixed** to see what
  has been remediated in the last 30 days and measure progress for the period.

> **Finding lifecycle (same four states as VMDR).** Driven by Qualys's own `evaluationDates`:
> **New** — failing, detected for the first time in the last 30 days · **Existing** — failing, seen
> before · **Fixed** — remediated (now passing, with a fix date inside the last 30 days) · **Reopened**
> — was fixed, now failing again. Pick **Status → Fixed** in the Quick Filters rail (Findings or
> Resources) to list just the remediated items; the fix date rides along into the CSV/Excel exports.

Across all views:

- **Remediation guidance** — Qualys's manual remediation steps are an optional **Remediation column**
  on every table (tick it in *Columns*), so the fix is visible inline without expanding a row, and it
  travels into the CSV and Excel exports. Pulled from the control metadata, no extra setup.
- A **hero band** with an overall posture score, a pass/fail compliance ring, and the 30-day trend.
- A left **Quick Filters** rail (Cloud, Severity, Result, Status, Account, Service, Policy, Resource
  type, Region) with live counts, plus a global search and an "**As of**" time-travel date picker.
- **Sortable, pick-and-choose columns**, **CSV** and **Excel (.xlsx)** export, pagination
  (50 / 100 / 200 per page). The Excel export adds a **Manual remediation** column — Qualys's manual
  remediation steps for each control (for Resources, every failing control's steps in that one cell).
- **Two kinds of tags, kept separate** — **Cloud tags** (the provider's own, e.g. AWS `cloudTags`,
  shown as `key=value`) and **Qualys tags** (Qualys's own asset tags, from the resource-inventory
  API). Each is its own optional column in the tables, its own column in both exports, and both are
  shown in the drill-downs and matched by the global search. They come from different endpoints and
  mean different things, so a resource may carry either, both, or neither — empty cells are normal.
- **Light (Qualys) / dark** theme toggle, and a **Settings** gear to update your credentials, switch
  Qualys platform, and set an **automatic refresh schedule** (daily at a time, or every N hours —
  runs in-app, no OS cron needed).

---

## Requirements

- **Python 3.9+** (only the standard library plus a few small packages — see `backend/requirements.txt`).
- A **Qualys account** with **CloudView / CSPM read access** (Reader-equivalent API permissions) and
  at least one cloud connector configured.
- No Node.js needed to *run* it — the web UI is pre-built and committed under `frontend/dist/`.

---

## Quick start

```bash
# from the project folder — cross-platform Python launcher:
python3 run.py                 # macOS / Linux / Windows  →  http://localhost:8770
python3 run.py start           # run in the BACKGROUND (terminal can close)
python3 run.py stop            # stop the background server
python3 run.py status          # is it running?
```

`./run.sh` (macOS/Linux) and `run.bat` (Windows) are thin shortcuts that just call `run.py`.

The launcher creates a Python virtualenv, installs the backend dependencies, and starts the app on
**http://localhost:8770** (it opens your browser automatically in foreground mode).

Then in the browser:

1. Pick your **Qualys platform** (e.g. *US Platform 2*), enter your **username** and **password**.
2. Click **Connect & pull posture**. It validates the credentials, then pulls your first snapshot.
3. Use **Refresh** any time to pull a fresh snapshot; the "As of" picker lets you look back over the
   30-day history.

**Just want to see the UI first?** Run it in demo mode with synthetic sample data (no Qualys account
needed):

```bash
./run.sh --demo
```

See **[USAGE.md](./USAGE.md)** for a full walkthrough.

---

## Where your data lives

| Path | What it is |
|------|-----------|
| `backend/data/posture.db` | Your local SQLite snapshot history (git-ignored; delete to reset). |
| `backend/data/secret.key` | The encryption key for your stored password (git-ignored; `0600`). |
| `backend/data/app.log` | Rotating application log (for troubleshooting; git-ignored). |

Both are created on first run and are excluded from version control by `.gitignore`. To fully reset,
stop the app and delete the `backend/data/` folder.

---

## Upgrading from an earlier version

Your snapshot history and stored credentials live entirely in `backend/data/` — which is **not**
shipped in the release — so upgrading never touches them. To move to a newer build:

```bash
python3 run.py stop                        # 1. stop the old version
unzip -o qualys-posture-dashboard-share.zip  # 2. extract OVER the existing folder
                                           #    (no backend/data/ in the zip → your DB + key are untouched)
python3 run.py start                        # 3. start — the DB auto-migrates on launch
```

Then in the browser, click **Refresh** once. The app keeps the same `posture.db`, adds any new
columns automatically (including the ones behind the **Fixed** status), and the Refresh repopulates
the lifecycle data so **Status → Fixed** reflects the current 30-day window. Nothing is reset — your
history and login carry over.

> `unzip -o` adds and replaces files but does not delete ones removed in a release. For a
> guaranteed-clean swap, unzip into a fresh folder and copy your old `backend/data/` across.

---

## Options

```bash
./run.sh --port 9000      # run on a different port
./run.sh --demo           # seed synthetic sample data (no credentials required)
```

Environment variables (optional): `QPD_PORT`, `QPD_HOST`, `QPD_DATA_DIR` (where the SQLite DB + key
are written).

---

## How it works (in one paragraph)

The backend (FastAPI) authenticates to your Qualys **gateway** (`POST /auth` → JWT), enumerates your
cloud connectors, and walks the paged **CloudView CSPM evaluations** endpoints to fetch the current
posture and the failing/passing resources per control. It writes a **daily snapshot** to SQLite
(idempotent per day, pruned to 30 days) and serves both the JSON API and the pre-built React UI on a
single local port. It reads the **current** evaluation state — not a 7/30-day window; the 30-day
history is built from your own daily refreshes.

---

## Rebuilding the UI (only if you change the frontend)

The committed `frontend/dist/` means the app runs with **zero Node install**. If you edit the
frontend source and want to rebuild:

```bash
cd frontend && npm ci && npm run build
```

---

## Author

**Author:** *Yash Jhunjhunwala (Lead SME, Cloud Security)*
**Project:** Qualys Posture Dashboard
**Last Updated:** 2026-11
