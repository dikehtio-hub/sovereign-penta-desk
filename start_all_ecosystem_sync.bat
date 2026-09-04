@echo off
title Monarch Ecosystem - Master Quad-Market Telemetry Synchronizer
chcp 65001 >nul

echo ======================================================================
echo 👑 Starting Sovereign Quad-Market Obsidian Sync Exporters (15s Loop)...
echo ======================================================================
echo  1. HyperLiquid Desk    (Perp DEX, HIP-3 TradFi, Whales)
echo  2. Polymarket Desk     (Prediction Markets, Sharp Trader PnL)
echo  3. Quant Trading Lab   (CME & Crypto Futures, Killzones, Risk Sentinel)
echo  4. Tax & Bankroll Desk (Safe Bankroll, Escrow, Drop-Folder Ingestion)
echo ======================================================================

set OBSIDIAN_VAULT_PATH=C:\Users\ixis1\Desktop\DEV\obsidian_vault

:: 1. Launch HyperLiquid Exporter
cd /d "C:\Users\ixis1\Desktop\DEV\HyperLiquid\HL_Monarch"
start "Monarch Obsidian Sync" python main.py obsidian --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [1/4] HyperLiquid sync watcher launched.

:: 2. Launch Polymarket Exporter
cd /d "C:\Users\ixis1\Desktop\DEV\Polymarket\Polymarket_Monarch"
start "Polymarket Obsidian Sync" python obsidian_sync.py --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [2/4] Polymarket sync watcher launched.

:: 3. Launch Quant Trading Lab Exporter
cd /d "C:\Users\ixis1\Desktop\DEV\quant_trading_lab"
start "Quant Lab Obsidian Sync" .\venv\Scripts\python.exe telemetry\obsidian_exporter.py --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [3/4] Quant Trading Lab sync watcher launched.

:: 4. Launch Tax & Bankroll Reserve Synchronizer
cd /d "C:\Users\ixis1\Desktop\DEV"
start "Tax Reserve Sync" python -m Tax_Reserve_Agent.obsidian_sync --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [4/4] Tax & Bankroll sync watcher launched.

echo ======================================================================
echo 🌟 All 4 Trading Desks are actively streaming live telemetry into:
echo    %OBSIDIAN_VAULT_PATH%
echo ======================================================================
timeout /t 3 >nul
