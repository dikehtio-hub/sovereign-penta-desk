---
type: Entity/Sharp Trader
title: Sharp trader Anonymous
description: Polymarket sharp trader Anonymous (0x3a66…6e0d); identity unresolved.
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
  wallet: '0x3a66ad8eebd06ac1b91ee17664d939ef7bde6e0d'
  pseudonym: Anonymous
  proxy_wallet: null
  eoa_address: null
  identity_resolved_at: null
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:50:10Z'
    pnl_7d: 0.59
    realized_pnl_7d: 1.2
    volume_7d: 13.62
    trades_7d: 7
    win_rate: 60.0
    is_sharp: false
---
# Sharp trader Anonymous

## Identity

- wallet: `0x3a66ad8eebd06ac1b91ee17664d939ef7bde6e0d`
- pseudonym: **Anonymous**
- profile: https://polymarket.com/profile/0x3a66ad8eebd06ac1b91ee17664d939ef7bde6e0d
- proxy wallet: `-` · EOA: `unresolved`
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): [[Wallets/0x3a66ad8eebd06ac1b91ee17664d939ef7bde6e0d|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:50:10Z | 0.59 | 1.2 | 13.62 | 7 | 60.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
