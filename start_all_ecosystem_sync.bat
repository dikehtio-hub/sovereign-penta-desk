@echo off
title Monarch Ecosystem - Master Penta-Desk Telemetry Synchronizer
chcp 65001 >nul

echo ======================================================================
echo 👑 Starting Sovereign Penta-Desk Obsidian Sync Exporters (15s Loop)...
echo ======================================================================
echo  1. HyperLiquid Desk    (Perp DEX, HIP-3 TradFi, Whales)
echo  2. Polymarket Desk     (Prediction Markets, Sharp Trader PnL)
echo  3. Quant Trading Lab   (CME & Crypto Futures, Killzones, Risk Sentinel)
echo  4. Tax & Bankroll Desk (Safe Bankroll, Escrow, Drop-Folder Ingestion)
echo  5. Sports Desk + Cross-Market Arb (Fair Value, CLV, Asymmetric Tax)
echo ======================================================================

set OBSIDIAN_VAULT_PATH=C:\Users\ixis1\Desktop\DEV\obsidian_vault

:: 1. Launch HyperLiquid Exporter
cd /d "C:\Users\ixis1\Desktop\DEV\HyperLiquid\HL_Monarch"
start "Monarch Obsidian Sync" python main.py obsidian --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [1/5] HyperLiquid sync watcher launched.

:: 2. Launch Polymarket Exporter
cd /d "C:\Users\ixis1\Desktop\DEV\Polymarket\Polymarket_Monarch"
start "Polymarket Obsidian Sync" python obsidian_sync.py --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [2/5] Polymarket sync watcher launched.

:: 3. Launch Quant Trading Lab Exporter
cd /d "C:\Users\ixis1\Desktop\DEV\quant_trading_lab"
start "Quant Lab Obsidian Sync" .\venv\Scripts\python.exe telemetry\obsidian_exporter.py --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [3/5] Quant Trading Lab sync watcher launched.

:: 4. Launch Tax & Bankroll Reserve Synchronizer
cd /d "C:\Users\ixis1\Desktop\DEV"
start "Tax Reserve Sync" python -m Tax_Reserve_Agent.obsidian_sync --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [4/5] Tax & Bankroll sync watcher launched.

:: 5. Launch Sports Desk + Cross-Market Arb Exporters (one slot, two windows)
cd /d "C:\Users\ixis1\Desktop\DEV"
start "Sports Desk Obsidian Sync" python -m Sports_Desk.interfaces.obsidian_exporter --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
start "Cross-Market Arb Obsidian Sync" python -m cross_market.interfaces.obsidian_exporter --watch --interval 15 --vault "C:\Users\ixis1\Desktop\DEV\obsidian_vault"
echo ✓ [5/5] Sports Desk + Cross-Market Arb sync watchers launched.

echo ======================================================================
echo 🌟 All 5 Trading Desks are actively streaming live telemetry into:
echo    %OBSIDIAN_VAULT_PATH%
echo ======================================================================
timeout /t 3 >nul
