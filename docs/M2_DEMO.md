# M2 demo — October 30, 2026

## Run on the existing Capstone project computer

The project is already configured. If it is not running, open a PowerShell terminal in the
project root and run:

```powershell
.\Start-M2Demo.ps1
```

Open http://127.0.0.1:8010/ . Read the username/password from `.m2-demo-login.json` in the
project root. This is a private, generated local demo login, not the Gemini key.
Leave the terminal running. Ctrl+C stops the server.
The script uses `ccse_platform.ai_local_settings` and a separate `m2-demo.sqlite3`.
The previous `ai-local.sqlite3` is preserved. No team PostgreSQL database is used.

If PowerShell blocks local scripts, use the process-scoped policy already used for the AI runner:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\Start-M2Demo.ps1
```

The app is bound to loopback. Teammates can view a screen share or run their own local copy.
This URL is not a hosted team link.

## First installation on a teammate's computer

Use Python 3.12 and run from the extracted repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.lock.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
.\Start-M2Demo.ps1
```

The pinned runtime is Django 5.2.18, tested with this combined code. The backend's old 6.1
requirements entry has been replaced with the tested shared lockfile. Openpyxl is included
for the existing spreadsheet importer. PostgreSQL users additionally need `requirements-postgres.txt`.

Reviewing the captured example requires no Gemini API call. For fresh extraction, privately
set `GEMINI_API_KEY` and `GEMINI_MODEL` in `.env` and save it. Keep the key out of messages,
source control and screenshots. The supplied model setting worked in the live validation;
model access and quota depend on each teammate's Google project.

## Five-minute walkthrough

1. Sign in. Open **Conferences** to inspect the saved 2026 Computing Frontiers edition,
   or open **AI workbench** to review a pending suggestion.
2. In the workbench, choose the saved Computing Frontiers candidate. It is a real captured
   three-page extraction, not the unsaved fictional sample.
3. Inspect original field evidence, deadline/price source details, warnings and source links.
   The example has a conference-name alias conflict. **Use alternative 1**, then check its
   decision note. Correct a location or a registration label if useful.
4. Dates, times, deadline tracks, registration categories, amounts and currencies are ordinary
   editable fields. Add/remove controls change only the unsaved review until approval.
5. When updating an already saved edition, leave **Replace all existing deadline and price rows**
   unchecked to preserve unrelated saved rows. Check it only if this review intentionally supplies
   the entire replacement set, including any deliberate removals. A repeated full-example rehearsal
   can use this option to avoid retaining earlier label variants.
6. Enter reviewer notes, check the final source/conflict confirmation and click **Approve and save**.
   Open **View saved conference**. Verify dates, corrected location, ten AoE deadlines, six EUR
   price tiers and source links. The original extraction remains unchanged.
7. Open **Review history** to see who reviewed the record, when, and the notes. Open the integrated
   workbench from a history record to inspect its saved reviewed values. Already reviewed records
   cannot be decided again.
8. In **Conferences**, search/filter the catalog and click **Export CSV**.
9. For fresh AI research, enter `https://www.computingfrontiers.org/2026/`, year `2026`, and a page
   limit. Three pages can include registration/program details. One page is quicker but may omit prices.
   Repeated unchanged sources can reuse an existing candidate, including its reviewed status.
10. To demonstrate rejection, open a pending candidate, enter a reason, then **Reject suggestion**.
    Its status/history changes; the official catalog remains unchanged.

The captured conference took place in May 2026. It is intentionally historical and will not
appear with **Upcoming only** enabled. Unknown prices are not treated as free.

## Repeat the review demo without another API call

Stop the server first, then run:

```powershell
.\Start-M2Demo.ps1 -NewReview
```

This creates another pending copy of the captured extraction and retains earlier decisions.
Normal startup is idempotent and does not reset the login, duplicate the seed, or erase records.
If the demo username exists but the private login file has been lost, use Django's normal
password-reset management command yourself; setup intentionally does not reset existing passwords.

## Team integration

Backend baseline: `main` commit `b5ae7f3da326114c043b5ba9e21b06ced09edc1d`.
Review frontend source: `jonathan-m2-review` commit `a1c6fa70ad3ecdd4b0896265322380a03cb85843`.
AI source: `feature/ai-handoff-20261026-142400` commit `637055b3428ea3b444959a900dcda6911176c980`.

The Django workbench is `/review/workbench/`; review decisions POST to
`/api/review/candidates/<id>/decision/`. AI endpoints remain under `/api/ai/`.
Apply migrations through `0003_reviewed_payload` before using decisions. It depends on main's
`0002_conference_field_sources_and_more`. Existing raw payloads are retained, and reviewed
payloads/notes are separate audit fields.

For a shared environment, retain the team's settings/database, install the PostgreSQL driver if
needed, run migrations plus `setup_roles` and `configure_ai_role`, and assign real users appropriate
Reviewers/Editors/AI Researchers groups using the existing administration workflow. The local demo
bootstrap is development-only. PostgreSQL and multi-user deployment have not been exercised here.

Research is synchronous and may take several website/model requests. A hosted deployment needs
suitable timeouts or a background worker. No automatic research schedule, deadline notifications,
relevance scoring or ROI workflow has been added by this integration.

## Validation

```powershell
$env:DJANGO_SETTINGS_MODULE = "ccse_platform.ai_local_settings"
.\.venv\Scripts\python.exe .\ccse-conference-platform\manage.py test conferences --noinput
.\.venv\Scripts\python.exe .\ccse-conference-platform\manage.py makemigrations --check --dry-run
```

144 tests passed locally. The tests use a separate test database. If a managed machine blocks
its normal temporary directory, set `TEMP` and `TMP` to a writable local scratch directory before
running the inherited spreadsheet-import tests.
