@echo off
REM SecureUSB Setup Wizard Launcher
REM Runs the cross-platform CLI setup wizard

cd /d "%~dp0"
python ports\shared\setup_cli.py %*
if errorlevel 1 (
    echo.
    echo ERROR: Setup failed. Please ensure Python 3.11+ is installed.
    pause
    exit /b 1
)
