@echo off
chcp 65001 > nul
title HL_Monarch - Live Market Intelligence Dashboard
echo =======================================================================
echo    👑 HL_MONARCH: Hyperliquid & HIP3 TradFi Market Intelligence Suite
echo =======================================================================
echo Starting Live Terminal Dashboard...
python main.py dashboard
pause
