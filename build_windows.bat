@echo off
setlocal
echo ============================================================
echo           IRIS AI — Windows Build & Packaging Tool          
echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed with exit code %ERRORLEVEL%.
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] Windows packaging complete.
endlocal
