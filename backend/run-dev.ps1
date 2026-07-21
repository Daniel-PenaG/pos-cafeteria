# Arranca el backend en local (puerto 8000)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Windows a veces bloquea .pyd dentro de backend\venv (WinError 5).
# Usamos un venv fuera del proyecto para evitar permisos.
$VenvDir = Join-Path $env:USERPROFILE ".venvs\pos-cafeteria"
$Python = Join-Path $VenvDir "Scripts\python.exe"

function Ensure-Venv {
    if (-not (Test-Path $Python)) {
        Write-Host "Creando entorno virtual en $VenvDir ..."
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            & py -3 -m venv $VenvDir
        } else {
            python -m venv $VenvDir
        }
    }

    if (-not (Test-Path $Python)) {
        Write-Error "No se pudo crear el entorno virtual. Instala Python 3.11+ desde python.org"
    }
}

function Install-Requirements {
    Write-Host "Instalando dependencias..."
    & $Python -m pip install -r requirements.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-Error @"
No se pudieron instalar las dependencias.
Cierra otras terminales con el backend corriendo e intenta de nuevo.
Si persiste: Remove-Item -Recurse -Force '$VenvDir'
"@
    }
}

function Test-Uvicorn {
    & $Python -c "import uvicorn" 2>$null
    return ($LASTEXITCODE -eq 0)
}

Ensure-Venv

if (-not (Test-Uvicorn)) {
    Install-Requirements
}

if (-not (Test-Uvicorn)) {
    Write-Error "uvicorn no está instalado. Ejecuta: .\setup-dev.ps1"
}

$env:PORT = "8000"

Write-Host "API: http://127.0.0.1:8000/health"
Write-Host "Login local (SQLite nuevo): admin / admin123"
Write-Host "Ver ENTORNO_LOCAL_Y_PRODUCCION.md para cambiar a produccion"

& $Python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
