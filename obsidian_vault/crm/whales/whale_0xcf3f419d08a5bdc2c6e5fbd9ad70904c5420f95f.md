---
type: Entity/Whale
title: Whale 0xcf3f…f95f
description: 'Hyperliquid whale 0xcf3f…f95f: rank 24 by account equity at seed; first
  seen on BTC.'
tags:
- crm
- whale
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:50Z'
status: draft
sources:
- id: whale_wallets
  resource: HyperLiquid/HL_Monarch/data/hyperliquid_data.db
  title: hyperliquid_data.db whale_wallets (mode=ro)
  author: process:HL_Monarch.collector
dev:
  desk: 1
  address: '0xcf3f419d08a5bdc2c6e5fbd9ad70904c5420f95f'
  first_coin: BTC
  discovered_at: '2026-08-31T05:19:50Z'
  is_liquidator: false
  rank_at_seed: 24
  evidence:
  - at: '2026-08-31T05:19:51Z'
    account_value: 5326076.0
    position_value: 3541183.6
    leverage: 0.66
---
# Whale 0xcf3f…f95f

## Identity

- address: `0xcf3f419d08a5bdc2c6e5fbd9ad70904c5420f95f`
- discovered: `2026-08-31T05:19:50Z` via `BTC` ($32,004)
- system liquidator: False
- rank by equity at seed: 24
- live note (exporter-owned): [[Whales/0xcf3f419d08a5bdc2c6e5fbd9ad70904c5420f95f|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T05:19:51Z | 5326076.0 | 3541183.6 | 0.66 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
