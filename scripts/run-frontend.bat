@echo off
title Ucilnica - Web app (7686)
cd /d "%~dp0..\frontend"
echo Ucilnica web app - keep this window open while using the app.
echo.
if /i "%~1"=="dev" (
  call npm run dev
) else (
  call npm run preview
)
echo.
echo The web app stopped.
pause
