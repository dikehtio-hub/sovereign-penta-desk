---
type: Digest
title: Round 90 digest
description: 'Round 90 (2026-09-05): ITEM 13 PHASE 1 - AMM QUOTING ENGINE + REWARDS
  SIMULATOR (registry line 279)'
tags:
- digest
- work-chain
- round-90
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-90-complete
  title: AGENTS.md - Round 90 complete
  author: claude-code/fable-5.1
dev:
  round: 90
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 90 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 90 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

ITEM 13 PHASE 1 - AMM QUOTING ENGINE + REWARDS

SIMULATOR (registry line 279). NEW cross_market/amm_rewards.py: Avellaneda-
Stoikov quotes (reservation = fair - q*gamma*sigma^2*tau; half-spread = risk
term + (1/gamma) ln(1 + gamma/k); tick grid; never cross fair; an inventory
limit removes the growing side; a volatility spike widens, a larger one
pulls; event windows pull; optional pull inside the rewards window), the
programme's order score ((v - s)/v)^2 * size inside the max spread and above
the min size, Q_min two-sided in the 0.10-0.90 band and one-sided outside,
pool share against a competitor Q INPUT; a per-minute simulator over a
synthetic or supplied fair path with Poisson retail fills
(A*exp(-k*cents)); PAPER maker receipts (strategy polymarket_amm, fee 0)
under cross_market/data/paper_receipts; HALT.flag refuses (exit 3). The
roadmap's "20-40% APY" is unmeasured and the module says so in its output:
pool size and competitor liquidity are inputs, not measurements. Tests:
master MODULE 22 (4 tests, no network). Daemons and tonight's tasks
untouched.

## Related

- [[digests_register|Digests register]]
