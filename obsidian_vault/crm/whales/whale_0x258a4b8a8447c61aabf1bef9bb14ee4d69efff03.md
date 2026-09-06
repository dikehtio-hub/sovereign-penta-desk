---
type: Entity/Whale
title: Whale 0x258a…ff03
description: 'Hyperliquid whale 0x258a…ff03: rank 36 by account equity at seed; first
  seen on ARB.'
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
  address: '0x258a4b8a8447c61aabf1bef9bb14ee4d69efff03'
  first_coin: ARB
  discovered_at: '2026-09-06T04:54:12Z'
  is_liquidator: true
  rank_at_seed: 36
  evidence:
  - at: '2026-09-06T04:54:13Z'
    account_value: 4216329.25
    position_value: 9944350.38
    leverage: 2.36
---
# Whale 0x258a…ff03

## Identity

- address: `0x258a4b8a8447c61aabf1bef9bb14ee4d69efff03`
- discovered: `2026-09-06T04:54:12Z` via `ARB` ($24,498)
- system liquidator: True
- rank by equity at seed: 36
- live note (exporter-owned): none written for `0x258a4b8a8447c61aabf1bef9bb14ee4d69efff03` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | account_value | position_value | leverage |
|---|---|---|---|
| 2026-09-06T04:54:13Z | 4216329.25 | 9944350.38 | 2.36 |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[crm_register|CRM register]]
