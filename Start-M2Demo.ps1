param([ValidateRange(1024,65535)][int]$Port=8010,[switch]$NewReview)
$ErrorActionPreference="Stop"
$pythonPath=Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$managePath=Join-Path $PSScriptRoot "ccse-conference-platform\manage.py"
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Create .venv and install requirements-ai.lock.txt first." }
$previousSettings=$env:DJANGO_SETTINGS_MODULE
try {
    $env:DJANGO_SETTINGS_MODULE="ccse_platform.ai_local_settings"
    & $pythonPath $managePath migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
    $demoArguments=@()
    if ($NewReview) { $demoArguments += "--new-review" }
    & $pythonPath $managePath setup_m2_demo @demoArguments
    if ($LASTEXITCODE -ne 0) { throw "Demo setup failed." }
    & $pythonPath $managePath setup_platform --local-owner
    if ($LASTEXITCODE -ne 0) { throw "Workspace setup failed." }
    Write-Host ""
    Write-Host "Open http://127.0.0.1:$Port/app/"
    Write-Host "Login details: .m2-demo-login.json (keep this local)."
    Write-Host "Press Ctrl+C here to stop the demo."
    & $pythonPath $managePath runserver "127.0.0.1:$Port" --noreload
} finally {
    $env:DJANGO_SETTINGS_MODULE=$previousSettings
}

