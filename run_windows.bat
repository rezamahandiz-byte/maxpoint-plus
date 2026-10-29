@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo MAXPOINT Plus - Windows launcher
echo ============================================================

if not exist ".venv\Scripts\python.exe" goto create_venv
goto install_deps

:create_venv
where py >nul 2>nul
if errorlevel 1 goto no_python
py -3.14 --version >nul 2>nul
if not errorlevel 1 goto make_314
py -3.13 --version >nul 2>nul
if not errorlevel 1 goto make_313
py -3.12 --version >nul 2>nul
if not errorlevel 1 goto make_312
goto no_python

:make_314
py -3.14 -m venv .venv
goto venv_created
:make_313
py -3.13 -m venv .venv
goto venv_created
:make_312
py -3.12 -m venv .venv
goto venv_created

:venv_created
if errorlevel 1 goto failed

:install_deps
echo Installing/updating project dependencies. Internet is required on first run.
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto failed

echo Starting MAXPOINT Plus...
.venv\Scripts\flet.exe run src\main.py
if errorlevel 1 goto failed
exit /b 0

:no_python
echo ERROR: Python 3.12, 3.13, or 3.14 was not found via the Windows py launcher.
echo Install 64-bit Python from python.org, enable the py launcher, then retry.
pause
exit /b 1

:failed
echo.
echo MAXPOINT could not start. Keep the first ERROR message and share it for diagnosis.
pause
exit /b 1
