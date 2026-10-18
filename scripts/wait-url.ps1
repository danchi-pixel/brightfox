param([string]$Url, [int]$Seconds = 60)
# Polls a URL until it answers (exit 0) or the timeout passes (exit 1).
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 }
    } catch { }
    Start-Sleep -Milliseconds 500
}
exit 1
