[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Mock
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot 'backend'
$FrontendIndex = Join-Path $ProjectRoot 'frontend\dist\index.html'
$Go2rtcExe = Join-Path $ProjectRoot 'tools\go2rtc\go2rtc.exe'
$DataRoot = if ($env:IPCAM_DATA_DIR) { $env:IPCAM_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'IPCAM' }
$VenvPython = Join-Path $env:USERPROFILE '.ipcam\venv\Scripts\python.exe'
$LogsDir = Join-Path $DataRoot 'logs'
$CacheDir = Join-Path $DataRoot 'cache'
$StateFile = Join-Path $CacheDir 'processes.json'
New-Item -ItemType Directory -Path $LogsDir,$CacheDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Backend environment is missing. Run .\scripts\setup.ps1 first.' }
if (-not (Test-Path -LiteralPath $FrontendIndex)) { throw 'Frontend build is missing. Run .\scripts\setup.ps1 first.' }

try {
    $Existing = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/health' -TimeoutSec 1
    if ($Existing.status -eq 'ok') {
        Write-Host 'IPCAM is already running at http://127.0.0.1:8080' -ForegroundColor Green
        if (-not $NoBrowser) { Start-Process "http://127.0.0.1:8080/$(if($Mock){'?mock=true'})" }
        exit 0
    }
} catch { }

$Processes = [ordered]@{}
if (Test-Path -LiteralPath $Go2rtcExe) {
    $GoConfig = Join-Path $CacheDir 'go2rtc.yaml'
    if (-not (Test-Path -LiteralPath $GoConfig)) {
        @"
api:
  listen: 127.0.0.1:1984
webrtc:
  listen: 127.0.0.1:8555
streams: {}
"@ | Set-Content -LiteralPath $GoConfig -Encoding utf8
    }
    $GoProcess = Start-Process -FilePath $Go2rtcExe -ArgumentList @('-config', $GoConfig) -WorkingDirectory $CacheDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogsDir 'go2rtc.log') -RedirectStandardError (Join-Path $LogsDir 'go2rtc-error.log')
    $Processes.go2rtc = $GoProcess.Id
    Write-Host "[OK] go2rtc started (PID $($GoProcess.Id))"
} else {
    Write-Warning 'go2rtc.exe is absent; inventory and mock dashboard remain available.'
}

$BackendArgs = @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8080')
$BackendProcess = Start-Process -FilePath $VenvPython -ArgumentList $BackendArgs -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogsDir 'backend.log') -RedirectStandardError (Join-Path $LogsDir 'backend-error.log')
$Processes.backend = $BackendProcess.Id
$Processes | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding utf8

$Ready = $false
for ($Attempt=0; $Attempt -lt 40; $Attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/health' -TimeoutSec 1
        if ($Health.status -eq 'ok') { $Ready = $true; break }
    } catch { }
}
if (-not $Ready) {
    Write-Error "Backend did not become ready. Review $LogsDir\backend-error.log"
    exit 1
}

$Url = "http://127.0.0.1:8080/$(if($Mock){'?mock=true'})"
Write-Host "IPCAM is running: $Url" -ForegroundColor Green
Write-Host "Runtime data: $DataRoot"
if (-not $NoBrowser) { Start-Process $Url }
