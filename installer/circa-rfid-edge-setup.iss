; Inno Setup Script for Circa RFID Edge Service
; This creates a Windows installer that packages the backend .exe and frontend static files

#define MyAppName "Circa RFID Edge Service"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Circa"
#define MyAppURL "https://circa.vn"
#define MyAppExeName "edge-service.exe"
#define MyAppServiceName "CircaRfidEdgeService"

[Setup]
AppId={{A5B6C7D8-E9F0-4A1B-2C3D-4E5F6A7B8C9D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\CircaRfidEdge
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=output
OutputBaseFilename=Circa-RfidEdge-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Backend executable and dependencies
Source: "dist\edge-service\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; WinSW for running as Windows service
Source: "winsw\WinSW-x64.exe"; DestDir: "{app}"; DestName: "edge-service-service.exe"; Flags: ignoreversion
Source: "edge-service.xml"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\logs"; Permissions: users-full
Name: "{app}\data"; Permissions: users-full
Name: "{app}\conf"; Permissions: users-full

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "http://localhost:8088"
Name: "{group}\Open Web Interface"; Filename: "http://localhost:8088"
Name: "{group}\Configuration Folder"; Filename: "{app}\conf"
Name: "{group}\Logs Folder"; Filename: "{app}\logs"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Install and start the service
Filename: "{app}\edge-service-service.exe"; Parameters: "install"; StatusMsg: "Installing service..."; Flags: runhidden
Filename: "{app}\edge-service-service.exe"; Parameters: "start"; StatusMsg: "Starting service..."; Flags: runhidden
; Open web interface after installation
Filename: "http://localhost:8088"; Description: "Open Web Interface"; Flags: shellexec postinstall skipifsilent nowait

[UninstallRun]
; Stop and uninstall the service
Filename: "{app}\edge-service-service.exe"; Parameters: "stop"; Flags: runhidden
Filename: "{app}\edge-service-service.exe"; Parameters: "uninstall"; Flags: runhidden

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  // Check if service is already installed and stop it
  if FileExists(ExpandConstant('{app}\edge-service-service.exe')) then
  begin
    Exec(ExpandConstant('{app}\edge-service-service.exe'), 'stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{app}\edge-service-service.exe'), 'uninstall', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

