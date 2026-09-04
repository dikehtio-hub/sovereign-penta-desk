@echo off
chcp 65001 > nul
cd /d "%~dp0HL_Monarch"
echo =======================================================================
echo    👑 HL_MONARCH: Background Ingestion & Liquidation Collector
echo =======================================================================
python main.py collector
pause
