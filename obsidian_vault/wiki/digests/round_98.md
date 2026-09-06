---
type: Digest
title: Round 98 digest
description: 'Round 98 (2026-09-05): KNOWLEDGE - COMPILE WHAT EXISTS (backlog B3,
  B4, B6, B7, B9; Antigravity''s Round 97/97b rulings applied)'
tags:
- digest
- work-chain
- round-98
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:14:48Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-98-complete
  title: AGENTS.md - Round 98 complete
  author: claude-code/fable-5.1
dev:
  round: 98
  date: '2026-09-05'
  kind: round_digest
---
# Round 98 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

KNOWLEDGE - COMPILE WHAT EXISTS (backlog B3, B4, B6, B7,

B9; Antigravity's Round 97/97b rulings applied). B3: ingest.experiments now reads
HyperLiquid/HL_Monarch/data/experiments/*.meta.json too - registrations (acceptance_bar
and other numeric blocks as json_path dev:parameters; the control as dev:requires_files)
and archived controls (result numbers guarded, so overwriting the N=12 baseline is a C1
finding). B4: NEW ingest/rulings.py extracts every distinct Directive/Ratification/Ruling
N-N from AGENTS.md (27 pages, status draft, dev:citations with section+line+sentence
window, dev:asserts pins the citation) and maintains rulings_register. B6: NEW
knowledge/computations.py files the two dashboard shell twins and the knowledge CLIs as
OKF Attested Computation pages (runtime, computation, executor.receipt, attester;
declarative per R95-C). B7: committed knowledge/calendars/fomc_2026.yaml (Sep 16 18:00Z,
Oct 28 18:00Z, Dec 9 19:00Z after the clock change, SEP flags) and tax_2026.yaml (Q3 due
2026-09-15, Q4 due 2027-01-15); NEW ingest/calendar.py -> Event pages with T-2..T+5
dev:window (FOMC) or stale_after = due (tax); clob ingest now ENRICHES a calendar Event
(keeps window/sep/meeting). B9: NEW ingest/markets.py -> 97 Market pages from the
rules tokens, Experiment dev:tokens and the newest macro drop's FED-RATES family (identity
only, no prices); lint --fix-safe now deprecates a Market whose token left the drops
(ruling A5). NEW knowledge/registers.py: five machine-maintained register pages, all
linked from every Desk page (seed --force). Regime page carries latest_verdict +
regime_consensus_3 (ruling A3). Desk parameters for C3 (ruling A6): confidence_floor
0.99, fee_rate 0.0 x2 (after_tax_edge_hurdle is a method, not a constant - no parameter).
REAL VAULT: 184 pages + constitution, lint CLEAN. Tests: module 23 = 75; master 23
modules 1,011; total 1,093 + 1,011 + 546 = 2,650, all green offline. Daemons and tonight's
tasks untouched.

## Related

- [[digests_register|Digests register]]
