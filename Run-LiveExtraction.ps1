param(
    [Parameter(Mandatory=$true)][string]$Url,
    [int]$Year = 0,
    [string]$Model = "gemini-3.5-flash-lite",
    [switch]$SinglePage,
    [ValidateRange(1,5)][int]$MaxPages = 3,
    [string[]]$SourceUrls = @(),
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Run the README setup commands first to create .venv." }
$previousKey = $env:GEMINI_API_KEY
$previousModel = $env:GEMINI_MODEL
$previousSettings = $env:DJANGO_SETTINGS_MODULE
try {
    $envPath = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path -LiteralPath $envPath) -and -not $env:GEMINI_API_KEY) {
        throw "Add GEMINI_API_KEY=your_key to .env in this project folder and save it."
    }
    if ($PSBoundParameters.ContainsKey("Model")) { $env:GEMINI_MODEL = $Model }
    $env:DJANGO_SETTINGS_MODULE = "ccse_platform.ai_local_settings"
    $managePath = Join-Path $PSScriptRoot "ccse-conference-platform\manage.py"
    Write-Host "Checking Gemini key and configured model..."
    & $pythonPath $managePath check_gemini
    if ($LASTEXITCODE -ne 0) { throw "Gemini connection check failed. See the message above." }
    & $pythonPath $managePath migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "Database setup failed." }
    $arguments = @($managePath, "extract_conference", $Url, "--output", (Join-Path $PSScriptRoot "candidate-live.json"))
    if ($Year -gt 0) { $arguments += @("--year", "$Year") }
    $arguments += @("--max-pages", "$MaxPages")
    if ($SinglePage) { $arguments += "--single-page" }
    if ($Force) { $arguments += "--force" }
    foreach ($sourceUrl in $SourceUrls) { $arguments += @("--source-url", $sourceUrl) }
    & $pythonPath @arguments
    if ($LASTEXITCODE -ne 0) { throw "Live extraction failed. Read the message above." }
} finally {
    $env:GEMINI_API_KEY = $previousKey
    $env:GEMINI_MODEL = $previousModel
    $env:DJANGO_SETTINGS_MODULE = $previousSettings
}
