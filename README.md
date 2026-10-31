# CCSE Conference Workspace — desktop prototype

The updated Electron/React local demo bundles Django and the real 35-conference CAC dataset. Each computer has its own saved data. Start with [the desktop walkthrough](docs/DESKTOP_AND_SHARED_ACCESS.md) and [the project-plan status](docs/REQUIREMENTS_STATUS.md). Windows release executables are distributed separately from source. `Build-Desktop.ps1` rebuilds them.

The original source-project workflow below remains available.

---

# CCSE Conference Intelligence — integrated M2 prototype

An authenticated Django application connecting Gemini research, source-backed human review,
approval/rejection, the conference catalog, search, and CSV export.

Start with **[the M2 demo guide](docs/M2_DEMO.md)**. Run from this repository's root:

```powershell
.\Start-M2Demo.ps1
```

Open http://127.0.0.1:8010/ and use the private login in `.m2-demo-login.json`.
First-time installation and a five-minute walkthrough are in the guide.
The captured official-site example works without a Gemini key; fresh research uses your private `.env`.

The application combines the backend from `main` at `b5ae7f3`, the review interface adapted from
Jonathan's `jonathan-m2-review` at `a1c6fa7`, and the AI contribution at `637055b`.
Decisions now save to Django instead of downloading a proposed decision for later integration.
The original M1 HTML prototype and planning artifacts remain historical references.

Validation: **144 Django tests pass**, no missing migrations, and an actual browser walkthrough
confirmed fresh Gemini extraction, source review, corrected-value approval, rejection, catalog
persistence and CSV download. See [the validation record](docs/M2_VALIDATION.md).

This is a local development prototype. PostgreSQL deployment, hosted access, scheduled workers,
notifications and broader website evaluation remain separate work.
Never upload `.env`, `.venv`, `.m2-demo-login.json`, or local database files.
