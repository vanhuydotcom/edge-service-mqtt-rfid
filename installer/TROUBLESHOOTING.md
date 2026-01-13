# Troubleshooting Guide - Circa RFID Edge Service

## Service Won't Start After Installation

### Quick Diagnostics

Run these PowerShell commands as Administrator to diagnose the issue:

```powershell
# Check if service is installed
Get-Service -Name "CircaRfidEdgeService" -ErrorAction SilentlyContinue

# Check service status
sc query CircaRfidEdgeService

# Try to start the service manually
sc start CircaRfidEdgeService

# Check Windows Event Viewer for errors
Get-EventLog -LogName Application -Source "CircaRfidEdgeService" -Newest 10 -ErrorAction SilentlyContinue
```

### Check Service Logs

The service logs are located at:
```
C:\Program Files\CircaRfidEdge\logs\edge-service.log
C:\Program Files\CircaRfidEdge\logs\edge-service-service.wrapper.log
```

View the logs:
```powershell
Get-Content "C:\Program Files\CircaRfidEdge\logs\edge-service.log" -Tail 50
Get-Content "C:\Program Files\CircaRfidEdge\logs\edge-service-service.wrapper.log" -Tail 50
```

### Common Issues and Solutions

#### 1. Service Fails to Start - "Error 1053: The service did not respond"

**Cause**: The executable is taking too long to start or crashing immediately.

**Solution**:
1. Test the executable directly:
   ```powershell
   cd "C:\Program Files\CircaRfidEdge"
   .\edge-service.exe
   ```
2. Check if it starts successfully (should show logs in console)
3. Press Ctrl+C to stop
4. If it works, the issue is with the service wrapper

#### 2. Port Already in Use (Port 8088)

**Cause**: Another application is using port 8088.

**Solution**:
```powershell
# Check what's using port 8088
netstat -ano | findstr :8088

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or change the port in config file
notepad "C:\Program Files\CircaRfidEdge\conf\edge-config.json"
# Change "port": 8088 to another port
```

#### 3. MQTT Connection Failed

**Cause**: MQTT broker not running or wrong configuration.

**Solution**:
1. Check if MQTT broker is running on localhost:1883
2. Update MQTT settings in config:
   ```powershell
   notepad "C:\Program Files\CircaRfidEdge\conf\edge-config.json"
   ```
3. Restart the service after config changes

#### 4. Permission Denied Errors

**Cause**: Service doesn't have write permissions for logs/data directories.

**Solution**:
```powershell
# Grant full permissions to the service directories
icacls "C:\Program Files\CircaRfidEdge\logs" /grant "NT AUTHORITY\SYSTEM:(OI)(CI)F"
icacls "C:\Program Files\CircaRfidEdge\data" /grant "NT AUTHORITY\SYSTEM:(OI)(CI)F"
icacls "C:\Program Files\CircaRfidEdge\conf" /grant "NT AUTHORITY\SYSTEM:(OI)(CI)F"
```

#### 5. Database Initialization Failed

**Cause**: Cannot create or access SQLite database file.

**Solution**:
1. Check if data directory exists and is writable
2. Manually create the directory:
   ```powershell
   New-Item -ItemType Directory -Force -Path "C:\Program Files\CircaRfidEdge\data"
   ```

### Manual Service Management

#### Reinstall the Service
```powershell
cd "C:\Program Files\CircaRfidEdge"

# Stop and uninstall
.\edge-service-service.exe stop
.\edge-service-service.exe uninstall

# Reinstall and start
.\edge-service-service.exe install
.\edge-service-service.exe start
```

#### Check Service Configuration
```powershell
# View the WinSW configuration
notepad "C:\Program Files\CircaRfidEdge\edge-service.xml"
```

### Testing Without Service

To test if the application works without the Windows service:

```powershell
cd "C:\Program Files\CircaRfidEdge"
.\edge-service.exe
```

If it starts successfully:
- Open browser to http://localhost:8088
- You should see the web interface
- Press Ctrl+C to stop

If this works but the service doesn't, the issue is with WinSW configuration.

### Getting More Detailed Logs

Enable debug logging:
1. Set environment variable before starting:
   ```powershell
   $env:EDGE_LOG_LEVEL = "DEBUG"
   .\edge-service.exe
   ```

### Contact Support

If none of these solutions work, collect the following information:
1. Service logs from `C:\Program Files\CircaRfidEdge\logs\`
2. Output of `sc query CircaRfidEdgeService`
3. Windows Event Viewer errors
4. Output of running `.\edge-service.exe` directly

