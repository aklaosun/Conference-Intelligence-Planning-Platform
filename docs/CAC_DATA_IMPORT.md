# Real CAC spreadsheet data

Run from the project root with the sponsor workbook on your computer:

```powershell
.\Import-CACSpreadsheet.ps1 -Path ".\data\NEW CAC CONFERENCE LIST 2026.xlsx" -DryRun
.\Import-CACSpreadsheet.ps1 -Path ".\data\NEW CAC CONFERENCE LIST 2026.xlsx"
.\Start-M2Demo.ps1
```

Stop an already running server before restarting it after installing the code update.
The importer uses the local demo database and does not require a Gemini key.
The default workbook path is your Downloads folder if `-Path` is omitted.

The supplied workbook contains 35 populated conference rows, Sheet1 rows 3 through 37.
All 35 rows are retained with workbook name, SHA256, worksheet, source row, original
values, notes, focus area, category and other listed events. Open a conference to see
Imported spreadsheet data and expand Original spreadsheet values. CSV export includes
the spreadsheet provenance and notes as additional columns.

Explicit event dates take precedence over the 2026 workbook title. Missing event years
are inferred from the conference name or website URL where identifiable, otherwise the
workbook heading; those inferences are labeled for review. The ATC25 link is provisionally
interpreted as a 2025 edition. This does not verify that the website has current information.
Five rows have no event dates and retain unknown dates. Single listed dates do not imply
an end date. A long date range is flagged for review rather than corrected by guessing.
Original spelling and location text are preserved.

Every cost cell in this supplied workbook is blank. Import creates no registration prices,
and unknown amounts are not treated as free. Prices from previously reviewed website
research remain attached to their existing edition.

New imported editions need review. Import preserves existing edition values and verification
states, including the already reviewed Computing Frontiers edition, while attaching its
spreadsheet source. Exact reimports do not duplicate rows or source snapshots. An edited
workbook attaches a new source snapshot for review instead of silently replacing catalog values.

The local reconciliation report is `.m2-cac-import-report.json`, ignored by Git.
The requested source workbook is included at data/NEW CAC CONFERENCE LIST 2026.xlsx. Keep local databases, API keys, credentials and import run reports out of source control. The importer makes no external website requests.
