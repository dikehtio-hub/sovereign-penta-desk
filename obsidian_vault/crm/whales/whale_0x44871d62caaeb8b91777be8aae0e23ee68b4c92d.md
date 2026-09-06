---
type: Entity/Whale
title: Whale 0x4487…c92d
description: 'Hyperliquid whale 0x4487…c92d: rank 18 by account equity at seed; first
  seen on ETH.'
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
  address: '0x44871d62caaeb8b91777be8aae0e23ee68b4c92d'
  first_coin: ETH
  discovered_at: '2026-08-31T05:21:33Z'
  is_liquidator: false
  rank_at_seed: 18
  rank_now: 18
  evidence:
  - at: '2026-08-31T05:21:34Z'
    account_value: 7475275.4
    position_value: 30206344.98
    leverage: 4.04
---
# Whale 0x4487…c92d

## Identity

- address: `0x44871d62caaeb8b91777be8aae0e23ee68b4c92d`
- discovered: `2026-08-31T05:21:33Z` via `ETH` ($30,000)
- system liquidator: False
- rank by equity at seed: 18
- live note (exporter-owned): [[Whales/0x44871d62caaeb8b91777be8aae0e23ee68b4c92d|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T05:21:34Z | 7475275.4 | 30206344.98 | 4.04 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
