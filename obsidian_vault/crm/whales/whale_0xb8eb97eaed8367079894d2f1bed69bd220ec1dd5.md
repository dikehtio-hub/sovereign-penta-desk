---
type: Entity/Whale
title: Whale 0xb8eb…1dd5
description: 'Hyperliquid whale 0xb8eb…1dd5: rank 80 by account equity at seed; first
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
  address: '0xb8eb97eaed8367079894d2f1bed69bd220ec1dd5'
  first_coin: ETH
  discovered_at: '2026-08-31T05:19:24Z'
  is_liquidator: false
  rank_at_seed: 80
  rank_now: 80
  evidence:
  - at: '2026-08-31T05:19:24Z'
    account_value: 1932986.24
    position_value: 5547955.72
    leverage: 2.87
---
# Whale 0xb8eb…1dd5

## Identity

- address: `0xb8eb97eaed8367079894d2f1bed69bd220ec1dd5`
- discovered: `2026-08-31T05:19:24Z` via `ETH` ($150,035)
- system liquidator: False
- rank by equity at seed: 80
- live note (exporter-owned): none written for `0xb8eb97eaed8367079894d2f1bed69bd220ec1dd5` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T05:19:24Z | 1932986.24 | 5547955.72 | 2.87 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
