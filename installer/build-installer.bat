@echo off
REM Simple batch wrapper for the PowerShell build script

echo Building Circa RFID Edge Service Installer...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0build-installer.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build failed with error code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Build completed successfully!
pause

