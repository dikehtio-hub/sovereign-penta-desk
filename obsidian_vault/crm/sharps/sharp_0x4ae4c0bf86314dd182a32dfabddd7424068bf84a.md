---
type: Entity/Sharp Trader
title: Sharp trader Natural-Enterprise
description: Polymarket sharp trader Natural-Enterprise (0x4ae4…f84a); identity unresolved.
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
  wallet: '0x4ae4c0bf86314dd182a32dfabddd7424068bf84a'
  pseudonym: Natural-Enterprise
  proxy_wallet: '0x4ae4c0bf86314dd182a32dfabddd7424068bf84a'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:07:57Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:49:45Z'
    pnl_7d: 947.54
    realized_pnl_7d: 356.88
    volume_7d: 15145.54
    trades_7d: 209
    win_rate: 100.0
    is_sharp: true
---
# Sharp trader Natural-Enterprise

## Identity

- wallet: `0x4ae4c0bf86314dd182a32dfabddd7424068bf84a`
- pseudonym: **Natural-Enterprise**
- profile: https://polymarket.com/profile/0x4ae4c0bf86314dd182a32dfabddd7424068bf84a
- proxy wallet: `0x4ae4c0bf86314dd182a32dfabddd7424068bf84a` · EOA: `unresolved` (resolved `2026-08-31T04:07:57Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): [[Wallets/0x4ae4c0bf86314dd182a32dfabddd7424068bf84a|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:49:45Z | 947.54 | 356.88 | 15145.54 | 209 | 100.0 | True |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
