<#
.SYNOPSIS
  Create (or renew) the QA family used by deploy\smoke-test.ps1 on the live server.

.DESCRIPTION
  Automated checks must never use the children's own logins. This makes a separate family "qa"
  (name "QA") with two learners, "QA Learner" and "QA Sibling", plus two accounts:
    qa-parent   admin (parent) of the QA family only
    qa-learner  learner account of "QA Learner"
  The smoke test signs in with these to prove that one family can't see another's learners and that
  a learner can't see a sibling. They never see or change the real family's data.

  * Runs python -m app.manage create-family / add-learner / set-password --stdin over SSH.
  * Random passwords go only into Documents\Ucilnica-qa-login.txt (never printed, never on a
    command line). Run it again to renew both passwords; the family and learners are kept.
  * Ask the parent before running it: it creates accounts on the live site.
  * Remove it later:  ssh ... "cd /opt/ucilnica && docker compose exec -T ucilnica python -m app.manage suspend-family qa"

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\create-qa-family.ps1
#>
param(
  [string]$Server = "footballadmin@152.53.191.32",
  [string]$Key = "$env:USERPROFILE\.ssh\football7676_final",
  [string]$QaLoginFile = (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Ucilnica-qa-login.txt")
)
$ErrorActionPreference = "Stop"
$Remote = "/opt/ucilnica"
$SshArgs = @("-i", $Key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20")

function New-Password([int]$length = 24) {
  # Cryptographic randomness with rejection sampling (no modulo bias); no look-alike characters.
  $chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789".ToCharArray()
  $limit = 256 - (256 % $chars.Length)
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  $buf = New-Object byte[] 1
  $out = New-Object System.Text.StringBuilder
  while ($out.Length -lt $length) {
    $rng.GetBytes($buf)
    if ($buf[0] -lt $limit) { [void]$out.Append($chars[$buf[0] % $chars.Length]) }
  }
  $rng.Dispose()
  return $out.ToString()
}

# Runs on the server. It reads the two passwords from its standard input (first two lines), so they
# never appear in a command line or the process list. Every other exec gets </dev/null.
$serverScript = @'
set -euo pipefail
cd /opt/ucilnica
manage() { docker compose exec -T ucilnica python -m app.manage "$@"; }
clean() { local v="${1#$'\xef\xbb\xbf'}"; printf '%s' "${v%$'\r'}"; }
IFS= read -r parent_pw || true
IFS= read -r learner_pw || true
parent_pw="$(clean "${parent_pw:-}")"
learner_pw="$(clean "${learner_pw:-}")"
if [ "${#parent_pw}" -lt 20 ] || [ "${#learner_pw}" -lt 20 ]; then
  echo "No passwords received - nothing changed." >&2
  exit 1
fi
if ! docker compose ps --status running --services 2>/dev/null | grep -qx ucilnica; then
  echo "Ucilnica is not running on the server: run deploy\\deploy.ps1 first." >&2
  exit 1
fi
families="$(manage list-families </dev/null)"
if grep -q '^qa ' <<<"$families"; then
  echo "The QA family exists: renewing the QA passwords."
else
  manage create-family qa --name QA </dev/null
  manage add-learner qa 'QA Learner' --grade 6 </dev/null
  manage add-learner qa 'QA Sibling' --grade 6 </dev/null
fi
printf '%s\n' "$parent_pw" | manage set-password qa-parent --stdin --family qa
printf '%s\n' "$learner_pw" | manage set-password qa-learner --stdin --family qa --learner 'QA Learner'
unset parent_pw learner_pw
manage list-users --family qa </dev/null
'@

& ssh @SshArgs $Server "mkdir -p $Remote/incoming"
if ($LASTEXITCODE -ne 0) { throw "Could not connect. Unlock the key first:  ssh-add `"$Key`"" }

$tmp = Join-Path $env:TEMP "ucilnica-create-qa-family.sh"
# LF line endings and no byte-order mark, or bash on the server trips over them.
[IO.File]::WriteAllText($tmp, ($serverScript -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding $false))
try {
  & scp @SshArgs $tmp "${Server}:$Remote/incoming/create-qa-family.sh"
  if ($LASTEXITCODE -ne 0) { throw "Upload failed" }
} finally {
  Remove-Item $tmp -ErrorAction SilentlyContinue
}

$parentPw = New-Password
$learnerPw = New-Password
@($parentPw, $learnerPw) | & ssh @SshArgs $Server "bash $Remote/incoming/create-qa-family.sh; s=`$?; rm -f $Remote/incoming/create-qa-family.sh; exit `$s"
if ($LASTEXITCODE -ne 0) { throw "Creating the QA family failed on the server (see above). Run this script again once it's fixed." }

@("Ucilnica QA logins for deploy\smoke-test.ps1 (family 'qa' only - never the children's own logins)",
  "Username: qa-parent", "Password: $parentPw",
  "Username: qa-learner", "Password: $learnerPw") | Set-Content -Encoding ascii $QaLoginFile
Write-Host "Saved to $QaLoginFile. Run deploy\smoke-test.ps1 to use it."
