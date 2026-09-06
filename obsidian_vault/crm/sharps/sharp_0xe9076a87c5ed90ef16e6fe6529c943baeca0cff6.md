---
type: Entity/Sharp Trader
title: Sharp trader All-Peasant-Drug
description: Polymarket sharp trader All-Peasant-Drug (0xe907…cff6); identity unresolved.
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
  wallet: '0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6'
  pseudonym: All-Peasant-Drug
  proxy_wallet: '0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6'
  eoa_address: null
  identity_resolved_at: '2026-08-31T04:07:46Z'
  first_seen: '1970-01-21T16:40:53Z'
  evidence:
  - at: '2026-08-31T02:56:25Z'
    pnl_7d: 81832.37
    realized_pnl_7d: 108963.74
    volume_7d: 11881.44
    trades_7d: 393
    win_rate: 100.0
    is_sharp: true
---
# Sharp trader All-Peasant-Drug

## Identity

- wallet: `0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6`
- pseudonym: **All-Peasant-Drug**
- profile: https://polymarket.com/profile/0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6
- proxy wallet: `0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6` · EOA: `unresolved` (resolved `2026-08-31T04:07:46Z`)
- first seen: `1970-01-21T16:40:53Z`
- live note (exporter-owned): [[Wallets/0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6|trader note]]

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | pnl_7d | realized_pnl_7d | volume_7d | trades_7d | win_rate | is_sharp |
|---|---|---|---|---|---|---|
| 2026-08-31T02:56:25Z | 81832.37 | 108963.74 | 11881.44 | 393 | 100.0 | True |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[crm_register|CRM register]]
