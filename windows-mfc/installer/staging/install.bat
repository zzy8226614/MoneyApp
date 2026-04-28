@echo off
setlocal

set "TARGET=%LOCALAPPDATA%\MoneyAPPDesktop"
set "SRC=%~dp0"

if not exist "%TARGET%" mkdir "%TARGET%"
if not exist "%TARGET%\web\desktop-shell\src" mkdir "%TARGET%\web\desktop-shell\src"

copy /Y "%SRC%MoneyAppDesktop.exe" "%TARGET%\MoneyAppDesktop.exe" >nul
copy /Y "%SRC%index.html" "%TARGET%\web\desktop-shell\index.html" >nul
copy /Y "%SRC%app.js" "%TARGET%\web\desktop-shell\src\app.js" >nul
copy /Y "%SRC%bridge.js" "%TARGET%\web\desktop-shell\src\bridge.js" >nul
copy /Y "%SRC%styles.css" "%TARGET%\web\desktop-shell\src\styles.css" >nul

set "SHORTCUT_PS=%TEMP%\moneyapp_shortcut_%RANDOM%.ps1"
(
  echo $ws = New-Object -ComObject WScript.Shell
  echo $desktop = [Environment]::GetFolderPath('Desktop')
  echo $lnk = $ws.CreateShortcut((Join-Path $desktop 'MoneyAPP Desktop.lnk'))
  echo $lnk.TargetPath = '%TARGET%\MoneyAppDesktop.exe'
  echo $lnk.WorkingDirectory = '%TARGET%'
  echo $lnk.Save()
) > "%SHORTCUT_PS%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SHORTCUT_PS%" >nul 2>nul
del /Q "%SHORTCUT_PS%" >nul 2>nul

start "" "%TARGET%\MoneyAppDesktop.exe"
exit /b 0
