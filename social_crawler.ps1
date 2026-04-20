$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Show-Usage {
    @"
Social-Crawler Unified Launcher (Windows PowerShell)

Usage:
  .\social_crawler.ps1 dev  <start|stop|restart|status|logs> [--attach|-f]
  .\social_crawler.ps1 prod <start|stop|restart|status|logs> [--attach|-f]
  .\social_crawler.ps1 task [run_tasks.py args...]
  .\social_crawler.ps1 menu
  .\social_crawler.ps1 help

Examples:
  .\social_crawler.ps1 dev start
  .\social_crawler.ps1 dev logs -f
  .\social_crawler.ps1 prod restart
  .\social_crawler.ps1 task --list
"@ | Write-Host
}

function Resolve-Python {
    if ($env:PYTHON_BIN) { return $env:PYTHON_BIN }
    if (Test-Path ".venv\Scripts\python.exe") { return ".venv\Scripts\python.exe" }
    if (Test-Path ".venv\bin\python") { return ".venv\bin\python" }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py -3" }
    throw "Python interpreter not found. Please install Python 3.11+."
}

function Invoke-TaskRunner {
    param([string[]]$TaskArgs)
    $pythonCmd = Resolve-Python
    if ($pythonCmd -eq "py -3") {
        & py -3 "apps/crawler/run_tasks.py" @TaskArgs
    } else {
        & $pythonCmd "apps/crawler/run_tasks.py" @TaskArgs
    }
    exit $LASTEXITCODE
}

function Ensure-Bash {
    if (Get-Command bash -ErrorAction SilentlyContinue) { return }
    throw "bash not found. For dev/prod control on Windows, install Git Bash or run this in WSL."
}

function Invoke-ShBridge {
    param(
        [string]$ScriptName,
        [string[]]$ForwardArgs
    )
    Ensure-Bash

    $escapedRoot = $RootDir.Replace("\", "/")
    $joinedArgs = ""
    if ($ForwardArgs.Count -gt 0) {
        $joinedArgs = " " + (($ForwardArgs | ForEach-Object { "'" + ($_ -replace "'", "'\\''") + "'" }) -join " ")
    }
    $cmd = "cd '$escapedRoot' && ./$ScriptName$joinedArgs"
    & bash -lc $cmd
    exit $LASTEXITCODE
}

function Show-Menu {
    while ($true) {
        @"

Choose an action:
  1) dev start
  2) dev stop
  3) dev logs -f
  4) prod start
  5) prod stop
  6) prod logs -f
  7) task --list
  8) task (custom args)
  9) help
  0) exit
"@ | Write-Host

        $choice = Read-Host "> "
        switch ($choice) {
            "1" { Invoke-ShBridge -ScriptName "start_dev_local.sh" -ForwardArgs @("start") }
            "2" { Invoke-ShBridge -ScriptName "start_dev_local.sh" -ForwardArgs @("stop") }
            "3" { Invoke-ShBridge -ScriptName "start_dev_local.sh" -ForwardArgs @("logs", "-f") }
            "4" { Invoke-ShBridge -ScriptName "start_prod_server.sh" -ForwardArgs @("start") }
            "5" { Invoke-ShBridge -ScriptName "start_prod_server.sh" -ForwardArgs @("stop") }
            "6" { Invoke-ShBridge -ScriptName "start_prod_server.sh" -ForwardArgs @("logs", "-f") }
            "7" { Invoke-TaskRunner -TaskArgs @("--list") }
            "8" {
                $raw = Read-Host "run_tasks args"
                if ([string]::IsNullOrWhiteSpace($raw)) { continue }
                $parts = $raw.Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
                Invoke-TaskRunner -TaskArgs $parts
            }
            "9" { Show-Usage }
            "0" { exit 0 }
            default { Write-Host "Unknown choice: $choice" }
        }
    }
}

if ($args.Count -eq 0) {
    Show-Usage
    if ($Host.Name -ne "ServerRemoteHost") {
        Show-Menu
    }
    exit 0
}

$action = $args[0]
$rest = @()
if ($args.Count -gt 1) {
    $rest = $args[1..($args.Count - 1)]
}

switch ($action) {
    "dev" {
        if ($rest.Count -eq 0) { Show-Usage; exit 1 }
        Invoke-ShBridge -ScriptName "start_dev_local.sh" -ForwardArgs $rest
    }
    "prod" {
        if ($rest.Count -eq 0) { Show-Usage; exit 1 }
        Invoke-ShBridge -ScriptName "start_prod_server.sh" -ForwardArgs $rest
    }
    "task" {
        Invoke-TaskRunner -TaskArgs $rest
    }
    "menu" {
        Show-Menu
    }
    "help" {
        Show-Usage
    }
    "-h" {
        Show-Usage
    }
    "--help" {
        Show-Usage
    }
    default {
        Write-Host "Unknown action: $action"
        Show-Usage
        exit 1
    }
}
