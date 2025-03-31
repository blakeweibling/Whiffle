; WhiffleTrackerSetup.iss
; Inno Setup script to create an installer for WhiffleTracker.exe and its associated files

[Setup]
AppName=WhiffleTracker
AppVersion=1.0
DefaultDirName={autopf}\WhiffleTracker
DefaultGroupName=WhiffleTracker
OutputDir=F:\Whiffle\10.4 (onthefloor)\installer
OutputBaseFilename=WhiffleTrackerSetup
SetupIconFile=F:\Whiffle\10.4 (onthefloor)\pinball_icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
; The executable from the dist folder
Source: "F:\Whiffle\10.4 (onthefloor)\dist\WhiffleTracker.exe"; DestDir: "{app}"; Flags: ignoreversion

; JSON configuration files
Source: "F:\Whiffle\10.4 (onthefloor)\achievements.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\Whiffle\10.4 (onthefloor)\hsv_ranges.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\Whiffle\10.4 (onthefloor)\scoring_zones.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\Whiffle\10.4 (onthefloor)\whiffle_leaderboard.json"; DestDir: "{app}"; Flags: ignoreversion

; Media files
Source: "F:\Whiffle\10.4 (onthefloor)\background_music.mp3"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\Whiffle\10.4 (onthefloor)\ding.wav"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\Whiffle\10.4 (onthefloor)\splash.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\Whiffle\10.4 (onthefloor)\last_frame.png"; DestDir: "{app}"; Flags: ignoreversion

; Environment file
Source: "F:\Whiffle\10.4 (onthefloor)\.env"; DestDir: "{app}"; Flags: ignoreversion

; YOLOv8 model files
Source: "F:\Whiffle\10.4 (onthefloor)\whiffle_new_best.pt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Create a Start menu shortcut
Name: "{group}\WhiffleTracker"; Filename: "{app}\WhiffleTracker.exe"

; Create an uninstall shortcut in the Start menu
Name: "{group}\Uninstall WhiffleTracker"; Filename: "{uninstallexe}"

[Run]
; Optional: Launch the application after installation
Filename: "{app}\WhiffleTracker.exe"; Description: "Launch WhiffleTracker"; Flags: nowait postinstall skipifsilent