@echo off
setlocal
chcp 65001 >nul
set "SOLIDE_SCRIPT=%~dp0start_python_felles.py"
if not defined SOLIDE_IVANTI set "SOLIDE_IVANTI=C:\Program Files (x86)\Ivanti\Workspace Control\pwrgate.exe"

if not exist "%SOLIDE_SCRIPT%" goto missing_project
if not exist "%~dp0pyproject.toml" goto missing_project
if not exist "%~dp0src\solide\" goto missing_project
if exist "%SOLIDE_IVANTI%" goto felles

rem Ordinary Windows PC: use the same interpreter for install and start.
if defined SOLIDE_PYTHON goto custom_python
where py.exe >nul 2>nul
if not errorlevel 1 goto python_launcher
where python.exe >nul 2>nul
if errorlevel 1 goto missing_python
python.exe "%SOLIDE_SCRIPT%" %*
set "SOLIDE_EXIT=%errorlevel%"
goto local_done

:python_launcher
py.exe -3 "%SOLIDE_SCRIPT%" %*
set "SOLIDE_EXIT=%errorlevel%"
goto local_done

:custom_python
if not exist "%SOLIDE_PYTHON%" goto missing_python
"%SOLIDE_PYTHON%" "%SOLIDE_SCRIPT%" %*
set "SOLIDE_EXIT=%errorlevel%"
goto local_done

:local_done
if not "%SOLIDE_EXIT%"=="0" pause
exit /b %SOLIDE_EXIT%

:felles
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $p=(Resolve-Path -LiteralPath $env:SOLIDE_SCRIPT).Path; $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($p)); Set-Clipboard -Value ('import runpy, base64; runpy.run_path(base64.b64decode(''' + $encoded + ''').decode(''utf-8''), run_name=''solide_start_felles'')[''main'']()')"
if errorlevel 1 (
  echo Could not copy the Python FELLES command. Try again.
  pause
  exit /b 1
)
start "" "%SOLIDE_IVANTI%" 15694
if errorlevel 1 (
  echo Could not open Python FELLES through Ivanti.
  pause
  exit /b 1
)
echo Python FELLES opens through Ivanti.
echo Paste the copied command with Ctrl+V, then press Enter.
echo Keep the whole Solide folder in its permanent location.
pause
exit /b 0

:missing_project
echo Cannot find the complete Solide project next to this CMD file.
echo Extract the whole project first. Do not copy only the launcher files.
pause
exit /b 1

:missing_python
echo Python FELLES / Ivanti and a usable local Python were not found.
echo On a work PC, check that Python FELLES is available through Ivanti.
echo On a local PC, install Python 3.11+ or set SOLIDE_PYTHON to its full executable path.
pause
exit /b 1
