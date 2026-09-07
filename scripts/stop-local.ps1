[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$DataRoot = if ($env:IPCAM_DATA_DIR) { $env:IPCAM_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'IPCAM' }
$StateFile = Join-Path $DataRoot 'cache\processes.json'
if (-not (Test-Path -LiteralPath $StateFile)) { Write-Host 'No IPCAM process state was found.'; exit 0 }

$State = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
foreach ($Name in @('backend','go2rtc')) {
    $ProcessId = $State.$Name
    if (-not $ProcessId) { continue }
    $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $ProcessInfo) { continue }
    $IsOurs = $ProcessInfo.CommandLine -like '*IPCAM*' -or $ProcessInfo.ExecutablePath -like '*tools\go2rtc\go2rtc.exe'
    if ($IsOurs) { Stop-Process -Id $ProcessId -Force; Write-Host "Stopped $Name (PID $ProcessId)" }
    else { Write-Warning "PID $ProcessId no longer belongs to IPCAM; it was not stopped." }
}
Remove-Item -LiteralPath $StateFile -Force

