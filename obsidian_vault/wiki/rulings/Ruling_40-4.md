---
type: Ruling
title: 'Ruling 40-4: Decimals bug . spot_sz_decimals looked up the PERP base name
  in the spot table, so UBTC/UFART/UANSEM hedges a…'
description: '- **Decimals bug (Ruling 40-4).** `spot_sz_decimals` looked up the PERP
  base name in the spot table, so UBTC/UFART/UANSEM hedges all reported None and `matched_leg_size`
  sized off the perp leg alone.…'
tags:
- ruling
- ruling
- round-40
- extracted
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:46Z'
status: stable
stale_after: '2027-03-05T00:28:46Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: AGENTS.md · Round 40 findings
  author: human:operator
dev:
  round: 40
  ruling_id: R40-4
  kind: ruling
  citations:
  - section: Round 40 findings
    line: 2101
    excerpt: …- **Decimals bug (Ruling 40-4).** `spot_sz_decimals` looked up the PERP
      base name in the spot table, so UBTC/UFART/UANSEM hedges all reported None and
      `matched_leg_size` sized off the perp leg alone.…
  asserts:
  - file: AGENTS.md
    pattern: Ruling\s+40-4\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Ruling 40-4

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **Round 40 findings** (line 2101): …- **Decimals bug (Ruling 40-4).** `spot_sz_decimals` looked up the PERP base name in the spot table, so UBTC/UFART/UANSEM hedges all reported None and `matched_leg_size` sized off the perp leg alone.…

## Related

- [[rulings_register|Rulings register]]
