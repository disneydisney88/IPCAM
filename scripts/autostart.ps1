# IPCAM autostart watchdog: keeps the backend and the fixed-subdomain
# localtunnel endpoints alive. Intended to run hidden at user logon via a
# scheduled task; safe to run manually at any time (it detects what is
# already up). Stop with: Stop-ScheduledTask -TaskName "IPCAM Autostart"
param([int]$CheckSeconds = 60)
$ErrorActionPreference = 'Continue'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $env:LOCALAPPDATA 'IPCAM\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'autostart.log'
$Subdomain = 'ipcam-klcho'
$procs = @{ api = $null; go = $null }

function Log($message) {
    Add-Content -Path $Log -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message)
}

function Test-UrlHealth([string]$url) {
    try {
        $response = Invoke-WebRequest -Uri $url -Headers @{ 'bypass-tunnel-reminder' = '1' } -TimeoutSec 10 -UseBasicParsing
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

function Start-Lt([int]$port, [string]$sub, [string]$key) {
    $npx = (Get-Command npx -ErrorAction SilentlyContinue).Source
    if (-not $npx) { Log 'npx missing - cannot start tunnel'; return }
    $log = Join-Path $env:TEMP "ipcam-lt-$key.log"
    $err = Join-Path $env:TEMP "ipcam-lt-$key-err.log"
    Remove-Item $log, $err -ErrorAction SilentlyContinue
    $procs[$key] = Start-Process -FilePath $npx -ArgumentList @('-y', 'localtunnel', '--subdomain', $sub, '--port', "$port") -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    Log "localtunnel $sub started (pid $($procs[$key].Id))"
}

function Ensure-Lt([int]$port, [string]$sub, [string]$key, [bool]$dependencyUp) {
    if (-not $dependencyUp) { return }
    if (Test-UrlHealth "https://$sub.loca.lt/api/health") { return }
    Log "tunnel $sub down - restarting"
    if ($procs[$key] -and -not $procs[$key].HasExited) {
        Stop-Process -Id $procs[$key].Id -Force -ErrorAction SilentlyContinue
    }
    Start-Lt $port $sub $key
}

Log '=== autostart watchdog started ==='
while ($true) {
    try {
        $backendUp = Start-Backend
        Ensure-Lt 8080 $Subdomain 'api' $backendUp
        $goUp = $false
        try {
            $response = Invoke-WebRequest -Uri 'http://127.0.0.1:1984/' -TimeoutSec 3 -UseBasicParsing
            $goUp = $response.StatusCode -lt 500
        } catch { }
        if ($goUp) { Ensure-Lt 1984 "$Subdomain-g" 'go' $true }
    } catch {
        Log "loop error: $_"
    }
    Start-Sleep -Seconds $CheckSeconds
}
