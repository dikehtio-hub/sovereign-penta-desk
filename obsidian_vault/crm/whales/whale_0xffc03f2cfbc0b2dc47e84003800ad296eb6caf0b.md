---
type: Entity/Whale
title: Whale 0xffc0…af0b
description: 'Hyperliquid whale 0xffc0…af0b: rank 75 by account equity at seed; first
  seen on SOL.'
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
  address: '0xffc03f2cfbc0b2dc47e84003800ad296eb6caf0b'
  first_coin: SOL
  discovered_at: '2026-08-31T18:37:02Z'
  is_liquidator: false
  rank_at_seed: 75
  rank_now: 75
  evidence:
  - at: '2026-08-31T18:37:03Z'
    account_value: 2079647.49
    position_value: 41008.11
    leverage: 0.02
---
# Whale 0xffc0…af0b

## Identity

- address: `0xffc03f2cfbc0b2dc47e84003800ad296eb6caf0b`
- discovered: `2026-08-31T18:37:02Z` via `SOL` ($41,044)
- system liquidator: False
- rank by equity at seed: 75
- live note (exporter-owned): none written for `0xffc03f2cfbc0b2dc47e84003800ad296eb6caf0b` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T18:37:03Z | 2079647.49 | 41008.11 | 0.02 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
