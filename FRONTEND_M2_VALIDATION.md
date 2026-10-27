# Jonathan's M2 integration validation

## Checked in this environment

- Installed the exact Python dependencies in requirements-ai.lock.txt.
- `python ccse-conference-platform/manage.py test conferences --settings=ccse_platform.ai_local_settings`: **96 tests passed**, including Gavin's existing 89 tests and seven new frontend route/API contract checks. System check found no issues.
- New Django checks cover anonymous login redirect, candidate-view permission, rendered template/static discovery, GET-only page route, session/queue/detail contract, extraction CSRF enforcement and mocked result handling, and authoritative wrapper status.
- Two Node/jsdom suites passed: review form/export behavior and the live adapter wiring.
- Node checks cover source text escaping, unsafe source links, original payload retention, unknown prices, conflict decisions, date/year/price validation, rejection reason, import validation, draft retention, session permissions, candidate queue/detail, pagination, unsaved-edit guard, CSRF extraction payload, reused approved candidate state, and API error recovery.
- Both live example JSON payloads (Computing Frontiers and DjangoCon) render through the candidate review importer.
- JavaScript syntax checks passed for review.js and review-live.mjs.

## Reproduce

From the root, using Python 3.12 with Gavin's pinned dependencies installed:

```bash
python ccse-conference-platform/manage.py test conferences --settings=ccse_platform.ai_local_settings
```

For DOM/module tests, using Node 24+:

```bash
npm install
npm test
```

JavaScript test dependencies are development-only. The served page needs no build or Node runtime.

## Limits

Django tests use a temporary SQLite database; the extraction provider boundary is mocked. JavaScript tests use jsdom, mocked fetch responses, and stubbed download APIs. The official provider service is covered by Gavin's existing tests; this task did not make new Gemini requests or revalidate live website content.

A Chromium browser was not available in this environment. Native browser visual layout, file chooser/download behavior, interactive login, actual live provider extraction through the page, and production static serving still require manual QA.

No approve/reject endpoints were supplied, added, or called. The official edition save flow, authorization for decisions, backend edits to arrays/conflicts, transactionality, concurrency, and PostgreSQL behavior are not established by these results. Review packet backend_contract_verified remains false because the approval contract is missing, even though the AI API contract is now wired correctly.

Reviewers manually apply conflict resolutions and attest to the edits; the frontend does not semantically prove that selected alternatives were applied correctly. Deadline and price arrays remain JSON editors. Full schema/policy validation must also occur in the backend.
