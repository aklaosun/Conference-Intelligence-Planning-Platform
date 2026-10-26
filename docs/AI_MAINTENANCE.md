# School maintenance and configuration

## Ownership

For ongoing use, the school should own the Gemini API project, billing choice, and credentials.
Keep public conference page text separate from internal sponsor or student information.
Model availability and quotas are account-dependent; check AI Studio rather than assuming a fixed free quota.
There is no automatic paid fallback or retry loop.

## Secrets

.env is a local convenience file; .env.example is safe to share.
Do not upload .env, local databases, .venv, or command output containing credentials.
Deployments should inject GEMINI_API_KEY and GEMINI_MODEL through their secret configuration.
A populated local .env key takes priority over a process key; omit .env in production when using managed secrets.
Rotate the key in AI Studio and update the secret locally/server-side when ownership changes.

## Providers and models

Gemini uses REST generateContent with JSON output and a simplified response schema.
Pydantic applies the stricter constraints locally after the API returns.
No model tools, code execution, or external actions are enabled.

To change the model, update GEMINI_MODEL or use the runner's -Model option.
check_gemini lists/checks model access without generating content.
To change provider, implement the Provider interface from conferences/ai_service.py.
Keep validation, provenance, and pending-review storage unchanged.

A 429 stops inference/batch processing. Wait for the project's reset or lower the requested load.
Changing models should not silently opt the school into paid usage.

## Database and hosting

ai_local_settings.py uses SQLite for local development/tests and enables local debug behavior.
The team's base settings retain PostgreSQL. Set database credentials through environment variables;
requirements-postgres.txt supplies the optional PostgreSQL driver.
PostgreSQL execution has not been tested in this local environment.

Use a distinct DJANGO_SECRET_KEY, restrict ALLOWED_HOSTS, configure HTTPS/session settings and static files,
and use the school's approved deployment process. Do not deploy local development settings.
Select a worker/scheduler for refresh_conferences and ensure failed run reports are reviewed.

URL checks reject resolved private/non-global addresses, credentials in URLs, non-web schemes,
and nonstandard web ports. Redirect targets are rechecked.
A production host also needs outbound network restrictions to defend against DNS rebinding.
The AI component is a prototype for public HTML, not a general arbitrary-URL proxy.

## Changes and cache policy

Source text plus request scope, model, prompt version, and pipeline version form the fingerprint.
Unchanged sources reuse a previous candidate without further extraction calls.
Increase PROMPT_VERSION or PIPELINE_VERSION when behavior changes; use --force for a one-off reevaluation.
Deduplication is intended for the sequential worker; concurrent web requests can still create duplicate candidates.
No trusted records are touched during refreshes.

## Known limitations

- One-hop companion retrieval, at most five successfully analyzed pages.
- 2 MB body limit per page and 60,000 analyzed characters per page.
- No PDF parsing, browser rendering, external CSS fetching, or open-web search/discovery.
- Quote matching and schemas do not establish semantic truth.
- Missing or conflicting facts remain for human review; source-specific evaluation is still necessary.
- No sponsor-specific relevance score or ROI is invented without approved criteria.
- The existing backend approval function needs the fixes listed in AI_HANDOFF.md before production use.
