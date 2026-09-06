---
type: Entity/Whale
title: Whale 0xecb6…2b00
description: 'Hyperliquid whale 0xecb6…2b00: rank 1 by account equity at seed; first
  seen on BTC.'
tags:
- crm
- whale
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T06:28:48Z'
status: draft
sources:
- id: whale_wallets
  resource: HyperLiquid/HL_Monarch/data/hyperliquid_data.db
  title: hyperliquid_data.db whale_wallets (mode=ro)
  author: process:HL_Monarch.collector
dev:
  desk: 1
  address: '0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00'
  first_coin: BTC
  discovered_at: '2026-08-30T17:35:51Z'
  is_liquidator: true
  rank_at_seed: 1
  rank_now: 1
  evidence:
  - at: '2026-08-30T17:35:53Z'
    account_value: 73059495.55
    position_value: 158093023.15
    leverage: 2.16
---
# Whale 0xecb6…2b00

## Identity

- address: `0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00`
- discovered: `2026-08-30T17:35:51Z` via `BTC` ($65,004)
- system liquidator: True
- rank by equity at seed: 1
- live note (exporter-owned): [[Whales/0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-30T17:35:53Z | 73059495.55 | 158093023.15 | 2.16 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
