---
type: Digest
title: Round 60 digest
description: 'Round 60: STRESS CALIBRATION FROM REALIZED VOL, SPORTS SETTLEMENT HISTORY,
  FRACTIONAL CADENCE'
tags:
- digest
- work-chain
- round-60
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-60-complete
  title: AGENTS.md - Round 60 complete
  author: claude-code/fable-5.1
dev:
  round: 60
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 60 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 60 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

STRESS CALIBRATION FROM REALIZED VOL, SPORTS SETTLEMENT

HISTORY, FRACTIONAL CADENCE. load_live_inputs now measures stress_day_prob
and stress_vol_multiplier from hyperliquid_data.db when >= 14 distinct days
of hourly marks exist for the held perps (shock coin-day = daily realized
vol > 3x the pooled median; multiplier = mean shock vol / median), else
"assumed (< 14 days of marks)"; and reads placed_bets for >= 20 settled
wagers (cadence = settled / active days, win rate = wins / (wins + losses),
pushes excluded, mean odds), else "assumed (< 20 settled wagers)". Fractional
bets per day place the remainder as one extra wager with that probability.
start_all_ecosystem_sync.bat passes --risk-stress 0.5 to the Arb exporter so
the card always carries the stress table. 3 new tests. Live: both
calibrations fall back today (3.9 days of marks, 0 settled wagers) and say so.

## Related

- [[digests_register|Digests register]]
