---
type: Digest
title: Round 39 digest
description: 'Round 39: SPOT LIQUIDITY GROUNDING & NET-APR CANDIDATE RANKING'
tags:
- digest
- work-chain
- round-39
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-39-complete
  title: AGENTS.md - Round 39 complete
  author: claude-code/fable-5.1
dev:
  round: 39
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 39 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 39 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

SPOT LIQUIDITY GROUNDING & NET-APR CANDIDATE RANKING. A

spot TOKEN is no longer a spot MARKET: `get_spot_universe` keeps only tokens
whose best spot pair turned over >= SPOT_MIN_DAY_VOLUME ($10k) in 24h, read
from spotMetaAndAssetCtxs (46 of 499 tokens live). TSLA/AVGO spot did $0 while
their HIP-3 perps traded tens of millions; COIN/NVDA have a token and no pair.
Sampler candidates with a spread on record rank on net APR. 5 new tests.

## Related

- [[digests_register|Digests register]]
