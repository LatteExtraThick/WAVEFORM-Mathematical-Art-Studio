; Inno Setup script. Build after running build_windows.bat.
#define MyAppName "WAVEFORM"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "WAVEFORM Studio"
#define MyAppExeName "WAVEFORM.exe"

[Setup]
AppId={{B7E26F3D-3A20-4A88-91F3-62B1C5E6A8D1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WAVEFORM
DefaultGroupName=WAVEFORM
OutputDir=Output
OutputBaseFilename=WAVEFORM_Setup
SetupIconFile=..\assets\waveform.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\WAVEFORM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\WAVEFORM"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\WAVEFORM"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch WAVEFORM"; Flags: postinstall nowait skipifsilent
