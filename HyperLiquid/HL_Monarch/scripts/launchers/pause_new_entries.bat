@echo off
title Monarch - Pause Entries
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo ⏸️ Pausing New Trade Entries...
echo ======================================================================
python -m config.dynamic_config --pause
echo.
echo ⏸️ New trade entries paused. Existing positions remain active.
timeout /t 2 >nul 2>&1
