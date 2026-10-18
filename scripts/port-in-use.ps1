param([int]$Port)
# exit 0 = something is listening on the port, exit 1 = free
$c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($c) { exit 0 } else { exit 1 }
