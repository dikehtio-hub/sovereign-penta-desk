---
type: Entity/Sharp Trader
title: Sharp trader Better-Elevator
description: Polymarket sharp trader Better-Elevator (0xebcc…108f); identity unresolved.
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
  wallet: '0xebcc4ce33dada70d195fa3aa5aaa0276bf49108f'
  pseudonym: Better-Elevator
  proxy_wallet: '0xebcc4ce33dada70d195fa3aa5aaa0276bf49108f'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:07:59Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:49:35Z'
    pnl_7d: -53.44
    realized_pnl_7d: 126.91
    volume_7d: 415.76
    trades_7d: 111
    win_rate: 100.0
    is_sharp: false
---
# Sharp trader Better-Elevator

## Identity

- wallet: `0xebcc4ce33dada70d195fa3aa5aaa0276bf49108f`
- pseudonym: **Better-Elevator**
- profile: https://polymarket.com/profile/0xebcc4ce33dada70d195fa3aa5aaa0276bf49108f
- proxy wallet: `0xebcc4ce33dada70d195fa3aa5aaa0276bf49108f` · EOA: `unresolved` (resolved `2026-08-31T04:07:59Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): none written for `0xebcc4ce33dada70d195fa3aa5aaa0276bf49108f` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:49:35Z | -53.44 | 126.91 | 415.76 | 111 | 100.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
