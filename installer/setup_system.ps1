# setup_system.ps1 - Configure local machine for Circa RFID Edge
# - Imports mkcert Root CA (rootCA.pem) into LocalMachine\Root store
#
# Usage: Run as Administrator. The installer will execute this script automatically.
# Customization: Place rootCA.pem in the same folder as this script before building the installer.

$ErrorActionPreference = 'Stop'

function Ensure-Admin {
    $wi = [Security.Principal.WindowsIdentity]::GetCurrent()
    $wp = New-Object Security.Principal.WindowsPrincipal($wi)
    if (-not $wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "Elevating to Administrator..." -ForegroundColor Yellow
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
        exit 0
    }
}

function Install-RootCA {
    param(
        [string]$RootCAPath
    )
    if (-not (Test-Path $RootCAPath)) {
        Write-Host "[rootCA] rootCA.pem not found at $RootCAPath. Skipping import." -ForegroundColor Yellow
        return $false
    }

    try {
        $size = (Get-Item $RootCAPath).Length
        if ($size -lt 100) {
            Write-Host "[rootCA] File too small (likely placeholder). Skipping import." -ForegroundColor Yellow
            return $false
        }
    } catch {}

    Write-Host "[rootCA] Importing Root CA into Trusted Root store..." -ForegroundColor Cyan
    try {
        # Prefer Import-Certificate (Windows API)
        Import-Certificate -FilePath $RootCAPath -CertStoreLocation "cert:\LocalMachine\Root" -ErrorAction Stop | Out-Null
        Write-Host "[rootCA] Imported into LocalMachine\Root" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[rootCA] Import-Certificate failed, trying certutil..." -ForegroundColor Yellow
    }

    try {
        $p = Start-Process -FilePath "certutil.exe" -ArgumentList @("-f","-addstore","Root", $RootCAPath) -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -eq 0) {
            Write-Host "[rootCA] Installed via certutil." -ForegroundColor Green
            return $true
        } else {
            Write-Error "[rootCA] certutil failed with exit code $($p.ExitCode)"
        }
    } catch {
        Write-Error "[rootCA] Failed to install certificate: $($_.Exception.Message)"
        throw
    }
    return $false
}

# ---- Main ----
Ensure-Admin

$RootCAPath = Join-Path $PSScriptRoot 'rootCA.pem'

$installed = Install-RootCA -RootCAPath $RootCAPath

if ($installed) {
    Write-Host "Root CA installed successfully. Client will now trust the server certificate." -ForegroundColor Green
} else {
    Write-Host "Root CA not installed. Please ensure rootCA.pem is present in installer assets." -ForegroundColor Yellow
}

Write-Host "Setup completed." -ForegroundColor Green

