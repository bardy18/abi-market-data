@echo off
REM ============================================================
REM ABI Trading Platform - Package Builder
REM ============================================================
REM 
REM This script builds a standalone executable package of the
REM ABI Trading Platform using PyInstaller.
REM 
REM The package includes:
REM - Standalone executable (no Python installation needed)
REM - Empty trades.json and blacklist.json for user data
REM - Embedded S3 credentials for automatic snapshot downloads
REM ============================================================

echo.
echo ============================================================
echo ABI Trading Platform - Package Builder
echo ============================================================
echo.

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
REM Change to parent directory (abi-market-data root)
cd /d "%SCRIPT_DIR%.."

echo Current directory: %CD%
echo.
echo Building package...
echo (This may take several minutes...)
echo.

REM Run the build script
python packaging\build_package.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo Build completed successfully!
    echo ============================================================
    echo.
    echo Package location: dist\ABI_Trading_Platform.zip
    echo.
    echo Next steps:
    echo   1. Extract and test dist\ABI_Trading_Platform.zip
    echo   2. Upload dist\ABI_Trading_Platform.zip to your website
    echo.
) else (
    echo.
    echo ============================================================
    echo [!] Build failed!
    echo ============================================================
    echo.
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)

pause

