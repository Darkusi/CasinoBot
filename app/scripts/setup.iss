; Claims Casino Automation Suite Installer
; Inno Setup 6 Script

#define MyAppName "Claims Casino Automation Suite"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Claims Casino 2026"
#define MyAppURL "https://claimscasino.com"
#define MyAppExeName "CasinoBot.exe"

[Setup]
AppId={{B8F7C3A1-2D4E-5F6A-8B9C-0D1E2F3A4B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\build
OutputBaseFilename=CasinoBot-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableWelcomePage=no
CloseApplications=yes
RestartApplications=no
DisableFinishedPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\CasinoBot.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\.env"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\sites.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\logo.png"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Code]
var
  LaunchCheck: TNewCheckBox;

procedure InitializeWizard;
begin
  LaunchCheck := TNewCheckBox.Create(WizardForm);
  LaunchCheck.Parent := WizardForm.FinishedPage;
  LaunchCheck.Caption := 'Launch Claims Casino Automation Suite';
  LaunchCheck.Checked := True;
  LaunchCheck.Left := WizardForm.FinishedPage.Left + 40;
  LaunchCheck.Top := WizardForm.FinishedPage.Top + 136;
  LaunchCheck.Width := 300;
end;

function LaunchApp: Boolean;
begin
  Result := LaunchCheck.Checked;
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifsilent; Check: LaunchApp
