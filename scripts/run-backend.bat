@echo off
title Ucilnica - API server (7687)
cd /d "%~dp0..\backend"
echo Ucilnica API server - keep this window open while using the app.
echo.
set "UCILNICA_DATA_DIR=%~dp0..\data"
".venv\Scripts\python.exe" run.py --local
echo.
echo The API server stopped.
pause
