# Repository organization guide

This repository contains the integrated CCSE Conference Intelligence and Planning Platform proof of concept.

## Working application
- `ccse-conference-platform/` — Django backend, conference database models, management commands, templates, APIs, and Python tests. Keep its internal structure intact.
- `client/` — React/Vite frontend and Electron desktop client. Contains source and desktop tests.
- `desktop-backend/` — desktop service launcher.
- `deploy/` — container and hosted deployment configuration.
- `data/` — CAC sponsor workbook, demo dataset, and import notes. Keep source data and provenance.
- `examples/` — AI candidate examples and sample API payloads.

## Documentation
- `README.md` — project introduction and current demo entry point.
- `docs/M2_DEMO.md` — M2 demo workflow.
- `docs/M2_VALIDATION.md` and `docs/PACKAGED_VALIDATION.md` — test/validation reports.
- `docs/REQUIREMENTS_STATUS.md` — implementation alignment and known gaps.
- `docs/AI_HANDOFF.md`, `docs/AI_API.md`, `docs/AI_MAINTENANCE.md` — AI integration information.
- `docs/CAC_DATA_IMPORT.md` — source spreadsheet import.
- `docs/DESKTOP_AND_SHARED_ACCESS.md` — desktop setup and shared access.
- `docs/milestone1/M1_UI_Wireframes.pdf` — Milestone 1 UI wireframes.
- `docs/project-management/ProjectPlan_P26_T1_9-21.docx` — project plan.

## Historical prototypes
- `archive/m1-prototypes/` — standalone Milestone 1 HTML prototype and screenshots, retained as history, not as the active application.

## Root files
Root-level PowerShell scripts and configuration remain in place because setup/build instructions refer to their current paths. Do not move them without updating callers and verifying a clean build.

## Cleanup rules
1. Keep changes on a separate branch and submit a pull request.
2. Preserve migrations, tests, source data, dependency lockfiles, and packaged frontend assets unless replacement builds are verified.
3. Never commit credentials, local databases, .env files, or generated local login files.
4. After changing application paths, run Django tests, frontend build, and Electron smoke tests before merging.
5. Record sponsor acceptance separately from developer-reported test success.
