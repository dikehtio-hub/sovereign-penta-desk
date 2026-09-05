@echo off
title Monarch - Stop Obsidian Sync Daemon
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 👑 Stopping Monarch Obsidian Sync Daemon...
echo ======================================================================
taskkill /FI "WINDOWTITLE eq Monarch Obsidian Sync*" /F /T >nul 2>&1
echo ✓ Obsidian sync watcher stopped.
timeout /t 2 >nul 2>&1
