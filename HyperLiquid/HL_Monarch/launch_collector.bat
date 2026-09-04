@echo off
chcp 65001 > nul
cd /d "%~dp0"
title HL_Monarch - Real-Time Market Collector Daemon
echo =======================================================================
echo    HL_MONARCH: Background Data Ingestion and Liquidation Collector
echo =======================================================================
echo Starting Collector (Press Ctrl+C to stop)...
python main.py collector
pause
