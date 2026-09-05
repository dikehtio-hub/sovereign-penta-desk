---
type: Desk
title: 'Desk 1: HyperLiquid Monarch'
description: 'Perp DEX desk: delta-neutral funding harvester, whale cascade sweeper,
  L2 order-book sampler, liquidation engine and the collector that feeds a 4.9 GB
  snapshot warehouse.'
tags:
- desk
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T20:48:24Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
- id: round-95-blueprint
  resource: LLM_WIKI_BLUEPRINT.md
  title: Round 95 five-desk audit
  author: claude-code/fable-5.1
dev:
  desk: 1
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/basis_harvester.py
    pattern: 'class |def '
    claim: the basis harvester module is at its registered path
---
# Desk 1: HyperLiquid Monarch

Perp DEX desk: delta-neutral funding harvester, whale cascade sweeper, L2 order-book sampler, liquidation engine and the collector that feeds a 4.9 GB snapshot warehouse.

**Domain**: Hyperliquid perps and HIP-3 TradFi

## Code roots

- `HyperLiquid/HL_Monarch`

## Raw streams (federated, read-only)

- `HyperLiquid/HL_Monarch/data/hyperliquid_data.db (13 tables)`
- `HyperLiquid/HL_Monarch/data/collector_service.jsonl`
- `HyperLiquid/HL_Monarch/data/experiments/*.meta.json`

## Vault surface (exporter-owned, never written by the knowledge layer)

- `HyperLiquid_Monarch.md`
- `Trading_Terminal.md`
- `Bot_Control.md`
- `Bot_Config.md`
- `Whales/`

## Items

- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester (Basis Bot)]] · deployed
- [[Item_09_Live_Process_Supervisor_Health_Watchdog_Daemon|Item 9: Live Process Supervisor & Health Watchdog Daemon]] · deployed
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Hyperliquid Whale Cascade Sweeper]] · deployed
- [[Item_16_Fast_Time_Series_Warehouse_Incremental_Persistence|Item 16: Fast Time-Series Warehouse & Incremental Persistence]] · deployed
- [[Item_20_Sovereign_Master_Cockpit_UI_War_Room|Item 20: Sovereign Master Cockpit Ui (War Room Dashboard & Canvas)]] · deployed

## Rulings

- [[Ruling_R95|R95 - Ratification of the knowledge layer (R95-A to R95-G)]]

## Other desks

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]
- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## Related

- [[Monarch_Hub|Monarch Hub]] (exporter-owned dashboard index)
