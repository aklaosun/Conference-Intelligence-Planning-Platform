# M2 validation — October 30, 2026

## Automated checks

- Python 3.12 / Django 5.2.18 / local SQLite: **144 tests passed** in 23.111 seconds.
- Combined suite retains the backend tests and earlier AI tests, plus integration acceptance tests.
- Covered: extraction staging, permissions, CSRF, edit/approve/catalog/CSV, rejection reasons,
  raw-payload immutability, audit notes, conflict decisions, stale decisions, invalid rows,
  explicit clearing vs preserving unrelated rows, past editions and transactional rollback.
- Demo setup is repeatable, generates a non-superuser local login, preserves its password and
  seed, and refuses to run outside development settings.
- `makemigrations --check --dry-run`: **No changes detected**.
- Node syntax checks pass for the workbench scripts.
- Fixed and regression-checked Windows `.mjs` MIME handling: ES modules must be served as
  `application/javascript`, rather than the local Windows `text/plain` association.

## Actual browser walkthrough

The application ran at http://127.0.0.1:8010/ using the generated local Reviewer/AI Researcher account.

1. Signed in and opened the auto-connected AI workbench/queue.
2. Submitted Computing Frontiers 2026 with a one-page limit through the UI. A real Gemini request
   returned and persisted candidate #2 with twelve deadline rows and unknown registration pricing.
3. Opened the earlier captured three-page candidate #1. Edited location and the first registration
   label using form controls, exercised date/amount inputs, chose the first name-conflict alternative,
   recorded notes, confirmed source review and approved through the UI.
4. Followed the success link into the catalog: one 2026 edition, corrected location `Catania, Italy`,
   dates May 19–21, ten active deadlines with AoE retained, six active EUR prices with registration-page
   links, Complete/Verified status and reviewer timestamp.
5. Rejected fresh candidate #2 with a reason. The catalog stayed populated with the approved edition.
6. Downloaded the actual CSV through **Export CSV** and inspected its saved row. It contains the
   corrected location, year, dates, source URL and Verified status.

This is an acceptance demonstration on an isolated local demo database. It is not a claim that
every conference website, production PostgreSQL, shared deployment or automated scheduling works.
