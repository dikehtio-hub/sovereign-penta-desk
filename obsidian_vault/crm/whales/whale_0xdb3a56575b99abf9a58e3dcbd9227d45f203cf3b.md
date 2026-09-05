---
type: Entity/Whale
title: Whale 0xdb3a…cf3b
description: 'Hyperliquid whale 0xdb3a…cf3b: rank 49 by account equity at seed; first
  seen on HYPE.'
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
  address: '0xdb3a56575b99abf9a58e3dcbd9227d45f203cf3b'
  first_coin: HYPE
  discovered_at: '2026-08-31T20:09:40Z'
  is_liquidator: true
  rank_at_seed: 49
  evidence:
  - at: '2026-08-31T20:09:41Z'
    account_value: 2909761.09
    position_value: 379319.97
    leverage: 0.13
---
# Whale 0xdb3a…cf3b

## Identity

- address: `0xdb3a56575b99abf9a58e3dcbd9227d45f203cf3b`
- discovered: `2026-08-31T20:09:40Z` via `HYPE` ($28,717)
- system liquidator: True
- rank by equity at seed: 49
- live note (exporter-owned): [[Whales/0xdb3a56575b99abf9a58e3dcbd9227d45f203cf3b|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T20:09:41Z | 2909761.09 | 379319.97 | 0.13 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
