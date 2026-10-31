# Real CAC conference data

The source workbook contains the sponsor's 35 conference listings. The importer
retains original cells, notes and row provenance, labels year inference, leaves
missing costs unknown, and preserves previously reviewed catalog values.

From the repository root after installing requirements-ai.lock.txt:

    .\Import-CACSpreadsheet.ps1 -Path ".\data\NEW CAC CONFERENCE LIST 2026.xlsx" -DryRun
    .\Import-CACSpreadsheet.ps1 -Path ".\data\NEW CAC CONFERENCE LIST 2026.xlsx"
    .\Start-M2Demo.ps1

Open http://127.0.0.1:8010/ and sign in using your local .m2-demo-login.json.
Open Conferences to browse the imported data. New imported editions need review.
No Gemini key is required for the spreadsheet import.

The workbook is included as the requested source dataset. Local API keys,
credentials, import run reports and database files remain excluded.
