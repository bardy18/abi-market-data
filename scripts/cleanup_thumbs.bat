@echo off
REM ============================================================
REM ABI Market Data - Thumbnail Cleanup Tool
REM ============================================================
REM Usage:
REM   cleanup_thumbs.bat          (dry run)
REM   cleanup_thumbs.bat --apply  (apply changes)
REM Optional:
REM   --threshold N   Hamming distance threshold (default 8)
REM   --snapshots DIR Snapshots dir (default ..\snapshots)
REM ============================================================

setlocal
cd ..

echo Applying thumbnail cleanup...
python collector/cleanup_thumbs.py --apply

echo.
echo Done.
echo.
pause


