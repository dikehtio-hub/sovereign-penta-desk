---
type: Entity/Sharp Trader
title: Sharp trader Bland-Dynamite
description: Polymarket sharp trader Bland-Dynamite (0x496f…fa5d); identity unresolved.
tags:
- crm
- sharp-trader
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T04:51:55Z'
status: draft
sources:
- id: sharp_traders
  resource: Polymarket/Polymarket_Monarch/data/polymarket_whales.db
  title: polymarket_whales.db sharp_traders (mode=ro)
  author: process:Polymarket_Monarch.pnl_scanner
dev:
  desk: 3
  wallet: '0x496f76bd5cf4c2819c710ae90ed1c84b2dc6fa5d'
  pseudonym: Bland-Dynamite
  proxy_wallet: '0x496f76bd5cf4c2819c710ae90ed1c84b2dc6fa5d'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:07:51Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:50:13Z'
    pnl_7d: 1745.49
    realized_pnl_7d: 3399.59
    volume_7d: 1013.99
    trades_7d: 371
    win_rate: 100.0
    is_sharp: true
---
# Sharp trader Bland-Dynamite

## Identity

- wallet: `0x496f76bd5cf4c2819c710ae90ed1c84b2dc6fa5d`
- pseudonym: **Bland-Dynamite**
- profile: https://polymarket.com/profile/0x496f76bd5cf4c2819c710ae90ed1c84b2dc6fa5d
- proxy wallet: `0x496f76bd5cf4c2819c710ae90ed1c84b2dc6fa5d` · EOA: `unresolved` (resolved `2026-08-31T04:07:51Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): [[Wallets/0x496f76bd5cf4c2819c710ae90ed1c84b2dc6fa5d|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:50:13Z | 1745.49 | 3399.59 | 1013.99 | 371 | 100.0 | True |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
