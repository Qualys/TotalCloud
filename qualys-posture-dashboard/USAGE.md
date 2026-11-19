# Usage Guide — Qualys Posture Dashboard

A step-by-step guide to running and using the dashboard. For an overview, see
**[README.md](./README.md)**.

---

## 1. Run it

The launcher is **`run.py`** — one cross-platform Python script (macOS / Linux / Windows):

```bash
python3 run.py                 # foreground on http://localhost:8770 (Ctrl+C to stop)
python3 run.py --port 9000     # different port
```

`./run.sh` (macOS/Linux) and `run.bat` (Windows) are thin shortcuts that just call `run.py`, so
`./run.sh` works exactly the same.

It creates a Python virtual environment, installs the backend dependencies, and starts the app
(your browser opens automatically in foreground mode).

> No Node.js is required — the web UI ships pre-built. Python 3.9+ is the only prerequisite.

---

## 2. Connect your Qualys account

On first launch you'll see the **Setup** screen:

1. **Qualys platform** — pick your platform from the dropdown (e.g. *US Platform 2 (US2)*). If your
   pod isn't listed, choose **Custom gateway URL…** and paste your gateway
   (`https://gateway.<pod>.apps.qualys.com`).
2. **Username** / **Password** — your Qualys login. It needs **CloudView / CSPM read** permissions.
3. Click **Connect & pull posture**.

The app validates the credentials by minting a gateway token, stores them **encrypted** on your
machine, and starts pulling your first snapshot. A thin progress bar at the top shows the sync
running; controls appear within seconds and resources fill in behind them.

To change credentials or switch platform later, click the **⚙ Settings** gear (top-right), re-enter
your password, and **Save & refresh**.

---

## 3. The three views

Switch between them with the tabs next to the title.

### Controls
Every CSPM control, one row each. Columns include **CID**, control name, **Cloud**, **Severity**,
**Service**, a **Pass / Fail** bar, **Failed** count, and **% Fail**, plus a 30-day trend.
- **Click a control (its CID)** to expand and see the individual resources failing it, with evidence.
- Default sort is by CID; click any column header to re-sort.

### Resources
One row per cloud resource (the pivot). Shows **Account ID + alias**, **Type**, **Region**,
**Result** (PASS/FAIL), **Status** (New / Existing / Fixed / Reopened), **Top severity**, and
**Failing** count.
- **Click a resource** to expand its full list of failing **and** passing controls, each with
  evidence and lifecycle flags.
- The KPI cards show distinct **failing** vs **passing** resources plus New / Reopened / recently
  Fixed counts (from Qualys `evaluationDates`).

### Findings (the remediation "plan")
A **flat, ungrouped** list — **one row per (control × resource)**. CID-1 appears once for every
resource that fails it, then CID-2's failing resources, and so on. This is the working list you go
down to remediate.
- **Click a row** to load that finding's full evidence.
- Defaults to failing findings; use the **Result** filter to include passing ones.

#### Finding lifecycle status — New / Existing / Fixed / Reopened
Every finding (and resource) carries a lifecycle **Status**, the same four states you know from VMDR,
derived from Qualys's own `evaluationDates`:

| Status | Meaning | Underlying signal |
|--------|---------|-------------------|
| **New** | Failing, detected for the first time in the last 30 days | recent `firstEvaluated` |
| **Existing** | Failing, seen before | — |
| **Fixed** | **Remediated** — now passing, fixed in the last 30 days | `dateFixed`, result = PASS |
| **Reopened** | Was fixed, now failing again | `dateReopen`, result = FAIL |

- To **measure what was remediated in the period**, open the **Status** group in the Quick Filters
  rail and pick **Fixed** — the list switches to just the remediated items (this works on both the
  **Findings** and **Resources** tabs). The rail shows the live count for each state.
- Tick the **Fixed date** column (in **Columns**) to see *when* each finding was remediated. The
  **Status** and **Fixed date** both travel into the **CSV** and **Excel** exports, so you can track
  progress week over week.
- Why the Findings "Fixed" count can be larger than the Resources "Fixed" count: Findings counts every
  remediated *check* (control × resource), while Resources counts a whole resource as Fixed only once
  **all** of its controls are passing.

### Remediation guidance (on every screen)
Expanding a control (Controls tab), a finding (Findings tab), or a control inside a resource's drawer
(Resources tab → **▸ Remediation**) shows the **🛠 Remediation** panel for that control:
- **Why it matters** (rationale), **Manual remediation** (console steps), **CLI remediation** (with a
  **Copy** button), and **Build-time (IaC) remediation** (Terraform/CLI snippet, Copy button).
- Sourced from Qualys's control metadata — no extra configuration; it's captured on each refresh.

---

## 4. Filtering & searching

