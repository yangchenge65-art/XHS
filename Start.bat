@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\Start-Hotdesk.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Please send the error message for help.
  pause
)
endlocal
