# Arranca el backend en local (puerto 8000)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Instala/repara deps (incluye manejo de WinError 5 en cffi/argon2)
& "$PSScriptRoot\install-deps.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\venv\Scripts\Activate.ps1

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python no encontrado."
}

# Evita que una variable PORT del sistema rompa uvicorn
$env:PORT = "8000"

Write-Host "API: http://127.0.0.1:8000/health"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
