@echo off
chcp 65001 > nul
cd /d "%~dp0HL_Monarch"
echo =======================================================================
echo    👑 HL_MONARCH: Persistent Collector Service (auto-restart)
echo =======================================================================
echo.
echo Keeps the collector alive across crashes and reports real snapshot
echo coverage every 15 minutes. Everything downstream - the funding
echo backtester and the squeeze engine's percentiles - depends on this
echo running continuously rather than in bursts.
echo.
echo Structured log: HL_Monarch\data\collector_service.jsonl
echo Press Ctrl+C to stop.
echo.
python run_collector_service.py
pause
