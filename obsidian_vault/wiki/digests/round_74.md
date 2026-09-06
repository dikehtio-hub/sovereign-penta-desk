---
type: Digest
title: Round 74 digest
description: 'Round 74 (2026-09-05): ONE EXPORTER LOOP, TIER 2 PRE-REGISTERED'
tags:
- digest
- work-chain
- round-74
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-74-complete
  title: AGENTS.md - Round 74 complete
  author: claude-code/fable-5.1
dev:
  round: 74
  date: '2026-09-05'
  kind: round_digest
---
# Round 74 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

ONE EXPORTER LOOP, TIER 2 PRE-REGISTERED.

Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds
cross_market/data/cross_market_exporter.pid for --watch (pid_lock, mark word
"cross_market" so a Sports Desk exporter never passes as the holder), --status
(exit 0 running / 3 stopped; also prints the Item 18 state: last lead-lag run
from the Titans note, macro series readiness, ETA), --json, --pid-file.
start_cross_market_exporter.bat is guarded by --status like the watcher's
launcher, and start_all_ecosystem_sync.bat calls it behind `if errorlevel 3`
instead of opening a console loop - every loop the sync bat starts for the
arb desk is now detached and single-instance. Ruling 74-2: Tier 1 untouched;
Tier 2 pre-registered in cross_market/experiments/lead_lag_tier2.meta.json
(counts only, no subfamily correlation run) and enforced in code:
lead_lag --subfamily fed-rates|crypto reads the `sport` label the fetcher
stamped (drops carry no tag_slug), --latency-minutes 5 reports a peak inside
the poll interval as "contemporaneous repricing ... latency, not a lead".
4 new tests. Live 10:01Z: Arb exporter restarted through the guarded launcher - pythonw pid 35080 holds cross_market/data/cross_market_exporter.pid (the pre-lock loop 3556 was terminated first); a second launcher run printed "already running - kept"; --status: RUNNING, last run never, macro series NOT READY (span 8.3h, points 100), ETA 2026-09-06T01:39:49Z. Watcher pid 49812 untouched.

Round 73 REVIEW (end of 2026-09-05): MAIDEN RUN READS THE MACRO FAMILY, LOOPS
DETACHED. Research showed the forced maiden run was already "sufficient" -
but it correlated every drop (1,084 markets incl. 400 NFL questions) while
the gate counts macro stamps. lead_lag.load_drop_records/run/--family now
filter by tag family and LeadLagRefresher passes family="macro"; the macro-
only preview: 413 markets, 384 shifts, best lag -33 min, corr -0.195 -> "no
measurable lead-lag" (|corr| < 0.2). That is the likely honest verdict
tomorrow. Resilience: cross_market/console_log.tee_stdout + --log-file on
the watcher and the Arb exporter; start_polymarket_watcher.bat and
start_cross_market_exporter.bat launch both DETACHED (pythonw,
Start-Process) with logs under data/ (ignored); the sync bat calls the
watcher launcher. Both loops were restarted detached tonight, so the
01:39:49Z opening is unattended. 3 new tests. Live 09:19Z: watcher pythonw pid 49812 (lock 49812, stamp 09:18:49Z, 12 min after the last console stamp - series continuous), Arb exporter pythonw pid 3556 (log: lead-lag gated NOT READY), maiden regression due ~2026-09-06T01:39:49Z on macro drops.

## Related

- [[digests_register|Digests register]]
