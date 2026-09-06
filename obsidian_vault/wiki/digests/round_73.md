---
type: Digest
title: Round 73 digest
description: 'Round 73: ITEM 18 MAIDEN RUN AUTOMATED BEHIND THE SENTINEL GATE'
tags:
- digest
- work-chain
- round-73
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-73-complete
  title: AGENTS.md - Round 73 complete
  author: claude-code/fable-5.1
dev:
  round: 73
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 73 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 73 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

ITEM 18 MAIDEN RUN AUTOMATED BEHIND THE SENTINEL GATE.

The Cross-Market Arb exporter's loop carries a LeadLagRefresher: every
cycle it re-reads data_readiness on the stamped drops; while NOT READY it
does nothing; when READY it runs lead_lag.run() for --lead-lag-coin (BTC)
once, writes the result into Cross_Market_Titans.md between
<!-- lead-lag-horizon --> markers as "## ⚡ Lead-Lag Predictive Horizon
(Item 18)" (after the sentinel card; user notes untouched), and then waits
--lead-lag-cooldown-hours (24) measured from the run-at comment INSIDE the
block, so a restarted exporter honours the same cooldown. Insufficient
results are rendered honestly and still count as a run. --no-lead-lag
disables it. Round 72 was verification only. 3 new tests. The 01:39:49Z
opening tomorrow now needs no operator - only a running sync bat.

## Related

- [[digests_register|Digests register]]
