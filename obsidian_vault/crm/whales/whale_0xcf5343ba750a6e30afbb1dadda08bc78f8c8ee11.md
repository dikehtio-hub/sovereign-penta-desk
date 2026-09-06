---
type: Entity/Whale
title: Whale 0xcf53…ee11
description: 'Hyperliquid whale 0xcf53…ee11: rank 53 by account equity at seed; first
  seen on xyz:SKHX.'
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
  address: '0xcf5343ba750a6e30afbb1dadda08bc78f8c8ee11'
  first_coin: xyz:SKHX
  discovered_at: '2026-08-31T18:34:38Z'
  is_liquidator: false
  rank_at_seed: 53
  evidence:
  - at: '2026-08-31T18:34:39Z'
    account_value: 2815196.11
    position_value: 19280790.53
    leverage: 6.85
---
# Whale 0xcf53…ee11

## Identity

- address: `0xcf5343ba750a6e30afbb1dadda08bc78f8c8ee11`
- discovered: `2026-08-31T18:34:38Z` via `xyz:SKHX` ($11,056)
- system liquidator: False
- rank by equity at seed: 53
- live note (exporter-owned): [[Whales/0xcf5343ba750a6e30afbb1dadda08bc78f8c8ee11|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T18:34:39Z | 2815196.11 | 19280790.53 | 6.85 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
