# Run the updated local desktop demo

Version 0.3.0 · October 31, 2026

The preferred demo is a Windows x64 Electron application with a React interface and a bundled Django backend. Each person runs an independent local database. Installing or copying the app does **not** synchronize changes between people.

## For the team, sponsor, and professor

1. Obtain `CCSE-Workspace-Setup-0.3.0-x64.exe` or `CCSE-Workspace-Portable-0.3.0-x64.exe` from the team’s release files. Python, Node.js, PostgreSQL, and a terminal are not required to run these builds.
2. Run the installer, then open **CCSE Conference Workspace**. Alternatively, extract every file from `CCSE-Workspace-Windows-0.3.0.zip` and open `CCSE Conference Workspace.exe` inside its folder. Keep the entire folder together. The portable executable is also available; its unpacking can take about a minute before the window appears on this computer. These are unsigned capstone builds; only use the files supplied by the project team.
3. Wait for **Preparing your local workspace** to finish. On the first launch the application creates a private local database and imports the real dataset. Subsequent launches preserve local edits.
4. The app opens your personal **Local Demo Owner** workspace automatically. This local convenience is disabled on ordinary/shared-server configurations.
5. Open **Conference catalog**. The starting dataset contains 35 conferences and 35 editions from `NEW CAC CONFERENCE LIST 2026.xlsx`. All 35 records are CAC-related; a CDSA spreadsheet has not been supplied.
6. Use search and the year, center, and verification filters. Open a conference and expand its **Spreadsheet source** section to inspect the original worksheet, row, values, and import warnings.
7. Open **Plan this edition**. Choose a status and owner, record an objective, and add itemized expenses. Blank amounts mean unknown. Currencies stay separate. Save the plan, then reopen it to check persistence.
8. Open **Evaluation**. Scores remain unavailable until the administrator configures the sponsor’s actual criteria and weights, marks their approval, and records every required rating. No default rankings are invented; an evaluation score does not authorize attendance.
9. Open **Outcomes & follow-up** to record results, attendee/contact/partnership counts, and a follow-up action. Unknown counts can stay blank.
10. Open **Deadlines** to inspect upcoming deadlines, overdue deadlines for future events, historical deadlines, and open follow-up actions. Dates and timezone labels retain source information.
11. Open **Reports & outcomes** and export the planning CSV. Catalog CSV is available from the catalog page. CSV amounts stay blank when incomplete, preserve explicit zeroes, and keep currencies separate.
12. Close and reopen the app. Your saved plans and outcomes should still be present.

## Optional live AI extraction

1. Obtain your own complete Gemini API key from Google AI Studio. Do not share the key with the team or commit it to GitHub.
2. In the app, open **Live AI settings**. Paste the key into the password field and keep the configured model unless your account requires another available Gemini model.
3. Select **Save private AI settings**. The app does not display the saved key again. Leaving the key field blank preserves the current key. Saving confirms local storage; it does not prove the provider connection or quota is available.
4. Open **Research & review**, enter an official conference URL and edition year, and select **Extract conference**. Internet access and sufficient provider quota are required. Fetching is bounded to the selected maximum of 1–5 source pages.
5. Inspect the proposed fields, quoted evidence, warnings, sources, deadlines, prices, and any conflicts. Correct the suggestion or reject it. Approval requires a human confirmation and server-side validation.
6. Approval saves to this computer’s catalog. The original AI response is retained separately from reviewed values. Unknown prices do not become free registration.

The bundled dataset also includes previously captured **real** Computing Frontiers suggestions, so evidence review can be demonstrated without calling Gemini. The fictional developer sample is hidden in the embedded research screen.

## Local data and backups

Use **Workspace → Open local data folder** to find the database and private backend configuration. The standard Windows location is:

`%APPDATA%\CCSE Conference Workspace\data`

`workspace.sqlite3` holds local edits. `backend.env` contains any saved API key. `django-secret.txt` is private. `backend-start.log` contains startup diagnostics. `runtime.json` contains the current local port and process ID, not the launch token. Quit the application before copying `workspace.sqlite3` for a backup. Do not share the private configuration, secrets, login/session files, or your entire application-data folder.

The packaged backend binds only to `127.0.0.1` on a dynamically assigned port and stops with the app. It is not a server for other computers. Replacing the executable preserves the existing local database. The seed is loaded once and contains no user accounts, passwords, sessions, API keys, invented budgets, or invented outcomes.

## Run from the existing source project

For the original project database and private `.env`:

```powershell
cd "C:\Users\shan1\Downloads\Capstone project"
.\Start-M2Demo.ps1
```

Open the printed `/app/` URL. That source workflow uses the existing `.venv` and local project database. Its private `.m2-demo-login.json` and `.m2-owner-login.json` provide the appropriate local credentials. It is a separate database from the packaged personal desktop demo.

To launch the packaged desktop copy from this project, when the release file has been copied into `client\release`:

```powershell
.\Run-Desktop.ps1
```

## Rebuild the Windows desktop release

Builders need Windows x64, Python 3.12, Node.js 24 LTS, and internet access. Run from the repository root:

```powershell
.\Build-Desktop.ps1
```

The script creates an isolated `.desktop-build-venv`, installs pinned build dependencies, builds React, bundles Python/Django with PyInstaller, and builds the NSIS installer and portable executable. It runs the official Electron installation script explicitly after an npm install with lifecycle scripts disabled. Outputs are in `client\release`. Build output, virtual environments, installers, databases, and private settings are ignored by Git.

The committed public seed is `data/demo-catalog.json`; the original workbook is also in `data`. Rebuilding uses that reviewed seed, not a developer’s private database. A future dataset release should export only the five public conference/extraction models and check for private credentials before replacing the seed.

## Future shared access

The current agreed setup is independent local demos. Shared synchronization remains optional. The same React interface supports a persistent Django/PostgreSQL HTTPS backend. The desktop **Connect to a shared server** menu can point to it, and browser access uses `/app/`. Administrator invitations create personal Viewer, Contributor, or Coordinator accounts. Invite links expire in three days and can be revoked.

Deployment files and strict `production_settings.py` are prepared under `deploy`, but have not been deployed or validated against a live PostgreSQL host. Do not point teammates at a localhost invitation URL. A hosted server needs its own private secrets, persistent database, HTTPS, backups, and a manually created administrator; it must not use the local demo owner bootstrap.

Weekly report email is disabled in local demos. A future shared deployment must configure SMTP and approved recipients, enable server email, and schedule `python manage.py send_weekly_reports --send` daily. Without `--send`, the command is a dry run. Normal retries skip a report already marked delivered for that week; a process failure after SMTP acceptance but before committing its delivery record can still cause a duplicate retry.

## Current limits

- Windows x64 release only. macOS/Linux users can use the source Django application in a browser; native builds need packaging on the corresponding OS.
- Local copies do not synchronize. Live AI requires an individual provider key, internet access, and available quota.
- Sponsor-approved criteria, weights, and final acceptance rules have not been supplied. They must be confirmed before evaluations are treated as authoritative.
- The supplied workbook has 35 CAC records, no cost values, five editions without dates, and some inferred years. Import warnings remain visible. Existing source-backed CF prices/deadlines are retained.
- Full discovery automation, hosted scheduling, normalized center/theme relationships, accessibility acceptance testing, and sponsor sign-off remain on the roadmap. See `REQUIREMENTS_STATUS.md`.
