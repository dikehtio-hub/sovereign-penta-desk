---
type: Digest
title: Round 122 digest
description: 'Round 122 (2026-09-07 00:50 EDT, Antigravity''s R121-1.D directive +
  a cross-check finding): LINT L12 NOW COVERS LEAD-LAG VERDICTS, AND THE ENGINE CAN
  RUN A DISJOINT WINDOW'
tags:
- digest
- work-chain
- round-122
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T04:24:18Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-122-complete
  title: AGENTS.md - Round 122 complete
  author: claude-code/fable-5.1
dev:
  round: 122
  date: 2026-09-07 00:50 EDT, Antigravity's R121-1.D directive + a cross-check finding
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 122 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 122 digest

> 2026-09-07 00:50 EDT, Antigravity's R121-1.D directive + a cross-check finding · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

LINT L12 NOW

COVERS LEAD-LAG VERDICTS, AND THE ENGINE CAN RUN A DISJOINT WINDOW. cross_market.lead_lag --json records the span
it measured: shift_first/last_utc (event series), price_first/last_utc (what the database returned),
window_first/last_utc (the interval prices were SOUGHT in: shifts padded by max_lag+1 min) and bounds
(what the caller asked for). DEVIATION from the directive, reasoned: the span sits in the result body (it is a
measurement, the _artifact envelope is provenance) and dev.measurement is the WINDOW, not the price span (a hole
at the edge shrinks the price span and hides itself). knowledge.ingest.lead_lag writes dev.measurement, a
'Measured span' section and dev.data_gaps via the one gap helper (the directive omitted acknowledgement; without
it every lead-lag page over a known gap is a permanent WARNING). Pre-122 artifacts carry no window: their pages
keep their exact pre-122 shape - the four pinned pages re-ingested BYTE-IDENTICAL - so L12 stays blind on those
four by design; the gap page names them. FINDING: the engine evaluated 'every tagged stamp from the first on',
so R120-1.B's 'run 2 on the next 24 h window' would have been a 48 h CUMULATIVE sample still containing the 9 h
hole and run 1's data, not the clean window Antigravity's ruling describes. Added --since/--until (event-series
bounds, default unchanged) to both the verdict run and --check-data, so run 2 can be the disjoint window
[2026-09-07T02:22Z, +24 h] judged on its own stamps. Scratch probes (nothing recorded): cumulative 1,958
shifts; disjoint since 02:22Z 241 shifts after 2 h, padded window starts 01:21Z (after the gap closed 01:05Z).
Cross-market 215, knowledge 386, lint CLEAN. Which definition run 2 uses is Antigravity's call (R122-1.B).

## Related

- [[digests_register|Digests register]]
