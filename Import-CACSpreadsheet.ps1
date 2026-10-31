param(
    [string]$Path=(Join-Path $env:USERPROFILE "Downloads\NEW CAC CONFERENCE LIST 2026.xlsx"),
    [switch]$DryRun
)
$ErrorActionPreference="Stop"
$pythonPath=Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$managePath=Join-Path $PSScriptRoot "ccse-conference-platform\manage.py"
if (-not (Test-Path -LiteralPath $Path)) { throw "Spreadsheet not found: $Path" }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Create .venv and install requirements-ai.lock.txt first." }
$previousSettings=$env:DJANGO_SETTINGS_MODULE
try {
    $env:DJANGO_SETTINGS_MODULE="ccse_platform.ai_local_settings"
    & $pythonPath $managePath migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
    $reportPath=Join-Path $PSScriptRoot ".m2-cac-import-report.json"
    $importArguments=@($Path,"--report",$reportPath)
    if ($DryRun) { $importArguments += "--dry-run" }
    & $pythonPath $managePath import_cac_workbook @importArguments
    if ($LASTEXITCODE -ne 0) { throw "Spreadsheet import failed. Check the error above." }
    Write-Host "Reconciliation report: .m2-cac-import-report.json (keep local)."
} finally {
    $env:DJANGO_SETTINGS_MODULE=$previousSettings
}
