$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$buildEnv=Join-Path $root '.desktop-build-venv'
$python=Join-Path $buildEnv 'Scripts\python.exe'
$npm=(Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
$node=(Get-Command node.exe -ErrorAction SilentlyContinue).Source
if(-not $npm -or -not $node){throw 'Install Node.js 24 LTS, then reopen PowerShell.'}
if(-not(Test-Path -LiteralPath $python)){
    $existing=Join-Path $root '.venv\Scripts\python.exe'
    if(Test-Path -LiteralPath $existing){& $existing -m venv $buildEnv}else{& py -3.12 -m venv $buildEnv}
    if($LASTEXITCODE -ne 0){throw 'Python 3.12 is required to build the desktop backend.'}
}
& $python -m pip install -r (Join-Path $root 'requirements-desktop-build.lock.txt')
if($LASTEXITCODE -ne 0){throw 'Build dependencies could not be installed.'}
Push-Location (Join-Path $root 'client')
try{
    & $npm ci --ignore-scripts
    if($LASTEXITCODE -ne 0){throw 'npm ci failed.'}
    & $node 'node_modules\electron\install.js'
    if($LASTEXITCODE -ne 0){throw 'The official Electron runtime could not be installed.'}
    & $npm run build
    if($LASTEXITCODE -ne 0){throw 'React build failed.'}
}finally{Pop-Location}
$previousSettings=$env:DJANGO_SETTINGS_MODULE
$previousData=$env:CCSE_DESKTOP_DATA_DIR
$previousPythonPath=$env:PYTHONPATH
try{
    $env:DJANGO_SETTINGS_MODULE='ccse_platform.desktop_settings'
    $env:PYTHONPATH=(Join-Path $root 'ccse-conference-platform')+[IO.Path]::PathSeparator+$previousPythonPath
    $env:CCSE_DESKTOP_DATA_DIR=Join-Path $buildEnv 'build-config'
    & $python -m PyInstaller --noconfirm --onedir --name ccse-backend `
      --distpath (Join-Path $root 'desktop-backend\dist') `
      --workpath (Join-Path $root 'desktop-backend\build') `
      --specpath (Join-Path $root 'desktop-backend') `
      --paths (Join-Path $root 'ccse-conference-platform') `
      --collect-all django --collect-all conferences --collect-all ccse_platform `
      --collect-all openpyxl --collect-all pydantic --collect-all pydantic_core --collect-all bs4 --collect-all whitenoise `
      --hidden-import ccse_platform.desktop_settings --hidden-import ccse_platform.urls `
      --hidden-import django.db.backends.sqlite3.base --hidden-import django.contrib.sessions.backends.db `
      --hidden-import django.template.loaders.app_directories --hidden-import django.template.loaders.filesystem `
      --icon (Join-Path $root 'client\electron\icon.ico') (Join-Path $root 'desktop-backend\server_runner.py')
    if($LASTEXITCODE -ne 0){throw 'Bundled backend build failed.'}
}finally{$env:DJANGO_SETTINGS_MODULE=$previousSettings;$env:CCSE_DESKTOP_DATA_DIR=$previousData;$env:PYTHONPATH=$previousPythonPath}
Push-Location (Join-Path $root 'client')
try{
    & $npm run package:windows
    if($LASTEXITCODE -ne 0){throw 'Windows installer packaging failed.'}
    & $npm run package:portable
    if($LASTEXITCODE -ne 0){throw 'Portable packaging failed.'}
    Write-Host 'Ready: client\release\CCSE-Workspace-Setup-0.3.0-x64.exe and CCSE-Workspace-Portable-0.3.0-x64.exe'
}finally{Pop-Location}
