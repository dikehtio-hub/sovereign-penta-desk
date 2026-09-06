---
type: Entity/Sharp Trader
title: Sharp trader Insignificant-Forelimb
description: Polymarket sharp trader Insignificant-Forelimb (0x2e1f…8fde); identity
  unresolved.
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
  wallet: '0x2e1f908b32bced89c0010fad8f35c469cfbd8fde'
  pseudonym: Insignificant-Forelimb
  proxy_wallet: '0x2e1f908b32bced89c0010fad8f35c469cfbd8fde'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:08:07Z'
  first_seen: '1970-01-21T16:41:00Z'
  evidence:
  - at: '2026-08-31T02:57:23Z'
    pnl_7d: -196.86
    realized_pnl_7d: 0.0
    volume_7d: 2636.94
    trades_7d: 359
    win_rate: 0.0
    is_sharp: false
---
# Sharp trader Insignificant-Forelimb

## Identity

- wallet: `0x2e1f908b32bced89c0010fad8f35c469cfbd8fde`
- pseudonym: **Insignificant-Forelimb**
- profile: https://polymarket.com/profile/0x2e1f908b32bced89c0010fad8f35c469cfbd8fde
- proxy wallet: `0x2e1f908b32bced89c0010fad8f35c469cfbd8fde` · EOA: `unresolved` (resolved `2026-08-31T04:08:07Z`)
- first seen: `1970-01-21T16:41:00Z`
- live note (exporter-owned): none written for `0x2e1f908b32bced89c0010fad8f35c469cfbd8fde` (the exporter tracks a different set)

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:57:23Z | -196.86 | 0.0 | 2636.94 | 359 | 0.0 | False |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
