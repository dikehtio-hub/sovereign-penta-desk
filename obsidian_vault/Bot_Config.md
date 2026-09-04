---
title: Monarch Bot Configuration & Dynamic Risk Controller
basis_notional_usd: 10000.0
max_concurrent_positions: 5
max_drawdown_limit_pct: 10.0
basis_min_funding_apr: 25.0
basis_min_net_apr: 20.0
basis_holding_days: 7.0
max_spread_bps: 25.0
whale_danger_zone_pct: 5.0
alert_cooldown_seconds: 60.0
emergency_killswitch: false
pause_new_entries: false
active_preset: "custom"
allow_synthetic_tradfi_basis: false
spot_min_volume_notional_multiple: 10.0
spot_min_day_volume: 50000.0
tags:
  - monarch
  - bot-config
  - risk-management
---

# ⚙️ Monarch Bot Configuration & Dynamic Risk Controller

> [!INFO] **Live Parameter Hot-Reload Controller**
> Edit any field in the YAML frontmatter above and save. Running daemons automatically detect changes in `< 1s` without dropping WebSocket feeds.
> - **Active Risk Preset**: `CUSTOM`
> - **Execution Status**: 🟢 **ACTIVE**
> - **Emergency Kill-Switch**: 🟢 **ARMED / READY (NORMAL)**

---

## 🎛️ 1-Click Quick Presets & Safety Actions

| Preset / Action | Notional / Leg | Max Slots | Min Gross APR | Min Net APR | Action Trigger |
| :--- | :---: | :---: | :---: | :---: | :--- |
| 🛡️ **Conservative** | `$5,000` | `1` | `35.0%` | `25.0%` | [[Bot_Control#Presets|Run Conservative Preset]] |
| ⚖️ **Balanced (Default)** | `$10,000` | `2` | `25.0%` | `20.0%` | [[Bot_Control#Presets|Run Balanced Preset]] |
| ⚔️ **Aggressive** | `$25,000` | `4` | `18.0%` | `14.0%` | [[Bot_Control#Presets|Run Aggressive Preset]] |
| 🚨 **EMERGENCY STOP** | — | `0` | — | — | [[Bot_Control#Safety|Trigger Emergency Halt]] |
| ⏸️ **Pause / Resume** | — | — | — | — | [[Bot_Control#Safety|Toggle Entry Gating]] |

---

## 📊 Active Strategy Parameter Deck

| Parameter Key | Current Value | Safe Operating Bounds | Parameter Description |
| :--- | :---: | :---: | :--- |
| **`basis_notional_usd`** | **`$10,000.00`** | `$1,000 - $100,000` | Capital allocation per leg ($10k notional = $20k total commitment per position) |
| **`max_concurrent_positions`** | **`5`** | `1 - 10 slots` | Maximum simultaneous delta-neutral basis pairs open |
| **`max_drawdown_limit_pct`** | **`10.0%`** | `1.0% - 50.0%` | Maximum portfolio drawdown threshold before automated gating |
| **`basis_min_funding_apr`** | **`25.0%`** | `5.0% - 300.0%` | Gross annualized funding rate threshold required for entry |
| **`basis_min_net_apr`** | **`20.0%`** | `1.0% - 250.0%` | Net annualized funding rate required after both legs' spread & fees |
| **`basis_holding_days`** | **`7.0 days`** | `1.0 - 60.0 days` | Holding period used to amortize entry/exit spread frictions |
| **`max_spread_bps`** | **`25.0 bps`** | `2.0 - 100.0 bps` | Maximum allowable top-of-book bid/ask spread on spot & perp |
| **`whale_danger_zone_pct`** | **`5.0%`** | `1.0% - 30.0%` | Liquidation distance threshold for high-risk whale account alerts |
| **`alert_cooldown_seconds`** | **`60s`** | `5 - 600 seconds` | Minimum seconds between duplicate liquidation cascade webhooks |
| **`allow_synthetic_tradfi_basis`** | **`false`** | `true / false` | Allow basis hedges on stock, index, commodity, bond and FX perps (weekend-gap risk; keep false) |
| **`spot_min_volume_notional_multiple`** | **`10.0x`** | `1 - 100x` | Spot pair must turn over this many times the per-leg notional per day (10x = one fill is 10% of ADV) |
| **`spot_min_day_volume`** | **`$50,000`** | `$10,000 - $10,000,000` | Absolute floor on the spot pair's 24h notional, whatever the notional multiple gives |

---

## 🔗 Quick Navigation

- [[Monarch_Hub|👑 Monarch Intelligence Hub]]
- [[Bot_Control|🎮 Bot Control & Activation Deck]]
- [[Trading_Terminal|📈 Live Trading Terminal & 50-Trade Hurdle]]
- [[HyperLiquid_Monarch|🏛 HyperLiquid Market Dashboard]]
- [[Polymarket_Monarch|🌐 Polymarket Intelligence]]
- [[Quant_Trading_Lab|⚡ Quant Trading Lab]]
---

## 📝 Strategy Notes & Runbook
*Add your custom trading notes, risk checklists, parameter justifications, and strategy runbooks below:*
- **Risk Checklist**: Verified spot liquidity, checked funding persistence (>4h), confirmed maker fees.
- **Notes**:
