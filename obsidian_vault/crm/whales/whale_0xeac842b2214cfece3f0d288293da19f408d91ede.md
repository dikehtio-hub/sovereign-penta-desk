---
type: Entity/Whale
title: Whale 0xeac8…1ede
description: 'Hyperliquid whale 0xeac8…1ede: rank 59 by account equity at seed; first
  seen on NEAR.'
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
  address: '0xeac842b2214cfece3f0d288293da19f408d91ede'
  first_coin: NEAR
  discovered_at: '2026-09-05T06:23:59Z'
  is_liquidator: false
  rank_at_seed: 59
  evidence:
  - at: '2026-09-05T06:24:00Z'
    account_value: 2394381.34
    position_value: 18119.58
    leverage: 0.01
---
# Whale 0xeac8…1ede

## Identity

- address: `0xeac842b2214cfece3f0d288293da19f408d91ede`
- discovered: `2026-09-05T06:23:59Z` via `NEAR` ($18,182)
- system liquidator: False
- rank by equity at seed: 59
- live note (exporter-owned): [[Whales/0xeac842b2214cfece3f0d288293da19f408d91ede|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-09-05T06:24:00Z | 2394381.34 | 18119.58 | 0.01 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
