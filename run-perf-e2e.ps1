# Capturas E2E rendimiento — autocontenido (usuario sintético opcional).
$ErrorActionPreference = "Continue"
$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$ApiUrl = "http://127.0.0.1:8000"
$PreviewUrl = "http://127.0.0.1:4173"
$ApiPort = 8000
$PreviewPort = 4173

$BackendProc = $null
$PreviewProc = $null
$ExitCode = 0
$GeneratedCaptureUser = $false
$capLogin = ""
$capPass = ""

function Assert-LocalUrl([string]$Label, [string]$Raw) {
    if ([string]::IsNullOrWhiteSpace($Raw)) { throw "${Label} no definida" }
    try { $u = [Uri]$Raw } catch { throw "${Label} no es URL valida" }
    $h = $u.Host.ToLowerInvariant()
    if ($h -notin @("127.0.0.1", "localhost", "::1")) {
        throw "${Label} debe ser localhost"
    }
    return $Raw.TrimEnd("/")
}

function Assert-SafePerfDatabase([string]$Url) {
    if ([string]::IsNullOrWhiteSpace($Url)) {
        throw "PERF_DATABASE_URL requerida (PostgreSQL/SQLite local desechable)."
    }
    $low = $Url.ToLowerInvariant()
    if ($low -match "amazonaws|rds\.|neon\.tech|supabase\.co|railway\.app|render\.com|azure|heroku") {
        throw "PERF_DATABASE_URL parece produccion remota."
    }
    if ($low -notmatch "127\.0\.0\.1|localhost|:memory:") {
        throw "PERF_DATABASE_URL debe apuntar a host local."
    }
    if ($low -match "test_pos\.db|test_pos_perf") {
        throw "No usar test_pos.db existentes como PERF_DATABASE_URL."
    }
}

function Test-PortFree([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pids = ($conn | Select-Object -ExpandProperty OwningProcess -Unique) -join ","
        throw "Puerto $Port ocupado (PID: $pids). Libera manualmente."
    }
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSec = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "Timeout esperando $Url"
}

function Stop-OwnedProcess([System.Diagnostics.Process]$Proc) {
    if ($null -eq $Proc -or $Proc.HasExited) { return }
    try { Stop-Process -Id $Proc.Id -Force -ErrorAction Stop } catch { }
}

function Get-BackendPython {
    $VenvDir = Join-Path $env:USERPROFILE ".venvs\pos-cafeteria"
    $Python = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $VenvDir }
        else { python -m venv $VenvDir }
    }
    if (-not (Test-Path $Python)) { throw "Falta venv Python en $VenvDir" }
    return $Python
}

function New-CaptureCredentials {
    $login = "capture_" + [guid]::NewGuid().ToString("N").Substring(0, 12)
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $pass = [Convert]::ToBase64String($bytes).Replace("+", "x").Replace("/", "y").Substring(0, 24)
    return @{ Login = $login; Password = $pass }
}

try {
    $perfDb = $env:PERF_DATABASE_URL
    if ([string]::IsNullOrWhiteSpace($perfDb)) {
        throw "PERF_DATABASE_URL requerida."
    }
    Assert-SafePerfDatabase $perfDb

    $prodDb = $env:DATABASE_URL
    if (-not [string]::IsNullOrWhiteSpace($prodDb) -and $prodDb.Trim() -eq $perfDb.Trim()) {
        throw "PERF_DATABASE_URL no puede coincidir con DATABASE_URL."
    }

    $capLogin = $env:CAPTURE_LOGIN
    $capPass = $env:CAPTURE_PASSWORD
    if ([string]::IsNullOrWhiteSpace($capLogin) -or [string]::IsNullOrWhiteSpace($capPass)) {
        $gen = New-CaptureCredentials
        $capLogin = $gen.Login
        $capPass = $gen.Password
        $GeneratedCaptureUser = $true
        Write-Host "Usuario sintetico de captura generado (login: $capLogin). Contrasena no se imprime."
    }

    if ($env:API_URL) { $ApiUrl = Assert-LocalUrl "API_URL" $env:API_URL }
    if ($env:PREVIEW_URL) { $PreviewUrl = Assert-LocalUrl "PREVIEW_URL" $env:PREVIEW_URL }
    Test-PortFree $ApiPort
    Test-PortFree $PreviewPort

    $Python = Get-BackendPython

    $seedEnv = @{
        PERF_DATABASE_URL = $perfDb
        CAPTURE_LOGIN     = $capLogin
        CAPTURE_PASSWORD  = $capPass
    }
    Write-Host "Seed E2E en base desechable..."
    $env:PERF_DATABASE_URL = $perfDb
    $env:CAPTURE_LOGIN = $capLogin
    $env:CAPTURE_PASSWORD = $capPass
    Push-Location $BackendDir
    try {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $Python scripts/seed_e2e_capture.py 2>&1 | Out-Null
        $ErrorActionPreference = $prevEap
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { throw "seed_e2e_capture fallo" }

    $env:DATABASE_URL = $perfDb
    $env:LOCAL_SEED_CATALOG = "false"
    $env:PORT = "$ApiPort"
    $env:CORS_ORIGINS = "http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:5173,http://localhost:5173"
    Write-Host "Backend $ApiUrl ..."
    $BackendProc = Start-Process -FilePath $Python -ArgumentList @(
        "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort"
    ) -WorkingDirectory $BackendDir -PassThru -WindowStyle Hidden

    Wait-HttpOk "$ApiUrl/health"

    Push-Location $FrontendDir
    try {
        $env:VITE_API_URL = $ApiUrl
        npm run build -- --mode e2e
        if ($LASTEXITCODE -ne 0) { throw "npm run build fallo" }

        $PreviewProc = Start-Process -FilePath "npm.cmd" -ArgumentList @(
            "run", "preview", "--", "--host", "127.0.0.1", "--port", "$PreviewPort"
        ) -WorkingDirectory $FrontendDir -PassThru -WindowStyle Hidden

        Wait-HttpOk $PreviewUrl

        $env:PREVIEW_URL = $PreviewUrl
        $env:API_URL = $ApiUrl
        $env:CAPTURE_LOGIN = $capLogin
        $env:CAPTURE_PASSWORD = $capPass
        npm run capture:perf-flujos
        if ($LASTEXITCODE -ne 0) { throw "capture:perf-flujos fallo" }
        npm run measure:perf-e2e
        if ($LASTEXITCODE -ne 0) { throw "measure:perf-e2e fallo" }
    } finally {
        Pop-Location
    }

    Write-Host "Capturas en docs/screenshots/rendimiento-flujos/"
} catch {
    Write-Error $_.Exception.Message
    $ExitCode = 1
} finally {
    Stop-OwnedProcess $PreviewProc
    Stop-OwnedProcess $BackendProc
    if ($GeneratedCaptureUser -and $capLogin -and $env:PERF_DATABASE_URL) {
        $Python = Get-BackendPython
        $env:CAPTURE_LOGIN = $capLogin
        Push-Location $BackendDir
        try { & $Python scripts/teardown_e2e_capture.py 2>$null } finally { Pop-Location }
    }
    Remove-Item Env:CAPTURE_PASSWORD -ErrorAction SilentlyContinue
}

exit $ExitCode
