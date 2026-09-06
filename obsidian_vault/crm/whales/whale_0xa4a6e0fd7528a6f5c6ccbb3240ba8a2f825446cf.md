---
type: Entity/Whale
title: Whale 0xa4a6…46cf
description: 'Hyperliquid whale 0xa4a6…46cf: rank 84 by account equity at seed; first
  seen on UNI.'
tags:
- crm
- whale
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T04:55:31Z'
status: draft
sources:
- id: whale_wallets
  resource: HyperLiquid/HL_Monarch/data/hyperliquid_data.db
  title: hyperliquid_data.db whale_wallets (mode=ro)
  author: process:HL_Monarch.collector
dev:
  desk: 1
  address: '0xa4a6e0fd7528a6f5c6ccbb3240ba8a2f825446cf'
  first_coin: UNI
  discovered_at: '2026-08-31T22:29:55Z'
  is_liquidator: true
  rank_at_seed: 84
  evidence:
  - at: '2026-08-31T22:29:56Z'
    account_value: 1862215.11
    position_value: 1861555.78
    leverage: 1.0
---
# Whale 0xa4a6…46cf

## Identity

- address: `0xa4a6e0fd7528a6f5c6ccbb3240ba8a2f825446cf`
- discovered: `2026-08-31T22:29:55Z` via `UNI` ($21,060)
- system liquidator: True
- rank by equity at seed: 84
- live note (exporter-owned): none written for `0xa4a6e0fd7528a6f5c6ccbb3240ba8a2f825446cf` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T22:29:56Z | 1862215.11 | 1861555.78 | 1.0 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
