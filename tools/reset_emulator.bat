@echo off
setlocal
:: Reset an Android emulator: stop the running one, then start it again with wiped user data.
:: Usage: tools\reset_emulator.bat [avd_name]   (default: same as start_emulator.bat)
:: Stops only when exactly one emulator runs; with several, adb emu kill refuses and -wipe-data may fail.

set "ADB="
for /f "delims=" %%P in ('where adb 2^>nul') do if not defined ADB set "ADB=%%P"
if not defined ADB if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
if not defined ADB if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" set "ADB=%ANDROID_SDK_ROOT%\platform-tools\adb.exe"

if defined ADB (
    echo Stopping running emulator ...
    rem -wipe-data refuses to run while the AVD is in use, so wait until it is gone.
    "%ADB%" emu kill >nul 2>&1 && "%ADB%" wait-for-disconnect
) else (
    echo WARNING: adb not found, cannot stop a running emulator.
)

set "EMULATOR_EXTRA_ARGS=-wipe-data"
call "%~dp0start_emulator.bat" %1
exit /b %ERRORLEVEL%
