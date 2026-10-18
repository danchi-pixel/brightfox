<#
.SYNOPSIS
  Copy the newest Ucilnica backups from the server to this PC (an off-site copy).

.DESCRIPTION
  Downloads the newest weekly and the newest daily backup into Documents\Ucilnica-backups,
  skipping files already there. Each zip holds ucilnica.db, the homework photos (files/) and
  manifest.json; restoring is described in deploy\DEPLOYMENT.md. The zips contain the kids' chats
  and photos: keep that folder private.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\pull-backup.ps1
#>
param(
  [string]$Server = "footballadmin@152.53.191.32",
  [string]$Key = "$env:USERPROFILE\.ssh\football7676_final",
  [string]$Target = (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Ucilnica-backups")
)
$ErrorActionPreference = "Stop"
$SshArgs = @("-i", $Key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20")
$RemoteDir = "/opt/ucilnica/data/backups"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

$names = & ssh @SshArgs $Server "ls -1t $RemoteDir/ 2>/dev/null | grep -E '^ucilnica-backup-.*-(daily|weekly)\.zip$'"
# grep exits 1 when there is nothing to list; anything higher is a connection problem.
if ($LASTEXITCODE -gt 1) { throw "Could not list backups. Unlock the key first:  ssh-add `"$Key`"" }
$wanted = @()
$wanted += $names | Where-Object { $_ -like "*-weekly.zip" } | Select-Object -First 1
$wanted += $names | Where-Object { $_ -like "*-daily.zip" } | Select-Object -First 1
$wanted = @($wanted | Where-Object { $_ })
if (-not $wanted.Count) { Write-Host "No scheduled backups on the server yet."; exit 0 }

foreach ($name in $wanted) {
  $dest = Join-Path $Target $name
  if (Test-Path $dest) { Write-Host "Already have $name"; continue }
  Write-Host "Downloading $name ..."
  & scp @SshArgs "${Server}:$RemoteDir/$name" $dest
  if ($LASTEXITCODE -ne 0) { throw "Download of $name failed" }
}
Write-Host "Backups are in $Target"
