@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" call setup.bat --no-pause
if not exist "frontend\node_modules" call setup.bat --no-pause
rem Localhost always serves current source. start.bat dev remains compatible.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1"
if errorlevel 1 pause
