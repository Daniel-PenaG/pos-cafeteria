# Empaqueta el backend para Elastic Beanstalk (sin venv, .env ni BD local)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$zip = Join-Path $root "deploy-eb.zip"

if (Test-Path $zip) { Remove-Item $zip -Force }

Push-Location (Join-Path $root "backend")
try {
    Compress-Archive -Path @(
        "app",
        "Procfile",
        "requirements.txt",
        ".ebextensions",
        ".platform"
    ) -DestinationPath $zip -Force
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Listo: $zip"
Write-Host "Sube este ZIP a Elastic Beanstalk."
Write-Host "Frontend: conecta Amplify al repo (usa amplify.yml en la raiz)."
