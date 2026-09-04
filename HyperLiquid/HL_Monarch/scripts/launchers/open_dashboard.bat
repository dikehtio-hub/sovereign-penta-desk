@echo off
title HL_Monarch - Live Terminal Dashboard
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 🖥️ Launching HL_Monarch Live Rich Terminal Dashboard...
echo ======================================================================
start "HL_Monarch Live Dashboard" python main.py dashboard
