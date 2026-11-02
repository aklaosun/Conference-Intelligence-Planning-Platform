# CCSE Conference Workspace

A conference research and planning prototype for Kennesaw State University's College of Computing and Software Engineering, supporting CAC and CDSA workflows. The current demo uses **35 real CAC conferences and 35 yearly editions** from the supplied spreadsheet.

The application combines a React interface, an Electron Windows client, and a Django backend. The packaged desktop demo includes Python and its backend, so recipients do not need development tools to run it.

**Current release: 0.3.1 · Local Windows x64 demo · Alerts update November 2, 2026.** Each computer keeps its own database; changes do not synchronize between teammates.

## Run the desktop demo

1. Obtain `CCSE-Workspace-Windows-0.3.1.zip` from the team's shared release files. Executables are distributed separately from this source repository.
2. Extract **all** files. Open the `CCSE Conference Workspace` folder and double-click `CCSE Conference Workspace.exe`. Keep the executable and its supporting files together.
3. Wait for the local workspace to initialize. The app creates a private database, loads the real conference seed, and opens a local demo owner account automatically.
4. Start with **Conference catalog**, open a conference, and inspect its **Spreadsheet source**. Then try **Plan this edition**, budgets, outcomes, deadlines, and CSV reports.
5. Close and reopen the app to continue with your saved data.

Python, Node.js, PostgreSQL, and terminal commands are **not required** for the packaged demo. The alternative `CCSE-Workspace-Portable-0.3.1-x64.exe` also works, but unpacking took about a minute per launch on the test computer. The extracted-folder ZIP is recommended for repeated demonstrations. These are unsigned capstone builds supplied by the project team.

For live AI extraction, open **Live AI settings** and save your own Google AI Studio key. Browsing, planning, reports, and reviewing saved real suggestions work without a key. Live extraction requires internet access, an available Gemini model, and provider quota.

See the [complete desktop walkthrough](docs/DESKTOP_AND_SHARED_ACCESS.md).

## What the prototype includes

- Searchable conference catalog with yearly editions, filters, verification status, original spreadsheet values, row provenance, and import warnings.
- Gemini research across a bounded set of official pages, with quoted evidence and staged suggestions.
- Human correction, approval, and rejection; the original AI response is retained separately from reviewed values.
- Planning statuses, owners, objectives, itemized estimated/actual expenses, and totals kept separate by currency. Missing amounts remain unknown.
- Configurable evaluation criteria and weights. Scores require approved criteria and complete ratings; a score does not approve attendance.
- Outcome summaries, attendee/contact/partnership counts, follow-up actions, deadline views, and catalog/planning CSV exports.
- In-app alert center with a bell badge, dashboard summary, deadline and follow-up reminders, role-scoped review requests, and personal read status.
- Administrator, Viewer, Contributor, and Coordinator permissions, plus invitation support for a future shared deployment.

## In app alerts

Open **Alerts** from the sidebar or bell in the top bar. Deadlines and incomplete dated follow-ups appear within 30 days, including overdue actions; deadlines for finished events stay in history. Coordinators and administrators also see pending AI review requests. Filter by type or unread status and mark individual or shown alerts read. Read status is personal, survives restart, and never completes the underlying task. Changed deadlines return as unread; completed follow-ups and resolved review requests leave the feed.

The feed refreshes every minute while the app is open and when returning to it. Reminders compare calendar dates using the workspace date and preserve source timezone labels, including AoE; consult the source for exact cutoff times. Email, operating-system notifications, and delivery while the app is closed remain separate work.

## Run the browser application from source

The following PowerShell commands initialize a **fresh clone** with the public demo seed. They require Git and Python 3.12. Compiled React assets are included, so Node.js is only needed when rebuilding the frontend or desktop release.

```powershell
git clone https://github.com/aklaosun/Conference-Intelligence-Planning-Platform.git
cd Conference-Intelligence-Planning-Platform

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.lock.txt

$env:DJANGO_SETTINGS_MODULE = "ccse_platform.ai_local_settings"
.\.venv\Scripts\python.exe -X utf8 .\ccse-conference-platform\manage.py migrate --noinput
.\.venv\Scripts\python.exe -X utf8 .\ccse-conference-platform\manage.py loaddata .\data\demo-catalog.json

.\Start-M2Demo.ps1
```

