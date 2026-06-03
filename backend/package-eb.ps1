# Genera deploy-eb.zip con la estructura correcta para Elastic Beanstalk
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$zip = Join-Path (Split-Path $root -Parent) "deploy-eb.zip"

if (Test-Path $zip) { Remove-Item $zip -Force }

Push-Location $root
try {
    Compress-Archive -Path @(
        "app",
        "Procfile",
        "requirements.txt",
        "application.py",
        ".ebextensions"
    ) -DestinationPath $zip -Force
} finally {
    Pop-Location
}

Write-Host "Creado: $zip"
Write-Host "Raiz del ZIP: Procfile, requirements.txt, app/, application.py"
Write-Host "Despliega con: eb deploy (desde backend) o sube deploy-eb.zip a EB."
