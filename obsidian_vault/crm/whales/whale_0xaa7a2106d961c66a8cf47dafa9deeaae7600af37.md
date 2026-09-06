---
type: Entity/Whale
title: Whale 0xaa7a…af37
description: 'Hyperliquid whale 0xaa7a…af37: rank 70 by account equity at seed; first
  seen on BTC.'
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
  address: '0xaa7a2106d961c66a8cf47dafa9deeaae7600af37'
  first_coin: BTC
  discovered_at: '2026-08-31T05:18:55Z'
  is_liquidator: false
  rank_at_seed: 70
  evidence:
  - at: '2026-08-31T05:18:57Z'
    account_value: 2200075.3
    position_value: 6754766.21
    leverage: 3.07
---
# Whale 0xaa7a…af37

## Identity

- address: `0xaa7a2106d961c66a8cf47dafa9deeaae7600af37`
- discovered: `2026-08-31T05:18:55Z` via `BTC` ($113,903)
- system liquidator: False
- rank by equity at seed: 70
- live note (exporter-owned): [[Whales/0xaa7a2106d961c66a8cf47dafa9deeaae7600af37|whale note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-08-31T05:18:57Z | 2200075.3 | 6754766.21 | 3.07 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
