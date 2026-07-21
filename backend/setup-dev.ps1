# Instalación inicial del backend (solo una vez o tras borrar el venv)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$VenvDir = Join-Path $env:USERPROFILE ".venvs\pos-cafeteria"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "Entorno virtual: $VenvDir"

if (Test-Path $VenvDir) {
    Write-Host "Eliminando venv anterior..."
    Remove-Item -Recurse -Force $VenvDir
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py -3 -m venv $VenvDir
} else {
    python -m venv $VenvDir
}

if (-not (Test-Path $Python)) {
    Write-Error "No se pudo crear el venv. Verifica que Python 3.11+ esté instalado."
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt

Write-Host ""
Write-Host "Listo. Ejecuta: .\run-dev.ps1"
