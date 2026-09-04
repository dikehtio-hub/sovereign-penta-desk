@echo off
title Monarch - Resume Entries
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 🟢 Resuming Trade Entries and Clearing Kill-Switch...
echo ======================================================================
python -m config.dynamic_config --resume
echo.
echo 🟢 System armed. Normal execution resumed.
timeout /t 2 >nul
