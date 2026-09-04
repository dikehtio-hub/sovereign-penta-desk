@echo off
title HL_Monarch - Live Basis Scan
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 📈 Scanning Live Spot-Hedged Delta-Neutral Basis Yield Opportunities...
echo ======================================================================
python main.py basis
echo.
echo Press any key to close...
pause >nul
