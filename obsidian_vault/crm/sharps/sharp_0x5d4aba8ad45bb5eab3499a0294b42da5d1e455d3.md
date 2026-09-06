---
type: Entity/Sharp Trader
title: Sharp trader Anonymous
description: Polymarket sharp trader Anonymous (0x5d4a…55d3); identity resolved to
  an EOA.
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
  wallet: '0x5d4aba8ad45bb5eab3499a0294b42da5d1e455d3'
  pseudonym: Anonymous
  proxy_wallet: '0x569076fca4ebe9e287927ce36d50dd7738e3900a'
  eoa_address: '0x5d4aba8ad45bb5eab3499a0294b42da5d1e455d3'
  identity_resolved_at: '2026-08-31T04:07:53Z'
  first_seen: '1970-01-21T16:40:53Z'
  evidence:
  - at: '2026-08-31T02:50:56Z'
    pnl_7d: 2661.8
    realized_pnl_7d: 2663.16
    volume_7d: 1839.2
    trades_7d: 359
    win_rate: 100.0
    is_sharp: true
---
# Sharp trader Anonymous

## Identity

- wallet: `0x5d4aba8ad45bb5eab3499a0294b42da5d1e455d3`
- pseudonym: **Anonymous**
- profile: https://polymarket.com/profile/0x5d4aba8ad45bb5eab3499a0294b42da5d1e455d3
- proxy wallet: `0x569076fca4ebe9e287927ce36d50dd7738e3900a` · EOA: `0x5d4aba8ad45bb5eab3499a0294b42da5d1e455d3` (resolved `2026-08-31T04:07:53Z`)
- first seen: `1970-01-21T16:40:53Z`
- live note (exporter-owned): [[Wallets/0x5d4aba8ad45bb5eab3499a0294b42da5d1e455d3|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:50:56Z | 2661.8 | 2663.16 | 1839.2 | 359 | 100.0 | True |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
