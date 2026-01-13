# Circa RFID Edge Service Installer

This directory contains the configuration and scripts to build a Windows installer for the RFID Edge Service.

## What Gets Installed

The installer packages:
- **Backend**: FastAPI service compiled to a standalone `.exe` with PyInstaller
- **Frontend**: React web interface (static files)
- **All Dependencies**: Python packages and Node.js modules are bundled
- **Windows Service**: Automatically installs and starts as a Windows service using WinSW

## Prerequisites

### For Building Locally (Windows only)

1. **Python 3.12+**
   - Download from https://www.python.org/downloads/

2. **Node.js 22+**
   - Download from https://nodejs.org/

3. **Inno Setup 6**
   - Download from https://jrsoftware.org/isdl.php
   - Install to default location: `C:\Program Files (x86)\Inno Setup 6`

4. **PyInstaller**
   - Will be installed automatically by the build script

## Building the Installer

### Option 1: Local Build (Windows)

```powershell
cd installer
.\build-installer.ps1 -Version "1.0.0"
```

The installer will be created in `installer/output/Circa-RfidEdge-Setup-1.0.0.exe`

### Option 2: GitHub Actions (Any OS)

Push a tag to trigger the build:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Or manually trigger from GitHub UI:
1. Go to Actions → Build Windows Installer
2. Click "Run workflow"
3. Enter version number
4. Download the artifact when complete

## What the Installer Does

1. **Installs files** to `C:\Program Files\CircaRfidEdge\`
2. **Creates directories**:
   - `logs/` - Service logs
   - `data/` - SQLite database
   - `conf/` - Configuration files
3. **Installs Windows service** named "Circa RFID Edge Service"
4. **Starts the service** automatically
5. **Opens web interface** at http://localhost:8088

## After Installation

### Access the Web Interface
Open your browser to: http://localhost:8088

### Manage the Service

```powershell
# Stop service
cd "C:\Program Files\CircaRfidEdge"
.\edge-service-service.exe stop

# Start service
.\edge-service-service.exe start

# Restart service
.\edge-service-service.exe restart

# Check status
.\edge-service-service.exe status
```

### Configuration

Edit configuration files in:
```
C:\Program Files\CircaRfidEdge\conf\edge-config.json
```

After changing configuration, restart the service.

### View Logs

Logs are located in:
```
C:\Program Files\CircaRfidEdge\logs\
```

## Uninstallation

Use Windows "Add or Remove Programs" or run:
```
C:\Program Files\CircaRfidEdge\unins000.exe
```

The uninstaller will:
1. Stop the service
2. Uninstall the service
3. Remove all files (except user data in `data/` and `conf/`)

## Files in This Directory

- `edge-service.spec` - PyInstaller configuration for building the .exe
- `edge-service.xml` - WinSW service configuration
- `circa-rfid-edge-setup.iss` - Inno Setup installer script
- `build-installer.ps1` - PowerShell build script for local builds
- `assets/` - Icons and other assets
- `output/` - Built installers (generated)
- `dist/` - PyInstaller output (generated)
- `winsw/` - WinSW executable (downloaded)

## Troubleshooting

### Build fails with "Python not found"
Make sure Python is in your PATH. Restart PowerShell after installing Python.

### Build fails with "Inno Setup not found"
Install Inno Setup to the default location or update the path in `build-installer.ps1`.

### Service won't start
Check logs in `C:\Program Files\CircaRfidEdge\logs\` for error messages.

### Port 8088 already in use
Another service is using port 8088. Stop that service or change the port in `conf/edge-config.json`.

