[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceDir = Join-Path $ProjectRoot 'frontend'
$BuildDir = Join-Path ([IO.Path]::GetTempPath()) ("IPCAM-frontend-build-" + [guid]::NewGuid().ToString('N'))
$DistDir = Join-Path $SourceDir 'dist'

$Npm = Get-Command npm -ErrorAction SilentlyContinue
$Pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
if (-not $Npm -and -not $Pnpm) { throw 'Node.js/npm or pnpm is required to rebuild the frontend.' }
$Node = Get-Command node -ErrorAction SilentlyContinue
if (-not $Node -and $Pnpm) {
    $BundledNode = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $Pnpm.Source) '..\..\node\bin\node.exe'))
    if (Test-Path -LiteralPath $BundledNode) {
        $env:Path = (Split-Path -Parent $BundledNode) + ';' + $env:Path
        $Node = Get-Command node -ErrorAction SilentlyContinue
    }
}
if (-not $Node) { throw 'The Node.js executable is not available on PATH.' }

New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
try {
    foreach ($File in @('package.json','pnpm-workspace.yaml','tsconfig.json','tsconfig.app.json','tsconfig.node.json','vite.config.ts','index.html')) {
        Copy-Item -LiteralPath (Join-Path $SourceDir $File) -Destination $BuildDir -Force
    }
    Copy-Item -LiteralPath (Join-Path $SourceDir 'src'),(Join-Path $SourceDir 'public') -Destination $BuildDir -Recurse
    Push-Location $BuildDir
    try {
        if ($Npm) { & $Npm.Source install; & $Npm.Source run build }
        else { & $Pnpm.Source install; & $Pnpm.Source run build }
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
    Copy-Item -Path (Join-Path $BuildDir 'dist\*') -Destination $DistDir -Recurse -Force
    if (Test-Path -LiteralPath (Join-Path $BuildDir 'pnpm-lock.yaml')) {
        Copy-Item -LiteralPath (Join-Path $BuildDir 'pnpm-lock.yaml') -Destination (Join-Path $SourceDir 'pnpm-lock.yaml') -Force
    }
    Write-Host '[OK] Frontend production build completed in local temp storage' -ForegroundColor Green
} finally {
    if (Test-Path -LiteralPath $BuildDir) { Remove-Item -LiteralPath $BuildDir -Recurse -Force }
}
