@echo off
REM ============================================================
REM ABI Market Data Collector - Quick Launch
REM ============================================================
REM 
REM Instructions:
REM 1. Make sure the game is open in windowed mode (1600x900)
REM 2. Position the game window in the upper-left corner
REM 3. Navigate to any starting category in the Market
REM 4. Double-click this file to start capturing
REM 
REM Controls:
REM   SPACE - Start capture mode
REM   C     - Capture current screen
REM   ESC   - Finish and save snapshot
REM   Q     - Quit without saving
REM ============================================================

echo.
echo ============================================================
echo ABI Market Data Collector
echo ============================================================
echo.
echo Starting collector...
echo.

cd ..
python collector/continuous_capture.py

echo.
echo ============================================================
echo Collector finished!
echo ============================================================
echo.
pause


