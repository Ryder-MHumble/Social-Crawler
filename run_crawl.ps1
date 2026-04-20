$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
Write-Host "[Deprecated Entry] run_crawl.ps1 -> use .\social_crawler.ps1 task ..."

& ".\social_crawler.ps1" task @args
exit $LASTEXITCODE
