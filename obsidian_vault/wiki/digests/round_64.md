---
type: Digest
title: Round 64 digest
description: 'Round 64: PAPER ARB CLOSED-LOOP DRILL, STALE-QUOTE ENGINE GROUNDWORK'
tags:
- digest
- work-chain
- round-64
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-64-complete
  title: AGENTS.md - Round 64 complete
  author: claude-code/fable-5.1
dev:
  round: 64
  date: null
  kind: round_digest
---
# Round 64 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

PAPER ARB CLOSED-LOOP DRILL, STALE-QUOTE ENGINE GROUNDWORK.

cross_market/paper_drill.py drives Betslip.stake_cross_market(paper=True)
over synthetic equal-payout pairs, writes two paper receipts per dutch
(tagged drill:1), shows the arb desk flip from "assumed (< 10 arb fills)"
to "measured (paper_receipts receipts, N fills / E arbs ...)" through the
risk simulator's own loader and --calibration-report, then REMOVES its
receipts unless --keep (synthetic history must not be "measured" later).
Sports_Desk/engine/stale_quotes.py is the Item-11-style core (sharp move =
>= 2 pts at >= 0.5 pt/min; stale retail = latest quote >= 60 s before the
move's end, <= 15 min old, >= 2 pts cheap vs the sharp post-move price;
drifts counted as overpriced), pure functions + a fair_odds_measurements
scanner, no execution. 7 new tests; master suite is 19 modules.

## Related

- [[digests_register|Digests register]]
