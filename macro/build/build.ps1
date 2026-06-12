# Builds dist\BiomeBeacon.exe (PyInstaller onefile).
# Usage:  pwsh macro/build/build.ps1 [-Python path\to\python.exe]
param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$buildDir = $PSScriptRoot
$repoRoot = Split-Path (Split-Path $buildDir -Parent) -Parent

if (-not $Python) {
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $Python = (Test-Path $venvPython) ? $venvPython : "python"
}

Write-Host "Using Python: $Python"
& $Python -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller missing - installing..."
    & $Python -m pip install pyinstaller
}

& $Python -m PyInstaller `
    --noconfirm --clean `
    --distpath (Join-Path $buildDir "dist") `
    --workpath (Join-Path $buildDir "work") `
    (Join-Path $buildDir "biomebeacon.spec")

if ($LASTEXITCODE -eq 0) {
    $exe = Join-Path $buildDir "dist\BiomeBeacon.exe"
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "`nOK: $exe ($size MB)"
} else {
    exit $LASTEXITCODE
}
