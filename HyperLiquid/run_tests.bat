@echo off
chcp 65001 > nul
cd /d "%~dp0HL_Monarch"
echo =======================================================================
echo    👑 Running HL_Monarch Test Suite...
echo =======================================================================
python -m unittest discover tests -v
pause
