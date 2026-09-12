# IPCAM autostart watchdog: keeps the backend and the permanent ngrok
# tunnel alive. Intended to run hidden at user logon via a scheduled task
# ("IPCAM Autostart"); safe to run manually at any time.
# Stop with: Stop-ScheduledTask -TaskName "IPCAM Autostart"
param([int]$CheckSeconds = 60)
$ErrorActionPreference = 'Continue'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $env:LOCALAPPDATA 'IPCAM\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'autostart.log'
$DomainFile = Join-Path $env:LOCALAPPDATA 'IPCAM\ngrok-domain.txt'
$Ngrok = Join-Path $env:LOCALAPPDATA 'IPCAM\tools\ngrok\ngrok.exe'

function Log($message) {
    Add-Content -Path $Log -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message)
}

function Test-UrlHealth([string]$url) {
    try {
        $response = Invoke-WebRequest -Uri $url -Headers @{ 'ngrok-skip-browser-warning' = '1' } -TimeoutSec 10 -UseBasicParsing
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Start-Backend {
    if (Test-UrlHealth 'http://127.0.0.1:8080/api/health') { return $true }
    Log 'backend down - starting start-local.ps1'
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $ProjectRoot 'scripts\start-local.ps1'), '-NoBrowser' -WindowStyle Hidden
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 3
        if (Test-UrlHealth 'http://127.0.0.1:8080/api/health') { Log 'backend started'; return $true }
    }
    Log 'backend failed to start'
    return $false
}

function Get-NgrokDomain {
    if (-not (Test-Path -LiteralPath $DomainFile)) { return $null }
    $domain = (Get-Content -LiteralPath $DomainFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    return ($domain ?? '').Trim()
}

$ngrokProc = $null
function Ensure-Ngrok([string]$domain) {
    $script:ngrokProcHealthy = $false
    if (Test-UrlHealth "https://$domain/api/health") {
        if ($script:ngrokProc -and -not $script:ngrokProc.HasExited) { return }
        return
    }
    Log "ngrok tunnel $domain down - restarting"
    if ($script:ngrokProc -and -not $script:ngrokProc.HasExited) {
        Stop-Process -Id $script:ngrokProc.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process ngrok -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Ngrok } | Stop-Process -Force -ErrorAction SilentlyContinue
    $script:ngrokProc = Start-Process -FilePath $Ngrok -ArgumentList @('http', "--domain=$domain", '8080') -WindowStyle Hidden -PassThru
    Log "ngrok restarted (pid $($script:ngrokProc.Id))"
}

Log '=== autostart watchdog started ==='
while ($true) {
    try {
        $null = Start-Backend
        $domain = Get-NgrokDomain
        if ($domain) { Ensure-Ngrok $domain }
    } catch {
        Log "loop error: $_"
    }
    Start-Sleep -Seconds $CheckSeconds
}
