@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\Start-Hotdesk.ps1" -InstallOnly
if errorlevel 1 (
  echo.
  echo Installation failed. Please send the error message for help.
) else (
  echo.
  echo Installation complete. Double-click Start.bat to open Hotdesk.
)
pause
endlocal
