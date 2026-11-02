@echo off
setlocal
:: Start an Android emulator with the same flags the live tool uses.
:: Usage: tools\start_emulator.bat [avd_name]   (default: first AVD from emulator -list-avds)
:: Extra emulator flags can be passed in EMULATOR_EXTRA_ARGS (reset_emulator.bat uses -wipe-data).

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
if "%TICKETS_WATCHER_COMMAND_RUN%"=="1" (
    powershell -NoProfile -Command "$ErrorActionPreference = 'Stop'; try { $arguments = '-avd ' + [char]34 + $env:AVD + [char]34 + ' -no-snapshot-save -crash-report-mode disabled ' + $env:EMULATOR_EXTRA_ARGS; Start-Process -FilePath $env:EMULATOR -ArgumentList $arguments; exit 0 } catch { [Console]::Error.WriteLine($_); exit 1 }"
    if errorlevel 1 (
        echo ERROR: failed to launch the Android emulator.
        exit /b 1
    )
    exit /b 0
)
:: Detached on purpose: the emulator keeps running after this bat ends.
start "Android Emulator %AVD%" "%EMULATOR%" -avd "%AVD%" -no-snapshot-save -crash-report-mode disabled %EMULATOR_EXTRA_ARGS%
exit /b %ERRORLEVEL%
