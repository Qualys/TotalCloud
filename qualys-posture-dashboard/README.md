# Qualys Posture Dashboard

A small, self-hosted dashboard for looking at your Qualys CSPM posture. You run it on your own
machine, enter your Qualys credentials once, and it pulls the cloud-security posture for all of your
connected AWS, Azure and GCP accounts. It keeps a daily history for the last 30 days and shows it in
three views.

It runs entirely locally. The only outbound traffic is from your machine to your own Qualys gateway.
Everything is kept in a local SQLite file, and the Qualys password is encrypted on disk. Nothing is
sent anywhere else.

## The three views

- **Controls** — one row per CSPM control, with severity, service, the pass/fail split and
  percentage, failing and passing resource counts, and a 30-day trend sparkline. Click a control to
  see the resources that fail it.
- **Resources** — one row per cloud resource, with its overall pass/fail result, top severity,
  failing and passing control counts, and a New / Existing / Fixed / Reopened status. Expand a row to
  see its failing and passing controls with evidence.
- **Findings** — a flat remediation list with one row per control-and-resource pair, so you can work
  through every failing check individually. Each finding carries the same New / Existing / Fixed /
  Reopened status, so filtering to Fixed shows what has been remediated in the last 30 days.

The four statuses come from Qualys's own `evaluationDates` and work the same way as VMDR: New is
failing and seen for the first time in the last 30 days, Existing is failing and seen before, Fixed is
now passing with a fix date inside the last 30 days, and Reopened was fixed but is failing again. The
fix date is included in the CSV and Excel exports.

## Other things it does

- Shows Qualys's manual remediation steps as an optional column on any table, and includes them in the
  exports. They come from the control metadata, so there is nothing extra to set up.
- A header band with an overall posture score, a pass/fail ring, and the 30-day trend.
- A left filter rail (cloud, severity, result, status, account, service, policy, resource type,
  region) with live counts, a global search, and an "as of" date picker for looking back over the
  history.
- Sortable columns you can show or hide, CSV and Excel export, and pagination (50 / 100 / 200 per
  page).
- Two separate kinds of tags: the cloud provider's own tags (for example AWS `cloudTags`) and
  Qualys's asset tags. Each has its own column and its own export column, and both are searchable. They
  come from different APIs and mean different things, so a resource may have either, both or neither.
- Light and dark themes, and a settings panel to update credentials, switch Qualys platform, and set
  an automatic refresh (daily at a set time, or every N hours). The schedule runs inside the app, so
  there is no OS cron to configure.

## Requirements

- Python 3.9 or newer. It uses the standard library plus a few small packages listed in
  `backend/requirements.txt`.
- A Qualys account with CloudView / CSPM read access and at least one cloud connector configured.
- No Node.js is needed to run it. The web UI is pre-built and committed under `frontend/dist/`.

## Quick start

```bash
python3 run.py            # macOS / Linux / Windows  ->  http://localhost:8770
python3 run.py start      # run in the background (you can close the terminal)
python3 run.py stop       # stop the background server
python3 run.py status     # check whether it is running
```

`./run.sh` (macOS/Linux) and `run.bat` (Windows) just call `run.py`.

On first run the launcher creates a virtualenv, installs the backend dependencies, and starts the app
on http://localhost:8770 (it opens the browser for you in foreground mode).

Then, in the browser:

1. Pick your Qualys platform (for example US Platform 2) and enter your username and password.
2. Click Connect & pull posture. It checks the credentials and pulls the first snapshot.
3. Use Refresh whenever you want a fresh snapshot. The "as of" picker lets you look back over the
   30-day history.

To try the UI without a Qualys account, run it with sample data:

```bash
./run.sh --demo
```

See [USAGE.md](./USAGE.md) for a fuller walkthrough.

## Where your data lives

| Path | What it is |
|------|-----------|
| `backend/data/posture.db` | Local SQLite snapshot history. Delete it to reset. |
| `backend/data/secret.key` | Encryption key for the stored password (`0600`). |
| `backend/data/app.log` | Rotating application log, for troubleshooting. |

These are created on first run and are excluded from version control by `.gitignore`. To reset
completely, stop the app and delete the `backend/data/` folder.

## Upgrading

Your history and stored credentials live in `backend/data/`, which is not part of the release, so
upgrading does not touch them:

```bash
python3 run.py stop                           # stop the old version
unzip -o qualys-posture-dashboard-share.zip   # extract over the existing folder
python3 run.py start                          # start again; the DB migrates on launch
```

Then click Refresh once in the browser. The app keeps the same `posture.db`, adds any new columns
automatically, and the refresh repopulates the lifecycle data. Your history and login carry over.

Note that `unzip -o` replaces files but does not delete ones that were removed in a release. For a
guaranteed-clean swap, unzip into a new folder and copy your old `backend/data/` across.

## Options

```bash
./run.sh --port 9000      # use a different port
./run.sh --demo           # sample data, no credentials needed
```

Optional environment variables: `QPD_PORT`, `QPD_HOST`, and `QPD_DATA_DIR` (where the SQLite DB and
key are written).

## How it works

The FastAPI backend authenticates to your Qualys gateway (`POST /auth` returns a JWT), lists your
cloud connectors, and pages through the CloudView CSPM evaluation endpoints to get the current posture
and the failing/passing resources per control. It writes one snapshot per day to SQLite (idempotent,
pruned to 30 days) and serves both the JSON API and the pre-built React UI on a single local port. It
reads the current evaluation state rather than a 7- or 30-day window; the 30-day history is built from
your own daily refreshes.

## Rebuilding the UI

The committed `frontend/dist/` is what lets the app run without Node. If you change the frontend
source and need to rebuild it:

```bash
cd frontend && npm ci && npm run build
```

## Author

Yash Jhunjhunwala (Lead SME, Cloud Security)
Project: Qualys Posture Dashboard
Last updated: November 2026
