param(
    [Parameter(Mandatory = $true)][string]$Authtoken,
    [Parameter(Mandatory = $true)][string]$Domain,
    [int]$Port = 8080
)
# One-time ngrok setup + start: a stable public URL that never changes.
# 1) Get a free ngrok account (https://dashboard.ngrok.com/signup)
# 2) Copy your authtoken (https://dashboard.ngrok.com/get-started/your-authtoken)
# 3) Reserve a free static domain (https://dashboard.ngrok.com/domains -> Create domain)
# Then run:  scripts\start-ngrok.ps1 -Authtoken XXXX -Domain xxx.ngrok-free.app
# After that, set once in Streamlit Cloud Secrets:
#   IPCAM_API_BASE_URL = "https://xxx.ngrok-free.app"
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Ngrok = Join-Path $env:LOCALAPPDATA 'IPCAM\tools\ngrok\ngrok.exe'
if (-not (Test-Path -LiteralPath $Ngrok)) { throw "ngrok.exe not found at $Ngrok" }

& $Ngrok config add-authtoken $Authtoken
Write-Host "[OK] authtoken saved" -ForegroundColor Green

try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 } catch { $health = $null }
if (-not $health -or $health.status -ne 'ok') {
    Write-Host "Backend is not running on port $Port - starting it..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $ProjectRoot 'scripts\start-local.ps1'), '-NoBrowser' -WindowStyle Hidden
    Start-Sleep -Seconds 10
}

Write-Host "[..] Starting ngrok tunnel: https://$Domain -> 127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Permanent URL : https://$Domain" -ForegroundColor Green
Write-Host "  This URL NEVER changes. Streamlit Cloud Secrets:" -ForegroundColor Yellow
Write-Host "    IPCAM_API_BASE_URL = `"https://$Domain`"" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Keep this window open for remote access; Ctrl+C to stop." -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan

& $Ngrok http --domain=$Domain $Port
