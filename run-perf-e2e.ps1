# E2E autocontenido: seed PG desechable, backend, preview e2e, medición y capturas.
param(
  [int]$BackendPort = 8000,
  [int]$PreviewPort = 4173,
  [switch]$NavOnly,
  [switch]$SkipCapture,
  [switch]$SkipMeasure
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

Get-Job -Name "pos-e2e-backend", "pos-e2e-preview" -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Job $_ -ErrorAction SilentlyContinue
  Remove-Job $_ -Force -ErrorAction SilentlyContinue
}
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

function Get-PortListener([int]$Port) {
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $conn) { return $null }
  $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
  return [PSCustomObject]@{
    Port = $Port
    PID  = [int]$conn.OwningProcess
    Name = if ($proc) { $proc.ProcessName } else { "?" }
  }
}

function Assert-PortFree([int]$Port) {
  $occ = Get-PortListener $Port
  if ($occ) {
    Write-Error "Puerto $Port ocupado por PID $($occ.PID) ($($occ.Name)). Use otros puertos, p. ej. -BackendPort 8010 -PreviewPort 4174. No se matan procesos ajenos."
  }
}

function Wait-HttpOk([string]$Url, [int]$MaxSec = 180) {
  $deadline = (Get-Date).AddSeconds($MaxSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
    } catch { }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

$VenvDir = Join-Path $env:USERPROFILE ".venvs\pos-cafeteria"
$Python = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $Python)) {
  Write-Error "Falta venv en $VenvDir. Ejecuta backend\setup-dev.ps1"
}

Assert-PortFree $BackendPort
Assert-PortFree $PreviewPort

Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

$perfUrl = if ($env:PERF_DATABASE_URL) { $env:PERF_DATABASE_URL.Trim() } else { "" }
if (-not $perfUrl) {
  $perfUrl = "postgresql+psycopg2://pos_test@127.0.0.1:5433/pos_bench"
  $env:PERF_DATABASE_URL = $perfUrl
}

$prodUrl = if ($env:DATABASE_URL) { $env:DATABASE_URL.Trim() } else { "" }
if ($prodUrl -and $prodUrl -eq $perfUrl) {
  Write-Error "PERF_DATABASE_URL no puede ser igual a DATABASE_URL"
}

$apiUrl = "http://127.0.0.1:$BackendPort"
$previewUrl = "http://127.0.0.1:$PreviewPort"

Write-Host "E2E: API $apiUrl | Preview $previewUrl | PG desechable"

$credsFile = Join-Path $env:TEMP "pos-e2e-creds-$PID.json"
$env:E2E_CREDS_FILE = $credsFile
if (Test-Path $credsFile) { Remove-Item $credsFile -Force }

Write-Host "Seed E2E..."
Push-Location $BackendDir
& $Python scripts/seed_e2e_capture.py
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

if (-not (Test-Path $credsFile)) {
  Write-Error "Seed no generó credenciales sintéticas."
}
$creds = Get-Content $credsFile -Raw | ConvertFrom-Json
$env:CAPTURE_LOGIN = $creds.login
$env:CAPTURE_PASSWORD = $creds.password
Remove-Item $credsFile -Force -ErrorAction SilentlyContinue
$env:E2E_CREDS_FILE = ""

$env:DATABASE_URL = $perfUrl
$env:VITE_API_URL = $apiUrl
$env:PREVIEW_URL = $previewUrl
$env:API_URL = $apiUrl

Push-Location $FrontendDir
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
npm run build -- --mode e2e 2>&1 | Out-Null
$buildExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Pop-Location
if ($buildExit -ne 0) { throw "build e2e falló (exit $buildExit)" }

$viteJs = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
if (-not (Test-Path $viteJs)) {
  Write-Error "Falta vite en frontend/node_modules. Ejecuta npm install en frontend."
}
$nodeExe = (Get-Command node -ErrorAction Stop).Source

$corsOrigins = @(
  $previewUrl
  "http://localhost:$PreviewPort"
  "http://127.0.0.1:4173"
  "http://localhost:4173"
  "http://127.0.0.1:5173"
  "http://localhost:5173"
) -join ","

$backendJob = Start-Job -Name "pos-e2e-backend" -ScriptBlock {
  param($py, $dir, $port, $dbUrl, $cors)
  $env:DATABASE_URL = $dbUrl
  $env:CORS_ORIGINS = $cors
  Set-Location $dir
  & $py -m uvicorn app.main:app --host 127.0.0.1 --port $port
} -ArgumentList $Python, $BackendDir, $BackendPort, $perfUrl, $corsOrigins

$previewJob = Start-Job -Name "pos-e2e-preview" -ScriptBlock {
  param($node, $vite, $dir, $port)
  Set-Location $dir
  & $node $vite preview --host 127.0.0.1 --port $port --strictPort
} -ArgumentList $nodeExe, $viteJs, $FrontendDir, $PreviewPort

try {
  $prevEap = $ErrorActionPreference
  if (-not (Wait-HttpOk "$apiUrl/health")) {
    $beLog = Receive-Job $backendJob -ErrorAction SilentlyContinue | Select-Object -Last 15
    throw "Backend no respondió en :$BackendPort. Job: $beLog"
  }
  if (-not (Wait-HttpOk "$previewUrl/")) {
    $pvLog = Receive-Job $previewJob -ErrorAction SilentlyContinue | Select-Object -Last 15
    throw "Preview no respondió en :$PreviewPort. Job: $pvLog"
  }

  Push-Location $FrontendDir
  $ErrorActionPreference = "Continue"
  if (-not $SkipMeasure) {
    Write-Host "Medición navegación..."
    npm run measure:perf-e2e-nav
    if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $prevEap; throw "measure:perf-e2e-nav falló" }
  }

  npm run verify:cobro-idempotencia-e2e
  if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $prevEap; throw "verify:cobro-idempotencia-e2e falló" }

  if (-not $SkipCapture) {
    Write-Host "Capturas navegación..."
    npm run capture:navegacion-operativa
    if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $prevEap; throw "capture:navegacion-operativa falló" }
  }

  if (-not $NavOnly) {
    npm run measure:perf-e2e
    if ($LASTEXITCODE -ne 0) { Write-Warning "measure:perf-e2e opcional falló" }
  }
  $ErrorActionPreference = $prevEap
  Pop-Location
}
finally {
  Get-Job -Name "pos-e2e-backend","pos-e2e-preview" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Job $_ -ErrorAction SilentlyContinue
    Remove-Job $_ -Force -ErrorAction SilentlyContinue
  }
  Push-Location $BackendDir
  $env:PERF_DATABASE_URL = $perfUrl
  $env:CAPTURE_LOGIN = $creds.login
  & $Python scripts/teardown_e2e_capture.py 2>$null
  Pop-Location
  Remove-Item Env:CAPTURE_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:CAPTURE_LOGIN -ErrorAction SilentlyContinue
  Write-Host "E2E finalizado."
}
