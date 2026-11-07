# Free shared prototype hosting

Use a Render **Free web service** and a Neon **Free PostgreSQL project**. This is a shared demonstration environment with application-level accounts. Do not enable paid compute, paid database tiers, disks, workers, or cron services. Free plans have quotas and may pause or sleep; they are not a production availability commitment.

Official references: [Render free services](https://render.com/docs/free), [Neon Free plan](https://neon.com/pricing), [Django on Render](https://render.com/docs/deploy-django).

## First deployment

1. Publish the reviewed source branch containing `render.yaml`, the 0.4.0 web update, and deployment fixes to the team repository. A local working copy is not available to Render until it is pushed. Use a pull request; no force push is needed.
2. In a Neon Free project, create the PostgreSQL database and obtain its TLS connection string. Keep the database password and connection string private. Choose a region close to the web service. Do not use the expiring Render Free PostgreSQL database for the final milestone.
3. Create a Render Blueprint from that exact source branch and review its plan. It must contain one Free Docker web service and no paid resources. Automatic source deployment is disabled in this blueprint.
4. Set `DATABASE_URL` to the private Neon connection string. Set `BOOTSTRAP_ADMIN_EMAIL` and a strong unique `BOOTSTRAP_ADMIN_PASSWORD` privately. Set a private `DJANGO_SECRET_KEY` of at least 50 characters (for example, 48 cryptographically random bytes encoded as hex). Render’s default generated value may be too short for this application. `RENDER_EXTERNAL_URL` supplies the initial HTTPS origin; use `PUBLIC_BASE_URL` when moving to a university domain.
5. Approve deployment. Startup applies migrations, creates role permissions, imports the public 35-conference seed only if the database is empty, and creates the first administrator only if no active root administrator exists. Existing data and passwords are preserved on later deployments.
6. Verify the HTTPS `/health/` endpoint, sign in at `/app/`, change the initial password, and test roles, invitation acceptance, real catalog, alerts, saved plans, and export. Once the administrator is confirmed, remove the bootstrap password variable. It is not needed when an active administrator already exists.
7. Invite the team, professor, and sponsor using People & access. Give each person a private account with an appropriate role. Do not distribute a shared administrator password.

Live Gemini research is optional: set `GEMINI_API_KEY` privately in the Render service environment. Browsing, saved reviews, planning, outcomes, and export work without a key. Local AI settings are deliberately unavailable on hosted settings.

## Persistence and later migration

All users and application data live in PostgreSQL, not the web service's temporary disk. Keep independent PostgreSQL backups and retain the source branch and runtime configuration. The university can run the same Docker image/application against a new PostgreSQL instance; migrate the database and set the new HTTPS origin, database URL, and private Django secret. Hosting accounts and passwords are not part of the source repository.

The independent hosted workspace starts with the public seed. Personal local desktop/browser databases and their private credentials are not automatically uploaded. Any later import of personal saved plans or decisions should be a deliberate migration.

## Current validation limit

Local account/theme/alert tests and deployment initialization tests pass. Docker is not installed in the local environment, so the Linux image build and live PostgreSQL/HTTPS acceptance must be verified during the first cloud deployment. A deployment is complete only after a live URL and successful application checks are available.

## Gemini and email

Use **Service connections** as an administrator to check Gemini access and request a single test email to your own account address. Never enter API keys into the application or commit them to Git.

Set these privately in the Render service environment:

| Variable | Value |
| --- | --- |
| `GEMINI_API_KEY` | Full existing Google AI Studio key |
| `GEMINI_MODEL` | An available model with a free tier; currently configured as `gemini-3.5-flash-lite` |
| `EMAIL_PROVIDER` | `brevo` |
| `BREVO_API_KEY` | Private Brevo API key, not the SMTP password |
| `DEFAULT_FROM_EMAIL` | Verified sender, e.g. `CCSE Conference Workspace <verified-address@example.org>` |
| `WORKSPACE_EMAIL_ENABLED` | `1`, only after the sender is verified |
| `REPORT_JOB_TOKEN` | A separate private random token of at least 48 characters |

Render Free blocks standard SMTP ports. The Brevo backend sends over HTTPS without another Python dependency. Create a **Free** Brevo account, activate transactional email, and verify the sender first. Personal sender domains may be rewritten to Brevo’s domain; reliable branded delivery later needs a domain the team controls. Provider acceptance does not prove inbox delivery. Verify the test email in the inbox/spam folder. Never enable paid auto-upgrades.

People & access offers an explicit checkbox to email a newly created invitation. It is off by default. If provider acceptance fails, the valid private link remains available for manual sharing. Invites still expire after three days and can only be accepted once.

### Free weekly-report scheduler

1. Merge the reviewed workflow `.github/workflows/weekly-reports.yml` into the repository’s **default branch**. GitHub scheduled workflows do not run from a feature branch. The Linux runner is free for this public repository; do not move it to a paid runner.
2. Store the same private `REPORT_JOB_TOKEN` value in Render and in the repository Actions secret **`CCSE_REPORT_JOB_TOKEN`**. Do not reuse a password, Django signing key, or API key.
3. Enable GitHub Actions and run **Weekly conference reports → Run workflow** to verify the hook. No emails are sent unless a subscription is explicitly enabled and due that day. The hook is POST-only, bearer-protected, and returns counts without report contents.
4. In Reports & outcomes, add each agreed recipient, select their weekday, and explicitly enable delivery. Only send reports to approved recipients.

The workflow calls the hosted service daily at **14:17 UTC**; Django selects subscriptions due on the current America/New_York calendar day. The first request may wake the free service. Schedules may be delayed and GitHub can disable schedules after prolonged repository inactivity. Each subscription is recorded once per week, and a stable Brevo idempotency key helps avoid duplicates on retries. Email-provider acceptance can be ambiguous after timeouts: inspect Brevo activity before manually resending. This does not send deadline/follow-up emails; those remain in-app alerts.

Official references: [Render Free restrictions](https://render.com/docs/free), [Brevo transactional API](https://developers.brevo.com/reference/send-transac-email), [Brevo sender verification](https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email), [GitHub scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
