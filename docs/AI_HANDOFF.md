> M2 integration update (October 30): see [the current demo guide](M2_DEMO.md). The AI-only handoff and earlier test counts below are historical.

# AI contribution handoff

## Delivered scope

The assigned URL-to-candidate extraction workflow is implemented:
- Public HTML retrieval with timeouts, a 2 MB response limit, redirect checks, and blocked private IPs.
- Crossed-out text preservation for HTML tags, inline styling, and simple embedded CSS rules.
- Bounded companion-page selection: registration first, then calls/deadlines, then program/venue.
- Same-host, same-edition automatic links; explicit public source URLs are also supported.
- Gemini structured extraction with strict local schema, date, price, currency, and evidence checks.
- Source URLs, retrieval times, analyzed text snapshots, source IDs, and content hashes.
- Track-specific deadline names and consistent handling of AoE as a deadline convention.
- Publication fees, ancillary tickets, incremental surcharges, and unpublished calculated prices excluded.
- Multi-page merge, duplicate removal, conflict alternatives, and missing-information warnings.
- Fact-based summary and changes against the previous candidate for that URL/year.
- Repeat-run fingerprinting: unchanged sources reuse the prior candidate without model extraction calls.
- Sequential batch refresh command with JSON reports and fail-stop behavior on provider errors.
- Authenticated candidate list/detail/extraction endpoints, CSRF bootstrap, a browser integration module,
  and a read-only admin inspector.
- Reproducible dependencies, a role setup command, automated tests, and live examples.

The AI writes only ExtractionCandidate. Approval, rejection, official catalog updates,
deadline notifications, and the final frontend remain the other components' integration responsibilities.

## Local setup

Use the root .venv and Python 3.12. requirements-ai.lock.txt records the tested versions.
A new clone needs the setup in README.md. The private .env supports GEMINI_API_KEY and GEMINI_MODEL.
An explicitly supplied key overrides .env; a populated project .env key overrides a stale process key.
For the model: an explicit argument/process GEMINI_MODEL takes priority, then .env, then the documented default.

Run a local extraction:

```powershell
.\Run-LiveExtraction.ps1 -Url "https://www.computingfrontiers.org/2026/" -Year 2026
```

Optional controls:

```powershell
.\Run-LiveExtraction.ps1 -Url "https://www.computingfrontiers.org/2026/" -Year 2026 -MaxPages 2 -Force
.\Run-LiveExtraction.ps1 -Url "https://2026.djangocon.us/" -Year 2026 -SinglePage
```

Inspect pending records:

```powershell
$env:DJANGO_SETTINGS_MODULE = "ccse_platform.ai_local_settings"
.\.venv\Scripts\python.exe .\ccse-conference-platform\manage.py createsuperuser
.\.venv\Scripts\python.exe .\ccse-conference-platform\manage.py configure_ai_role
.\.venv\Scripts\python.exe .\ccse-conference-platform\manage.py runserver
```

Open http://127.0.0.1:8000/admin/. Assign the AI Researchers group through Django admin
to users who may extract/view candidates. Admin login also requires staff status.
The group grants no approval or deletion rights.

## Backend connection

Existing single-page calls remain supported:

```python
from conferences.ai_service import extract_and_stage
candidate = extract_and_stage(url, expected_year=2027)
```

For the complete research and monitoring pipeline:

```python
from conferences.research_service import research_and_stage
run = research_and_stage(url, expected_year=2027, max_pages=3)
candidate = run.candidate
# run.created is False when unchanged content reused an existing record.
```

A replaceable provider exposes model and extract(page, expected_year) -> dict.
It returns the provider-response schema; the service validates evidence and builds the candidate envelope.
No credentials or model-produced approval decisions belong in that envelope.

Schema 1.1 preserves fields.<name>.value, deadlines, registration_prices, sources, and warnings.
It adds conflicts, summary, changes, and monitoring metadata. The existing approval service can consume
non-conflicting core values, as checked by an integration test. The JSON schema is in
docs/ai-candidate.schema.json; it is a transport contract, not a correctness guarantee.

## Conflict rules

Conflicting critical scalar fields are set to null and retain alternatives with source evidence.
Conflicting deadline or registration-price rows are withheld from the main arrays and retained in conflicts.
A reviewer must select/correct alternatives before approval; do not approve every raw alternative.
Non-critical descriptive differences keep the primary source's value and expose alternatives.
Absent metadata does not count as disagreement; a known timezone can enrich an otherwise identical deadline.

Different editions are not merged. A companion page that explicitly identifies another edition is excluded.
A linked page without an edition year may contribute to the requested edition, with source context retained;
its conference event dates still must match the requested edition.

## Batch automation

Edit examples/refresh-manifest.json to list the official URLs and years to monitor:

```powershell
$env:DJANGO_SETTINGS_MODULE = "ccse_platform.ai_local_settings"
.\.venv\Scripts\python.exe .\ccse-conference-platform\manage.py refresh_conferences .\examples\refresh-manifest.json --output .\refresh-report.json
```

A manifest contains 1–100 conferences; each may set follow_links, source_urls, and max_pages (1–5).
The worker is sequential. Page content must be retrieved to detect changes; unchanged content avoids inference.
Use --force to bypass this optimization. Quota/auth/provider errors stop the batch; website errors are
reported per target. Failed batches return a nonzero exit code, with details in the output report.

The school's scheduler can invoke this command on its chosen schedule. No scheduled task has been
installed on your computer. Run long extraction batches outside web request timeouts.

## Teammate integration checklist

Joshua/backend:
- Keep the existing Conference, ConferenceEdition, Deadline, RegistrationPrice, and ExtractionCandidate tables.
- Include the AI routes from ccse_platform/urls.py and install the listed dependencies.
- Read the current record status from the API wrapper, rather than raw_payload.status.
- Require explicit human review; do not expose approve/reject without authorization and CSRF protection.
- Resolve conflicts and allow edits to deadline and price arrays as well as scalar fields.
- Before production approval, address the existing approval_service.py issues: a single transaction,
  update existing values correctly, avoid retaining superseded deadlines, copy source_url to child records,
  and calculate completeness separately from verification.
- The AI component does not change those existing approval policies or silently mark records approved.

Jonathan/frontend:
- Use examples/frontend-integration.mjs and docs/AI_API.md.
- Load pending candidates; show values, source evidence, warnings, conflicts, and change flags.
- Render source text with textContent or escaped Django templates.
- Treat missing prices as unknown, never as free.
- Send edited/selected values to the backend's authorized approval workflow.

School/sponsor:
- Supply the long-term API project/account and identify its maintainer.
- Select hosting, PostgreSQL configuration, a batch/job schedule, and usage limits.
- Approve any future relevance or ROI criteria before those are implemented.

## Scope boundaries

This completes the defined extraction/automation contribution. Open-web conference discovery,
sponsor-specific relevance scoring, ROI, PDF extraction, JavaScript rendering, and alert delivery
are separate capabilities rather than implicit claims of this handoff.
No automatic approval, paid-provider fallback, or scheduled execution is enabled.
