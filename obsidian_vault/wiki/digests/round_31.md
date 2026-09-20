---
type: Digest
title: Round 31 digest
description: 'Round 31: Targets D (exit hysteresis) and E (leverage policy) applied,
  and **Item 14 built as a GATED, NON-TRADING module** - see findings'
tags:
- digest
- work-chain
- round-31
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-31-complete
  title: AGENTS_ARCHIVE.md - Round 31 complete
  author: claude-code/fable-5.1
dev:
  round: 31
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 31 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 31 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

Targets D (exit hysteresis) and E (leverage policy) applied,

and **Item 14 built as a GATED, NON-TRADING module** - see findings. 38 new tests.

Round 29 before it: Item 8, the funding harvester's BUCKET GATE and after-tax
economics (`HL_Monarch/strategies/funding_harvester.py`). The delta-neutral
engine already existed and was left alone; what was missing was the layer
between it and the bankroll. 24 new tests.

Round 27 before it: Item 6, cross-market arbitrage (`cross_market/hybrid_arb.py`,
`matcher.py`, `hud.py`, `--cross-market` on Monarch_Shark). 52 new tests.

Round 26m before it. **The repository now has version history** — it had none
through ~12 rounds of work. Two commits: the baseline (`743496b`, 526 files) and
the reconcile alias (`5e188a5`).

Suites, all offline:

| suite | count |
|---|---|
| master + bridges + cross-market + exporters + ingestors (22 modules, incl. test_titan_correlator, test_lead_lag, test_risk_simulator, test_execution_log, test_stale_quotes, test_c2_bot, test_latency_sniper, test_amm_rewards) | 936 OK |
| HL_Monarch (pytest) | 1083 passed |
| Tax_Reserve_Agent (5 modules) | 546 OK |

Tax config is **New Jersey resident** (Union, 07083): composite 32.37% =
24% federal + 6.37% NJ + 2% buffer, `casual_standard_deduction`.

## Related

- [[digests_register|Digests register]]
