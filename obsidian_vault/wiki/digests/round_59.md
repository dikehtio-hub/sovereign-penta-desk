---
type: Digest
title: Round 59 digest
description: 'Round 59: RISK SENTINEL AUTO-REFRESH, SYSTEMIC STRESS FACTOR'
tags:
- digest
- work-chain
- round-59
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-59-complete
  title: AGENTS.md - Round 59 complete
  author: claude-code/fable-5.1
dev:
  round: 59
  date: null
  kind: round_digest
---
# Round 59 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

RISK SENTINEL AUTO-REFRESH, SYSTEMIC STRESS FACTOR. The

Cross-Market Arb Obsidian exporter carries a RiskRefresher: Risk_Sentinel.md
is re-simulated on the first cycle, every --risk-every cycles (60 = 15 min at
15 s) or as soon as the paper book's signature (equity, positions, coins)
moves; 20,000 paths + a 5,000-path grid (~5 s) so the loop is not stalled for
the CLI's 25 s; write_note_if_changed keeps unchanged cards off disk.
risk_simulator gained --stress-correlation (0..1) with --stress-day-prob
(0.02) and --stress-vol-multiplier (3): on a shock day perp vol is
multiplied, funding compresses and flips negative, arb leg failures double,
all together; the report and card show baseline vs stressed VaR99, practical
ruin, cash buffer and desk P&Ls. Zero correlation is bit-identical to an
unstressed run. 3 new tests.

## Related

- [[digests_register|Digests register]]