Open [http://127.0.0.1:8010/app/](http://127.0.0.1:8010/app/). Use the generated private `.m2-demo-login.json` for review access or `.m2-owner-login.json` for administrator access. Leave the terminal running; Ctrl+C stops the server.

For an existing source installation, run `Start-M2Demo.ps1` without reloading the seed. The source browser workflow uses its project database, which is separate from the packaged desktop database.

For fresh AI extraction in the source workflow, copy `.env.example` to `.env` if it does not already exist, then privately set `GEMINI_API_KEY` and `GEMINI_MODEL`. The packaged desktop's **Live AI settings** screen stores its configuration separately.

To import or reconcile the supplied workbook using the repeatable importer:

```powershell
.\Import-CACSpreadsheet.ps1 -Path ".\data\NEW CAC CONFERENCE LIST 2026.xlsx" -DryRun
.\Import-CACSpreadsheet.ps1 -Path ".\data\NEW CAC CONFERENCE LIST 2026.xlsx"
```

See [spreadsheet import behavior and reconciliation](docs/CAC_DATA_IMPORT.md).

## Build the Windows desktop release

Builders need Windows x64, Python 3.12, Node.js 24 LTS, and internet access. From the repository root:

```powershell
.\Build-Desktop.ps1
.\Run-Desktop.ps1
```

The build script creates an isolated build environment, builds React, bundles Django/Python, and produces Windows artifacts under `client/release`. The launcher prefers the extracted folder build when present. Build output and local data are ignored by Git; distribute executable downloads separately from source commits.

## Validation

The November 2 alert update passed **199 regression/integration tests**, including 13 alert tests, and the client checks. The original October 31 portable and extracted-folder distributions passed **16 packaged-runtime check groups**, including a real Gemini extraction, source review decisions, permissions, budget calculations, CSV contents, clean shutdown, and persistence after restart.

To run the source tests after the source setup above:

```powershell
$env:DJANGO_SETTINGS_MODULE = "ccse_platform.ai_local_settings"
.\.venv\Scripts\python.exe -X utf8 .\ccse-conference-platform\manage.py test conferences
```

See the [packaged validation report](docs/PACKAGED_VALIDATION.md) for evidence and scope. The optional installer was built; acceptance testing covered the portable and extracted-folder applications rather than a system installation/uninstallation cycle.

## Data, access, and current limits

- Local desktop data is stored under `%APPDATA%\CCSE Conference Workspace\data`. Use **Workspace → Open local data folder** to find it. Quit the app before backing up `workspace.sqlite3`.
- API keys, `backend.env`, `.env`, generated login files, secrets, sessions, virtual environments, and local databases must stay out of commits and shared demo downloads.
- The provided workbook supplies CAC records; a CDSA dataset has not been supplied. Missing costs, dates, and inferred years remain visible rather than being invented.
- Sponsor-approved criteria/weights and final acceptance remain pending. This is a prototype, not a claim that every project-plan requirement is complete.
- Shared hosting, live PostgreSQL validation, production scheduling/SMTP, native macOS/Linux releases, and other remaining work are documented in the [requirements status](docs/REQUIREMENTS_STATUS.md). Shared-server configuration is prepared for future use; it is not deployed. Email delivery is disabled in local demos.

## Documentation

- [Desktop walkthrough, private AI setup, and local backups](docs/DESKTOP_AND_SHARED_ACCESS.md)
- [Packaged validation](docs/PACKAGED_VALIDATION.md)
- [Project-plan alignment and remaining work](docs/REQUIREMENTS_STATUS.md)
- [Spreadsheet import and provenance](docs/CAC_DATA_IMPORT.md)
- [AI API reference](docs/AI_API.md)

Earlier M1/M2 artifacts remain in the repository as historical project records. This README and the desktop/packaged-validation guides describe the current local demo.
