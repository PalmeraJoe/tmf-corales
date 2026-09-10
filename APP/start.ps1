$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv")) {
  py -3 -m venv .venv
}

& "$root\.venv\Scripts\python.exe" -m pip install -r "$root\requirements.txt"
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) {
  npm install
}
npm run build

Set-Location $root
$env:PYTHONPATH = "$root\backend"
Write-Host "Baliza en http://127.0.0.1:8000"
& "$root\.venv\Scripts\python.exe" -m uvicorn baliza.main:app --host 127.0.0.1 --port 8000
