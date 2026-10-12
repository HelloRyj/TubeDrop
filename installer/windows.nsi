Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!include "FileFunc.nsh"

Name "TubeDrop"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\TubeDrop"
InstallDirRegKey HKCU "Software\TubeDrop\Installer" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
ShowInstDetails show
ShowUninstDetails show
Icon "${PAYLOAD}/app/icon.ico"
UninstallIcon "${PAYLOAD}/app/icon.ico"
VIProductVersion "1.1.0.0"
VIAddVersionKey "ProductName" "TubeDrop"
VIAddVersionKey "FileDescription" "TubeDrop Windows Installer"
VIAddVersionKey "FileVersion" "1.1.0"
VIAddVersionKey "LegalCopyright" "TubeDrop contributors"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchTubeDrop
!define MUI_FINISHPAGE_RUN_TEXT "打开 TubeDrop"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "TubeDrop 需要 64 位 Windows。"
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "TubeDrop 需要 Windows 10 或更新版本。"
    Abort
  ${EndIf}
FunctionEnd

Function .onVerifyInstDir
  ${GetFileName} "$INSTDIR" $0
  ${If} $0 != "TubeDrop"
    MessageBox MB_ICONEXCLAMATION "请选择名为 TubeDrop 的独立安装目录。"
    Abort
  ${EndIf}
FunctionEnd

Section "TubeDrop"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}/*"
  WriteINIStr "$INSTDIR\installation.ini" "TubeDrop" "AppId" "local.tubedrop.desktop"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\TubeDrop"
  CreateShortcut "$SMPROGRAMS\TubeDrop\TubeDrop.lnk" "$INSTDIR\runtime\pythonw.exe" '$\"$INSTDIR\app\windows_launcher.py$\"' "$INSTDIR\app\icon.ico"
  CreateShortcut "$SMPROGRAMS\TubeDrop\卸载 TubeDrop.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\TubeDrop\Installer" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "DisplayName" "TubeDrop"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "DisplayVersion" "1.1.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "DisplayIcon" "$INSTDIR\app\icon.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop" "NoRepair" 1
SectionEnd

Function LaunchTubeDrop
  Exec '$\"$INSTDIR\runtime\pythonw.exe$\" $\"$INSTDIR\app\windows_launcher.py$\"'
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  ${un.GetFileName} "$INSTDIR" $0
  ReadINIStr $1 "$INSTDIR\installation.ini" "TubeDrop" "AppId"
  ${If} $0 != "TubeDrop"
  ${OrIf} $1 != "local.tubedrop.desktop"
    MessageBox MB_ICONSTOP "安装目录校验失败，已停止卸载。"
    Abort
  ${EndIf}
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\bin"
  Delete "$INSTDIR\dependencies.json"
  Delete "$INSTDIR\installation.ini"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\TubeDrop\TubeDrop.lnk"
  Delete "$SMPROGRAMS\TubeDrop\卸载 TubeDrop.lnk"
  RMDir "$SMPROGRAMS\TubeDrop"
  DeleteRegKey HKCU "Software\TubeDrop\Installer"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TubeDrop"
SectionEnd
