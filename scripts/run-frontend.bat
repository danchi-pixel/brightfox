@echo off
title Ucilnica - Web app (7686)
cd /d "%~dp0..\frontend"
echo Ucilnica web app - keep this window open while using the app.
echo.
call npm run dev
echo.
echo The web app stopped.
pause
