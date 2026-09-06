---
type: Ruling
title: 'Ruling 45-3: named sample_orderbooks() / _spot_universe_cache; the real names
  are _sample_pass / _spot_universe_cached, an…'
description: '- Ruling 45-3 named `sample_orderbooks()` / `_spot_universe_cache`;
  the real names are `_sample_pass` / `_spot_universe_cached`, and the cold-start
  path is already pinned by `test_the_spot_universe_is_cached_refreshed_and_never_
  guessed` (failed lookup -> zero candidates, retry, stale copy survives)'
tags:
- ruling
- ruling
- round-45
- extracted
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:10Z'
status: stable
stale_after: '2027-03-05T00:28:46Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: AGENTS.md · Round 45 findings
  author: human:operator
dev:
  round: 45
  ruling_id: R45-3
  kind: ruling
  citations:
  - section: Round 45 findings
    line: 2036
    excerpt: …- Ruling 45-3 named `sample_orderbooks()` / `_spot_universe_cache`;
      the real names are `_sample_pass` / `_spot_universe_cached`, and the cold-start
      path is already pinned by `test_the_spot_universe_is_cached_refreshed_and_never_
      guessed` (failed lookup -> zero candidates, retry, stale copy survives).
  asserts:
  - file: AGENTS.md
    pattern: Ruling\s+45-3\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Ruling 45-3

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **Round 45 findings** (line 2036): …- Ruling 45-3 named `sample_orderbooks()` / `_spot_universe_cache`; the real names are `_sample_pass` / `_spot_universe_cached`, and the cold-start path is already pinned by `test_the_spot_universe_is_cached_refreshed_and_never_ guessed` (failed lookup -> zero candidates, retry, stale copy survives).

## Related

- [[rulings_register|Rulings register]]
