<#
.SYNOPSIS
  Read-only checks of the live Ucilnica site after a deploy (changes no family data, never calls the AI).

.DESCRIPTION
  * Signs in ONLY with the QA family's accounts from Documents\Ucilnica-qa-login.txt (made by
    deploy\create-qa-family.ps1): the first Username/Password pair is qa-parent, the second qa-learner.
    Never the parent's or the children's real logins. Passwords are never printed.
  * Only GET requests, plus signing the QA accounts in and out. Nothing reaches Foxy.
  * The live family-isolation check: the QA parent asks for /api/learners/<id>/home for every id from
    1 to 50 (or higher, if a QA learner's id is higher). Every id that isn't a QA learner must answer
    404 - the same as an id that doesn't exist. The QA learner gets 404 for every id but its own.
  Exit code 1 if any check fails. Works in Windows PowerShell 5.1.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\smoke-test.ps1
#>
param(
  [string]$Base = "https://brightfox.si",
  [string]$QaLoginFile = (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Ucilnica-qa-login.txt"),
  [int]$ProbeMax = 50
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$HostName = ([Uri]$Base).Host
$CookieName = "uc_session"
$results = New-Object System.Collections.Generic.List[string]

function Ok($name, $cond, $detail = "") {
  $mark = if ($cond) { "PASS" } else { "FAIL" }
  $line = "{0}  {1}{2}" -f $mark, $name, $(if ($detail) { "  ($detail)" } else { "" })
  $results.Add($line); Write-Host $line -ForegroundColor $(if ($cond) { "Green" } else { "Red" })
}
function Skip($name, $why) { $line = "SKIP  $name  ($why)"; $results.Add($line); Write-Host $line -ForegroundColor Yellow }
function Info($text) { Write-Host "      $text" -ForegroundColor DarkGray }

function Hit($method, $path, $session = $null, $body = $null) {
  $p = @{ Uri = $Base + $path; Method = $method; UseBasicParsing = $true; TimeoutSec = 60 }
  if ($session) { $p.WebSession = $session }
  if ($null -ne $body) { $p.Body = ($body | ConvertTo-Json -Depth 6); $p.ContentType = "application/json" }
  try {
    $r = Invoke-WebRequest @p
    return [pscustomobject]@{ Status = [int]$r.StatusCode; Body = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()); Headers = $r.Headers }
  } catch {
    $resp = $_.Exception.Response
    if (-not $resp) { throw }
    return [pscustomobject]@{ Status = [int]$resp.StatusCode; Body = ""; Headers = $resp.Headers }
  }
}
function J($r) {
  # Assign first, then output: Windows PowerShell 5.1 would otherwise hand back a JSON list as ONE item.
  if ($r.Body) { $o = $r.Body | ConvertFrom-Json; return $o }
}
function ReadLogin($file, $index) {
  $users = @(Get-Content $file | Where-Object { $_ -like "Username:*" } | ForEach-Object { ($_ -replace "^Username:\s*", "").Trim() })
  $pws = @(Get-Content $file | Where-Object { $_ -like "Password:*" } | ForEach-Object { ($_ -replace "^Password:\s*", "").Trim() })
  if ($index -ge $users.Count -or $index -ge $pws.Count) { throw "$file has no login number $($index + 1)." }
  return @{ user = $users[$index]; pass = $pws[$index] }
}
function Login($cred) {
  $s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $r = Hit POST "/api/auth/login" $s @{ username = $cred.user; password = $cred.pass }
  return @{ s = $s; status = $r.Status; body = (J $r); cookie = [string]$r.Headers["Set-Cookie"] }
}
function SessionCookie($session) {
  $c = @($session.Cookies.GetCookies([Uri]$Base)) | Where-Object { $_.Name -eq $CookieName } | Select-Object -First 1
  if ($c) { return $c.Value }
  return $null
}
function WithCookie($value) {
  # A fresh session that replays an old cookie: proves the server ended the session, not just the browser.
  $s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $c = New-Object Net.Cookie($CookieName, $value, "/", $HostName)
  $c.Secure = $true
  $s.Cookies.Add($c)
  return $s
}
function Probe($session, $allowed, $last) {
  # Status of /api/learners/<id>/home for every id 1..$last; returns the ids that broke the rule.
  $bad = New-Object System.Collections.Generic.List[string]
  $hidden = 0
  foreach ($id in 1..$last) {
    $code = (Hit GET "/api/learners/$id/home" $session).Status
    $expect = if ($allowed -contains $id) { 200 } else { 404 }
    if ($code -ne $expect) { $bad.Add("id $id -> $code") } elseif ($expect -eq 404) { $hidden++ }
  }
  return @{ bad = $bad; hidden = $hidden }
}

Write-Host "`n== HTTPS, headers and robots"
$redir = & curl.exe -s -o NUL -w "%{http_code} %{redirect_url}" "http://$HostName/l/1"
Ok "http -> https redirect" ($redir -match ("^30[18] https://" + [regex]::Escape($HostName) + "/l/1")) $redir
$home_ = Hit GET "/"
Ok "app loads" ($home_.Status -eq 200 -and $home_.Body.Contains("<title>BrightFox</title>"))
$health = Hit GET "/api/health"
$hj = J $health
Ok "health" ($health.Status -eq 200 -and $hj.status -eq "ok") "version $($hj.version)"
foreach ($h in "Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "X-Robots-Tag") {
  Ok "header $h" ([bool]$home_.Headers[$h])
}
$pp = [string]$home_.Headers["Permissions-Policy"]
Ok "Permissions-Policy blocks microphone and camera" ($pp -match "microphone=\(\)" -and $pp -match "camera=\(\)") $pp
Ok "robots.txt disallows all" ((Hit GET "/robots.txt").Body -match "Disallow: /")

Write-Host "`n== Private data needs a sign-in"
foreach ($p in "/api/family", "/api/family/accounts", "/api/learners/1/home", "/docs", "/openapi.json") {
  $code = (Hit GET $p).Status
  Ok "anonymous $p -> 401" ($code -eq 401) "got $code"
}

if (-not (Test-Path $QaLoginFile)) {
  Skip "QA family checks" "no $QaLoginFile; run deploy\create-qa-family.ps1 once (never uses the children's own logins)"
} else {
  Write-Host "`n== QA parent (family 'qa' only)"
  $parent = Login (ReadLogin $QaLoginFile 0)
  Ok "QA parent signs in as a parent" ($parent.status -eq 200 -and $parent.body.role -eq "admin" -and $parent.body.family.name -eq "QA") "status $($parent.status)"
  Ok "cookie is Secure, HttpOnly, SameSite=Strict" ($parent.cookie -match "(?i)secure" -and $parent.cookie -match "(?i)httponly" -and $parent.cookie -match "(?i)samesite=strict")
  $p = $parent.s
  $fam = J (Hit GET "/api/family" $p)
  $learners = @($fam.learners)
  $names = @($learners | ForEach-Object { $_.name } | Sort-Object)
  Ok "parent sees only the QA learners" ($fam.slug -eq "qa" -and ($names -join "|") -eq "QA Learner|QA Sibling") ($names -join ", ")
  $accounts = @(J (Hit GET "/api/family/accounts" $p))
  Ok "parent sees only QA accounts" ($accounts.Count -ge 1 -and @($accounts | Where-Object { $_.username -notlike "qa-*" }).Count -eq 0) (($accounts | ForEach-Object { $_.username }) -join ", ")
  $qaIds = @($learners | ForEach-Object { [int]$_.id })
  $own = @($learners | Where-Object { $_.name -eq "QA Learner" } | ForEach-Object { [int]$_.id }) | Select-Object -First 1
  $sibling = @($learners | Where-Object { $_.name -eq "QA Sibling" } | ForEach-Object { [int]$_.id }) | Select-Object -First 1
  foreach ($l in $learners) {
    Ok "parent opens $($l.name)'s home" ((Hit GET "/api/learners/$($l.id)/home" $p).Status -eq 200) "id $($l.id)"
  }
  $last = $ProbeMax
  foreach ($id in $qaIds) { if ($id + 10 -gt $last) { $last = $id + 10 } }
  $probe = Probe $p $qaIds $last
  Ok "family isolation: other families' learners are invisible (ids 1-$last)" ($probe.bad.Count -eq 0 -and $qaIds.Count -ge 2) `
    $(if ($probe.bad.Count) { $probe.bad -join "; " } else { "$($probe.hidden) other ids -> 404, QA ids $($qaIds -join ', ') -> 200" })

  Write-Host "`n== QA learner"
  $kid = Login (ReadLogin $QaLoginFile 1)
  Ok "QA learner signs in as a learner" ($kid.status -eq 200 -and $kid.body.role -eq "learner" -and $kid.body.learner_id -eq $own) "learner id $($kid.body.learner_id)"
  $k = $kid.s
  $kh = Hit GET "/api/learners/$own/home" $k
  Ok "learner opens own home" ($kh.Status -eq 200 -and (J $kh).owner -eq $true)
  Ok "learner can't open the family settings" ((Hit GET "/api/family" $k).Status -eq 404)
  Ok "learner can't list the accounts" ((Hit GET "/api/family/accounts" $k).Status -eq 404)
  if ($sibling) {
    Ok "learner can't open the sibling's home" ((Hit GET "/api/learners/$sibling/home" $k).Status -eq 404) "id $sibling"
  } else { Skip "learner can't open the sibling's home" "no 'QA Sibling' in the QA family" }
  $kprobe = Probe $k @($own) $last
  Ok "learner sees no other learner (ids 1-$last)" ($kprobe.bad.Count -eq 0) $(if ($kprobe.bad.Count) { $kprobe.bad -join "; " } else { "$($kprobe.hidden) ids -> 404" })

  Write-Host "`n== Sign-out"
  $kidCookie = SessionCookie $k
  Hit POST "/api/auth/logout" $k | Out-Null
  Ok "after the learner signs out, its old cookie is refused" ($kidCookie -and (Hit GET "/api/learners/$own/home" (WithCookie $kidCookie)).Status -eq 401)
  $parentCookie = SessionCookie $p
  Hit POST "/api/auth/logout" $p | Out-Null
  Ok "after sign-out data is blocked" ((Hit GET "/api/family" $p).Status -eq 401)
  Ok "after the parent signs out, its old cookie is refused" ($parentCookie -and (Hit GET "/api/family" (WithCookie $parentCookie)).Status -eq 401)
  $st = J (Hit GET "/api/auth/status" $p)
  Ok "status says signed out" ($st.authenticated -eq $false)
}

$fails = @($results | Where-Object { $_ -like "FAIL*" }).Count
$skips = @($results | Where-Object { $_ -like "SKIP*" }).Count
Write-Host ("`n{0} checks, {1} failed, {2} skipped" -f $results.Count, $fails, $skips)
if ($fails) { exit 1 }
