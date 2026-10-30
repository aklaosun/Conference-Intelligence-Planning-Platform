# Uploading the integrated M2 code

The new bundle contains the combined application, including the latest backend baseline and
adapted review frontend. It supersedes the older AI-only upload ZIP. No upload/push was performed
by the assistant; the project owner handles that step.

Use a new feature branch and a PR. Review the changes against main before merging. Do not overwrite
new teammate work if main has advanced. Preserve the migrations and both `tests.py` (backend) and
`test_ai.py` (AI), as well as `test_research.py` and `test_integration.py`.

The companion patch is based on main commit `b5ae7f3da326114c043b5ba9e21b06ced09edc1d`.
From a checkout at that baseline, run `git apply --check` against the patch before applying it.
If it reports conflicts, integrate the differences explicitly rather than replacing the repository blindly.
The full ZIP also preserves main's existing planning artifacts and historical M1 prototype.

Keep `.env`, `.venv`, `.m2-demo-login.json`, `.sqlite3` files, local candidate exports and run logs
out of GitHub. The clean bundle excludes those files. `.env.example` and the public captured
examples are intentionally included for setup and repeatable demonstrations.

After uploading, share the branch/PR link and `docs/M2_DEMO.md` with the team. A local URL cannot
be opened from another teammate's computer; use a screen share or let them run their local copy.
