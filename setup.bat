@echo off
setlocal EnableExtensions
title Ucilnica - Setup
cd /d "%~dp0"

echo.
echo  ===============================================
echo    Ucilnica - one-time setup
echo  ===============================================
echo.

rem ---------------------------------------------------------------- Python
rem Prefer a real Python install by path: on this PC the bare "python"/"py" can be the Microsoft Store
rem alias, which hangs instead of running.
set "PY="
for %%V in (312 313) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
)
if not defined PY (
  echo [X] Python 3.12 was not found in %LOCALAPPDATA%\Programs\Python.
  echo     Install it from https://www.python.org/downloads/  or:  winget install Python.Python.3.12
  goto :fail
)
echo [OK] Python: %PY%

rem ---------------------------------------------------------------- Node.js
where node >nul 2>&1
if errorlevel 1 (
  echo [X] Node.js was not found. Install the LTS version from https://nodejs.org/
  goto :fail
)
for /f "delims=" %%N in ('node --version') do echo [OK] Node.js %%N

rem ---------------------------------------------------------------- Backend
echo.
echo Installing backend (Python) packages...
if not exist "backend\.venv\Scripts\python.exe" (
  "%PY%" -m venv "backend\.venv"
  if errorlevel 1 goto :fail
)
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt" --quiet
if errorlevel 1 goto :fail
rem Windows Smart App Control blocks SQLAlchemy's freshly installed compiled speed-ups ("An Application
rem Control policy has blocked this file"). SQLAlchemy ships the same modules as plain Python, so remove the
rem compiled copies on this PC (the server runs Linux and keeps them). Never switch Smart App Control off.
powershell -NoProfile -Command "Get-ChildItem 'backend\.venv\Lib\site-packages\sqlalchemy' -Recurse -Filter '*_cy.*.pyd' | Remove-Item -Force"
"backend\.venv\Scripts\python.exe" -c "import sqlalchemy, alembic, fastapi, anthropic" || goto :fail
echo [OK] Backend packages installed

rem ---------------------------------------------------------------- Frontend
echo.
echo Installing frontend (Node) packages...
pushd "frontend"
call npm install --no-audit --no-fund
if errorlevel 1 ( popd & goto :fail )
echo.
echo Building the web app...
call npm run build
if errorlevel 1 ( popd & goto :fail )
popd
echo [OK] Web app built

echo.
echo  Setup complete. Start the app with start.bat
echo.
if /i not "%~1"=="--no-pause" pause
exit /b 0

:fail
echo.
echo  Setup did not finish. Fix the problem above and run setup.bat again.
if /i not "%~1"=="--no-pause" pause
exit /b 1
