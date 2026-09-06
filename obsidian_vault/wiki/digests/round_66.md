---
type: Digest
title: Round 66 digest
description: 'Round 66: STALE-PANEL FEED LIVENESS, --json, Sports_Desk.md SECTION'
tags:
- digest
- work-chain
- round-66
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-66-complete
  title: AGENTS.md - Round 66 complete
  author: claude-code/fable-5.1
dev:
  round: 66
  date: null
  kind: round_digest
---
# Round 66 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

STALE-PANEL FEED LIVENESS, --json, Sports_Desk.md SECTION.

scan_market_db measures the newest quote in the WHOLE measurements table
(newest_quote_at / newest_quote_age_seconds) and sets feed_warning when it
is older than 15 min or older than the lookback ("feed stale / ..."); the
panel header reads "[STALE] newest quote: X min ago | lookback: N min |
sharp moves: M | stale retail: K" and prints "[WARN] ..." beneath (CLI and
menu [t]). scan_to_dict + `monarch_shark --stale --json`. Sports_Desk.md
carries "## 🕒 Stale Quotes & Market Consensus Latency" from collect()
(display only; an empty feed says "No sharp moves detected in last 180m
(newest quote none)" under a feed warning). 3 new tests.

## Related

- [[digests_register|Digests register]]
