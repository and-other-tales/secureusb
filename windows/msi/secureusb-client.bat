@echo off
REM SecureUSB GUI Client Launcher
REM Note: Windows port may use PySide6 instead of GTK4

cd /d "%~dp0"
python src\gui\client.py %*
if errorlevel 1 (
    echo.
    echo ERROR: Client failed to start.
    pause
    exit /b 1
)
