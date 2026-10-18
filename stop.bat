@echo off
setlocal
cd /d "%~dp0"
echo Stopping Ucilnica...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 7686,7687 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop; Write-Host ('  stopped process ' + $_) } catch {} }"
taskkill /FI "WINDOWTITLE eq Ucilnica - API server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Ucilnica - Web app*" /T /F >nul 2>&1
echo Done.
ping -n 3 127.0.0.1 >nul
