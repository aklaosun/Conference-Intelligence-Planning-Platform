param([ValidateRange(1024,65535)][int]$Port=8020)
$ErrorActionPreference='Stop'
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'Create .venv and install requirements-web.lock.txt first. See README.md.'}
$previousSettings=$env:DJANGO_SETTINGS_MODULE
try {
    $env:DJANGO_SETTINGS_MODULE='ccse_platform.web_settings'
    $manage=Join-Path $PSScriptRoot 'ccse-conference-platform\manage.py'
    & $python $manage migrate --noinput
    if($LASTEXITCODE -ne 0){throw 'Database migrations failed.'}
    & $python $manage setup_web
    if($LASTEXITCODE -ne 0){throw 'Web workspace setup failed.'}
    Write-Host "Open http://127.0.0.1:$Port/app/"
    Write-Host 'Initial administrator login: .web-data/admin-login.json. Keep it private.'
    Write-Host 'Use My account to change your password and People & access to invite users.'
    Write-Host 'Press Ctrl+C to stop the local server.'
    & $python $manage runserver "127.0.0.1:$Port" --noreload
    if($LASTEXITCODE -ne 0){throw 'The local web server stopped with an error.'}
} finally {$env:DJANGO_SETTINGS_MODULE=$previousSettings}
