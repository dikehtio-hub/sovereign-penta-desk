---
type: Entity/Whale
title: Whale 0x936c…bb0f
description: 'Hyperliquid whale 0x936c…bb0f: rank 6 by account equity at seed; first
  seen on ETH.'
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
  address: '0x936cf4fb95c30ce83f658b5bbb247e4bb381bb0f'
  first_coin: ETH
  discovered_at: '2026-08-31T05:27:15Z'
  is_liquidator: true
  rank_at_seed: 6
  evidence:
  - at: '2026-08-31T05:27:15Z'
    account_value: 14920798.31
    position_value: 30572257.66
    leverage: 2.05
---
# Whale 0x936c…bb0f

## Identity

- address: `0x936cf4fb95c30ce83f658b5bbb247e4bb381bb0f`
- discovered: `2026-08-31T05:27:15Z` via `ETH` ($30,689)
- system liquidator: True
- rank by equity at seed: 6
- live note (exporter-owned): [[Whales/0x936cf4fb95c30ce83f658b5bbb247e4bb381bb0f|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T05:27:15Z | 14920798.31 | 30572257.66 | 2.05 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
