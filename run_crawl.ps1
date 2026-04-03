$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if ($env:PYTHON_BIN) {
    & $env:PYTHON_BIN "tasks/runner/run_crawl.py" @args
    exit $LASTEXITCODE
}

if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" "tasks/runner/run_crawl.py" @args
    exit $LASTEXITCODE
}

if (Test-Path ".venv\bin\python") {
    & ".venv\bin\python" "tasks/runner/run_crawl.py" @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python "tasks/runner/run_crawl.py" @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "tasks/runner/run_crawl.py" @args
    exit $LASTEXITCODE
}

Write-Host "Python interpreter not found. Please install Python 3.10+."
exit 1

