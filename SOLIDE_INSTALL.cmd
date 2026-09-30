@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "IVANTI=C:\Program Files (x86)\Ivanti\Workspace Control\pwrgate.exe"
if not exist "%IVANTI%" (
  echo Ivanti ble ikke funnet. Bruk python install_python_felles.py pa lokal utviklings-PC.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=(Resolve-Path -LiteralPath './install_python_felles.py').Path; $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($p)); Set-Clipboard -Value ('import runpy, base64; runpy.run_path(base64.b64decode(''' + $encoded + ''').decode(''utf-8''), run_name=''solide_install_felles'')[''main'']()')"
if errorlevel 1 exit /b 1
start "" "%IVANTI%" 15694
echo Lim inn kommandoen i Python FELLES med Ctrl+V og trykk Enter.
pause
