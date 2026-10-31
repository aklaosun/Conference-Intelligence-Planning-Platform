param([string]$ServerUrl='')
$ErrorActionPreference='Stop'
$portable=Join-Path $PSScriptRoot 'client\release\CCSE-Workspace-Portable-0.3.0-x64.exe'
$folderApp=Join-Path $PSScriptRoot 'client\release\win-unpacked\CCSE Conference Workspace.exe'
$previousServer=$env:CCSE_SERVER_URL
$previousLocal=$env:CCSE_LOCAL_DEMO
try{
    if($ServerUrl){$env:CCSE_SERVER_URL=$ServerUrl}else{Remove-Item Env:\CCSE_SERVER_URL -ErrorAction SilentlyContinue;$env:CCSE_LOCAL_DEMO='1'}
    if(Test-Path -LiteralPath $folderApp){Start-Process -FilePath $folderApp;return}
    if(Test-Path -LiteralPath $portable){Start-Process -FilePath $portable;return}
    $client=Join-Path $PSScriptRoot 'client'
    $npm=(Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if(-not $npm){throw 'Use the packaged desktop app, or install Node.js 24 LTS for source development.'}
    if(-not(Test-Path (Join-Path $client 'node_modules\electron\dist\electron.exe'))){throw 'Run .\Build-Desktop.ps1 first, or use the packaged desktop app.'}
    Push-Location $client
    try{& $npm run desktop;if($LASTEXITCODE -ne 0){throw 'Desktop client failed.'}}finally{Pop-Location}
}finally{$env:CCSE_SERVER_URL=$previousServer;$env:CCSE_LOCAL_DEMO=$previousLocal}
