# Free shared prototype hosting

Use a Render **Free web service** and a Neon **Free PostgreSQL project**. This is a shared demonstration environment with application-level accounts. Do not enable paid compute, paid database tiers, disks, workers, or cron services. Free plans have quotas and may pause or sleep; they are not a production availability commitment.

Official references: [Render free services](https://render.com/docs/free), [Neon Free plan](https://neon.com/pricing), [Django on Render](https://render.com/docs/deploy-django).

## First deployment

1. Publish the reviewed source branch containing `render.yaml`, the 0.4.0 web update, and deployment fixes to the team repository. A local working copy is not available to Render until it is pushed. Use a pull request; no force push is needed.
2. In a Neon Free project, create the PostgreSQL database and obtain its TLS connection string. Keep the database password and connection string private. Choose a region close to the web service. Do not use the expiring Render Free PostgreSQL database for the final milestone.
3. Create a Render Blueprint from that exact source branch and review its plan. It must contain one Free Docker web service and no paid resources. Automatic source deployment is disabled in this blueprint.
4. Set `DATABASE_URL` to the private Neon connection string. Set `BOOTSTRAP_ADMIN_EMAIL` and a strong unique `BOOTSTRAP_ADMIN_PASSWORD` privately. Render generates the Django secret. `RENDER_EXTERNAL_URL` supplies the initial HTTPS origin; use `PUBLIC_BASE_URL` when moving to a university domain.
5. Approve deployment. Startup applies migrations, creates role permissions, imports the public 35-conference seed only if the database is empty, and creates the first administrator only if no active root administrator exists. Existing data and passwords are preserved on later deployments.
6. Verify the HTTPS `/health/` endpoint, sign in at `/app/`, change the initial password, and test roles, invitation acceptance, real catalog, alerts, saved plans, and export. Once the administrator is confirmed, remove the bootstrap password variable. It is not needed when an active administrator already exists.
7. Invite the team, professor, and sponsor using People & access. Give each person a private account with an appropriate role. Do not distribute a shared administrator password.

Live Gemini research is optional: set `GEMINI_API_KEY` privately in the Render service environment. Browsing, saved reviews, planning, outcomes, and export work without a key. Local AI settings are deliberately unavailable on hosted settings.

## Persistence and later migration

All users and application data live in PostgreSQL, not the web service's temporary disk. Keep independent PostgreSQL backups and retain the source branch and runtime configuration. The university can run the same Docker image/application against a new PostgreSQL instance; migrate the database and set the new HTTPS origin, database URL, and private Django secret. Hosting accounts and passwords are not part of the source repository.

The independent hosted workspace starts with the public seed. Personal local desktop/browser databases and their private credentials are not automatically uploaded. Any later import of personal saved plans or decisions should be a deliberate migration.

## Current validation limit

Local account/theme/alert tests and deployment initialization tests pass. Docker is not installed in the local environment, so the Linux image build and live PostgreSQL/HTTPS acceptance must be verified during the first cloud deployment. A deployment is complete only after a live URL and successful application checks are available.
