@echo off
chcp 65001 > nul
cd /d "%~dp0HL_Monarch"
echo =======================================================================
echo    👑 HL_MONARCH: Live Market Intelligence Terminal Dashboard
echo =======================================================================
python main.py dashboard
pause
