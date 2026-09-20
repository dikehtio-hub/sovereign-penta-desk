---
type: Digest
title: Round 121 digest
description: 'Round 121 (2026-09-06 23:55 EDT, operator: "proceed" on Antigravity''s
  Round 120 rulings + the

  operator''s own five decisions): EVERYTHING AUTHORISED IS DONE; THE COLLECTOR HARDENING
  IS STAGED ON A BRANCH, NOT DEPLOYED'
tags:
- digest
- work-chain
- round-121
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-121-complete
  title: AGENTS_ARCHIVE.md - Round 121 complete
  author: claude-code/fable-5.1
dev:
  round: 121
  date: '2026-09-06 23:55 EDT, operator: "proceed" on Antigravity''s Round 120 rulings
    + the

    operator''s own five decisions'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 121 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 121 digest

> 2026-09-06 23:55 EDT, operator: "proceed" on Antigravity's Round 120 rulings + the
operator's own five decisions · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

EVERYTHING AUTHORISED IS DONE; THE COLLECTOR HARDENING IS STAGED ON A BRANCH,

NOT DEPLOYED. Operator decisions executed and verified field-by-field: Monarch_FOMC_Drill's two battery flags
cleared (nothing else on the task changed); the four stale one-off tasks deleted (only Monarch_FOMC_Drill
remains). The four permissioned items: (1) the pre-flight's --online now judges the four daemons' STREAMS -
newest asset_snapshots row, newest watcher drop, exporter log write - against 15/15/5-minute limits (33
checks, 0 FAIL, 1 WARN: W32Time); (2) knowledge.drills.event_json writes ./event.json from one number
(--bps), refuses to overwrite without --force; (3) knowledge/data_gaps.json -> knowledge.ingest.data_gaps ->
wiki/events/data_gap_2026-09-06_hl_asset_snapshots.md (9.32 h) + lint L12 (an Experiment whose measured
span overlaps a gap it does not list under dev.data_gaps) + the fade adapter acknowledging gaps itself; (4)
basis windows audited: none opened inside the gap, 1,764 overlapping ones carry coverage 0.61-0.99 - the
schema already marks the hole. FINDING attached to Round 120: lead_lag takes BTC prices from asset_snapshots,
so the Tier 2/2b window held a 9.3 h price hole; the registration's readiness bar covers tagged stamps only;
readings stand with the caveat on the gap page. R119-1.B: hardening committed on feat/collector-hardening
(worktree, nothing checked out in the live tree): periodic universe re-sync (every 60 polls, forced after a
skip); insert_snapshots row-by-row fallback naming offenders; supervisor watchdog that RESTARTS on a stale
stream (>15 min, once per hour) and only WARNS on coverage decay (DEVIATION: coverage stays low for 24 h
after any gap - a restart on it would loop); 8 tests, HL suite 1,118 green on the branch. R120-1.C: the four
lead-lag artifacts moved to cross_market/experiments/ and re-ingested at their ORIGINAL instants; pages and
history rows unchanged in number; lead_lag --json now carries the R102-2 envelope. Three adapter defects
found by the idempotence check and fixed: tests_run counted its own page (1 -> 2 on re-ingest); a --force
recompile reset a registration's tests_run to 0 over a live value (two writers of one field - one owner
now, lead_lag_verdict_count); the lead-lag ingest logged even when nothing moved. Knowledge 385, lint CLEAN
507 pages, idempotent across lead_lag/experiments/data_gaps/seed. NO DAEMON RESTARTED this round.

## Related

- [[digests_register|Digests register]]
