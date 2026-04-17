$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
Write-Host "[Deprecated Entry] run_crawl.ps1 is kept for compatibility. Target layout: apps/crawler."

if ($env:PYTHON_BIN) {
    & $env:PYTHON_BIN "apps/crawler/run_tasks.py" @args
    exit $LASTEXITCODE
}

if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" "apps/crawler/run_tasks.py" @args
    exit $LASTEXITCODE
}

if (Test-Path ".venv\bin\python") {
    & ".venv\bin\python" "apps/crawler/run_tasks.py" @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python "apps/crawler/run_tasks.py" @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "apps/crawler/run_tasks.py" @args
    exit $LASTEXITCODE
}

Write-Host "Python interpreter not found. Please install Python 3.10+."
exit 1
