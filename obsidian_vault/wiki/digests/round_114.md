---
type: Digest
title: Round 114 digest
description: 'Round 114 (2026-09-06): THE REOPENING QUESTION WAS ASKED OF THE RIGHT
  POPULATION AND THE ANSWER IS INSUFFICIENT; THE DRILL''S ENTRY POINT IS UNDER VERSION
  CONTROL; THE PRE-FLIGHT CHECKS THE CLOCK'
tags:
- digest
- work-chain
- round-114
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-114-complete
  title: AGENTS_ARCHIVE.md - Round 114 complete
  author: claude-code/fable-5.1
dev:
  round: 114
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 114 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 114 digest

> 2026-09-06 · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE REOPENING QUESTION WAS ASKED OF THE RIGHT POPULATION AND THE

ANSWER IS INSUFFICIENT; THE DRILL'S ENTRY POINT IS UNDER VERSION CONTROL; THE PRE-FLIGHT CHECKS THE
CLOCK. D2 (Ruling R113-1.C option 3): a new engine runner, analytics/fade_rebenchmark.py, asks the
registration's question of the persisted excursions read-only and writes a JSON artifact next to the
registration (tracked); knowledge/ingest/fade_rebenchmark.py grades it INDEPENDENTLY against the
registration's own gates and its own rule text. THE POPULATION WAS THE FINDING: cascade_excursions
holds two treatment sources the desk's schema says must never be pooled; the fade's is trade_sweep
(the engine default, the registration's own 'sweeps accumulate'). Round 113 pooled both and read the
sample as ready. Over trade_sweep alone: 13,645 events on 46 coins, top coin ZEC 26.8%
against a 20% ceiling, 5.49-day span against 7 required - two gates fail, verdict INSUFFICIENT,
engine and page agree. Had the sample qualified, ratio_30m 0.7896 with P(>= 1.25) = 0.0000 at
20,000 draws would have been FAIL; stated for completeness, not a verdict. The registration now
carries a dated `population` block (bars unchanged); the progress mirror measures the named
population, gains the max_hhi gate, and no longer treats an INSUFFICIENT verdict as terminal - the
page says ACCUMULATING and names the blocking gates. D1 (R113-1.F): the batch file moved to
cross_market/scripts/ and is tracked; the task's action re-pointed with trigger, battery flags,
logon and instance policy verified identical before and after; the pre-flight FAILS if the batch is
ever untracked. D3: the pre-flight grew to 29 checks - W32Time service state (STOPPED on this
machine; +0.37 s measured against time.windows.com, so a HOMEWORK line, not an emergency), NTP offset,
books-dir writability by a removed probe, stamp path length (182 of 240), MultipleInstances policy,
orphan record-loop processes. Real run: 0 FAIL, 3 WARN. A DOUBLE WRITER was caught on the first real
run: the experiments ingest compiled the new *.verdict.json as a registration into the same page the
adapter writes; JSON carrying the engine's `_artifact` envelope is now skipped there. Tests: knowledge
302 (+16), HL 1,108 (+5). Lint CLEAN at 496 pages; idempotent across fade/experiments/digests/seed.
NO DAEMON RESTARTED; W32Time deliberately left as found.

## Related

- [[digests_register|Digests register]]
