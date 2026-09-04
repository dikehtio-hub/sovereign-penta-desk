@echo off
title Polymarket Monarch - Stop Daemon
chcp 65001 >nul

echo ======================================================================
echo 🌐 Stopping Polymarket Monarch Daemon...
echo ======================================================================
taskkill /FI "WINDOWTITLE eq Polymarket Monarch*" /F /T >nul 2>&1
echo ✓ Polymarket Monarch stopped.
timeout /t 2 >nul
