# Empaqueta el backend para Elastic Beanstalk (ZIP compatible con Linux)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$zip = Join-Path $root "deploy-eb.zip"
$backend = Join-Path $root "backend"
$script = Join-Path $root "scripts\zip_eb.py"

$python = $null
foreach ($candidate in @(
    (Join-Path $backend "venv\Scripts\python.exe"),
    "py",
    "python3",
    "python"
)) {
    if ($candidate -match "python\.exe$") {
        if (Test-Path $candidate) { $python = $candidate; break }
    } elseif (Get-Command $candidate -ErrorAction SilentlyContinue) {
        if ($candidate -eq "py") { $python = "py -3" } else { $python = $candidate }
        break
    }
}

if (-not $python) {
    Write-Error "No se encontro Python. Instala Python o activa backend\venv"
}

if ($python -eq "py -3") {
    & py -3 $script $backend $zip
} else {
    & $python $script $backend $zip
}

Write-Host ""
Write-Host "Listo: $zip"
Write-Host "Sube este ZIP en EB -> Upload and deploy"
Write-Host "O usa GitHub Actions (recomendado): push a main"
