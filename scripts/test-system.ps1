[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot 'backend'
$FrontendDir = Join-Path $ProjectRoot 'frontend'
$DataRoot = if ($env:IPCAM_DATA_DIR) { $env:IPCAM_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'IPCAM' }
$Python = Join-Path $env:USERPROFILE '.ipcam\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Run setup.ps1 first.' }

Push-Location $BackendDir
try { & $Python -m pytest -q } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }

$Npm = Get-Command npm -ErrorAction SilentlyContinue
$Pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
if ($Npm -or $Pnpm) {
    & (Join-Path $PSScriptRoot 'build-frontend.ps1')
} else { Write-Warning 'Node.js is absent; using the existing verified frontend build.' }

Write-Host 'All system tests passed.' -ForegroundColor Green
