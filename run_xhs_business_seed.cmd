@echo off
setlocal

cd /d "%~dp0"
echo [Business Seed Entry] Xiaohongshu business keyword crawl.

if defined PYTHON_BIN (
    "%PYTHON_BIN%" apps\crawler\run_tasks.py xhs_business_seed %*
    exit /b %errorlevel%
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" apps\crawler\run_tasks.py xhs_business_seed %*
    exit /b %errorlevel%
)

if exist ".venv\bin\python" (
    ".venv\bin\python" apps\crawler\run_tasks.py xhs_business_seed %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python apps\crawler\run_tasks.py xhs_business_seed %*
    exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 apps\crawler\run_tasks.py xhs_business_seed %*
    exit /b %errorlevel%
)

echo Python interpreter not found. Please install Python 3.10+.
exit /b 1

