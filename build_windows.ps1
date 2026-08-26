<#
.SYNOPSIS
    Unified Windows Build Script for IRIS AI (Python Backend + Electron Frontend).
.DESCRIPTION
    Compiles the Python backend using PyInstaller into a windowless binary and bundles
    it with the Electron frontend via electron-builder into NSIS installer and portable EXE.
.PARAMETER Clean
    Cleans previous build and release directories before building.
.PARAMETER Target
    Build target: 'all' (NSIS + Portable, default), 'dir' (unpacked directory for fast testing), or 'installer' (NSIS only).
#>

[CmdletBinding()]
param (
    [switch]$Clean,
    [ValidateSet("all", "dir", "installer", "portable")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          IRIS AI -- Windows Build and Packaging Tool       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check prerequisites
$PythonExe = Join-Path $ScriptDir "backend\venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = Join-Path $ScriptDir "backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Virtualenv Python not found at: $PythonExe" -ForegroundColor Red
    Write-Host "Please set up the backend virtual environment first." -ForegroundColor Yellow
    exit 1
}

$NpmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $NpmCmd) {
    Write-Host "[ERROR] 'npm' command not found. Please ensure Node.js is installed." -ForegroundColor Red
    exit 1
}

# 2. Clean if requested
if ($Clean) {
    Write-Host ""
    Write-Host "[1/4] Cleaning previous build artifacts..." -ForegroundColor Yellow
    $PathsToClean = @(
        (Join-Path $ScriptDir "dist"),
        (Join-Path $ScriptDir "build"),
        (Join-Path $ScriptDir "frontend\dist"),
        (Join-Path $ScriptDir "frontend\release")
    )
    foreach ($p in $PathsToClean) {
        if (Test-Path $p) {
            Write-Host "  Removing: $p" -ForegroundColor DarkGray
            Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue
        }
    }
}

# 3. Build Backend using PyInstaller
Write-Host ""
Write-Host "[2/4] Compiling Python Backend with PyInstaller..." -ForegroundColor Green
$SpecFile = Join-Path $ScriptDir "iris_backend.spec"
& $PythonExe -m PyInstaller --clean -y $SpecFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller build failed." -ForegroundColor Red
    exit 1
}

$BackendExe = Join-Path $ScriptDir "dist\iris_backend\iris_backend.exe"
if (-not (Test-Path $BackendExe)) {
    Write-Host "[ERROR] Compiled backend executable not found at: $BackendExe" -ForegroundColor Red
    exit 1
}
Write-Host "  Backend executable compiled successfully: $BackendExe" -ForegroundColor Green

# 4. Build Frontend Vite Assets
Write-Host ""
Write-Host "[3/4] Building Frontend Vite assets..." -ForegroundColor Green
$FrontendDir = Join-Path $ScriptDir "frontend"
npm --prefix $FrontendDir run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend Vite build failed." -ForegroundColor Red
    exit 1
}

# 5. Package with Electron-Builder
Write-Host ""
Write-Host "[4/4] Packaging Electron Desktop Application..." -ForegroundColor Green
switch ($Target) {
    "dir" {
        npm --prefix $FrontendDir run package:dir
    }
    "installer" {
        npm --prefix $FrontendDir run package:installer
    }
    default {
        npm --prefix $FrontendDir run package:installer
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Electron-Builder packaging failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "                  BUILD COMPLETED SUCCESSFULLY               " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$ReleaseDir = Join-Path $ScriptDir "frontend\release"
if (Test-Path $ReleaseDir) {
    Write-Host ""
    Write-Host "Output Artifacts in: $ReleaseDir" -ForegroundColor Green
    Get-ChildItem $ReleaseDir -File | Format-Table Name, Length, LastWriteTime -AutoSize
}