- **Quick Filters rail** (left): click any value under **Cloud, Severity, Result, Status, Account,
  Service, Policy, Resource type, Region** to filter. Counts next to each value update as you filter;
  a group with an active filter shows a dot. Click **Clear all** at the top of the rail (or the chips
  under the hero) to reset.
- **Search box** (top): free-text match on control name/CID (Controls) or resource ID
  (Resources/Findings).
- **As of** (top): time-travel to any earlier day in your 30-day history. The hero, cards, and tables
  all reflect the chosen snapshot.
- Every widget — posture score, compliance ring, KPI cards, tables, and rail counts — reacts to the
  active filters together.

---

## 5. Columns, sorting, export, pagination

- **Columns** button (above each table): tick/untick columns to show; your choice is remembered.
  Extra time columns (First/Last evaluated, Date fixed, Date reopened) are available here.
- **Sort**: click any column header (click again to reverse).
- **Export CSV**: downloads the current, filtered, sorted table.
- **Export Excel**: downloads the current, filtered table as `.xlsx` (rendered by the local backend),
  with one extra column the CSV doesn't have — **Manual remediation**, the plain-text manual
  remediation steps for the control. On the Resources tab that cell holds the steps for *every*
  control the resource fails (`[CID] control — steps`, most severe first). Note it follows the
  active filters, but not the on-screen sort order or column picks.
- **Cloud tags** and **Qualys tags** columns (Findings + Resources) — two *different* things, never
  merged into one column:
  - **Cloud tags** are the provider's own resource tags (`key=value`), read from `cloudTags` on the
    CSPM evaluation response.
  - **Qualys tags** are Qualys's own asset tags (tag names), read from the resource-inventory API and
    joined onto each resource during the refresh.

  Both are off by default — tick them in **Columns**. They render as chips (first two, then `+N`;
  hover for the full set), Qualys tags tinted so the two are never confused. The CSV and Excel
  exports always include **both** regardless of the picker, the Controls drill-down shows both, and
  the Resource drawer lists them on separate rows. The global **search** box matches either kind, so
  typing `Owner`, a cost-centre value, or a Qualys tag name filters straight to those resources.

  *Why cloud tags are sparse (measured on live data — ~47% of AWS rows carry them):* Qualys reports
  cloud tags from two places and neither is complete.
  1. The CSPM **evaluation** response omits the `cloudTags` field entirely for some resource types
     (CloudWatch log groups, and CloudFront until we backfill it) — Qualys doesn't collect them there.
  2. The **resource-inventory** API covers some of those gaps (CloudFront went 0% → 97%, IAM users
     0% → 41% this way) but returns nothing for others (S3 buckets, SNS topics).
  3. For every remaining resource the field is present and simply empty — those resources are
     genuinely untagged in the cloud account.

  The refresh reads both sources and merges them, evaluation tags winning where both exist. GCP
  returns no tags on either API, so that column stays empty for GCP. An empty cell is normal.
- **Remediation** column (all three tables): Qualys's manual remediation steps for the control,
  shown inline (two lines, hover for the full text) instead of behind a click. It's a *pickable*
  column — tick **Remediation** in **Columns** when you want it. On the Resources tab the cell shows
  the most-severe failing control's fix plus `(+N more failing controls)`; the **Excel** export
  carries every failing control's steps in full.
- **Rows** selector in the pager: 50 / 100 / 200 per page (top and bottom pagers).

---

## 6. Refreshing & history

- **Refresh** (top-right) pulls a fresh snapshot from Qualys. It runs in the background — you can keep
  working while it streams data in.
- Each refresh stores **one snapshot per day** (re-refreshing the same day overwrites it). Snapshots
  older than 30 days are pruned automatically.
- The **30-day trend** and the **As of** picker are built from these daily snapshots, so the trend
  fills in as you refresh over multiple days.

> Note: the dashboard reads the **current** posture state from Qualys, so its totals reflect *now* —
> not the Qualys web console's "Last 7/30 Days" windowed counters, which aggregate differently.

### Moving to a newer version (keeping your data)

Your snapshot history and saved credentials live in `backend/data/`, which is **not** part of the
release — so upgrading leaves them in place:

1. `python3 run.py stop`
2. `unzip -o qualys-posture-dashboard-share.zip` — extract over your existing folder. Because the zip
   has no `backend/data/`, your `posture.db` and encryption key are untouched.
3. `python3 run.py start` — the database migrates itself on launch, adding any new columns (including
   the ones behind the **Fixed** status) to your existing data.
4. Click **Refresh** once. This repopulates the lifecycle data so **Status → Fixed** reflects the
   current 30-day window on both the Findings and Resources tabs.

Nothing is reset: same database, same login, plus the new **Fixed** status. (`unzip -o` replaces
files but won't delete ones dropped in a release; for a spotless swap, unzip into a new folder and
copy your old `backend/data/` across.)

