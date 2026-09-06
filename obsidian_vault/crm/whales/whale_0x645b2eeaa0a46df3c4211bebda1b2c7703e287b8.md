---
type: Entity/Whale
title: Whale 0x645b…87b8
description: 'Hyperliquid whale 0x645b…87b8: rank 5 by account equity at seed; first
  seen on HYPE.'
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
  address: '0x645b2eeaa0a46df3c4211bebda1b2c7703e287b8'
  first_coin: HYPE
  discovered_at: '2026-09-01T02:28:10Z'
  is_liquidator: true
  rank_at_seed: 5
  evidence:
  - at: '2026-09-01T02:28:11Z'
    account_value: 16665883.68
    position_value: 43246291.27
    leverage: 2.59
---
# Whale 0x645b…87b8

## Identity

- address: `0x645b2eeaa0a46df3c4211bebda1b2c7703e287b8`
- discovered: `2026-09-01T02:28:10Z` via `HYPE` ($37,524)
- system liquidator: True
- rank by equity at seed: 5
- live note (exporter-owned): [[Whales/0x645b2eeaa0a46df3c4211bebda1b2c7703e287b8|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-09-01T02:28:11Z | 16665883.68 | 43246291.27 | 2.59 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
