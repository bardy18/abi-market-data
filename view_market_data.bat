@echo off
REM ============================================================
REM ABI Market Trading App - Quick Launch
REM ============================================================
REM 
REM This launches the trading app GUI to view and analyze
REM your collected market data snapshots.
REM 
REM Features:
REM - View all captured items
REM - Search and filter by category or name
REM - See price history and trends
REM - Track moving averages and volatility
REM ============================================================

echo.
echo ============================================================
echo ABI Market Trading App
echo ============================================================
echo.
echo Loading snapshots...
echo.

python trading_app/main.py

echo.
echo ============================================================
echo Trading app closed
echo ============================================================
echo.

