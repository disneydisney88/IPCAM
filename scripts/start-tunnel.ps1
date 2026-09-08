param(
    [int]$Port = 8080,
    [string]$CloudflaredPath = ""
)
# Starts a Cloudflare quick tunnel to the local IPCAM backend and prints
# the temporary public URL. Keep this window open while you use the cloud
# dashboard; the URL changes every time you run this script.
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
Write-Host "[..] Starting Cloudflare Tunnel (keep this window open)..."

$log = Join-Path $env:TEMP "ipcam-tunnel-out.log"
$err = Join-Path $env:TEMP "ipcam-tunnel-err.log"
Remove-Item $log, $err -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath $Exe -ArgumentList @('tunnel', '--url', "http://127.0.0.1:$Port", '--no-autoupdate') -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err

$url = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    $text = @()
    if (Test-Path $err) { $text += Get-Content $err -ErrorAction SilentlyContinue }
    if (Test-Path $log) { $text += Get-Content $log -ErrorAction SilentlyContinue }
    $match = $text | Select-String -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
    if ($match) { $url = $match.Matches[0].Value; break }
    if ($proc.HasExited) { break }
}
if (-not $url) {
    Write-Host "Tunnel failed to start. Check log: $err" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Tunnel URL : $url" -ForegroundColor Green
Write-Host "  Open it anywhere for the full dashboard (admin lock applies)."
Write-Host ""
Write-Host "  Paste into Streamlit Cloud Secrets (Manage app > Settings > Secrets):" -ForegroundColor Yellow
Write-Host "  IPCAM_API_BASE_URL = `"$url`"" -ForegroundColor Yellow
Write-Host ""
Write-Host "  NOTE: the URL changes every time you run this script." -ForegroundColor Gray
Write-Host "  Press Ctrl+C here to close the tunnel (cloud access stops)." -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan
Wait-Process -Id $proc.Id
