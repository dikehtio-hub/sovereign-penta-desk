@echo off
title Monarch - Emergency Killswitch
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 🚨 ENGAGING EMERGENCY KILL-SWITCH...
echo ======================================================================
python -m config.dynamic_config --killswitch
echo.
echo 🚨 EMERGENCY STOP ACTIVATED. All new entries halted.
timeout /t 3 >nul 2>&1
