---
type: Digest
title: Round 37 digest
description: 'Round 37: STALLED-SERVICE DETECTION, CANDIDATE SPREAD SAMPLING & REPO
  UNTRACKING'
tags:
- digest
- work-chain
- round-37
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-37-complete
  title: AGENTS_ARCHIVE.md - Round 37 complete
  author: claude-code/fable-5.1
dev:
  round: 37
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 37 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 37 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

STALLED-SERVICE DETECTION, CANDIDATE SPREAD SAMPLING & REPO

UNTRACKING. The dashboard header has a fifth state - a live service that has
written nothing for 45s shows STALLED in red; order book sampling now runs
held positions > top-5 positive-funding candidates > rotated > core, so a
spread exists before an entry instant; five more runtime/cache/backup files
are untracked and ignored. A latent Round 34 flake (same-second drop filenames
overwriting) is fixed. 5 new tests.

## Related

- [[digests_register|Digests register]]
