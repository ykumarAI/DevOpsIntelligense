# Builds a single self-contained Windows executable: dist\DevOpsDashboard.exe
# The resulting EXE needs NO prerequisites on the target machine
# (Python, Node, and all dependencies are bundled inside).
#
# Only THIS build machine needs Python 3.10+ and Node.js installed.
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"

function Resolve-Python {
    # Avoid the Microsoft Store alias stub in WindowsApps.
    $venvPy = Join-Path $backend ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return $venvPy }
    foreach ($name in @("py", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
            if ($name -eq "py") { return "py -3" }
            return $cmd.Source
        }
    }
    $known = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $known) { return $known }
    throw "No usable Python found. Install Python 3.10+ (python.org) and re-run."
}

Write-Host "==> [1/5] Building frontend..." -ForegroundColor Cyan
Push-Location $frontend
if (-not (Test-Path "node_modules")) { npm.cmd install }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
Pop-Location

Write-Host "==> [2/5] Copying frontend into backend/frontend_dist..." -ForegroundColor Cyan
$distSrc = Join-Path $frontend "dist"
$distDest = Join-Path $backend "frontend_dist"
if (Test-Path $distDest) { Remove-Item $distDest -Recurse -Force }
Copy-Item $distSrc $distDest -Recurse

Write-Host "==> [3/5] Preparing Python environment..." -ForegroundColor Cyan
$python = Resolve-Python
Push-Location $backend
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Expression "& $python -m venv .venv"
}
$py = Join-Path $backend ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
& $py -m pip install -r requirements-build.txt

Write-Host "==> [4/5] Building EXE with PyInstaller..." -ForegroundColor Cyan
& $py -m PyInstaller --clean --noconfirm dashboard.spec
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "PyInstaller build failed." }
Pop-Location

Write-Host "==> [5/5] Collecting output..." -ForegroundColor Cyan
$exeSrc = Join-Path $backend "dist\DevOpsDashboard.exe"
$outDir = Join-Path $root "dist"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
Copy-Item $exeSrc $outDir -Force

$final = Join-Path $outDir "DevOpsDashboard.exe"
$sizeMB = [math]::Round((Get-Item $final).Length / 1MB, 1)
Write-Host ""
Write-Host "SUCCESS: $final ($sizeMB MB)" -ForegroundColor Green
Write-Host "Ship this single .exe." -ForegroundColor Green
Write-Host "no Python, Node, or other prerequisites required." -ForegroundColor Green
