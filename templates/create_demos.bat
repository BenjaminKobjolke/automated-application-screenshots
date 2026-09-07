@echo off
REM Records this app's demos with the automated-application-screenshots tool,
REM into tools\create_media\output\demos\<name>\. One demo only: create_demos.bat 1
REM Keep hands off mouse and keyboard while the window is recording.
REM
REM Copy this file next to your app's config and change CONFIG below.
setlocal
set "CONFIG=%~dp0yourapp.json"

echo ========================================
echo  Create Demo Media
echo ========================================
echo.
REM The tool resolves output_dir against the config file's own folder.
cd /d "%~dp0"

set "SELECTOR=%~1"
if "%SELECTOR%"=="" set "SELECTOR=all"

REM Sibling checkout by default; SCREENSHOT_TOOL_DIR overrides it per machine.
set "TOOL_DIR=%SCREENSHOT_TOOL_DIR%"
if "%TOOL_DIR%"=="" set "TOOL_DIR=%~dp0..\..\..\automated-application-screenshots"
if not exist "%TOOL_DIR%" (
    echo.
    echo ERROR: Screenshot tool not found at "%TOOL_DIR%".
    echo Set SCREENSHOT_TOOL_DIR to its checkout path, or clone it next to this repo.
    exit /b 1
)

uv run --project "%TOOL_DIR%" screenshot-tool --config "%CONFIG%" --demo %SELECTOR%
if errorlevel 1 (
    echo.
    echo Demo recording FAILED
    exit /b 1
)
echo.
echo Media written to %~dp0output\demos\ 
pause
