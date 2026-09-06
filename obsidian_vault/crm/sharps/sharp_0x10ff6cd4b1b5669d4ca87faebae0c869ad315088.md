---
type: Entity/Sharp Trader
title: Sharp trader Tempting-Chrysalis
description: Polymarket sharp trader Tempting-Chrysalis (0x10ff…5088); identity unresolved.
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
  wallet: '0x10ff6cd4b1b5669d4ca87faebae0c869ad315088'
  pseudonym: Tempting-Chrysalis
  proxy_wallet: '0x10ff6cd4b1b5669d4ca87faebae0c869ad315088'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:08:06Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:57:11Z'
    pnl_7d: -180348.64
    realized_pnl_7d: 0.0
    volume_7d: 117770.23
    trades_7d: 480
    win_rate: 0.0
    is_sharp: false
---
# Sharp trader Tempting-Chrysalis

## Identity

- wallet: `0x10ff6cd4b1b5669d4ca87faebae0c869ad315088`
- pseudonym: **Tempting-Chrysalis**
- profile: https://polymarket.com/profile/0x10ff6cd4b1b5669d4ca87faebae0c869ad315088
- proxy wallet: `0x10ff6cd4b1b5669d4ca87faebae0c869ad315088` · EOA: `unresolved` (resolved `2026-08-31T04:08:06Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): none written for `0x10ff6cd4b1b5669d4ca87faebae0c869ad315088` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:57:11Z | -180348.64 | 0.0 | 117770.23 | 480 | 0.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
