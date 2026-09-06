---
type: Digest
title: Round 99 digest
description: 'Round 99 (2026-09-05): KNOWLEDGE - CRM SEEDS (B8) + DIRECTIVES RATIFIED
  (B4, Ruling 98-1)'
tags:
- digest
- work-chain
- round-99
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-99-complete
  title: AGENTS.md - Round 99 complete
  author: claude-code/fable-5.1
dev:
  round: 99
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 99 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 99 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

KNOWLEDGE - CRM SEEDS (B8) + DIRECTIVES RATIFIED (B4,

Ruling 98-1). NEW knowledge/ingest/entities.py: crm/titans, crm/whales (top N by
account_value), crm/sharps (sharp_traders + tracked_wallets), crm/books (pinnacle as
the sharp reference, one page per retail_book with per sport/market-type evidence from
edge_opportunities); all SQLite opened file:...?mode=ro. THE INVARIANT: the `## Judgement`
section, `verified`, `stale_after` and a status promoted past draft are never
overwritten on re-ingest; evidence rows append (dedup by scan time, newest 50). TITAN
DEFINITION CORRECTED: the identity cache has 1,685 entries (the Round 95 audit printed
the first eight keys and called them eight pairs), every one a whale EOA by
construction, and none of their proxies appears in the Polymarket trader tables. A
titan therefore requires presence on BOTH venues (proxy or EOA in sharp_traders /
tracked_wallets, or a sharp's resolved EOA in whale_wallets): 0 today, which
agrees with the dashboard's 0 institutional actors and the empty cross_market_titans
table. NEW knowledge/ratify.py records a ratification (verified + status + dev:
ratified_by, register rebuilt, one Ratify log bullet, idempotent); ingest.rulings titles
are now the whole cleaned sentence; all 27 extracted pages re-titled and ratified under
98-1. Also: lint --fix-safe rebuilds index.md (98-5); HL experiments dev:item 14 with
related_items [8]; sixth register crm_register linked from every Desk. REAL VAULT:
370 pages + constitution (100 whales, 79 sharps, 4 books, 0 titans), lint
CLEAN. Tests: module 23 = 82; master 23 modules 1,018; total 2,657, all green offline.
Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
