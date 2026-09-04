@echo off
title Monarch Ecosystem - Stop All Telemetry Synchronizers
chcp 65001 >nul

echo ======================================================================
echo 🛑 Stopping All Sovereign Penta-Desk Obsidian Telemetry Sync Daemons...
echo ======================================================================

taskkill /FI "WINDOWTITLE eq Monarch Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [1/5] Stopped HyperLiquid sync watcher.

taskkill /FI "WINDOWTITLE eq Polymarket Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [2/5] Stopped Polymarket sync watcher.

taskkill /FI "WINDOWTITLE eq Quant Lab Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [3/5] Stopped Quant Trading Lab sync watcher.

taskkill /FI "WINDOWTITLE eq Tax Reserve Sync*" /F /T >nul 2>&1
echo ✓ [4/5] Stopped Tax & Bankroll sync watcher.

taskkill /FI "WINDOWTITLE eq Sports Desk Obsidian Sync*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Cross-Market Arb Obsidian Sync*" /F /T >nul 2>&1
echo ✓ [5/5] Stopped Sports Desk + Cross-Market Arb sync watchers.

echo ======================================================================
echo ✓ All 5 sync watchers cleanly terminated.
echo ======================================================================
timeout /t 2 >nul
