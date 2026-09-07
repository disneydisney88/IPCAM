param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8080",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = if ($env:IPCAM_PYTHON) { $env:IPCAM_PYTHON } else { "python" }
$env:IPCAM_API_BASE_URL = $ApiBaseUrl
Set-Location $projectRoot
& $python -m streamlit run .\streamlit_app.py --server.address 127.0.0.1 --server.port $Port
