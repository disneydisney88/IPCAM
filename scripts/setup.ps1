[CmdletBinding()]
param(
    [switch]$DownloadGo2rtc,
    [switch]$InstallNode,
    [switch]$RebuildFrontend
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot 'backend'
$FrontendDir = Join-Path $ProjectRoot 'frontend'
$DataRoot = if ($env:IPCAM_DATA_DIR) { $env:IPCAM_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'IPCAM' }
$VenvDir = Join-Path $env:USERPROFILE '.ipcam\venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$Go2rtcExe = Join-Path $ProjectRoot 'tools\go2rtc\go2rtc.exe'

Write-Host "IPCAM setup: $ProjectRoot" -ForegroundColor Cyan

$PythonCandidates = @()
if ($env:IPCAM_PYTHON) { $PythonCandidates += $env:IPCAM_PYTHON }
$PythonCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe') -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object FullName
$PathPython = Get-Command python -ErrorAction SilentlyContinue
if ($PathPython) { $PythonCandidates += $PathPython.Source }
$Python = $null
foreach ($Candidate in $PythonCandidates | Select-Object -Unique) {
    if (-not (Test-Path -LiteralPath $Candidate) -or $Candidate -like '*\WindowsApps\*') { continue }
    try {
        $CandidateVersion = & $Candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ([version]$CandidateVersion -ge [version]'3.12') { $Python = $Candidate; $PythonVersion = $CandidateVersion; break }
    } catch { }
}
if (-not $Python) {
    throw 'A standard (non-Microsoft-Store) Python 3.12+ is required so runtime files stay at %LOCALAPPDATA%\IPCAM. Install it with: winget install --id Python.Python.3.13 --exact'
}
Write-Host "[OK] Python $PythonVersion ($Python)"

if (Test-Path -LiteralPath $VenvPython) {
    $VenvConfig = Join-Path $VenvDir 'pyvenv.cfg'
    $ExpectedHome = [IO.Path]::GetFullPath((Split-Path -Parent $Python)).TrimEnd('\')
    $CurrentHome = if (Test-Path -LiteralPath $VenvConfig) { ((Get-Content -LiteralPath $VenvConfig | Where-Object { $_ -like 'home =*' }) -replace '^home =\s*','').TrimEnd('\') } else { '' }
    if ($CurrentHome -ne $ExpectedHome) {
        Write-Host '[..] Recreating venv with the selected standard Python'
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }
}
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host '[..] Creating backend virtual environment'
    & $Python -m venv $VenvDir
}
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $BackendDir 'requirements.txt')

$FrontendBuilt = Test-Path -LiteralPath (Join-Path $FrontendDir 'dist\index.html')
if ($FrontendBuilt -and -not $RebuildFrontend) {
    Write-Host '[OK] Pre-built frontend is ready (use -RebuildFrontend to rebuild)'
} else {
  $Npm = Get-Command npm -ErrorAction SilentlyContinue
  $Pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
  if (-not $Npm -and -not $Pnpm -and $InstallNode) {
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $Winget) { throw 'winget is unavailable. Install Node.js LTS from https://nodejs.org/' }
    & $Winget.Source install --id OpenJS.NodeJS.LTS --exact --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
    $Npm = Get-Command npm -ErrorAction SilentlyContinue
  }
  if ($Npm -or $Pnpm) {
    & (Join-Path $PSScriptRoot 'build-frontend.ps1')
  } elseif ($FrontendBuilt) {
    Write-Warning 'Node.js is not installed. The pre-built dashboard can run, but install Node.js LTS before frontend development.'
  } else {
    throw 'Node.js is required to build the dashboard. Rerun with -InstallNode or install Node.js LTS from https://nodejs.org/.'
  }
}

$Ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if ($Ffprobe) { Write-Host "[OK] ffprobe: $($Ffprobe.Source)" } else { Write-Warning 'ffprobe not found. Install an official FFmpeg Windows build and add its bin folder to PATH.' }

if ($DownloadGo2rtc -and -not (Test-Path -LiteralPath $Go2rtcExe)) {
    Write-Host '[..] Downloading go2rtc from the official GitHub release'
    $Release = Invoke-RestMethod -Uri 'https://api.github.com/repos/AlexxIT/go2rtc/releases/latest' -Headers @{ 'User-Agent'='IPCAM-Setup' }
    $Asset = $Release.assets | Where-Object name -eq 'go2rtc_win64.zip' | Select-Object -First 1
    if (-not $Asset) { throw 'The official release has no go2rtc_win64.zip asset.' }
    $TempZip = Join-Path ([IO.Path]::GetTempPath()) ("ipcam-go2rtc-" + [guid]::NewGuid().ToString('N') + '.zip')
    try {
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $TempZip
        Expand-Archive -LiteralPath $TempZip -DestinationPath (Split-Path -Parent $Go2rtcExe) -Force
        $Downloaded = Get-ChildItem -LiteralPath (Split-Path -Parent $Go2rtcExe) -Filter 'go2rtc*.exe' | Select-Object -First 1
        if ($Downloaded.FullName -ne $Go2rtcExe) { Move-Item -LiteralPath $Downloaded.FullName -Destination $Go2rtcExe -Force }
    } finally {
        if (Test-Path -LiteralPath $TempZip) { Remove-Item -LiteralPath $TempZip -Force }
    }
}
if (Test-Path -LiteralPath $Go2rtcExe) { Write-Host '[OK] go2rtc.exe' } else { Write-Warning 'go2rtc is optional for inventory/mock mode. Run setup.ps1 -DownloadGo2rtc to enable it.' }

$env:PYTHONPATH = $BackendDir
& $VenvPython -c "from app.database.core import init_db; init_db(); print('[OK] SQLite initialized')"
Write-Host "Setup complete. Run .\scripts\start-local.ps1" -ForegroundColor Green
