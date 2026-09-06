---
type: Market
title: Will the Fed decide differently in the next three decisions (Sep–Oct–Dec)?
description: 'Polymarket market (FED-RATES): Will the Fed decide differently in the
  next three decisions (Sep–Oct–Dec)?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:00:50Z'
status: draft
resource: polymarket:token:31175473935814723265701109747270066913208899162677041393612245983856160819005
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T065828_873438Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '31175473935814723265701109747270066913208899162677041393612245983856160819005'
  family: FED-RATES
  condition_id: '0x36511fb29c3775d1822da8973744ab264334a1fced738b3af390dadc0136b50c'
  market_slug: will-the-fed-decide-differently-in-the-next-three-decisions-sepoctdec
  event_slug: fed-decisions-sepdec
  event_title: Fed decisions (Sep–Dec)
  start_time: '2026-09-02T20:24:24Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed decide differently in the next three decisions (Sep–Oct–Dec)?

> Polymarket · family FED-RATES · token `311754739358…`

## Identity

- token_id: `31175473935814723265701109747270066913208899162677041393612245983856160819005`
- condition_id: `0x36511fb29c3775d1822da8973744ab264334a1fced738b3af390dadc0136b50c`
- market_slug: `will-the-fed-decide-differently-in-the-next-three-decisions-sepoctdec`
- event: Fed decisions (Sep–Dec) (`fed-decisions-sepdec`)
- start_time: `2026-09-02T20:24:24Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
