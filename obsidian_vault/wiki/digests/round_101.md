---
type: Digest
title: Round 101 digest
description: 'Round 101 (2026-09-05): KNOWLEDGE PHASE 4 - BASES VIEWS + TEMPLATES
  (B13), DASHBOARD SHELL TWINS + DESK BACKLINKS (F1), DOCSTRING THESES (B12), RECEIPT
  EDGE/HURDLE (Ruling 100-b) + Rulings 100-a/c/e/f'
tags:
- digest
- work-chain
- round-101
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-101-complete
  title: AGENTS.md - Round 101 complete
  author: claude-code/fable-5.1
dev:
  round: 101
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 101 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 101 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

KNOWLEDGE PHASE 4 - BASES VIEWS + TEMPLATES (B13),

DASHBOARD SHELL TWINS + DESK BACKLINKS (F1), DOCSTRING THESES (B12), RECEIPT EDGE/HURDLE
(Ruling 100-b) + Rulings 100-a/c/e/f. NEW knowledge/views.py: seven wiki/_views/*.base
(Obsidian Bases; filters file.inFolder, table views) and four wiki/_templates/*.md whose
frontmatter is OKF-valid before a placeholder is filled; `_` folders are tooling, skipped
by index and lint. NEW knowledge/ingest/theses.py: ALL-CAPS docstring sections of the desk
modules -> wiki/concepts/thesis_*.md (35 pages), every heading pinned with dev:asserts
so a silent deletion is a C1 finding; eighth register theses_register. F1: Sports_Desk,
cross_market, HL_Monarch (three notes), Polymarket_Monarch and Tax_Reserve_Agent exporters
now print a `Desk:` wikilink and a `Shell twin:` --once command; SOURCE-ONLY - the running
exporter (56412) does not reload and is unaffected until restarted; quant_trading_lab's
exporter is its own repo with a dirty tree and was not touched. Receipts:
log_execution_receipt(gross_edge=, after_tax_hurdle=) stamps `edge:`/`hurdle:` into notes;
latency_sniper.record_paper passes edge = event confidence and hurdle = the worst fill
breakeven (both probabilities, so edge >= hurdle IS the sniper's rule), falling back for
older writer doubles. Journal: --claim free-text predictions scored by hand (--score --event
E --outcome 0|1, scored_by human:operator); debrief reports Daily Paper Notional Turnover,
drawdown vs killswitch UNCHECKED (fills are not realised loss, 100-c), per-fill hurdle
PASS/FLAG/UNCHECKED. tests_run written back onto the registration PAGE per tier (100-e; the
raw meta file untouched). Ruling_98-1.md ratified under 98-1 and its page lists the 27
pages it ratified (## Effect in this wiki). REAL VAULT: 415 pages + constitution, lint
CLEAN. Tests: module 23 = 100; master 23 modules 1,036; total 2,675, all green
offline (exporter, sniper and receipt suites re-run). Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
