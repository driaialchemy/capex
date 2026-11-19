# One command for the live demo. Run from anywhere:
# powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".\.env")) {
    Copy-Item ".\.env.example" ".\.env"
}

.\.venv\Scripts\python.exe -m streamlit run app.py
