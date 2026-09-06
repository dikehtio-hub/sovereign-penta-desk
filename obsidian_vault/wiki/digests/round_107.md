---
type: Digest
title: Round 107 digest
description: 'Round 107 (2026-09-06): THE OPERATOR CAN NOW ASK THE VAULT A QUESTION'
tags:
- digest
- work-chain
- round-107
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-107-complete
  title: AGENTS.md - Round 107 complete
  author: claude-code/fable-5.1
dev:
  round: 107
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 107 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 107 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE OPERATOR CAN NOW ASK THE VAULT A QUESTION.

knowledge/query.py answers the two queries the constitution pre-baked in s.Query:
`--drill-card <event>` and `--regime BTC`. The drill card is read at T-2 with a clock running,
and every design choice follows from that: it NEVER WRITES (not a log bullet, not a usage
counter - inside its own window the pages it describes are frozen), it fits in under 60 lines
with a test asserting it, it COMPUTES the countdown rather than restating the release instant,
and it assembles from compiled PAGES rather than going back to the raw JSON. A missing Event
page refuses with the list of known events: a blank card two minutes before a print is worse
than no card. R106-1.E: `rank_at_seed` is frozen and a new `rank_now` carries the live figure -
Round 106 made whale pages refreshable, which put that field in the same trap `first_seen`
fell into on markets. R95-E: the three volatile exporter-written dashboards are untracked;
`git status` is now pristine between rounds. Tests: knowledge 156 (+11), HyperLiquid +
cross-market 1,314, all green offline. Vault 423 pages, lint CLEAN, adapters idempotent by
hash. NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
