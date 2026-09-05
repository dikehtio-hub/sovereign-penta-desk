---
type: Entity/Sharp Trader
title: Sharp trader Vigilant-Environment
description: Polymarket sharp trader Vigilant-Environment (0xdbdd…a5de); identity
  unresolved.
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
  wallet: '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
  pseudonym: Vigilant-Environment
  proxy_wallet: '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:08:06Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:57:17Z'
    pnl_7d: -377603.62
    realized_pnl_7d: 0.0
    volume_7d: 66790.22
    trades_7d: 331
    win_rate: 0.0
    is_sharp: false
---
# Sharp trader Vigilant-Environment

## Identity

- wallet: `0xdbdd45150249e229eb4ca8aa48a30dca21faa5de`
- pseudonym: **Vigilant-Environment**
- profile: https://polymarket.com/profile/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de
- proxy wallet: `0xdbdd45150249e229eb4ca8aa48a30dca21faa5de` · EOA: `unresolved` (resolved `2026-08-31T04:08:06Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): [[Wallets/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:57:17Z | -377603.62 | 0.0 | 66790.22 | 331 | 0.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
