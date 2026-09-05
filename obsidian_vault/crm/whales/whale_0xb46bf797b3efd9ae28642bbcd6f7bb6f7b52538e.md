---
type: Entity/Whale
title: Whale 0xb46b…538e
description: 'Hyperliquid whale 0xb46b…538e: rank 42 by account equity at seed; first
  seen on ZEC.'
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
  address: '0xb46bf797b3efd9ae28642bbcd6f7bb6f7b52538e'
  first_coin: ZEC
  discovered_at: '2026-09-02T10:40:36Z'
  is_liquidator: false
  rank_at_seed: 42
  evidence:
  - at: '2026-09-02T10:40:37Z'
    account_value: 3159707.13
    position_value: 6288513.74
    leverage: 1.99
---
# Whale 0xb46b…538e

## Identity

- address: `0xb46bf797b3efd9ae28642bbcd6f7bb6f7b52538e`
- discovered: `2026-09-02T10:40:36Z` via `ZEC` ($10,089)
- system liquidator: False
- rank by equity at seed: 42
- live note (exporter-owned): [[Whales/0xb46bf797b3efd9ae28642bbcd6f7bb6f7b52538e|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-09-02T10:40:37Z | 3159707.13 | 6288513.74 | 1.99 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
