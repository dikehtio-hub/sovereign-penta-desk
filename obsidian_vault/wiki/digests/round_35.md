---
type: Digest
title: Round 35 digest
description: 'Round 35: SPREAD ALIGNMENT, L2 SPREAD SAMPLING & SUPERVISOR HARDENING'
tags:
- digest
- work-chain
- round-35
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-35-complete
  title: AGENTS_ARCHIVE.md - Round 35 complete
  author: claude-code/fable-5.1
dev:
  round: 35
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 35 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 35 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

SPREAD ALIGNMENT, L2 SPREAD SAMPLING & SUPERVISOR HARDENING.

Each spread leg is stored under its OWN signed handicap (Ruling 5.B) and the
cross-market sample now matches 7 of 7 questions; the collector that owns
maintenance samples top-of-book spreads for a bounded coin set into
`orderbook_snapshots` (Ruling 5.C), which joins the fail-closed set; the
supervisor holds the host awake (Ruling 5.A); a live PID counts as the service
only if its command line says "collector", and the dashboard's embedded
collector re-decides ownership every cycle. 21 new tests.

## Related

- [[digests_register|Digests register]]
