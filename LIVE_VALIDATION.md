> M2 integration update (October 30): see [the current demo guide](docs/M2_DEMO.md). The AI-only handoff and earlier test counts below are historical.

# AI validation — October 26, 2026

## Automated checks

89 tests pass on Python 3.12 / Django 5.2.18 with the pinned dependencies.
Django system checks report no issues. makemigrations --check --dry-run reports no changes.
The browser integration module passes Node syntax checking.

Coverage includes public URL/redirect validation, crossed-out content, provider errors, key loading,
dates, edition mismatch, currency and amount evidence, APC/surcharge exclusion, source provenance,
multi-page conflicts, track-specific deadlines, AoE normalization, duplicate removal, missing metadata,
unchanged detection, force refresh, changed values, partial-source/provider failures, manifest validation,
batch failure reporting, candidate pagination, permissions, CSRF rejection and successful CSRF bootstrap,
and idempotent AI-role configuration.

The test suite uses deterministic synthetic provider results; it does not make billable/live API calls.

## Live checks

Computing Frontiers 2026:
- Three official pages analyzed: homepage, registration page, and technical program.
- May 19–21, 2026 and Catania, Sicily, Italy matched the official homepage.
- Current February 1 submission dates were retained; crossed-out January dates were excluded.
- Six explicitly published registration tiers were recovered from the registration page in EUR.
- The late-fee increment was left as a formula warning rather than calculated into an unpublished total.
- Publication APCs and extra-page charges were excluded from attendance registration.
- AoE was retained only as a deadline convention.
- The final live sample includes ten supported deadline rows and one descriptive conference-name variation
  exposed as a conflict. A missing theme quote was removed rather than silently accepted.

DjangoCon US 2026:
- A separate official homepage was analyzed.
- August 24–28, 2026 and the published Chicago venue matched the source.
- Unestablished attendance-format and registration-price values remained unknown with warnings.

A repeated real-source run demonstrated unchanged-content reuse without Gemini extraction calls.
Prompt/pipeline/model/scope changes intentionally invalidate cached results.
All live extractions remained needs_review. No trusted catalog records were written.

See examples/live-computing-frontiers-candidate.json and examples/live-djangocon-candidate.json.
Distributed examples omit full source text snapshots; the local database retains them for review.

## Evidence and limits

Primary sources:
- https://www.computingfrontiers.org/2026/
- https://www.computingfrontiers.org/2026/registration.html
- https://www.computingfrontiers.org/2026/program.html
- https://2026.djangocon.us/

These are sample acceptance checks, not an accuracy percentage or proof of completeness across websites.
Humans must review every candidate and resolve warnings/conflicts before approval.
PostgreSQL, a production host, a scheduler, and the team's final review interface were not exercised here.
