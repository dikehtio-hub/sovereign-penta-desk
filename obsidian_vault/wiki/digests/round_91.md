---
type: Digest
title: Round 91 digest
description: 'Round 91 (2026-09-05): RULING R6 - COMPETITOR Q MEASURED FROM RECORDED
  BOOKS'
tags:
- digest
- work-chain
- round-91
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-91-complete
  title: AGENTS_ARCHIVE.md - Round 91 complete
  author: claude-code/fable-5.1
dev:
  round: 91
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 91 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 91 digest

> 2026-09-05 · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

RULING R6 - COMPETITOR Q MEASURED FROM

RECORDED BOOKS. amm_rewards.book_q() scores every resting level of a
recorded CLOB stamp inside the programme window (per side, Q_min by the
band rule); replay_rewards() runs it over a stamps folder and adds the
share a hypothetical two-sided quote (--size at mid +/- --quote-offset)
would earn; the pool rate stays the ONE input (--pool, printed ASSUMED,
until Ruling R5 records it). CLI: amm_rewards --replay-books DIR --pool X.
FIRST MEASUREMENT (the Fed "no change in Sept 2026" market, one real stamp
at 16:59Z): mid 0.505, book Q bid 28,828 / ask 93,337 / Q_min 28,828 over 6
levels in the 3-cent window; a 100-share quote at +/-1 cent earns a 0.09%
share. Retail-sized quoting on a heavily-made market earns a rounding
error of the pool; the module says so rather than an APY. Tests: module 22
now 5 tests. Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
