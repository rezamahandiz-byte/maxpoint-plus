@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo MAXPOINT - Android APK build (requires internet + Flutter SDK)
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found in PATH.
  pause
  exit /b 1
)
python -m pip install -e .
if errorlevel 1 goto :error

where flet >nul 2>nul
if errorlevel 1 (
  echo ERROR: flet CLI was not found after dependency install.
  pause
  exit /b 1
)

flet build apk -v
if errorlevel 1 goto :error

if not exist "build\flutter\android\app\src\main\res\raw" mkdir "build\flutter\android\app\src\main\res\raw"
copy /Y "src\assets\sounds\maxpoint_chime.wav" "build\flutter\android\app\src\main\res\raw\maxpoint_chime.wav" >nul
if errorlevel 1 goto :error
copy /Y "src\assets\android\keep.xml" "build\flutter\android\app\src\main\res\raw\keep.xml" >nul
if errorlevel 1 goto :error

where flet-android-notifications-patch >nul 2>nul
if errorlevel 1 (
  echo ERROR: notification patch command was not installed.
  echo Try: python -m pip install -e .
  pause
  exit /b 1
)
flet-android-notifications-patch --project-root build/flutter
if errorlevel 1 goto :error

where flutter >nul 2>nul
if errorlevel 1 (
  echo ERROR: Flutter SDK was not found in PATH.
  echo Install Flutter and Android SDK, then reopen this script.
  pause
  exit /b 1
)
pushd "build\flutter"
flutter build apk --release
if errorlevel 1 (
  popd
  goto :error
)
popd

if exist "build\flutter\build\app\outputs\flutter-apk\app-release.apk" (
  copy /Y "build\flutter\build\app\outputs\flutter-apk\app-release.apk" "MAXPOINT-Plus-v0.7.apk" >nul
  echo.
  echo SUCCESS: MAXPOINT-Plus-v0.7.apk was created in this folder.
  pause
  exit /b 0
)

echo ERROR: Flutter finished but the expected APK file was not found.
echo Inspect build\flutter\build\app\outputs\flutter-apk\
pause
exit /b 1

:error
echo.
echo BUILD FAILED. The error above should identify the missing dependency or build step.
pause
exit /b 1
