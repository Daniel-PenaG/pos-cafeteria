# Instala dependencias del backend en Windows.
# Evita WinError 5 (Acceso denegado) en _cffi_backend.*.pyd cuando Python/uvicorn
# o el antivirus tienen el archivo bloqueado.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-PyVersion([string]$Exe, [string[]]$ExtraArgs = @()) {
    try {
        $out = & $Exe @($ExtraArgs + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return "$out".Trim() }
    } catch { }
    return $null
}

function Find-PreferredPython {
    # Prefer 3.12 (runtime.txt), then 3.11. Avoid 3.14 on Windows for cffi wheels.
    $tries = @(
        @{ Exe = "py"; Args = @("-3.12") },
        @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "python"; Args = @() },
        @{ Exe = "py"; Args = @() }
    )
    foreach ($t in $tries) {
        $ver = Get-PyVersion $t.Exe $t.Args
        if (-not $ver) { continue }
        if ($ver -match '^3\.(11|12)$') {
            return @{ Exe = $t.Exe; Args = $t.Args; Version = $ver }
        }
        # Keep first working python as fallback
        if (-not $script:Fallback) {
            $script:Fallback = @{ Exe = $t.Exe; Args = $t.Args; Version = $ver }
        }
    }
    if ($script:Fallback) { return $script:Fallback }
    Write-Error "No se encontro Python. Instala 3.12 desde https://www.python.org/downloads/"
}

Write-Host "Cerrando procesos Python que puedan bloquear cffi/argon2..."
Get-Process python*, uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$py = Find-PreferredPython
Write-Host "Python detectado: $($py.Version) ($($py.Exe) $($py.Args -join ' '))"

if ($py.Version -and $py.Version -notmatch '^3\.(11|12)$') {
    Write-Host ""
    Write-Warning "Este proyecto esta pensado para Python 3.12 (ver backend/runtime.txt)."
    Write-Warning "Tienes $($py.Version). En Windows, 3.14 a menudo falla al instalar cffi/argon2-cffi (WinError 5)."
    Write-Host "Instala Python 3.12 y ejecuta: py -3.12 -m venv venv"
    Write-Host "Luego vuelve a correr: .\install-deps.ps1"
    Write-Host ""
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$recreate = -not (Test-Path $venvPython)

if (Test-Path $venvPython) {
    $venvVer = Get-PyVersion $venvPython
    Write-Host "venv actual: Python $venvVer"
    if ($py.Version -match '^3\.(11|12)$' -and $venvVer -and $venvVer -ne $py.Version) {
        Write-Host "Recreando venv con Python $($py.Version) (antes $venvVer)..."
        $recreate = $true
    }
}

if ($recreate) {
    if (Test-Path "venv") {
        Write-Host "Eliminando venv anterior..."
        Remove-Item -Recurse -Force "venv" -ErrorAction SilentlyContinue
        if (Test-Path "venv") {
            Write-Error "No se pudo borrar venv\. Cierra Cursor/terminales que usen ese entorno y reintenta."
        }
    }
    Write-Host "Creando venv..."
    & $py.Exe @($py.Args + @("-m", "venv", "venv"))
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "No existe venv\Scripts\python.exe"
}

Get-ChildItem "venv\Lib\site-packages\_cffi_backend*.pyd" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Eliminando archivo bloqueado previo: $($_.Name)"
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}

Write-Host "Actualizando pip..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Instalando requirements.txt (incluye passlib[argon2] y argon2-cffi)..."
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Si ves WinError 5 / Acceso denegado en _cffi_backend:" -ForegroundColor Yellow
    Write-Host "  1. Cierra uvicorn, otras terminales con el venv activo y el IDE si hace falta."
    Write-Host "  2. Excluye la carpeta venv del antivirus o ejecuta la terminal como Administrador."
    Write-Host "  3. Borra backend\venv y vuelve a ejecutar: .\install-deps.ps1"
    Write-Host "  4. Usa Python 3.12: py -3.12 -m venv venv"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "OK. Dependencias instaladas."
Write-Host "Activa el entorno: .\venv\Scripts\Activate.ps1"
Write-Host "Admin SQL:     python scripts\crear_admin.py --login admin --password `"TuClaveSegura123`""
