---
type: Digest
title: Round 52 digest
description: 'Round 52: STAMPED POLYMARKET DROPS, MULTI-TAG WATCHER, LEAK FIX, VAULT
  TRACKED'
tags:
- digest
- work-chain
- round-52
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-52-complete
  title: AGENTS_ARCHIVE.md - Round 52 complete
  author: claude-code/fable-5.1
dev:
  round: 52
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 52 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 52 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

STAMPED POLYMARKET DROPS, MULTI-TAG WATCHER, LEAK FIX, VAULT

TRACKED. `--watch` now writes a stamped copy (`polymarket_<UTC stamp>Z.json`)
beside the canonical file on every price change and prunes copies older than
192h by the stamp in their name, so Item 18 gets its probability series.
`--tags sports,crypto,fed-rates` fetches several Gamma tags in one watcher
(non-sports by verified `tag_slug`, labelled by slug, narrowed by `--keywords`).
The unclosed read-only connection in find_market_probability is closed on the
no-table path. open_dashboard.bat (Antigravity's root launcher) and the five
new whale dossiers are tracked. 5 new tests. No collector code; no restart.

## Related

- [[digests_register|Digests register]]
