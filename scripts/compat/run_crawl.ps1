$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Resolve-Path (Join-Path $scriptDir "..\..")
Set-Location $rootDir
Write-Host "[Deprecated Entry] scripts/compat/run_crawl.ps1 -> use .\social_crawler.ps1 task ..."

& ".\social_crawler.ps1" task @args
exit $LASTEXITCODE
