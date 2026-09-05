---
type: Entity/Sharp Trader
title: Sharp trader Giant-Window
description: Polymarket sharp trader Giant-Window (0x7c1e…bab3); identity unresolved.
tags:
- crm
- sharp-trader
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:50Z'
status: draft
sources:
- id: sharp_traders
  resource: Polymarket/Polymarket_Monarch/data/polymarket_whales.db
  title: polymarket_whales.db sharp_traders (mode=ro)
  author: process:Polymarket_Monarch.pnl_scanner
dev:
  desk: 3
  wallet: '0x7c1ee865a785de4c00ee90ed86a38489fb8bbab3'
  pseudonym: Giant-Window
  proxy_wallet: '0x7c1ee865a785de4c00ee90ed86a38489fb8bbab3'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:08:04Z'
  first_seen: '1970-01-21T16:40:53Z'
  evidence:
  - at: '2026-08-31T02:50:37Z'
    pnl_7d: -6579775.37
    realized_pnl_7d: 0.0
    volume_7d: 1761.19
    trades_7d: 443
    win_rate: 0.0
    is_sharp: false
---
# Sharp trader Giant-Window

## Identity

- wallet: `0x7c1ee865a785de4c00ee90ed86a38489fb8bbab3`
- pseudonym: **Giant-Window**
- profile: https://polymarket.com/profile/0x7c1ee865a785de4c00ee90ed86a38489fb8bbab3
- proxy wallet: `0x7c1ee865a785de4c00ee90ed86a38489fb8bbab3` · EOA: `unresolved` (resolved `2026-08-31T04:08:04Z`)
- first seen: `1970-01-21T16:40:53Z`
- live note (exporter-owned): [[Wallets/0x7c1ee865a785de4c00ee90ed86a38489fb8bbab3|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:50:37Z | -6579775.37 | 0.0 | 1761.19 | 443 | 0.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
