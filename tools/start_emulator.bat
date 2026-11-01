@echo off
setlocal
:: Start an Android emulator with the same flags the live tool uses.
:: Usage: tools\start_emulator.bat [avd_name]   (default: first AVD from emulator -list-avds)

set "EMULATOR="
for /f "delims=" %%P in ('where emulator 2^>nul') do if not defined EMULATOR set "EMULATOR=%%P"
if not defined EMULATOR if defined ANDROID_HOME if exist "%ANDROID_HOME%\emulator\emulator.exe" set "EMULATOR=%ANDROID_HOME%\emulator\emulator.exe"
if not defined EMULATOR if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\emulator\emulator.exe" set "EMULATOR=%ANDROID_SDK_ROOT%\emulator\emulator.exe"
if not defined EMULATOR (
    echo ERROR: emulator not found on PATH, in ANDROID_HOME or in ANDROID_SDK_ROOT.
    exit /b 1
)

set "AVD=%~1"
if not defined AVD for /f "delims=" %%A in ('"%EMULATOR%" -list-avds 2^>nul') do if not defined AVD set "AVD=%%A"
if not defined AVD (
    echo ERROR: no AVD given and "%EMULATOR%" -list-avds found none.
    exit /b 1
)

echo Starting emulator %AVD% ...
:: Detached on purpose: the emulator keeps running after this bat ends.
start "Android Emulator %AVD%" "%EMULATOR%" -avd "%AVD%" -no-snapshot-save -crash-report-mode disabled
exit /b %ERRORLEVEL%
