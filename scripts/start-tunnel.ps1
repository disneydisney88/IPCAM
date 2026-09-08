param(
    [int]$Port = 8080,
    [int]$Go2rtcPort = 1984,
    [string]$CloudflaredPath = ""
)
# Opens Cloudflare quick tunnels for the IPCAM backend (dashboard/API) and,
# when go2rtc is running, for the live-stream gateway (1984) so Live View
# works from outside your network. URLs change on every run of this script.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Exe = if ($CloudflaredPath) { $CloudflaredPath } else { Join-Path $ProjectRoot 'tools\cloudflared\cloudflared.exe' }

if (-not (Test-Path -LiteralPath $Exe)) {
    Write-Host "[..] Downloading cloudflared to tools\cloudflared\ ..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Exe) | Out-Null
    Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile $Exe
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

function Start-OneTunnel([int]$localPort, [string]$label) {
    $log = Join-Path $env:TEMP "ipcam-tunnel-$label-out.log"
    $err = Join-Path $env:TEMP "ipcam-tunnel-$label-err.log"
    Remove-Item $log, $err -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $Exe -ArgumentList @('tunnel', '--url', "http://127.0.0.1:$localPort", '--no-autoupdate') -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $text = @()
        if (Test-Path $err) { $text += Get-Content $err -ErrorAction SilentlyContinue }
        if (Test-Path $log) { $text += Get-Content $log -ErrorAction SilentlyContinue }
        $m = $text | Select-String -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
        if ($m) { return @{ Url = $m.Matches[0].Value; Proc = $p } }
        if ($p.HasExited) { break }
    }
    return @{ Url = $null; Proc = $p }
}

Write-Host "[..] Starting Cloudflare tunnels (keep this window open)..." -ForegroundColor Cyan
$main = Start-OneTunnel $Port "api"
$go = @{ Url = $null; Proc = $null }
if ($go2rtcUp) { $go = Start-OneTunnel $Go2rtcPort "go2rtc" }

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Dashboard / API : $($main.Url)" -ForegroundColor Green
Write-Host "  Streamlit Cloud Secrets:" -ForegroundColor Yellow
Write-Host "    IPCAM_API_BASE_URL = `"$($main.Url)`"" -ForegroundColor Yellow
if ($go.Url) {
    Write-Host ""
    Write-Host "  Live gateway (go2rtc) : $($go.Url)" -ForegroundColor Green
    Write-Host "  To watch LIVE VIEW from outside, restart the backend with:" -ForegroundColor Yellow
    Write-Host "    `$env:IPCAM_GO2RTC_API = '$($go.Url)'" -ForegroundColor Yellow
    Write-Host "    `$env:IPCAM_GO2RTC_MODE = 'hls'" -ForegroundColor Yellow
    Write-Host "    scripts\stop-local.ps1" -ForegroundColor Yellow
    Write-Host "    scripts\start-local.ps1 -NoBrowser" -ForegroundColor Yellow
} else {
    Write-Host "  go2rtc not detected on $Go2rtcPort - live-view tunnel skipped." -ForegroundColor Gray
}
Write-Host ""
Write-Host "  NOTE: URLs change every time you run this script." -ForegroundColor Gray
Write-Host "  Press Ctrl+C here to close all tunnels." -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan

$procs = @($main.Proc)
if ($go.Proc) { $procs += $go.Proc }
Wait-Process -Id $procs.Id
