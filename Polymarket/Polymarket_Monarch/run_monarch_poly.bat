@echo off
title Polymarket Monarch - 100% Free Self-Hosted Intelligence
color 0A

:: Ensure console runs in UTF-8
chcp 65001 >nul

cd /d "%~dp0"

:MENU
cls
echo =====================================================================
echo       POLYMARKET MONARCH: 100% FREE NATIVE PREDICTION INTELLIGENCE
echo       (Zero Moon Dev API / Zero Paid Keys / Self-Hosted SQLite)
echo =====================================================================
echo.
echo   [1] Live 3-Panel Terminal Dashboard (Leaderboard + Whales + Macro)
echo   [2] Run Whale Collector (Public WebSocket + SQLite Data Ingestion)
echo   [3] Run 7-Day PnL Scanner (Scan active wallets for $300+ Sharp Traders)
echo   [4] Quick Backfill (Ingest latest 100 public trades into SQLite)
echo   [5] Audit Single Wallet PnL
echo   [6] OFFLINE Replay Demo (recorded whale trades, no internet)
echo   [7] Sync to Obsidian Vault (One-Shot Export to Markdown)
echo   [8] Continuous Obsidian Live-Sync Daemon (Real-Time Watcher)
echo   [9] Run Test Suite
echo   [10] Exit
echo.
echo =====================================================================
set /p CHOICE="Select an option [1-10]: "

if "%CHOICE%"=="1" goto RUN_DASHBOARD
if "%CHOICE%"=="2" goto RUN_COLLECTOR
if "%CHOICE%"=="3" goto RUN_SCANNER
if "%CHOICE%"=="4" goto RUN_BACKFILL
if "%CHOICE%"=="5" goto RUN_WALLET_AUDIT
if "%CHOICE%"=="6" goto RUN_REPLAY
if "%CHOICE%"=="7" goto RUN_OBSIDIAN_ONCE
if "%CHOICE%"=="8" goto RUN_OBSIDIAN_WATCH
if "%CHOICE%"=="9" goto RUN_TESTS
if "%CHOICE%"=="10" goto EXIT
goto MENU

:RUN_DASHBOARD
cls
python terminal_dashboard.py --refresh-rate 2.0 --min-usd 1000
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_COLLECTOR
cls
python whale_collector.py --min-usd 1000
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_SCANNER
cls
python pnl_scanner.py --max-wallets 25 --min-pnl 300 --obsidian
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_BACKFILL
cls
python whale_collector.py --backfill-only
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_WALLET_AUDIT
cls
set /p TARGET_WALLET="Enter Polygon/Polymarket Wallet Address (0x...): "
python pnl_scanner.py --wallet "%TARGET_WALLET%" --obsidian
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_REPLAY
cls
python whale_collector.py --replay
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_OBSIDIAN_ONCE
cls
python obsidian_sync.py --once
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_OBSIDIAN_WATCH
cls
python obsidian_sync.py --watch --interval 15
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_TESTS
cls
python -m pytest tests -q
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:EXIT
exit /b 0
