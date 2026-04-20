$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir
$LauncherDir = "scripts/launcher"

function Show-Usage {
    @"
Social-Crawler 统一入口 (Windows PowerShell)

直接运行:
  .\social_crawler.ps1
  .\social_crawler.ps1 menu
  .\social_crawler.ps1 help

开发环境:
  .\social_crawler.ps1 dev start
  .\social_crawler.ps1 dev stop
  .\social_crawler.ps1 dev status
  .\social_crawler.ps1 dev logs -f

生产环境:
  .\social_crawler.ps1 prod start
  .\social_crawler.ps1 prod stop
  .\social_crawler.ps1 prod status
  .\social_crawler.ps1 prod logs -f

任务执行:
  .\social_crawler.ps1 task --list
  .\social_crawler.ps1 task sentiment_monitor

说明:
  - 不带参数时会打印帮助；在交互终端中会进入菜单
  - dev/prod 真实实现已收拢到 scripts/launcher/
  - 根目录对外只保留这一个 PowerShell 入口
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
        [string]$ScriptPath,
        [string[]]$ForwardArgs
    )
    Ensure-Bash

    $escapedRoot = $RootDir.Replace("\", "/")
    $escapedHint = ".\\social_crawler.ps1" -replace "'", "'\\''"
    $joinedArgs = ""
    if ($ForwardArgs.Count -gt 0) {
        $joinedArgs = " " + (($ForwardArgs | ForEach-Object { "'" + ($_ -replace "'", "'\\''") + "'" }) -join " ")
    }
    $cmd = "cd '$escapedRoot' && SOCIAL_CRAWLER_CMD_HINT='$escapedHint' ./$ScriptPath$joinedArgs"
    & bash -lc $cmd
    exit $LASTEXITCODE
}

function Show-Menu {
    while ($true) {
        @"

请选择操作:
  1) 开发环境启动
  2) 开发环境关闭
  3) 开发环境日志
  4) 生产环境启动
  5) 生产环境关闭
  6) 生产环境日志
  7) 查看任务列表
  8) 自定义任务参数
  9) 查看帮助
  0) exit
"@ | Write-Host

        $choice = Read-Host "> "
        switch ($choice) {
            "1" { Invoke-ShBridge -ScriptPath "$LauncherDir/dev.sh" -ForwardArgs @("start") }
            "2" { Invoke-ShBridge -ScriptPath "$LauncherDir/dev.sh" -ForwardArgs @("stop") }
            "3" { Invoke-ShBridge -ScriptPath "$LauncherDir/dev.sh" -ForwardArgs @("logs", "-f") }
            "4" { Invoke-ShBridge -ScriptPath "$LauncherDir/prod.sh" -ForwardArgs @("start") }
            "5" { Invoke-ShBridge -ScriptPath "$LauncherDir/prod.sh" -ForwardArgs @("stop") }
            "6" { Invoke-ShBridge -ScriptPath "$LauncherDir/prod.sh" -ForwardArgs @("logs", "-f") }
            "7" { Invoke-TaskRunner -TaskArgs @("--list") }
            "8" {
                $raw = Read-Host "run_tasks args"
                if ([string]::IsNullOrWhiteSpace($raw)) { continue }
                $parts = $raw.Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
                Invoke-TaskRunner -TaskArgs $parts
            }
            "9" { Show-Usage }
            "0" { exit 0 }
            default { Write-Host "未知选项: $choice" }
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
        Invoke-ShBridge -ScriptPath "$LauncherDir/dev.sh" -ForwardArgs $rest
    }
    "prod" {
        if ($rest.Count -eq 0) { Show-Usage; exit 1 }
        Invoke-ShBridge -ScriptPath "$LauncherDir/prod.sh" -ForwardArgs $rest
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
        Write-Host "未知操作: $action"
        Show-Usage
        exit 1
    }
}
