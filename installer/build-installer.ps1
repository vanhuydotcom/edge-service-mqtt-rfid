# Build script for Circa RFID Edge Service Installer
# This script builds the complete Windows installer locally

param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building Circa RFID Edge Service v$Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "`n[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Please install Python 3.12+" -ForegroundColor Red
    exit 1
}

# Check Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js not found. Please install Node.js 22+" -ForegroundColor Red
    exit 1
}

# Check PyInstaller
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller
}

# Check Inno Setup
$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $InnoSetupPath)) {
    Write-Host "ERROR: Inno Setup not found at $InnoSetupPath" -ForegroundColor Red
    Write-Host "Please install Inno Setup from https://jrsoftware.org/isdl.php" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] All prerequisites found" -ForegroundColor Green

Write-Host "`n[2/6] Installing Python dependencies..." -ForegroundColor Yellow
Set-Location "$RootDir\backend"
python -m pip install -e .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[3/6] Building Frontend..." -ForegroundColor Yellow
Set-Location "$RootDir\frontend"
npm install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[4/6] Building Backend with PyInstaller..." -ForegroundColor Yellow
Set-Location "$ScriptDir"
python -m PyInstaller --clean --noconfirm edge-service.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[5/6] Downloading WinSW..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "winsw" | Out-Null
if (-not (Test-Path "winsw\WinSW-x64.exe")) {
    Invoke-WebRequest -Uri "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe" -OutFile "winsw\WinSW-x64.exe"
    Write-Host "[OK] WinSW downloaded" -ForegroundColor Green
} else {
    Write-Host "[OK] WinSW already exists" -ForegroundColor Green
}

Write-Host "`n[6/6] Building Installer with Inno Setup..." -ForegroundColor Yellow
# Update version in ISS file
$IssFile = "circa-rfid-edge-setup.iss"
$IssContent = Get-Content $IssFile -Raw
$IssContent = $IssContent -replace '#define MyAppVersion ".*"', "#define MyAppVersion `"$Version`""
Set-Content -Path $IssFile -Value $IssContent

& $InnoSetupPath $IssFile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Installer location: $ScriptDir\output\Circa-RfidEdge-Setup-$Version.exe" -ForegroundColor Cyan
Write-Host ""

