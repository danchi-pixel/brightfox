param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$viteEntry = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $viteEntry)) {
    throw 'Run setup.bat first to install the project dependencies.'
}
# Pin this launcher to this checkout, never a shell's old scratch DB or remote API.
$env:UCILNICA_DATA_DIR = Join-Path $projectRoot 'data'
$env:UCILNICA_API_HOST = '127.0.0.1'
$env:UCILNICA_API_PORT = '7687'
$env:UCILNICA_HOST = '127.0.0.1'
$env:UCILNICA_API_URL = 'http://127.0.0.1:7687'
$env:UCILNICA_LOCAL_FAMILY = 'danijel'
$env:UCILNICA_COOKIE_SECURE = '0'
$env:UCILNICA_BEHIND_PROXY = '0'
Remove-Item Env:UCILNICA_STATIC_DIR -ErrorAction SilentlyContinue
Push-Location $backendDir
try { $expected = (& $pythonExe -c 'from app.config import WORKSPACE_ID; print(WORKSPACE_ID)').Trim() }
finally { Pop-Location }
if ($LASTEXITCODE) { throw 'Cannot read the checkout identity.' }

function Get-Health {
    param([string]$Url)
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 3 } catch { return $null }
}
function Wait-Health {
    param([string]$Url)
    $until = (Get-Date).AddSeconds(60)
    do {
        $health = Get-Health $Url
        if ($health) { return $health }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $until)
    throw "BrightFox did not start: $Url. Check data/logs."
}
$apiListener = Get-NetTCPConnection -LocalPort 7687 -State Listen -ErrorAction SilentlyContinue
$webListener = Get-NetTCPConnection -LocalPort 7686 -State Listen -ErrorAction SilentlyContinue
if ($apiListener) {
    $health = Get-Health 'http://127.0.0.1:7687/api/health'
    if (!$health -or $health.workspace_id -ne $expected -or $health.mode -ne 'local') {
        throw 'Port 7687 is an old or different server. Stop that server before starting this checkout.'
    }
}
if ($webListener) {
    $web = Get-Health 'http://127.0.0.1:7686/__brightfox_local'
    if (!$web -or $web.workspace_id -ne $expected -or $web.mode -ne 'development') {
        throw 'Port 7686 is an old build or another project. Stop that server before starting this checkout.'
    }
}
Push-Location $backendDir
try {
    & $pythonExe -m app.local_setup
    if ($LASTEXITCODE) { throw 'Local profile setup failed; no servers were started.' }
} finally { Pop-Location }
$logDir = Join-Path $env:UCILNICA_DATA_DIR 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stateFile = Join-Path $env:UCILNICA_DATA_DIR 'local-servers.json'
$processState = @{}
if (Test-Path -LiteralPath $stateFile) {
    $saved = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    foreach ($entry in $saved.PSObject.Properties) { $processState[$entry.Name] = $entry.Value }
}
function Save-Server {
    param([string]$Name, [System.Diagnostics.Process]$Process)
    $processState[$Name] = @{ id = $Process.Id; started = $Process.StartTime.ToUniversalTime().Ticks.ToString() }
    $processState | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
}
if (!$apiListener) {
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('run.py', '--local') -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'backend.log') -RedirectStandardError (Join-Path $logDir 'backend-error.log')
    Save-Server 'backend' $apiProcess
}
$health = Wait-Health 'http://127.0.0.1:7687/api/health'
if ($health.workspace_id -ne $expected -or $health.mode -ne 'local') { throw 'Backend checkout verification failed.' }
if (!$webListener) {
    $nodeExe = (Get-Command node.exe).Source
    $webProcess = Start-Process -FilePath $nodeExe -ArgumentList @(('"' + $viteEntry + '"'), '--host', '127.0.0.1') -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'frontend.log') -RedirectStandardError (Join-Path $logDir 'frontend-error.log')
    Save-Server 'frontend' $webProcess
}
$web = Wait-Health 'http://127.0.0.1:7686/__brightfox_local'
$proxied = Wait-Health 'http://127.0.0.1:7686/api/health'
if ($web.workspace_id -ne $expected -or $web.mode -ne 'development' -or $proxied.workspace_id -ne $expected -or $proxied.mode -ne 'local') {
    throw 'Frontend or API proxy points to a different checkout.'
}
Write-Host 'BrightFox ready: http://localhost:7686 (current source, automatic content reload).'
if (!$NoBrowser) { Start-Process 'http://localhost:7686' }
