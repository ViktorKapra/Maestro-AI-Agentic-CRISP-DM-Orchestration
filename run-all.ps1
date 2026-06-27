<#
.SYNOPSIS
    Runs the maads pipeline and then the dashboard (API + UI) in the FOREGROUND,
    streaming all output into the current terminal.

.DESCRIPTION
    Everything runs in this same window so you can watch what happens live:
      1. Pipeline  ->  maads run --case <Case>          (runs to completion)
      2. Dashboard ->  maads dashboard --case <Case>    (blocks; Ctrl+C to stop)
    The dashboard opens the browser at http://127.0.0.1:<Port>/ by itself.
    Nothing is launched as a background process.

.EXAMPLE
    .\run-all.ps1
    .\run-all.ps1 -Case house_prices -Port 8765
    .\run-all.ps1 -Build              # rebuild the frontend first
    .\run-all.ps1 -NoPipeline         # skip the pipeline, only run the dashboard
#>
[CmdletBinding()]
param(
    [string]$Case = "titanic",
    [int]$Port = 8765,
    [switch]$Build,        # rebuild dashboard/dist before starting
    [switch]$NoPipeline    # skip the pipeline, start only the dashboard
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- Python from the venv ---------------------------------------------------
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "venv Python not found: $python  (create it with: python -m venv .venv)"
}

# UTF-8 so the emoji in the logs don't trigger 'charmap' errors
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# --- (optional) build the frontend ------------------------------------------
$nodeDir = Join-Path $root ".tools\node-v24.18.0-win-x64"
if ($Build) {
    if (-not (Test-Path $nodeDir)) {
        throw "Portable Node not found in $nodeDir. Drop -Build or install Node."
    }
    Write-Host "==> Building the dashboard frontend..." -ForegroundColor Cyan
    $env:Path = "$nodeDir;$env:Path"
    Push-Location (Join-Path $root "dashboard")
    if (-not (Test-Path "node_modules")) { npm install }
    npm run build
    Pop-Location
}

# --- 1) Pipeline in the FOREGROUND (output streams here) --------------------
if (-not $NoPipeline) {
    Write-Host "==> Running pipeline for '$Case' (live output below)..." -ForegroundColor Cyan
    & $python -m maads run --case $Case
    Write-Host "==> Pipeline finished (exit code $LASTEXITCODE)." -ForegroundColor Cyan
}
































# --- 2) Dashboard (API + UI) in the FOREGROUND -----------------------------
Write-Host "==> Starting dashboard (API + UI) at http://127.0.0.1:$Port/?case=$Case" -ForegroundColor Cyan
Write-Host "    (blocks here; press Ctrl+C to stop)" -ForegroundColor DarkGray
& $python -m maads dashboard --case $Case --port $Port
