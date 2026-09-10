param(
    [int]$Port = 8080,
    [int]$Go2rtcPort = 1984,
    [string]$Subdomain = "ipcam-klcho"
)
# Starts free localtunnel endpoints with FIXED subdomains:
#   https://<Subdomain>.loca.lt        -> backend/dashboard/API
#   https://<Subdomain>-g.loca.lt      -> go2rtc live gateway
# The same URLs come back every time you run this script (as long as the
# subdomain is still free). No account needed.
$ErrorActionPreference = 'Stop'

function Get-NpxPath {
    $cmd = Get-Command npx -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw 'npx not found - install Node.js first (scripts\setup.ps1 can help).'
}

try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 } catch { $health = $null }
if (-not $health -or $health.status -ne 'ok') {
    Write-Host "Backend is not running on port $Port. Start it first:" -ForegroundColor Red
    Write-Host "  scripts\start-local.ps1 -NoBrowser" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Backend healthy on http://127.0.0.1:$Port" -ForegroundColor Green

$go2rtcUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Go2rtcPort/" -TimeoutSec 2 -UseBasicParsing
    $go2rtcUp = $r.StatusCode -ge 200 -and $r.StatusCode -lt 500
} catch { }

function Start-OneLt([int]$localPort, [string]$sub, [string]$label) {
    $log = Join-Path $env:TEMP "ipcam-lt-$label-out.log"
    $err = Join-Path $env:TEMP "ipcam-lt-$label-err.log"
    Remove-Item $log, $err -ErrorAction SilentlyContinue
    $npx = Get-NpxPath
    $p = Start-Process -FilePath $npx -ArgumentList @('-y', 'localtunnel', '--subdomain', $sub, '--port', "$localPort") -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        $text = @()
        if (Test-Path $err) { $text += Get-Content $err -ErrorAction SilentlyContinue }
        if (Test-Path $log) { $text += Get-Content $log -ErrorAction SilentlyContinue }
        $m = $text | Select-String -Pattern 'your url is: (https://\S+)' | Select-Object -First 1
        if ($m) { return @{ Url = $m.Matches[0].Groups[1].Value; Proc = $p } }
        if ($p.HasExited) { break }
    }
    return @{ Url = $null; Proc = $p }
}

Write-Host "[..] Starting localtunnel endpoints (keep this window open)..." -ForegroundColor Cyan
$main = Start-OneLt $Port $Subdomain "api"
$go = @{ Url = $null; Proc = $null }
if ($go2rtcUp) { $go = Start-OneLt $Go2rtcPort "$Subdomain-g" "go2rtc" }

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Dashboard / API : $($main.Url)" -ForegroundColor Green
Write-Host "  Streamlit Cloud Secrets (set once):" -ForegroundColor Yellow
Write-Host "    IPCAM_API_BASE_URL = `"$($main.Url)`"" -ForegroundColor Yellow
if ($go.Url) {
    Write-Host ""
    Write-Host "  Live gateway (go2rtc) : $($go.Url)" -ForegroundColor Green
    Write-Host "  For remote LIVE VIEW, restart the backend with:" -ForegroundColor Yellow
    Write-Host "    `$env:IPCAM_GO2RTC_API = '$($go.Url)'" -ForegroundColor Yellow
    Write-Host "    `$env:IPCAM_GO2RTC_MODE = 'hls'" -ForegroundColor Yellow
    Write-Host "    scripts\stop-local.ps1" -ForegroundColor Yellow
    Write-Host "    scripts\start-local.ps1 -NoBrowser" -ForegroundColor Yellow
} else {
    Write-Host "  go2rtc not detected on $Go2rtcPort - live tunnel skipped." -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Same URLs return every time you run this script." -ForegroundColor Gray
Write-Host "  Browser visits to .loca.lt may ask for the tunnel password:" -ForegroundColor Gray
Write-Host "  it is your public IP, shown at https://loca.lt/mytunnelpassword" -ForegroundColor Gray
Write-Host "  Press Ctrl+C here to close all tunnels." -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan

$procs = @($main.Proc)
if ($go.Proc) { $procs += $go.Proc }
Wait-Process -Id $procs.Id
