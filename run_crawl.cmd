@echo off
setlocal

cd /d "%~dp0"
echo [Deprecated Entry] run_crawl.cmd ^-^> use social_crawler.ps1 task ...

powershell -NoProfile -ExecutionPolicy Bypass -File ".\social_crawler.ps1" task %*
exit /b %errorlevel%
