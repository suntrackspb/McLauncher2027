#define AppName GetEnv("APP_NAME")
#define AppId GetEnv("BUNDLE_ID")
#define AppVersion GetEnv("LAUNCHER_VERSION")
#define LauncherExe AppName + ".exe"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\dist
OutputBaseFilename=McLauncher2027-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\launcher\{#LauncherExe}
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
; The updater replaces launcher\ in full. Inno's uninstaller lives in {app}.
Source: "..\dist\{#AppName}\*"; DestDir: "{app}\launcher"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\launcher\{#LauncherExe}"; WorkingDir: "{app}\launcher"

[Run]
Filename: "{app}\launcher\{#LauncherExe}"; WorkingDir: "{app}\launcher"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Also remove files added by an in-app update after installation.
Type: filesandordirs; Name: "{app}\launcher"
