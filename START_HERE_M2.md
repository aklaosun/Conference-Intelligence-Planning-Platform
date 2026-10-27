# Jonathan's M2 integration — start here

## What this package does

This is Gavin's supplied branch plus Jonathan's Django review integration. It is based on commit 637055b3428ea3b444959a900dcda6911176c980, not a merge of the team's latest main branch. It has not been pushed, merged, or deployed.

Use the shared **aklaosun/Conference-Intelligence-Planning-Platform** repository for these Django files. Your separate printsbycruz/frontend GitHub Pages repository cannot run Django or its session-authenticated APIs.

The new `/review/` page connects to Gavin's documented session, extraction, candidate queue, and detail endpoints. It uses his same-origin adapter (copied unchanged as ai-client.mjs), session authentication, permission checks, and CSRF bootstrap. It understands the real `payload` wrapper and `needs_review` status, supports pagination and extraction, renders source text safely, and warns before replacing an edited candidate with another API result.

Review export is still a draft packet. There is no server approve/reject endpoint in the provided branch. Exporting does not update the official catalog. We did not change approval_service.py or silently invent an approval API.

## Files to add in the shared repository

Copy the files INSIDE the `ccse-m2-integration` folder to matching paths in your shared checkout/branch. Do not upload the enclosing folder or ZIP to the source repository.

New application files:

1. `ccse-conference-platform/conferences/review_views.py`
2. `ccse-conference-platform/conferences/review_urls.py`
3. `ccse-conference-platform/conferences/templates/conferences/review.html`
4. `ccse-conference-platform/conferences/static/conferences/review.js`
5. `ccse-conference-platform/conferences/static/conferences/review-live.mjs`
6. `ccse-conference-platform/conferences/static/conferences/ai-client.mjs`

Tests and notes:

7. `ccse-conference-platform/conferences/test_review_frontend.py`
8. `frontend-tests/review.test.cjs`
9. `frontend-tests/live.test.mjs`
10. `package.json` (if the team has since added one, merge the test scripts/dependency rather than replacing it)
11. `START_HERE_M2.md`
12. `docs/FRONTEND_M2_VALIDATION.md`

One existing application file needs a small route change:

13. `ccse-conference-platform/ccse_platform/urls.py`

The supplied urls.py already has these changes applied. Because the screenshot shows this file is involved in the team's merge conflicts, preserve the current team's routes and merge these lines into it; do not replace the latest file wholesale:

```python
from django.urls import include, path  # retain other existing imports

urlpatterns = [
    path("", include("conferences.review_urls")),
    # retain all existing admin / AI / backend routes
]
```

The root README has an optional appended M2 section; merge that section if useful. All other original branch files in this ZIP are context, not new Jonathan changes. No changes to settings.py, admin.py, models.py, migrations, tests.py, or approval_service.py are needed by this frontend addition. Resolve Gavin/main merge conflicts with the owners separately.

Suggested commit: `Connect M2 Django review screen to AI candidate APIs`

## Run locally (Python 3.12)

Install Gavin's existing dependencies and use the local SQLite settings. These commands assume the extracted project root and an activated virtual environment:

```bash
python -m pip install -r requirements-ai.lock.txt
python ccse-conference-platform/manage.py migrate --settings=ccse_platform.ai_local_settings
python ccse-conference-platform/manage.py createsuperuser --settings=ccse_platform.ai_local_settings
python ccse-conference-platform/manage.py configure_ai_role --settings=ccse_platform.ai_local_settings
python ccse-conference-platform/manage.py runserver --settings=ccse_platform.ai_local_settings
```

Open http://127.0.0.1:8000/review/, sign in, and click **Connect / refresh session**. A superuser has the required permissions. AI Researchers users need candidate-view permission; the existing admin login also requires staff status. The page itself checks candidate-view permission, while the AI APIs separately enforce extraction/view permissions.

For a new real extraction, configure GEMINI_API_KEY privately per Gavin's handoff. No API key belongs in frontend JavaScript, screenshots, commits, or chat messages. No new key was supplied or used to test this package.

The provided local settings use DEBUG=True to serve static assets in development. The team's production deployment must serve Django static assets normally. This is not a GitHub Pages deployment.

## What to show Ayo now

1. Sign in and open `/review/`.
2. Connect the session and load the pending queue.
3. If there are no candidates locally, enter an official URL and edition year and extract with a configured Gemini key; otherwise use an existing pending candidate. The fictional sample and JSON import remain available for offline UI checks.
4. Open a candidate and inspect fields, evidence, source records, warnings, changes, and conflicts.
5. Edit fields and JSON deadline/price arrays. Empty prices mean unknown, not free.
6. Document conflict decisions and confirm source review, then export reviewed values. Explain that this is a packet for the backend, not a saved approval.
7. Try a rejected/approved API candidate: the review exports are disabled based on wrapper status.
8. Verify API errors leave the current candidate visible and controls usable.

For importing an example payload without an API wrapper, status is unknown and decision export is intentionally disabled. Get the current status from the API; do not assume an old example file is still pending.

## What is needed from Joshua

- Confirm the current backend branch and reconcile shared routes with Gavin.
- Supply or implement authorized approve/reject endpoints, methods, request format, responses, and permission rules.
- Support corrected scalar fields AND deadline/price arrays, documented conflict decisions, and validation errors.
- Make approvals transactional; reject stale/repeated decisions; update existing values and superseded deadlines correctly; preserve source URLs and reviewer audit information; keep completeness separate from verification, as Gavin requested.
- Confirm deployment and database settings for Ayo's shared test environment.

Once that contract is available, connect the exported reviewed values to it, validate on the server, and test extraction → review → approve → persisted correct edition. That final approval/save workflow remains incomplete.
