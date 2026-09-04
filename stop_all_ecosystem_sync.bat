@echo off
title Monarch Ecosystem - Stop All Telemetry Synchronizers
chcp 65001 >nul

echo ======================================================================
echo 🛑 Stopping All Sovereign Quad-Market Obsidian Telemetry Sync Daemons...
echo ======================================================================

taskkill /FI "WINDOWTITLE eq Monarch Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [1/4] Stopped HyperLiquid sync watcher.

taskkill /FI "WINDOWTITLE eq Polymarket Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [2/4] Stopped Polymarket sync watcher.

taskkill /FI "WINDOWTITLE eq Quant Lab Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [3/4] Stopped Quant Trading Lab sync watcher.

taskkill /FI "WINDOWTITLE eq Tax Reserve Sync*" /F /T >nul 2>&1
echo ✓ [4/4] Stopped Tax & Bankroll sync watcher.

echo ======================================================================
echo ✓ All 4 sync watchers cleanly terminated.
echo ======================================================================
timeout /t 2 >nul
