---
type: Entity/Sharp Trader
title: Sharp trader Rotating-Mammoth
description: Polymarket sharp trader Rotating-Mammoth (0xe59b…06ef); identity unresolved.
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
  wallet: '0xe59b2c5916dd9c8f0dcf7b7ba46aff511dc806ef'
  pseudonym: Rotating-Mammoth
  proxy_wallet: '0xe59b2c5916dd9c8f0dcf7b7ba46aff511dc806ef'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:08:09Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:49:32Z'
    pnl_7d: -44.56
    realized_pnl_7d: -0.01
    volume_7d: 11.86
    trades_7d: 2
    win_rate: 0.0
    is_sharp: false
---
# Sharp trader Rotating-Mammoth

## Identity

- wallet: `0xe59b2c5916dd9c8f0dcf7b7ba46aff511dc806ef`
- pseudonym: **Rotating-Mammoth**
- profile: https://polymarket.com/profile/0xe59b2c5916dd9c8f0dcf7b7ba46aff511dc806ef
- proxy wallet: `0xe59b2c5916dd9c8f0dcf7b7ba46aff511dc806ef` · EOA: `unresolved` (resolved `2026-08-31T04:08:09Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): none written for `0xe59b2c5916dd9c8f0dcf7b7ba46aff511dc806ef` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:49:32Z | -44.56 | -0.01 | 11.86 | 2 | 0.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