---

## 7. Themes

Use the **☀ / ☾** toggle (top-right) to switch between the **light Qualys** theme (default) and a
**dark** theme. Your choice is remembered.

---

## 8. Run it as an always-on app (no terminal needed)

By default the launcher runs in the **foreground** — the server stops when you close the terminal or
press Ctrl+C. To run it in the **background** so you can close the terminal:

```bash
python3 run.py start     # start in the background → http://localhost:8770
python3 run.py status    # is it running?
python3 run.py stop      # stop it
```

Background mode detaches the process (it survives closing the terminal), writes logs to `qpd.log`,
and stores its PID in `.qpd.pid`. Works the same on Windows (`python run.py start`).

### Start automatically at login / boot

For login/boot auto-start, let the OS service manager keep it alive and run the launcher in the
**foreground** (`--no-browser`) — the manager handles restarts.

**macOS (launchd — recommended).** Create `~/Library/LaunchAgents/com.qualys.posture.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.qualys.posture</string>
  <key>WorkingDirectory</key><string>/FULL/PATH/TO/qualys-posture-dashboard</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>run.py</string>
    <string>--no-browser</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/FULL/PATH/TO/qualys-posture-dashboard/qpd.log</string>
  <key>StandardErrorPath</key><string>/FULL/PATH/TO/qualys-posture-dashboard/qpd.log</string>
</dict></plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.qualys.posture.plist` (it starts now and at every
login; `launchctl unload …` to stop). Replace `/FULL/PATH/TO/…` with the real path.

**Linux (systemd user service).** Create `~/.config/systemd/user/qualys-posture.service`:

```ini
[Unit]
Description=Qualys Posture Dashboard
[Service]
WorkingDirectory=/FULL/PATH/TO/qualys-posture-dashboard
ExecStart=/usr/bin/python3 run.py --no-browser
Restart=on-failure
[Install]
WantedBy=default.target
```

Then: `systemctl --user daemon-reload && systemctl --user enable --now qualys-posture`
(`loginctl enable-linger $USER` if you want it up without being logged in).

**Windows (Task Scheduler).** Create a Basic Task → Trigger *At log on* → Action *Start a program* →
Program `python`, Arguments `run.py --no-browser`, "Start in" = the project folder. Tick "Run whether
user is logged on or not" for a service-like start.

### Keep the data fresh automatically (scheduled refresh)

**Easiest — in the app (no OS cron needed):** click the **⚙ Settings** gear → **Automatic refresh** →
tick *Refresh automatically on a schedule*, choose **Every day at HH:MM** or **Every N hours**, and
**Save schedule**. A background thread inside the app runs the refresh at that time (it catches up if
the machine was off at the scheduled moment). This works whenever the app is running — including when
started with `python run.py start` or as a login service (§ above).

**Alternative — OS-level cron/Task Scheduler** (e.g. if you don't keep the app running, or prefer the
OS to drive it). The server must be up; hit the sync endpoint:

```bash
# crontab -e  → refresh every day at 6am
0 6 * * *  curl -s -X POST http://localhost:8770/api/sync >/dev/null
```

Windows: Task Scheduler → daily → `curl.exe -s -X POST http://localhost:8770/api/sync`.

> One snapshot is stored per day (re-running the same day overwrites it), pruned to 30 days — so a
> daily schedule gives you a clean 30-day history with no duplicates.

### Logs

The app writes a rotating log to **`backend/data/app.log`** (plus older `app.log.1…3`) — check it if a
refresh fails or the server won't start. In background mode (`python run.py start`), console output is
also captured to **`qpd.log`** in the project root.

---

## 9. Demo mode (no Qualys account)

To explore the UI with **synthetic sample data**:

```bash
./run.sh --demo
```

A banner indicates demo mode; **Refresh** is disabled. Connect real credentials (or delete
`backend/data/posture.db`) to switch to live data.

---

## 9. Reset / uninstall

- **Reset all data & credentials:** stop the app and delete the `backend/data/` folder. Next run
  starts fresh at the Setup screen.
- **Uninstall:** delete the project folder. Nothing is installed system-wide (everything lives in the
  project's `.venv` and `backend/data/`).

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Authentication failed (401)" | Re-check username/password and that you picked the **right platform**. |
| "Could not reach the Qualys gateway" | Check network/VPN; confirm the gateway URL for your pod. |
| No accounts / empty posture | Ensure your Qualys account has **CloudView connectors** configured and CSPM read access. |
| Port already in use | Run with `--port <n>`. |
| Refresh fails / server won't start | Check **`backend/data/app.log`** (and `qpd.log` in background mode). |
| Scheduled refresh didn't run | Auto-refresh runs only while the app is running, and needs stored credentials. |
| Want to start over | Delete `backend/data/` and refresh. |
