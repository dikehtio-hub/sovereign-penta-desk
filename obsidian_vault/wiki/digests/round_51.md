---
type: Digest
title: Round 51 digest
description: 'Round 51: MEASURED MACRO SIGNALS & ITEM 18 LEAD-LAG (OFFLINE)'
tags:
- digest
- work-chain
- round-51
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-51-complete
  title: AGENTS.md - Round 51 complete
  author: claude-code/fable-5.1
dev:
  round: 51
  date: null
  kind: round_digest
---
# Round 51 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

MEASURED MACRO SIGNALS & ITEM 18 LEAD-LAG (OFFLINE). The

Titan note's macro block is no longer three hard-coded narratives: Polymarket
probabilities are looked up in whale_trades and in drop files (keyword groups
for a Fed cut and a BTC $100k milestone), HyperLiquid flow is measured from
latest_snapshots/asset_snapshots (OI-weighted funding APR, total OI, 24h OI
change) and every signal carries measured/source; a missing input is
"[NO LIVE MARKET FOUND]" or "[UNMEASURED: reason]", never a number. New
`cross_market/lead_lag.py` (Item 18) finds the lag at which probability shifts
and perp returns line up, from timestamped drops and a READ-ONLY snapshot DB,
and refuses to name one on thin evidence. 11 new tests; master suite is 16
modules. No collector code changed; no restart.

## Related

- [[digests_register|Digests register]]
