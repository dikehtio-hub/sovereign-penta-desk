---
type: Digest
title: Round 105 digest
description: 'Round 105 (2026-09-06): ALL FOUR R104 RULINGS IMPLEMENTED, AND LINT
  L8 FOUND 86 BROKEN LINKS THE MOMENT IT WAS SWITCHED ON'
tags:
- digest
- work-chain
- round-105
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-105-complete
  title: AGENTS.md - Round 105 complete
  author: claude-code/fable-5.1
dev:
  round: 105
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 105 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 105 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

ALL FOUR R104 RULINGS IMPLEMENTED, AND LINT L8 FOUND 86

BROKEN LINKS THE MOMENT IT WAS SWITCHED ON. R104-4: lint L8 flags a dangling outbound
wikilink - the mirror of L3, which only ever caught the opposite failure. Links inside code
fences and code spans are excluded, so the constitution can document `[[wikilinks]]` without
tripping it. R104-2: cascade_replay.py now emits an `_artifact` envelope (written_at, writer,
rows_in_table, seed) and writes --out atomically; the ingest reads written_at from it and
falls back to the file mtime only for pre-Round-105 artifacts, SAYING WHICH on the page.
R104-3: the guard went into pages.write_page rather than the eight named adapters - 31 call
sites already funnel through it, so one guard covers every adapter present and future. A page
whose content has not moved is not rewritten and keeps the generated.at it earned; the log
line and the entities 'updated' count are now conditional on a real change too. VERIFIED BY
HASH: running every adapter twice over unchanged data changes ZERO files. B1: new
wiki/concepts/cascade_anatomy.md. Tests: module 23 = 137 (+17), HyperLiquid + cross-market
1,311, all green offline. Vault 423 pages + constitution, lint CLEAN. No daemon touched.

## Related

- [[digests_register|Digests register]]
