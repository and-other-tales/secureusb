@echo off
REM SecureUSB Daemon Launcher (Windows Service)
REM Note: Windows port uses a different daemon implementation

cd /d "%~dp0"
python src\daemon\service.py %*
if errorlevel 1 (
    echo.
    echo ERROR: Daemon failed to start.
    pause
    exit /b 1
)
