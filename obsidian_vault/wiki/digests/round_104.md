---
type: Digest
title: Round 104 digest
description: 'Round 104 (2026-09-06, corrected in 104b): TWO NEW COMPILED PAGES ON
  DESK 1, AND FOUR REAL DEFECTS FOUND IN OUR OWN TOOLING WHILE BUILDING THEM'
tags:
- digest
- work-chain
- round-104
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-104-complete
  title: AGENTS_ARCHIVE.md - Round 104 complete
  author: claude-code/fable-5.1
dev:
  round: 104
  date: 2026-09-06, corrected in 104b
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 104 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 104 digest

> 2026-09-06, corrected in 104b · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

TWO NEW COMPILED PAGES ON DESK 1, AND

FOUR REAL DEFECTS FOUND IN OUR OWN TOOLING WHILE BUILDING THEM. Deliverables 1-2 (the wall-clock
test fix and the exporter --stop) landed earlier in the round at 25 green exporter tests.
B2: knowledge/ingest/funding.py compiles wiki/regimes/hl_funding_regime.md from
basis_realised_windows, read-only. B1/F3: knowledge/ingest/cascade_replay.py compiles
wiki/experiments/whale_sweeper_cascade_replay_verdict.md from the engine's own --json
artifact and RE-GRADES it against the pre-registration rather than copying the engine's
verdict string; the two agree (INSUFFICIENT), and a disagreement would be recorded as a
finding in both voices. Both pages pin their bars as dev.parameters (settings.py by regex,
the registration meta.json by json_path), so editing an acceptance bar after the data was
seen is a lint C1 error. Tests all green offline: module 23 = 119 (+17), HyperLiquid 1,100,
Sports 223, Polymarket 237, Tax 546, cross-market 211, Desk 4 151 (+6 skipped) = 2,587.
Desk 4 leaves 4 modules uncollectable for a missing `fastapi` - PRE-EXISTING, unrelated to
this round and unchanged by it. Vault 420 pages + constitution, lint CLEAN. No daemon was
touched and no desk module edited.

104b (same round, second commit): THE FUNDING PAGE OVERSTATED ITS OWN SECOND POPULATION
AND I CAUGHT IT BY READING THE HARVESTER INSTEAD OF ASSUMING IT. 104a labelled the 473
windows clearing the gross bar 'entry-qualifying ... the ones the harvester's own entry rule
would have taken'. That is false. `scan_basis_opportunities` requires the gross bar AND the
net bar AND a spread ceiling, with check_spreads=True by default, and its own docstring says
'a basis trade whose cost has not been measured has not been evaluated' - so the live rule
REFUSES an unmeasured-spread trade, while the measurement grid opens a window on a stride
regardless. The 28.05% median is therefore an UPPER BOUND on a superset, not a backtest, and
the page now says so in a call-out. Renamed the key entry_qualifying -> gross_bar_only, with
a compatibility reader so history rows written before the rename still render rather than
KeyError-ing an existing page. Two more facts settled by reading the writer rather than
guessing: realised_apr IS annualised (accrual_rate_hours/observed * HOURS_PER_YEAR * 100), so
it compares directly against the bars; and the 3,839 NULL rows are NULL because coverage fell
under MEASUREMENT_MIN_COVERAGE = 0.60, an observability exclusion, not an outcome one - so the
distribution is not survivorship-biased in the way I had flagged as an open question.
Module 23 = 120. The net bar is NOT decorative, as 104a's homework note wrongly implied: it is
enforced live and merely unevaluable retrospectively. HOMEWORK.md corrected.

## Related

- [[digests_register|Digests register]]
