@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "IVANTI=C:\Program Files (x86)\Ivanti\Workspace Control\pwrgate.exe"
if not exist "%IVANTI%" (
  where pythonw.exe >nul 2>nul
  if errorlevel 1 (
    echo Python ble ikke funnet. Installer Python 3.11+ og appens avhengigheter.
    pause
    exit /b 1
  )
  start "" pythonw.exe "%~dp0start_python_felles.py"
  exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=(Resolve-Path -LiteralPath './start_python_felles.py').Path; $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($p)); Set-Clipboard -Value ('import runpy, base64; runpy.run_path(base64.b64decode(''' + $encoded + ''').decode(''utf-8''), run_name=''solide_start_felles'')[''main'']()')"
if errorlevel 1 exit /b 1
start "" "%IVANTI%" 15694
echo Lim inn kommandoen i Python FELLES med Ctrl+V og trykk Enter.
pause
