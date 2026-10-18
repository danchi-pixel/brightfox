# exit 1 = the web app must be (re)built, exit 0 = the existing build is up to date
$root = Join-Path $PSScriptRoot "..\frontend"
$built = Join-Path $root "dist\index.html"
if (-not (Test-Path $built)) { exit 1 }
$builtTime = (Get-Item $built).LastWriteTime
$sources = @(Get-ChildItem -Path (Join-Path $root "src") -Recurse -File)
foreach ($f in @("index.html", "vite.config.ts", "package.json", "tsconfig.app.json")) {
    $p = Join-Path $root $f
    if (Test-Path $p) { $sources += Get-Item $p }
}
$publicDir = Join-Path $root "public"
if (Test-Path $publicDir) { $sources += Get-ChildItem -Path $publicDir -Recurse -File }
$newest = ($sources | Measure-Object -Property LastWriteTime -Maximum).Maximum
if ($newest -gt $builtTime) { exit 1 }
exit 0
