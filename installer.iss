#define MyAppName "FFT Gyro PRYM"
#define MyAppVersion "1.0"
#define MyAppPublisher "Neel"
#define MyAppExeName "FFT Gyro PRYM.exe"
#define PythonVersion "3.13.1"
#define PythonInstallerName "python-3.13.1-amd64.exe"

[Setup]
AppId={{B8A8DA33-4FCE-42F9-B6DC-123456789ABC}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=FFTGyroPRYM_FullSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Python installer
Source: "installers\{#PythonInstallerName}"; DestDir: "{tmp}"; Flags: deleteafterinstall
; get-pip.py script
Source: "installers\get-pip.py"; DestDir: "{tmp}"; Flags: deleteafterinstall
; Application files
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Required Python packages
Source: "requirements\*"; DestDir: "{tmp}\requirements"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Install Python only if not installed
Filename: "{tmp}\{#PythonInstallerName}"; \
    Parameters: "/quiet InstallAllUsers=1 PrependPath=1"; \
    StatusMsg: "Installing Python {#PythonVersion}..."; \
    Check: not IsPythonInstalled; \
    Flags: waituntilterminated

; Install pip first using get-pip.py
Filename: "{code:GetPythonPath}"; \
    Parameters: "{tmp}\get-pip.py"; \
    StatusMsg: "Installing pip..."; \
    WorkingDir: "{tmp}"; \
    Flags: waituntilterminated runhidden; \
    Check: FileExists('{code:GetPythonPath}')

; Then install required packages
Filename: "{code:GetPythonPath}"; \
    Parameters: "-m pip install -r ""{tmp}\requirements\requirements.txt"""; \
    StatusMsg: "Installing required packages..."; \
    WorkingDir: "{tmp}"; \
    Flags: waituntilterminated runhidden; \
    Check: FileExists('{code:GetPythonPath}')

; Launch application
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
    PythonPath: String;
begin
    Result := True;
    
    // Check if Python exists at the expected location
    PythonPath := GetPythonPath;
    if not FileExists(PythonPath) then
    begin
        MsgBox('Python installation not found at: ' + PythonPath + #13#10 +
               'The installer will attempt to install Python.', mbInformation, MB_OK);
    end;
end;

function GetPythonPath: String;
begin
    // Try different possible Python locations
    if FileExists('C:\Users\' + GetUserNameString + '\AppData\Local\Programs\Python\Python' + Copy('{#PythonVersion}', 1, 4) + '\python.exe') then
        Result := 'C:\Users\' + GetUserNameString + '\AppData\Local\Programs\Python\Python' + Copy('{#PythonVersion}', 1, 4) + '\python.exe'
    else if FileExists('C:\Python' + Copy('{#PythonVersion}', 1, 4) + '\python.exe') then
        Result := 'C:\Python' + Copy('{#PythonVersion}', 1, 4) + '\python.exe'
    else if FileExists(ExpandConstant('{pf}\Python' + Copy('{#PythonVersion}', 1, 4) + '\python.exe')) then
        Result := ExpandConstant('{pf}\Python' + Copy('{#PythonVersion}', 1, 4) + '\python.exe')
    else
        Result := 'python.exe';  // Try using PATH
end;

function GetUserNameString: String;
var
    Size: DWORD;
    Name: String;
begin
    Size := 256;
    SetLength(Name, Size);
    if GetUserName(Name, Size) then
        Result := Copy(Name, 1, Size - 1)
    else
        Result := 'Default';
end;

function IsPythonInstalled: Boolean;
var
    PythonPath: String;
begin
    Result := RegQueryStringValue(HKEY_LOCAL_MACHINE,
        'SOFTWARE\Python\PythonCore\{#PythonVersion}\InstallPath',
        '', PythonPath);
end;

function GetPythonDir(Value: string): string;
var
    InstallPath: string;
begin
    if RegQueryStringValue(HKEY_LOCAL_MACHINE,
      'SOFTWARE\Python\PythonCore\{#PythonVersion}\InstallPath',
      '', InstallPath) then
        Result := InstallPath
    else if RegQueryStringValue(HKEY_CURRENT_USER,
      'SOFTWARE\Python\PythonCore\{#PythonVersion}\InstallPath',
      '', InstallPath) then
        Result := InstallPath
    else
        Result := ExpandConstant('{pf}\Python{#PythonVersion}');
end;

function GetPipPath: String;
var
    PythonPath: String;
begin
    PythonPath := GetPythonDir('');
    if DirExists(PythonPath + '\Scripts') then
        Result := PythonPath + '\Scripts\pip.exe'
    else
        Result := PythonPath + '\pip.exe';
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}" 