@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment missing. Follow the setup instructions in README.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -u kemove_rgb.py %*
if errorlevel 1 pause
