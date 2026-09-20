---
type: Digest
title: Round 110 digest
description: 'Round 110 (2026-09-06): THE DIGESTS ARE NOW GUARDED, REGISTERED AND
  HONEST ABOUT WHAT THEY DROP'
tags:
- digest
- work-chain
- round-110
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-110-complete
  title: AGENTS_ARCHIVE.md - Round 110 complete
  author: claude-code/fable-5.1
dev:
  round: 110
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 110 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 110 digest

> 2026-09-06 · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE DIGESTS ARE NOW GUARDED, REGISTERED AND HONEST ABOUT

WHAT THEY DROP. R109-1.F: `Digest` is a registers.SPECS type, so seed writes an EMPTY digests
register from the first run and every desk can link it - fixing the CAUSE of the 27 test
failures Round 109 worked around rather than the symptom. That exposed a real conflict the
directive did not anticipate: seed and the digests adapter were BOTH building that page, with
different content, silently overwriting each other every run. There is now one writer.
R109-1.E: every digest pins `^Round <N> complete` in AGENTS.md with dev.asserts, so renaming
or deleting a round heading trips C1 on the page that quotes it instead of leaving 210 KB of
prose pointing at a section that is gone. R109-1.C: MAX_BODY_LINES 120 -> 250, and a clipped
entry now SAYS it was clipped and warns at compile time. Tests: knowledge 212 (+10), all green
offline. Vault 488 pages, lint CLEAN. NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
