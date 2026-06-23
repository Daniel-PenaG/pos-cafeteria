# Arranca el backend en local (puerto 8000)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "Creando entorno virtual..."
    python -m venv venv
}

.\venv\Scripts\Activate.ps1

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python no encontrado."
}

python -m pip install -r requirements.txt -q

# Evita que una variable PORT del sistema rompa uvicorn
$env:PORT = "8000"

Write-Host "API: http://127.0.0.1:8000/health"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
