---
type: Digest
title: Round 47 digest
description: 'Round 47: STRUCTURAL DEX FAIL-CLOSED, HOURLY DRIFT DETECTOR, ONE CANDIDATE
  SLOT PER UNDERLYING'
tags:
- digest
- work-chain
- round-47
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-47-complete
  title: AGENTS.md - Round 47 complete
  author: claude-code/fable-5.1
dev:
  round: 47
  date: null
  kind: round_digest
---
# Round 47 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

STRUCTURAL DEX FAIL-CLOSED, HOURLY DRIFT DETECTOR, ONE

CANDIDATE SLOT PER UNDERLYING. `CRYPTO_DEXES = {main, para}`; a perp on any dex
in neither CRYPTO_DEXES nor TRADFI_DEXES is refused as unclassified before
anyone has heard of the dex. The hourly cycle reads perpDexs and WARNS on any
name no settings set knows. `top_funding_candidates` keeps one slot per
`perp_base_symbol` (best-ranked listing wins) and skips bases already held.
hyna joins the deliberately-refused list so the detector stays quiet. 1 new
test, 2 extended.

## Related

- [[digests_register|Digests register]]
