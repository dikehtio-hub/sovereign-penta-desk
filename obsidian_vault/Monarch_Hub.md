---
title: Monarch Intelligence Hub & Executive Command Center
tags:
  - monarch
  - hub
  - executive-cockpit
  - dashboard
last_synced: "2026-09-04 20:23:15 UTC"
---

# 👑 Monarch Intelligence Hub & Executive Command Center

> [!INFO] **Vault Index**
> - **Last Refreshed**: `2026-09-04 20:23:15 UTC`
> - **Suites In This Vault**: `6` of 6
> - **Vault Root**: `C:\Users\ixis1\Desktop\DEV\obsidian_vault`

> [!TIP] **Both suites share this vault**
> Wikilinks resolve across suites, so a wallet seen on Hyperliquid and a trader
> seen on Polymarket can be linked to each other by hand, and Obsidian's graph
> view shows both intelligence networks as one connected graph.

---

## 🎛️ Command Desks & Intelligence Suites

| Command Desk / Suite | Domain | Covers | Status / Notes |
| :--- | :--- | :--- | :---: |
| [[Bot_Control|🎮 Bot Control & Activation Deck]] | Operations / Services | Background daemon telemetry, Windows 1-click launchers, Killswitch | `Active Cockpit` |
| [[Bot_Config|⚙️ Bot Configuration & Risk Controller]] | Risk & Sizing | Hot-reloadable YAML frontmatter, presets (Conservative/Balanced/Aggressive) | `Live Config` |
| [[Trading_Terminal|📈 Trading Terminal & 50-Trade Hurdle]] | Execution Telemetry | Paper account equity, active basis positions, resting limits, 50-trade hurdle | `Telemetry` |
| [[HyperLiquid_Monarch|👑 HyperLiquid Monarch]] | Perp DEX / HIP-3 TradFi | Liquidations, funding arbitrage, whale portfolios, danger zone | `79` whale notes |
| [[Polymarket_Monarch|👑 Polymarket Monarch]] | Prediction markets | Sharp-trader PnL, whale fills, macro sentiment, consensus radar | `41` trader notes |
| [[Quant_Trading_Lab|⚡ Quant Trading Lab]] | CME Futures / Microstructure | /NQ, /ES, /GC, /CL, 9 Strategy Stacks, ICT Killzones, Risk Sentinel | `Active Desk` |
| [[Cross_Market_Titans|👑 Cross-Market Titans]] | Multi-Venue Intelligence | Whale entity resolution, logarithmic conviction score, macro co-positioning | `Active Intelligence` |
| [[Sports_Desk|🏈 Sports Desk]] | Sportsbooks / Fair Value | Shin-devigged edges, after-tax hurdle, execution CLV, tax-ledger bridge | `Active Desk` |
| [[Cross_Market_Arb|⚖️ Cross-Market Arb]] | Polymarket vs Sportsbook | Matched pairs priced through the asymmetric tax, both characterisations | `Active Desk` |

---

## ⚡ Quick Launcher Deck

| Quick Action | Target Module | Shortcut |
| :--- | :--- | :---: |
| 🎮 **Bot Operations** | Service management, daemon PIDs, 1-click execution | [[Bot_Control|Open Bot Control Deck]] |
| ⚙️ **Risk Configuration** | Capital allocation, funding rate floors, dynamic presets | [[Bot_Config|Open Risk Controller]] |
| 📈 **Trading Terminal** | Paper balance, active basis pairs, 50-trade hurdle validation | [[Trading_Terminal|Open Trading Terminal]] |
| 🏛 **HyperLiquid Desk** | Spot-backed basis arb, liquidation waterfall, whale CRM | [[HyperLiquid_Monarch|Open HL Dashboard]] |
| 🌐 **Polymarket Desk** | Sharp trader PnL, multi-sharp consensus, macro sentiment | [[Polymarket_Monarch|Open Polymarket Desk]] |
| ⚡ **CME Futures Desk** | /NQ, /ES, /GC, /CL, 9 Strategy Stacks, Killzones | [[Quant_Trading_Lab|Open Quant Lab Desk]] |
| 👑 **Cross-Market Titans** | Multi-venue entity resolution, macro co-positioning | [[Cross_Market_Titans|Open Titans Desk]] |
| 🏈 **Sports Desk** | +EV hotlist, realised P&L, execution CLV, un-exported bet alerts | [[Sports_Desk|Open Sports Desk]] |
| ⚖️ **Cross-Market Arb** | Polymarket vs sportsbook pairs, 16.75% / 23.93% after-tax hurdles | [[Cross_Market_Arb|Open Cross-Market Arb]] |
| 🗺️ **Penta-Desk Canvas** | Visual cockpit: capital gating and reserve flows across all five desks | [[Canvases/Sovereign_Penta_Cockpit.canvas|Open Canvas]] |

---

## 🔗 Connected Ecosystem Topology

Both suites track **wallet addresses** as primary entities, backed by local SQLite databases (`hyperliquid_data.db` and `polymarket_whales.db`).
- **HyperLiquid**: Discovers whales from live perp fills (>= $25k) and records on-chain portfolio equity and liquidation margin stress.
- **Polymarket**: Discovers sharp traders from prediction-market fills and tracks 7-day realized/unrealized PnL and consensus convergence.
- **Quant Trading Lab**: Tracks CME Futures microstructure (/NQ, /ES, /GC, /CL), 9 Strategy Stacks, and real-time ICT Killzone session clocks.
- **Cross-Market Titans**: An address appearing in both venues is an institutional actor operating across perps and prediction markets.
- **Sports Desk**: Devigs the sharp book, scores retail prices against it, gates every stake through the tax ledger's after-tax hurdle, and flags bets the ledger has not yet seen.
- **Cross-Market Arb**: Pairs a Polymarket YES with the opposite sportsbook side and prices the worst branch after tax - each leg's loss is deductible only against income the other leg does not produce.

---
*Generated automatically by Monarch Intelligence Exporters.*
