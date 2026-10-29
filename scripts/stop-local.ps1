$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stateFile = Join-Path $projectRoot 'data\local-servers.json'
if (!(Test-Path -LiteralPath $stateFile)) {
    Write-Host 'No managed local servers. No unrelated processes were stopped.'
    exit 0
}
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($entry in $state.PSObject.Properties) {
    $process = Get-Process -Id $entry.Value.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $entry.Value.started) {
        # Include the Python reloader's worker. A reused PID is rejected by its creation timestamp.
        & taskkill.exe /PID $process.Id /T /F
        if ($LASTEXITCODE) { throw "Could not stop BrightFox $($entry.Name)." }
    }
}
Remove-Item -LiteralPath $stateFile
Write-Host 'BrightFox stopped.'
