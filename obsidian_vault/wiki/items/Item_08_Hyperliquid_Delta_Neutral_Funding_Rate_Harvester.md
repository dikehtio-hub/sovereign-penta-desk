---
type: Item
title: 'Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester (Basis Bot)'
description: Fully automated cash-and-carry harvester.
tags:
- item
- desk-1
- tier-2
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:42Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 1
  item: 8
  tier: 2
  registry_checked: true
  requires_files:
  - HyperLiquid/HL_Monarch/strategies/funding_harvester.py
  - HyperLiquid/HL_Monarch/analytics/funding_arbitrage.py
  - HyperLiquid/HL_Monarch/main.py
---
# Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester (Basis Bot)

> Tier 2: Core Execution & Cross-Market Alpha · deployed · [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]

## What it does

Fully automated cash-and-carry harvester. Simultaneously buys spot
and shorts perpetual contracts on HyperLiquid when annualized funding yield
exceeds entry hurdle (>=25% gross / >=20% net APR). Enforces:
* TradFi Quarantine: 7 TradFi DEXes (xyz, km, cash, flx, mkts, io, vntl) quarantined.
* Mixed-DEX Allow-List: para perps quarantined unless on crypto allow-list (ANSEM).
* 10x ADV Floor: Spot pair must have >= $100k 24h volume ($10k leg notional).
* Duplicate Guard: 1 position per underlying coin across spot and perps.
* Spread Ceiling: Max 25 bps spread on entry.
* Auto-Sweep: Closes positions if spot pair volume drops below floor.

## Where it lives

- `HyperLiquid/HL_Monarch/strategies/funding_harvester.py`
- `HyperLiquid/HL_Monarch/analytics/funding_arbitrage.py`
- `HyperLiquid/HL_Monarch/main.py`

## How to activate

```
# Scan live markets for basis opportunities:
python HyperLiquid/HL_Monarch/main.py basis --scan
# Run manual harvest check (displays open positions, accrued yield, cash):
python HyperLiquid/HL_Monarch/main.py basis --harvest
# Manually trigger illiquid spot leg sweep (service must be stopped):
python HyperLiquid/HL_Monarch/main.py basis --sweep-illiquid
# List liquid spot tokens with no perp mapping:
python HyperLiquid/HL_Monarch/main.py basis --unmapped-spot
# Change dynamic risk preset (hot-reloaded without daemon restart):
python HyperLiquid/HL_Monarch/main.py config --apply-preset conservative
python HyperLiquid/HL_Monarch/main.py config --apply-preset balanced
python HyperLiquid/HL_Monarch/main.py config --apply-preset aggressive
```

## Test

```
python -m pytest HyperLiquid/HL_Monarch/tests/test_funding_arbitrage.py -q
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 22:47 EDT (Round 30; TradFi / Spot liquidity guards added Rounds 38-48: 2026-09-04)

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
