---
type: Digest
title: Round 116 digest
description: 'Round 116 (2026-09-06, SELF-DIRECTED - the operator said "proceed on
  your own"; no Antigravity

  prompt): THE FOMC DRILL HAS BEEN REHEARSED LIVE, END TO END, INTO SCRATCH'
tags:
- digest
- work-chain
- round-116
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-116-complete
  title: AGENTS_ARCHIVE.md - Round 116 complete
  author: claude-code/fable-5.1
dev:
  round: 116
  date: '2026-09-06, SELF-DIRECTED - the operator said "proceed on your own"; no Antigravity

    prompt'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 116 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 116 digest

> 2026-09-06, SELF-DIRECTED - the operator said "proceed on your own"; no Antigravity
prompt · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE FOMC DRILL HAS BEEN REHEARSED LIVE, END TO END, INTO SCRATCH. New module

knowledge/drills/fomc_live_rehearsal.py: the pre-flight must show 0 FAIL; then latency_sniper.record_loop
stamps the three registered tokens against the REAL public CLOB books for --seconds into
cross_market/data/rehearsals/<stamp>/books (git-ignored); a SYNTHETIC event (fed_rate, change_bps 0,
source "REHEARSAL ... NOT a Federal Reserve statement") is written to scratch, anchored mid-recording;
survival_curve runs exactly as the drill card's step 2; knowledge.ingest.clob compiles the Reaction
Profiles, the Event page and the latency-decay concept into a scratch COPY of the vault, which is then
linted. The real vault, the real books directory and the repo-root event.json are hashed before and
after; a difference is a FAIL. Real 60 s run at 23:11Z: 60 polls, 180/180 stamps (100%), 0 fetch
failures, 0 rate limits, largest gap 1.001 s; three markets resolved from change_bps=0 (no change->YES;
hike 25->NO and hike 50+->NO deferred under Ruling R4 as neg_risk NO sides); 60-point series on the live
market; Tax Reserve Agent after-tax economics loaded; 3 profiles + event + concept compiled; nothing real
moved. Findings: (1) a bare urllib GET of the CLOB gets HTTP 403 - the recorder's browser-style
User-Agent (Round 87) is load-bearing and the rehearsal exercises it; (2) a token with an underscore
records fine and loads back as NOTHING (the stamp regex splits on "_") - now an explicit check, and
the fixture tokens were made realistic; (3) the latency-decay concept hard-coded its source as
obsidian_vault/wiki/profiles - now derived from the vault being written; (4) two lint rules are
meaningless on a relocated copy (L2 raw/index.md vault-relative paths; L9 on a git-ignored tree) and
are reported, not judged - the pages the drill produces are judged on every other rule and lint clean.
Also closed: Round 115 cross-check item 6 - only two registrations carry sample_requirements and the
mirror applies every filter both name. Tests: knowledge 318 (+15: 5 new, 10 inherited card tests).
Real vault lint CLEAN. NO DAEMON RESTARTED; operator decisions (W32Time, battery flags, collector,
Desk 4 packages) deliberately untouched.

## Related

- [[digests_register|Digests register]]
