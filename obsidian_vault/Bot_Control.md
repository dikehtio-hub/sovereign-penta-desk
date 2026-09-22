---
title: Monarch Bot Control & Activation Deck
tags:
  - monarch
  - bot-control
  - operations
  - launchers
last_synced: "2026-09-21 02:04:40 UTC"
---

# 🎮 Monarch Bot Control & Activation Deck

> [!INFO] **Live Service Telemetry & Operational State**
> - **HyperLiquid Ingestion Collector**: 🟢 **ONLINE (PID: 17852)** • SQLite DB Updated: `1s ago`
> - **Polymarket Engine**: ⚪ **IDLE (1633614s ago)**
> - **Active Risk Preset**: `CUSTOM` • Capital Per Leg: `$10,000`
> - **Execution State**: 🟢 **ACCEPTING ENTRIES** • Kill-Switch: 🟢 **ARMED (NORMAL)**
> - **Last Synchronized**: `2026-09-21 02:04:40 UTC`

---

## 🚀 1-Click Windows Launchers Deck

> [!TIP] **Execution Instructions**
> Click any launcher link below to execute the corresponding standalone Windows batch script in `scripts/launchers/`.

| Service / Action | Description | Primary Launcher | Stop / Reset |
| :--- | :--- | :---: | :---: |
| ⚡ **Master Tri-Market Sync** | Start ALL 3 sync exporters (HL + Polymarket + Quant Lab) | [🚀 Start All Sync](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/start_all_ecosystem_sync.bat) | [🛑 Stop All Sync](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/stop_all_ecosystem_sync.bat) |
| 🏛 **HyperLiquid Collector** | 436 Market perp ingestion daemon & orderbook watcher | [▶ Start Collector](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/start_collector.bat) | [⏹ Stop Collector](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/stop_collector.bat) |
| 🔄 **Obsidian Sync Watcher** | Real-time vault background synchronizer (15s loop) | [▶ Start Sync](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/start_obsidian_sync.bat) | [⏹ Stop Sync](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/stop_obsidian_sync.bat) |
| 🌐 **Polymarket Daemon** | Sharp trader PnL scanner & whale trade collector | [▶ Start Polymarket](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/start_poly_monarch.bat) | [⏹ Stop Polymarket](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/stop_poly_monarch.bat) |
| 📊 **Rich Terminal Dashboard** | Fullscreen institutional TUI terminal | [🖥️ Launch Dashboard](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/open_dashboard.bat) | — |
| 📈 **Delta-Neutral Basis Scan** | Scan live spot-hedged funding harvest opportunities | [⚡ Run Basis Scan](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/run_basis_scan.bat) | — |
| 🎯 **Polymarket PnL Scanner** | Scan 7-day realized/unrealized sharp trader rankings | [⚡ Run PnL Scan](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/run_pnl_scan.bat) | — |

---

## 🎛️ Dynamic Risk Presets & Safety Actions

| Action | Impact | Launcher Script |
| :--- | :--- | :---: |
| 🛡️ **Apply Conservative Preset** | $5k Notional, 1 Slot, 35% Gross / 25% Net APR Floor | [🛡️ Apply Conservative](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/apply_preset_conservative.bat) |
| ⚖️ **Apply Balanced Preset** | $10k Notional, 2 Slots, 25% Gross / 20% Net APR Floor | [⚖️ Apply Balanced](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/apply_preset_balanced.bat) |
| ⚔️ **Apply Aggressive Preset** | $25k Notional, 4 Slots, 18% Gross / 14% Net APR Floor | [⚔️ Apply Aggressive](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/apply_preset_aggressive.bat) |
| 🚨 **EMERGENCY KILL-SWITCH** | Instantly halts new entries and cancels resting orders | [🚨 TRIGGER EMERGENCY STOP](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/emergency_killswitch.bat) |
| ⏸️ **Pause New Entries** | Keeps existing positions active but prevents new opens | [⏸️ Pause Entries](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/pause_new_entries.bat) |
| 🟢 **Resume Entries** | Clears pause & killswitch, restoring execution | [▶ Resume Entries](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/scripts/launchers/resume_entries.bat) |

---

## 🔗 Cockpit Navigation

- [[Desk_01_HyperLiquid_Monarch|🧭 Desk 1: HyperLiquid Monarch (wiki)]] · Shell twin: `python HyperLiquid/HL_Monarch/main.py obsidian --once`
- [[Monarch_Hub|👑 Monarch Intelligence Hub]]
- [[Bot_Config|⚙️ Bot Configuration & Risk Controller]]
- [[Trading_Terminal|📈 Live Trading Terminal & 50-Trade Hurdle]]
- [[HyperLiquid_Monarch|🏛 HyperLiquid Market Dashboard]]
- [[Polymarket_Monarch|🌐 Polymarket Intelligence]]
- [[Quant_Trading_Lab|⚡ Quant Trading Lab]]
---

## 📝 My Research & Notes
*Log operational notes, maintenance schedules, and incident post-mortems below:*
- **Operator Notes**:
