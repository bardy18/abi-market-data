@echo off
REM ============================================================
REM ABI Market Data - Website Deployment
REM ============================================================
REM 
REM This script syncs the website folder to S3 for static web hosting.
REM Local website folder is treated as master - S3 will match it.
REM 
REM Bucket: abi-market-data-web (static web hosting enabled)
REM 
REM Requirements:
REM - AWS CLI installed and configured
REM - Write permissions to the bucket
REM ============================================================

echo.
echo ============================================================
echo ABI Market Data - Website Deployment
echo ============================================================
echo.

REM Change to script directory first to get relative paths
cd /d "%~dp0"

set BUCKET_NAME=abi-market-data-web
set S3_PATH=s3://%BUCKET_NAME%/
REM Change to parent directory to access website folder
cd /d "%~dp0.."
set LOCAL_PATH=website

echo Bucket: %BUCKET_NAME%
echo S3 Path: %S3_PATH%
echo Local Path: %LOCAL_PATH%
echo.
echo Deploying website to S3...
echo (This may take a moment...)
echo.

REM Sync local website to S3
REM --delete: Delete files in S3 that don't exist locally (makes S3 match local)
aws s3 sync "%LOCAL_PATH%" "%S3_PATH%" --delete --profile abi

if %ERRORLEVEL% EQU 0 goto :success
goto :failure

:success
echo.
echo ============================================================
echo Deployment completed successfully!
echo ============================================================
echo.
echo Website is now live at:
echo   http://%BUCKET_NAME%.s3-website-us-east-1.amazonaws.com
echo   (or your configured static website endpoint)
echo.
goto :end

:failure
echo.
echo ============================================================
echo [!] Deployment failed!
echo ============================================================
echo.
echo Please check:
echo   - AWS CLI is installed: aws --version
echo   - AWS credentials are configured: aws configure list
echo   - Bucket name is correct: %BUCKET_NAME%
echo   - You have write permissions to the bucket
echo   - Static web hosting is enabled on the bucket
echo.
pause
exit /b 1

:end
pause

