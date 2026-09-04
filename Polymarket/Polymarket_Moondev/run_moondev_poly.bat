@echo off
title Polymarket MoonDev Intelligence Suite
color 0B

:: Ensure console runs in UTF-8
chcp 65001 >nul

cd /d "%~dp0"

:MENU
cls
echo =====================================================================
echo          MOON DEV POLYMARKET ALPHA & INTELLIGENCE RUNNER
echo =====================================================================
echo.
echo   [1] Top Profitable Traders Tracker (Rank, 7D PnL, Volume, Profile Links)
echo   [2] Live Whale Trade Monitor ($1,000+ USD Position Shifts)
echo   [3] Continuous Trader Leaderboard (Auto-refresh every 60s)
echo   [4] Mega Whale Alert Stream ($5,000+ USD Fills Only)
echo   [5] Exit
echo.
echo =====================================================================
set /p CHOICE="Select an option [1-5]: "

if "%CHOICE%"=="1" goto RUN_TRADERS
if "%CHOICE%"=="2" goto RUN_WHALES
if "%CHOICE%"=="3" goto RUN_TRADERS_LOOP
if "%CHOICE%"=="4" goto RUN_MEGA_WHALES
if "%CHOICE%"=="5" goto EXIT
goto MENU

:RUN_TRADERS
cls
python poly_traders_tracker.py --limit 25
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_WHALES
cls
python poly_whale_monitor.py --min-usd 1000 --poll-interval 5
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_TRADERS_LOOP
cls
python poly_traders_tracker.py --loop --interval 60
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:RUN_MEGA_WHALES
cls
python poly_whale_monitor.py --min-usd 5000 --poll-interval 4
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:EXIT
exit /b 0
