---
type: Entity/Whale
title: Whale 0xfc27…9d9d
description: 'Hyperliquid whale 0xfc27…9d9d: rank 3 by account equity at seed; first
  seen on BTC.'
tags:
- crm
- whale
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T04:51:55Z'
status: draft
sources:
- id: whale_wallets
  resource: HyperLiquid/HL_Monarch/data/hyperliquid_data.db
  title: hyperliquid_data.db whale_wallets (mode=ro)
  author: process:HL_Monarch.collector
dev:
  desk: 1
  address: '0xfc27136e42af1732ddc9ce2605ea9bff1b959d9d'
  first_coin: BTC
  discovered_at: '2026-08-31T05:18:55Z'
  is_liquidator: true
  rank_at_seed: 3
  evidence:
  - at: '2026-08-31T05:18:57Z'
    account_value: 21515029.21
    position_value: 57447041.92
    leverage: 2.67
---
# Whale 0xfc27…9d9d

## Identity

- address: `0xfc27136e42af1732ddc9ce2605ea9bff1b959d9d`
- discovered: `2026-08-31T05:18:55Z` via `BTC` ($113,922)
- system liquidator: True
- rank by equity at seed: 3
- live note (exporter-owned): [[Whales/0xfc27136e42af1732ddc9ce2605ea9bff1b959d9d|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T05:18:57Z | 21515029.21 | 57447041.92 | 2.67 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
