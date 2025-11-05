@echo off
REM ============================================================
REM ABI Market Data - S3 Snapshot Sync
REM ============================================================
REM 
REM This script syncs local snapshots to S3 using AWS CLI.
REM Local snapshots folder is treated as master - S3 will match it.
REM 
REM Requirements:
REM - AWS CLI installed and configured
REM - S3_BUCKET_NAME environment variable set, OR
REM - Edit this script to set BUCKET_NAME directly
REM ============================================================

echo.
echo ============================================================
echo ABI Market Data - S3 Snapshot Sync
echo ============================================================
echo.

REM Get bucket name from environment variable or use default
if "%S3_BUCKET_NAME%"=="" (
    echo [!] S3_BUCKET_NAME environment variable not set
    echo.
    echo Please either:
    echo   1. Set S3_BUCKET_NAME environment variable, OR
    echo   2. Edit this script to set BUCKET_NAME directly
    echo.
    pause
    exit /b 1
)

set BUCKET_NAME=%S3_BUCKET_NAME%
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
aws s3 sync "%LOCAL_PATH%" "%S3_PATH%" --delete

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

