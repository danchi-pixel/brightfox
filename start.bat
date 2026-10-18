@echo off
setlocal EnableExtensions
title Ucilnica
cd /d "%~dp0"

rem Usage:  start.bat        -> normal mode (fast, built web app)
rem         start.bat dev    -> developer mode (Vite dev server with hot reload)
set "MODE=%~1"

echo.
echo  Ucilnica is starting...
echo.

if not exist "backend\.venv\Scripts\python.exe" (
  echo  First run detected - running setup...
  call "%~dp0setup.bat" --no-pause
  if errorlevel 1 goto :fail
)
if not exist "frontend\node_modules" (
  call "%~dp0setup.bat" --no-pause
  if errorlevel 1 goto :fail
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\port-in-use.ps1" -Port 7686
if not errorlevel 1 (
  echo  Ucilnica already seems to be running. Opening it in your browser...
  start "" "http://localhost:7686"
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\port-in-use.ps1" -Port 7687
if not errorlevel 1 (
  echo  [X] Port 7687 is used by another program. Close it ^(or run stop.bat^) and try again.
  goto :fail
)

if /i not "%MODE%"=="dev" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\needs-build.ps1"
  if errorlevel 1 (
    echo  Building the web app...
    pushd "frontend"
    call npm run build
    if errorlevel 1 ( popd & goto :fail )
    popd
  )
)

start "Ucilnica - API server (7687)" /min "%~dp0scripts\run-backend.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\wait-url.ps1" -Url "http://127.0.0.1:7687/api/health" -Seconds 90
if errorlevel 1 (
  echo  [X] The API server did not start. Check the "Ucilnica - API server" window for errors.
  goto :fail
)
echo  [OK] API server running on http://127.0.0.1:7687

start "Ucilnica - Web app (7686)" /min "%~dp0scripts\run-frontend.bat" %MODE%
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\wait-url.ps1" -Url "http://127.0.0.1:7686/" -Seconds 90
if errorlevel 1 (
  echo  [X] The web app did not start. Check the "Ucilnica - Web app" window for errors.
  goto :fail
)
echo  [OK] Web app running on http://localhost:7686
echo.
start "" "http://localhost:7686"
echo  Ucilnica is open in your browser. Use stop.bat (or close the two minimized windows) to stop.
echo.
ping -n 7 127.0.0.1 >nul
exit /b 0

:fail
echo.
pause
exit /b 1
