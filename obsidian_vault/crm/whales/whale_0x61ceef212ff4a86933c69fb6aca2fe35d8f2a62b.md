---
type: Entity/Whale
title: Whale 0x61ce…a62b
description: 'Hyperliquid whale 0x61ce…a62b: rank 19 by account equity at seed; first
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
  address: '0x61ceef212ff4a86933c69fb6aca2fe35d8f2a62b'
  first_coin: ETH
  discovered_at: '2026-09-01T00:10:53Z'
  is_liquidator: false
  rank_at_seed: 19
  evidence:
  - at: '2026-09-01T00:10:54Z'
    account_value: 7320696.29
    position_value: 17371447.55
    leverage: 2.37
---
# Whale 0x61ce…a62b

## Identity

- address: `0x61ceef212ff4a86933c69fb6aca2fe35d8f2a62b`
- discovered: `2026-09-01T00:10:53Z` via `ETH` ($70,000)
- system liquidator: False
- rank by equity at seed: 19
- live note (exporter-owned): none written for `0x61ceef212ff4a86933c69fb6aca2fe35d8f2a62b` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-09-01T00:10:54Z | 7320696.29 | 17371447.55 | 2.37 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
