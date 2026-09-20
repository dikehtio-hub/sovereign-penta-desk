---
type: Digest
title: Round 100 digest
description: 'Round 100 (2026-09-05): KNOWLEDGE PHASE 3 - JOURNAL + CALIBRATION LEDGER
  (B10), TYPED RELATIONS (B11, lint L6), STALENESS POLICY (B14, lint L7), UNIVERSAL
  CARRY-OVER (Ruling 99-2)'
tags:
- digest
- work-chain
- round-100
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-100-complete
  title: AGENTS_ARCHIVE.md - Round 100 complete
  author: claude-code/fable-5.1
dev:
  round: 100
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 100 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 100 digest

> 2026-09-05 · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

KNOWLEDGE PHASE 3 - JOURNAL + CALIBRATION LEDGER (B10),

TYPED RELATIONS (B11, lint L6), STALENESS POLICY (B14, lint L7), UNIVERSAL CARRY-OVER
(Ruling 99-2). NEW knowledge/journal.py: journal/YYYY-MM-DD.md on receipts or --create;
Plan and Open are human and preserved across re-runs; Executions come from the CSV
paper receipts (Tax Reserve Agent writer columns; strategy from notes or filename);
Debrief checks the day's paper notional against the quant lab's $3,500 daily killswitch
(a guarded dev:parameter) and reports the after-tax hurdle as UNCHECKED because the
receipt writer records no edge - the honest state, written on the page. Calibration
ledger: --predict records {event, field, op, value, p, at, by human:operator} BEFORE an
event; --score resolves against the Event page's dev:payload (written by ingest.clob
after the print), Brier = (p - outcome)^2, and rebuilds wiki/concepts/calibration.md
(count, mean Brier vs 0.25, reliability by p-bin). Predictions are never edited. Seventh
register journal_register, linked from every Desk. LINT L6: dev:relations with
supersedes (exists + deprecated, acyclic), contradicts (must carry resolved_by -> an
existing Ruling), measured_by (-> Experiment), enforced_in (-> repo file), depends_on.
LINT L7: Ruling 180 d / Concept 90 d must carry stale_after unless machine-maintained
(dev:register_for or dev:history) or deprecated; seeds and ingest.rulings stamp it;
Market is policed by C2, Reaction Profile/Event/Journal never stale. dev:tests_run: 0 on
registrations, the running verdict count per tier/scope on verdicts. carry_human_fields
now in experiments, computations, calendar, markets, clob Event, lead_lag Regime,
rulings, entities, journal (tested end to end with a forced rewrite of four types).
REAL VAULT: 375 pages + constitution, lint CLEAN (first quiet-day journal written for
2026-09-05). Tests: module 23 = 91; master 23 modules 1,027; total 2,666, all green
offline. Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
