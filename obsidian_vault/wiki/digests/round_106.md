---
type: Digest
title: Round 106 digest
description: 'Round 106 (2026-09-06): THE ADAPTER LIFECYCLE INVARIANT ENFORCED, DESK
  1 SPREAD SAMPLING GATED ON THE ENTRY BAR, AND GIT PROVENANCE NOW CHECKED'
tags:
- digest
- work-chain
- round-106
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-106-complete
  title: AGENTS.md - Round 106 complete
  author: claude-code/fable-5.1
dev:
  round: 106
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 106 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 106 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE ADAPTER LIFECYCLE INVARIANT ENFORCED, DESK 1 SPREAD

SAMPLING GATED ON THE ENTRY BAR, AND GIT PROVENANCE NOW CHECKED. R105-2: titans are
re-admitted when they fall below the cap, and pages whose SOURCE ROW is gone (a pruned sharp)
are NAMED in report.unmaintained rather than silently frozen - an adapter that cannot rebuild
a page should say so, not pretend. Markets re-admit every token that already has a page, but
NOT the way the ruling sketched it: a naive union would have written a degraded duplicate,
because with no drop record compile_market falls back to a placeholder question AND a
token-derived slug, so an aged-out market would get a second page at a new path while the good
one was orphaned. Identity is recovered from the page's own dev block instead. R104-1: the
spread gate went into collectors/orderbook_sampler.py, NOT incremental_persistence.py as
directed - the latter is a RETROSPECTIVE grid over historical instants and cannot sample L2 for
a window that opened days ago; it only reads orderbook_snapshots. B19/B20: lint L5 now resolves
`git:<sha>` sources and dev.citations with `git cat-file`, SKIPPING (not passing) outside a
repository. Tests: knowledge 145 (+8), HyperLiquid + cross-market 1,314 (+3), all green
offline. Vault 423 pages, lint CLEAN, adapters idempotent by hash. NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
