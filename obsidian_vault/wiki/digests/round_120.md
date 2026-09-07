---
type: Digest
title: Round 120 digest
description: 'Round 120 (2026-09-06 22:30 EDT, operator: "lets do what we can"): THE
  TIER 2b GATE CLOSED AND THE PRE-REGISTERED TIER 2 / TIER 2b LEAD-LAG RUNS WERE EXECUTED,
  AS REGISTERED, NO --force'
tags:
- digest
- work-chain
- round-120
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T02:32:58Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-120-complete
  title: AGENTS.md - Round 120 complete
  author: claude-code/fable-5.1
dev:
  round: 120
  date: '2026-09-06 22:30 EDT, operator: "lets do what we can"'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 120 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 120 digest

> 2026-09-06 22:30 EDT, operator: "lets do what we can" · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE TIER 2b GATE CLOSED AND THE

PRE-REGISTERED TIER 2 / TIER 2b LEAD-LAG RUNS WERE EXECUTED, AS REGISTERED, NO --force. The tagged macro
series cleared its bar at 22:25 EDT (286 stamps, 24.0 h, largest gap 5.1 min, 0 breaks; `lead_lag
--check-data` READY). All three preconditions in lead_lag_tier2b.meta.json held (Tier 1 verdict in
Cross_Market_Titans.md; watcher on the Round 76 code since 2026-09-05 22:20; tagged series ready). The
four registered commands ran with --json into cross_market/data/lead_lag_tier{2,2b}_{fed-rates,crypto}
_verdict.json and were ingested with knowledge.ingest.lead_lag --tier 2 / 2b. RESULTS: Tier 2 crypto: no-lead; Tier 2 fed-rates: no-lead; Tier 2b crypto: polymarket-leads; Tier 2b fed-rates: no-lead.
Per the registration's reading rule, Tier 2 and 2b are reported side by side and never resolved:
macro/crypto DISAGREES (Tier 2 no-lead at lag 38 min, corr -0.138, n 2,389; Tier 2b polymarket-leads at
lag 38 min, corr -0.325, n 910) - the dual-tagged markets (fetched under both crypto and fed-rates) carry
the signal; neither tier is 'the' answer, and the Tier 1 bar and verdict are untouched. fed-rates agrees
(no-lead both ways). Bars met on every subfamily (min_abs_corr 0.2, min_events 5, min_points 60). One 24 h
window, one coin, not independent of Tier 2 (registration caveat): a reading, not an edge. Vault 505
pages, lint CLEAN. NO DAEMON TOUCHED.

## Related

- [[digests_register|Digests register]]
