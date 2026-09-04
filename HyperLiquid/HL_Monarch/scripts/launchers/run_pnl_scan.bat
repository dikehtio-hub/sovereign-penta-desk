@echo off
title Polymarket - Sharp Trader PnL Scan
chcp 65001 >nul
cd /d "%~dp0..\..\..\..\Polymarket\Polymarket_Monarch"

echo ======================================================================
echo 🎯 Scanning Polymarket Sharp Trader 7-Day Realized & Unrealized PnL...
echo ======================================================================
python pnl_scanner.py --top 25
echo.
echo Press any key to close...
pause >nul
