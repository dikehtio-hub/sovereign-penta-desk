@echo off
title Polymarket Monarch Daemon
chcp 65001 >nul
cd /d "%~dp0..\..\..\..\Polymarket\Polymarket_Monarch"

echo ======================================================================
echo 🌐 Starting Polymarket Monarch Intelligence Suite...
echo ======================================================================
start "Polymarket Monarch" run_monarch_poly.bat
echo ✓ Polymarket Monarch launched.
timeout /t 3 >nul 2>&1
