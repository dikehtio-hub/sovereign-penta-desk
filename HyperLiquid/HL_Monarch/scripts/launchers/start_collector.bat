@echo off
title HL_Monarch - Collector Daemon Launcher
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 👑 Starting HL_Monarch Background Ingestion Collector Service...
echo ======================================================================
start "HL_Monarch Collector" python run_collector_service.py
echo ✓ Ingestion collector process launched in background window.
timeout /t 3 >nul
