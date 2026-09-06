---
type: Entity/Whale
title: Whale 0xba5d…a352
description: 'Hyperliquid whale 0xba5d…a352: rank 92 by account equity at seed; first
  seen on SOL.'
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
  address: '0xba5d9cc840745aeeeeedac5712e32f13ab8ea352'
  first_coin: SOL
  discovered_at: '2026-09-04T15:49:32Z'
  is_liquidator: false
  rank_at_seed: 92
  evidence:
  - at: '2026-09-04T15:49:33Z'
    account_value: 1796637.16
    position_value: 16204362.48
    leverage: 9.02
---
# Whale 0xba5d…a352

## Identity

- address: `0xba5d9cc840745aeeeeedac5712e32f13ab8ea352`
- discovered: `2026-09-04T15:49:32Z` via `SOL` ($33,999)
- system liquidator: False
- rank by equity at seed: 92
- live note (exporter-owned): none written for `0xba5d9cc840745aeeeeedac5712e32f13ab8ea352` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-09-04T15:49:33Z | 1796637.16 | 16204362.48 | 9.02 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
