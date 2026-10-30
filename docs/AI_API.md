# AI API contract

These routes use Django session authentication and permissions. POST requests require a CSRF token.
Anonymous requests redirect to the configured login page; missing permissions return 403.
Local development uses /admin/login/. The deployed app can supply its own authentication screens.

## Session bootstrap

GET /api/ai/session/

Returns csrf_token and permissions.extract / permissions.view_candidates.
It sets the CSRF cookie. See examples/frontend-integration.mjs for a working fetch adapter.

## Extraction

POST /api/ai/extract/

```json
{
  "url": "https://www.computingfrontiers.org/2026/",
  "year": 2026,
  "follow_links": true,
  "max_pages": 3,
  "source_urls": [],
  "force": false
}
```

url is required. year is optional (1900–2200). max_pages is 1–5 and defaults to 3.
source_urls is an optional list of up to four explicitly selected public URLs, counted in max_pages.
Automatic links stay on the same hostname; explicitly selected sources may use another public hostname.

Requires conferences.add_extractioncandidate.
- 201: new needs_review candidate.
- 200: unchanged content reused a prior candidate, which may already be approved/rejected.
- 400: malformed request.
- 422: website/edition/output validation failure.
- 503: credentials, model, quota, or provider failure.
A provider failure does not save a partially analyzed candidate.

```json
{
  "id": 7,
  "status": "needs_review",
  "created": true,
  "payload": {
    "schema_version": "1.1",
    "fields": {},
    "deadlines": [],
    "registration_prices": [],
    "sources": [],
    "warnings": [],
    "conflicts": [],
    "summary": {},
    "changes": {},
    "monitoring": {}
  }
}
```

The empty objects above illustrate the envelope, not a complete valid candidate.
See examples/synthetic-candidate.json and docs/ai-candidate.schema.json.
Raw payload status describes the extraction's original pending state; the wrapper status is current.

## Candidate queue

GET /api/ai/candidates/?status=needs_review&page=1&page_size=20

Requires conferences.view_extractioncandidate. status also accepts approved, rejected, or all.
page_size is 1–100; an optional url filter matches requested_url exactly.
Returns count, page, page_size, and results with id, status, requested_url, submitted_at, summary, warning_count.
Source snapshots/full payloads are omitted from this list response.

## Candidate detail

GET /api/ai/candidates/<id>/

Requires conferences.view_extractioncandidate. Returns id, current status, and payload.
Missing IDs return 404.

## Payload interpretation

fields.<name> has value, evidence, and source_id; it may include alternatives and corroborating_sources.
Null means not established, not false/zero/free.

sources retain id, source_url, title, retrieved_at, content_sha256, and analyzed_text.
Quotes must match a source's analyzed text after whitespace normalization. The source text excludes
crossed-out portions for quote validation. Matching does not prove correct interpretation.

deadlines contain type, date, time, timezone, evidence, source_id, source_url.
Type names identify tracks where available. AoE is retained symbolically; the AI does not schedule alerts.

registration_prices contain category, rate_type, amount (decimal string), currency, evidence, source_id, source_url.
Only explicitly published full attendance prices are included. Late-fee formulas are warned about rather
than calculated. Membership, author, and student labels should remain visible to the reviewer.

conflicts contains kind, field or identity, and alternatives.
Conflicting critical values/rows are withheld from normal fields/arrays until a reviewer resolves them.
Sources may describe overlapping sessions, so a conflict is a review signal rather than proof a site is wrong.

summary is deterministic from the validated payload. changes compares against a previous candidate.
On a reused result (created=false), changes describes that record's original comparison; it is not a new change alert.
Batch reports return empty change flags on unchanged runs.

## Operational limits

The prototype extraction endpoint is synchronous. A run can perform up to five website fetches and model calls,
so the shared deployment should invoke research_and_stage from a job/worker or the batch command
rather than rely on a short HTTP request timeout. No broker or automatic worker is installed.

The /api/ai/ routes handle research and candidates. The integrated backend decision endpoint is POST /api/review/candidates/<id>/decision/; see M2_DEMO.md. It requires a signed-in Reviewer, CSRF, a pending candidate, and validated review values.
