@echo off
REM ============================================================
REM ABI Market Data - S3 Snapshot Sync
REM ============================================================
REM 
REM This script syncs local snapshots to S3 using AWS CLI.
REM Local snapshots folder is treated as master - S3 will match it.
REM 
REM Bucket name is determined in this order:
REM 1. s3_config.json in packaging/ folder (preferred)
REM 2. s3_config.json in project root (fallback)
REM 3. S3_BUCKET_NAME environment variable
REM 4. Hardcoded default: abi-market-data-snapshots
REM 
REM Requirements:
REM - AWS CLI installed and configured
REM ============================================================

echo.
echo ============================================================
echo ABI Market Data - S3 Snapshot Sync
echo ============================================================
echo.

REM Change to script directory first to get relative paths
cd /d "%~dp0"

REM Try to get bucket name from s3_config.json - check packaging folder first, then root
set BUCKET_NAME=
set CONFIG_FILE_PACKAGING=..\packaging\s3_config.json
set CONFIG_FILE_ROOT=..\s3_config.json

REM Try packaging folder first (preferred location)
if exist "%CONFIG_FILE_PACKAGING%" (
    REM Use PowerShell to extract bucket name from JSON
    for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG_FILE_PACKAGING%' | ConvertFrom-Json).bucket"') do set BUCKET_NAME=%%i
)

REM Fall back to root if not found in packaging folder
if "%BUCKET_NAME%"=="" (
    if exist "%CONFIG_FILE_ROOT%" (
        REM Use PowerShell to extract bucket name from JSON
        for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG_FILE_ROOT%' | ConvertFrom-Json).bucket"') do set BUCKET_NAME=%%i
    )
)

REM Fall back to environment variable if config file didn't work
if "%BUCKET_NAME%"=="" (
    if not "%S3_BUCKET_NAME%"=="" (
        set BUCKET_NAME=%S3_BUCKET_NAME%
    )
)

REM Fall back to hardcoded default
if "%BUCKET_NAME%"=="" (
    set BUCKET_NAME=abi-market-data-snapshots
    echo [*] Using default bucket name: %BUCKET_NAME%
) else (
    echo [*] Using bucket name from config: %BUCKET_NAME%
)
echo.
set S3_PATH=s3://%BUCKET_NAME%/snapshots/
REM Change to parent directory to access snapshots folder
cd /d "%~dp0.."
set LOCAL_PATH=snapshots

echo Bucket: %BUCKET_NAME%
echo S3 Path: %S3_PATH%
echo Local Path: %LOCAL_PATH%
echo.
echo Syncing local snapshots to S3...
echo (This may take a moment...)
echo.

REM Sync local to S3
REM --delete: Delete files in S3 that don't exist locally (makes S3 match local)
REM Includes thumbs/ folder so trading app can download and display thumbnails
aws s3 sync "%LOCAL_PATH%" "%S3_PATH%" --delete --profile abi

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo Sync completed successfully!
    echo ============================================================
    echo.
) else (
    echo.
    echo ============================================================
    echo [!] Sync failed!
    echo ============================================================
    echo.
    echo Please check:
    echo   - AWS CLI is installed: aws --version
    echo   - AWS credentials are configured: aws configure list
    echo   - Bucket name is correct: %BUCKET_NAME%
    echo   - You have write permissions to the bucket
    echo.
    pause
    exit /b 1
)

pause

