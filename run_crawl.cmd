@echo off
setlocal

cd /d "%~dp0"

if defined PYTHON_BIN (
    "%PYTHON_BIN%" tasks\runner\run_crawl.py %*
    exit /b %errorlevel%
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tasks\runner\run_crawl.py %*
    exit /b %errorlevel%
)

if exist ".venv\bin\python" (
    ".venv\bin\python" tasks\runner\run_crawl.py %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python tasks\runner\run_crawl.py %*
    exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 tasks\runner\run_crawl.py %*
    exit /b %errorlevel%
)

echo Python interpreter not found. Please install Python 3.10+.
exit /b 1

