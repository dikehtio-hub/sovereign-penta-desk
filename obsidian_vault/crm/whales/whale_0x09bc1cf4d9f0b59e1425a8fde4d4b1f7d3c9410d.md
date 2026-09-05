---
type: Entity/Whale
title: Whale 0x09bc…410d
description: 'Hyperliquid whale 0x09bc…410d: rank 17 by account equity at seed; first
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
  address: '0x09bc1cf4d9f0b59e1425a8fde4d4b1f7d3c9410d'
  first_coin: BTC
  discovered_at: '2026-08-31T04:16:04Z'
  is_liquidator: false
  rank_at_seed: 17
  evidence:
  - at: '2026-08-31T04:16:07Z'
    account_value: 7534690.03
    position_value: 6569641.74
    leverage: 0.87
---
# Whale 0x09bc…410d

## Identity

- address: `0x09bc1cf4d9f0b59e1425a8fde4d4b1f7d3c9410d`
- discovered: `2026-08-31T04:16:04Z` via `BTC` ($60,011)
- system liquidator: False
- rank by equity at seed: 17
- live note (exporter-owned): [[Whales/0x09bc1cf4d9f0b59e1425a8fde4d4b1f7d3c9410d|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T04:16:07Z | 7534690.03 | 6569641.74 | 0.87 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
