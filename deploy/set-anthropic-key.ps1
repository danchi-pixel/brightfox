<#
.SYNOPSIS
  Store the Anthropic API key for Foxy (BrightFox's homework tutor) on the server.

.DESCRIPTION
  Uploads a small script and runs it in an interactive SSH session. You paste the key there
  (it stays hidden); it goes into /opt/ucilnica/secrets.env (mode 600) and the Ucilnica container
  is recreated. Run it again with a new key to replace the old one. Needs the SSH key unlocked (ssh-add).
  Tip: a separate Anthropic Console workspace with a monthly spend limit, just for Ucilnica.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\set-anthropic-key.ps1
#>
param(
  [string]$Server = "footballadmin@152.53.191.32",
  [string]$Key = "$env:USERPROFILE\.ssh\football7676_final"
)
$ErrorActionPreference = "Stop"
$Remote = "/opt/ucilnica"
$SshArgs = @("-i", $Key, "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=20")

& ssh @SshArgs -o BatchMode=yes $Server "mkdir -p $Remote/incoming"
if ($LASTEXITCODE -ne 0) { throw "Could not connect (or $Remote is missing). Unlock the key first:  ssh-add `"$Key`"" }
& scp @SshArgs "$PSScriptRoot\server\set-anthropic-key.sh" "${Server}:$Remote/incoming/set-anthropic-key.sh"
if ($LASTEXITCODE -ne 0) { throw "Upload failed" }
& ssh -t @SshArgs $Server "bash $Remote/incoming/set-anthropic-key.sh; rm -f $Remote/incoming/set-anthropic-key.sh"
