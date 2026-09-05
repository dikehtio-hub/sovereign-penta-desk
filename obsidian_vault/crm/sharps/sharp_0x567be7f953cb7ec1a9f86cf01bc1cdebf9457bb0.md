---
type: Entity/Sharp Trader
title: Sharp trader Adored-Pin-Doe
description: Polymarket sharp trader Adored-Pin-Doe (0x567b…7bb0); identity unresolved.
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
  wallet: '0x567be7f953cb7ec1a9f86cf01bc1cdebf9457bb0'
  pseudonym: Adored-Pin-Doe
  proxy_wallet: '0x567be7f953cb7ec1a9f86cf01bc1cdebf9457bb0'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:07:56Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:50:03Z'
    pnl_7d: 484.92
    realized_pnl_7d: 539.42
    volume_7d: 570.61
    trades_7d: 445
    win_rate: 100.0
    is_sharp: true
---
# Sharp trader Adored-Pin-Doe

## Identity

- wallet: `0x567be7f953cb7ec1a9f86cf01bc1cdebf9457bb0`
- pseudonym: **Adored-Pin-Doe**
- profile: https://polymarket.com/profile/0x567be7f953cb7ec1a9f86cf01bc1cdebf9457bb0
- proxy wallet: `0x567be7f953cb7ec1a9f86cf01bc1cdebf9457bb0` · EOA: `unresolved` (resolved `2026-08-31T04:07:56Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): [[Wallets/0x567be7f953cb7ec1a9f86cf01bc1cdebf9457bb0|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:50:03Z | 484.92 | 539.42 | 570.61 | 445 | 100.0 | True |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
