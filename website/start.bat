@echo off
setlocal

set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend

echo === SmartEV -- Local startup ===

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: python not found. Install Python 3.9+ and re-run.
  exit /b 1
)

cd /d "%BACKEND_DIR%"

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q -r requirements.txt

echo.
echo   SmartEV is starting at http://localhost:8000
echo   Landing page : http://localhost:8000/
echo   Dashboard    : http://localhost:8000/dashboard
echo   API docs     : http://localhost:8000/api/docs
echo   Press Ctrl+C to stop.
echo.

python main.py
