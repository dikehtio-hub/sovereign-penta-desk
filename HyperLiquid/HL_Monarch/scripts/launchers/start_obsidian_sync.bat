@echo off
title Monarch - Obsidian Sync Daemon
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 👑 Starting Monarch Obsidian Command Cockpit Synchronizer (15s Loop)...
echo ======================================================================
set OBSIDIAN_VAULT_PATH=C:\Users\ixis1\Desktop\DEV\obsidian_vault
start "Monarch Obsidian Sync" python main.py obsidian --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ Obsidian sync watcher launched in background.
timeout /t 3 >nul
