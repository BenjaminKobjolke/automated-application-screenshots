@echo off
echo ================================
echo Screenshot Tool - Installation
echo ================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: uv is not installed or not in PATH
    echo.
    echo Please install uv first:
    echo   winget install astral-sh.uv
    echo   or
    echo   pip install uv
    echo.
    pause
    exit /b 1
)

echo Found uv, installing dependencies...
echo.

:: Run uv sync to install all dependencies
uv sync

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Installation failed
    pause
    exit /b 1
)

echo.
echo ================================
echo Installation complete!
echo ================================
echo.
echo Run the tool with:
echo   uv run screenshot-tool
echo.
echo Or see help:
echo   uv run screenshot-tool --help
echo.
pause
