<#
.SYNOPSIS
  Publish the current Ucilnica code to the server (https://brightfox.si).

.DESCRIPTION
  Packs the source code (never the local data folder), uploads it, then on the server:
  backs up the database and photos, builds the new image and restarts - rolling back automatically
  if the new version doesn't start correctly. Runs on the same VPS as PitchDriven and MerchFocus.

  Needs the SSH key unlocked in the Windows ssh-agent:
    Start-Service ssh-agent; ssh-add "$env:USERPROFILE\.ssh\football7676_final"

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1
#>
param(
  [string]$Server = "footballadmin@152.53.191.32",
  [string]$Key = "$env:USERPROFILE\.ssh\football7676_final"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Remote = "/opt/ucilnica"
$SshArgs = @("-i", $Key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20")

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Green }

Step "Checking the connection to $Server"
& ssh @SshArgs $Server "echo connected" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Could not connect. Unlock the key first:  ssh-add `"$Key`""
}
& ssh @SshArgs $Server "mkdir -p $Remote/incoming"
if ($LASTEXITCODE -ne 0) {
  throw "Could not create $Remote (first install only). Run once, typing the sudo password:  ssh -t $Server sudo install -d -o footballadmin -g footballadmin -m 755 $Remote"
}

Step "Packing the source code"
$archive = Join-Path $env:TEMP "ucilnica-src.tar.gz"
Remove-Item $archive -ErrorAction SilentlyContinue
# An explicit list of folders, so local data, keys and the venv can never be shipped. The excludes are
# anchored to their folder ("backend/data", not "data", which would also drop backend/app/content/data).
& tar -czf $archive -C $Root `
  --exclude "backend/.venv" --exclude "backend/data" --exclude "backend/evals/results" `
  --exclude "frontend/node_modules" --exclude "frontend/dist" `
  --exclude "frontend/.env.local" --exclude "frontend/.env.*.local" `
  --exclude "__pycache__" --exclude ".pytest_cache" --exclude "*.pyc" --exclude "*.tsbuildinfo" `
  backend frontend deploy docs
if ($LASTEXITCODE -ne 0) { throw "Packing failed" }
"{0:N1} MB" -f ((Get-Item $archive).Length / 1MB) | Write-Host

Step "Uploading"
& scp @SshArgs $archive "${Server}:$Remote/incoming/src.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Upload failed" }

Step "Installing on the server (backup, build, restart)"
# Run the update script that ships with this version, after a syntax check of all server scripts
# (bash -n; this PC has no bash). No double quotes inside: Windows PowerShell 5.1 mangles them for ssh.
& ssh @SshArgs $Server "set -e; cd $Remote; rm -rf incoming/x; mkdir incoming/x; tar -xzf incoming/src.tar.gz -C incoming/x deploy/server; for f in incoming/x/deploy/server/*.sh; do bash -n `$f; done; bash incoming/x/deploy/server/update.sh"
$code = $LASTEXITCODE
Remove-Item $archive -ErrorAction SilentlyContinue
if ($code -ne 0) { throw "The update failed on the server (see the messages above). The previous version keeps running." }

Step "Done - https://brightfox.si  (check it: deploy\smoke-test.ps1)"
