# Backend setup

## First time

1. `pip install -r requirements.txt`
2. Copy `ccse_platform/local_settings.example.py` to `ccse_platform/local_settings.py` and put in your own Postgres password. This file is git-ignored, so passwords stay off GitHub.
3. `python manage.py migrate`
4. `python manage.py setup_roles` (creates the Reviewers and Editors groups)
5. `python manage.py createsuperuser`
6. `python manage.py runserver`, then open http://127.0.0.1:8000

Add people to groups in the admin at /admin (Users, pick a user, Groups).

## Roles

| Who | Can do |
|---|---|
| Any logged-in user | View dashboard, conferences, review queue, export CSV |
| Editors | Add and edit conferences, editions, deadlines, prices |
| Reviewers | Everything Editors can, plus Approve / Correct / Reject AI suggestions |
| Superuser | Everything |

## Pages

| URL | What it is |
|---|---|
| `/` | Dashboard: counts, deadlines in the next 60 days, upcoming conferences |
| `/conferences/` | Search and filter (text, center, year, format, status, upcoming) |
| `/conferences/export.csv` | CSV of whatever the current filters show |
| `/conferences/<id>/` | One conference with every yearly edition |
| `/review/` | Queue of AI suggestions |
| `/review/<id>/` | Evidence for each field, plus the correct-and-approve and reject forms |

## Sending extraction results (for the AI side)

Set `EXTRACTION_API_TOKEN` in `local_settings.py` (or as an environment variable). The endpoint is off until it's set.

```
POST /api/candidates/
Authorization: Bearer <EXTRACTION_API_TOKEN>
Content-Type: application/json
```

Body is the same JSON as the sample extraction output. Required: `requested_url`, `fields.conference_name.value`, `fields.year.value`. `deadlines`, `registration_prices`, `warnings` and `sources` must be lists if present. The whole body is stored untouched in `raw_payload`.

Returns `201 {"id": 12, "status": "needs_review"}`, `400 {"errors": [...]}` or `401`.

```
curl -X POST http://127.0.0.1:8000/api/candidates/ -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" -d @sample.json
```

## Importing the legacy spreadsheet

```
python manage.py import_legacy_excel path\to\conferences.xlsx --dry-run
python manage.py import_legacy_excel path\to\conferences.xlsx
```

Options: `--sheet "Sheet name"`, `--header-row 2`, `--default-year 2026`.

Columns are matched by header name (for example "Conference Name", "Dates", "Location", "Website", "Center", "Registration Cost", "Early Bird Deadline"). The command prints the mapping and any columns it ignored, so do a dry run first. Imported editions are marked Needs Review, and Partial Information when the date or location is missing. Running it again skips editions that already exist.

## Tests

`python manage.py test conferences`
