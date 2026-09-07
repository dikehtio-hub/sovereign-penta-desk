# Round 121 Handoff: every authorised item done; hardening staged on `feat/collector-hardening`; three adapter defects found and fixed

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-06 23:55 EDT (master commit in `git log -1`; branch commit `70bd232`)
**Subject**: Your Round 120 rulings (ANTIGRAVITY_PROMPT.md, two-writer protocol honoured) plus the operator's five decisions were executed. One deviation from R119-1.B item 3 (watchdog trigger) needs your ruling; three defects the idempotence check exposed are fixed; the 9 h price hole now has a page and is attached to Round 120's readings. Section 0 is the standing checklist.

---

## 0. THE STANDING CHECKLIST (authoritative as of 2026-09-06 23:55 EDT; mirrors HOMEWORK.md)

### Dated - the operator, in order
- [ ] **Any day before the 16th, ~3 min** - scheduler probe: `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1`. With the flags cleared it should now say PROBE OK on battery too.
- [ ] **Daily until the 16th, 10 s** - `python -m knowledge.drills.fomc_rehearsal --online` (33 checks: tokens resolve; four daemon streams advancing).
- [ ] **2026-09-13 or 14** - `python -m knowledge.drills.fomc_live_rehearsal`.
- [ ] **2026-09-15** - Q3 estimated tax: `python -m Tax_Reserve_Agent.main calendar`; verify the Round 30 health schedule exists.
- [ ] **2026-09-16 morning** - `fomc_rehearsal --online`, then `fomc_live_rehearsal`. **13:58** - T-2 card. **14:00** - read the statement, then `python -m knowledge.drills.event_json --bps <n>` (0 hold, 25 hike, -25 cut); then the survival curve and `knowledge.ingest.clob` per the card.

### Operator decisions - still open
- [ ] **Start W32Time**: `Start-Service W32Time; w32tm /resync` (elevated). The last pre-flight WARN.
- [ ] **Desk 4 packages**: `uvicorn` / `hyperliquid-python-sdk` - yes or no.
- [ ] **Deploy window for the collector hardening**: merge `feat/collector-hardening`, then `stop_collector.bat` + `start_collector.bat`, then verify with the snapshot-age one-liner. Not before you say so.
- [ ] **Send this handoff to Antigravity.**
- [x] ~~Battery flags~~ - CLEARED 23:14 EDT; only those two fields changed (before/after JSON compared).
- [x] ~~Stale one-off tasks~~ - the four deleted; `Monarch_FOMC_Drill` is the only Monarch task.

### Antigravity - open
- [ ] **Cross-check Round 121** (section 3).
- [ ] **R121-1.A** - ratify the watchdog deviation: RESTART on a stale stream (newest `asset_snapshots` row > 900 s while the child is alive, once per hour), WARN only on coverage decay. Reason in section 2.
- [ ] **R121-1.B** - ratify the `tests_run` single owner (`lead_lag_verdict_count`) and the self-exclusion fix; note the counters were 2 (inflated) on all four verdict pages before it.
- [ ] **R121-1.C** - acknowledge the caveat now attached to Round 120: the Tier 2/2b BTC series had a 9.3 h hole (asset_snapshots). Readings stand; R120-1.B's next two windows will not.
- [ ] **R121-1.D** - the lint L12 definition (measured span from `dev.measurement.first/last_event_utc`; lead-lag verdict pages carry no span, so L12 cannot see them - the gap page names them by hand). Direct whether `lead_lag --json` should record the price-series span so L12 can.

### Engineering queue
- [ ] Nothing unblocked. The branch waits for the deploy window; L12 for lead-lag waits for R121-1.D.
- [ ] Watching: fade window gate (delayed by the gap); whale share gate 20.08%; next tagged 24 h window for R120-1.B run 2 of 3.

### Resolved this round
- [x] Battery flags cleared; stale tasks deleted (operator's word).
- [x] Pre-flight `--online` judges the four daemons' STREAMS (33 checks; 0 FAIL, 1 WARN).
- [x] `knowledge.drills.event_json` (one number in, a correct file out, no overwrite without `--force`).
- [x] Data-gap page + lint L12 + fade adapter acknowledgement; basis windows audited.
- [x] Hardening staged on `feat/collector-hardening` (commit `70bd232`; 8 tests; HL suite 1,118 on the branch).
- [x] Lead-lag artifacts relocated (R120-1.C) with pinned instants; envelope added to `lead_lag --json`.

### Standing rules
- Laptop awake while a 24 h series accumulates (the next tagged window is accumulating now, for R120-1.B); clean shutdown only; never kill daemons by hand; after any stop script, verify the old PIDs are gone; never seed the live tax ledger; `DEV/HALT.flag` is the kill switch.
- Daemons: watcher 17688, exporter 62760, supervisor 24504, collector 60756. None restarted this round.

---

## 1. What was delivered

**Operator decisions (verified before/after)**
- `Monarch_FOMC_Drill`: `DisallowStartIfOnBatteries` and `StopIfGoingOnBatteries` -> False. Trigger, action, logon, instance policy, enabled, wake: unchanged (JSON compared field by field).
- `Monarch_Maiden_Protocol_A/B/C`, `Monarch_Watcher_Restart`: unregistered. Remaining Monarch task: the drill only.

**The four permissioned items (master)**
1. **Stream health in the pre-flight** (`--online`): collector = newest `asset_snapshots` row (limit 15 min), watcher = newest drop under `Sports_Desk/data/polymarket_drops` (15 min), exporter = `cross_market_exporter.log` mtime (5 min). An unreadable stream is a FAIL. Live: all three PASS; 33 checks, 0 FAIL, 1 WARN (W32Time).
2. **`knowledge.drills.event_json --bps N`**: writes `./event.json` with kind, source, confidence 0.995 and `observed_at` fixed; refuses to overwrite without `--force`; prints the file. Never fetches, never decides the number.
3. **Data gaps**: `knowledge/data_gaps.json` (tracked) -> `knowledge.ingest.data_gaps` -> `wiki/events/data_gap_2026-09-06_hl_asset_snapshots.md` (9.32 h, cause, streams, affected evaluations). **Lint L12** warns when an Experiment's `dev.measurement.first/last_event_utc` span overlaps a gap it does not list under `dev.data_gaps`; the fade adapter now computes and writes that list. On the real vault L12 fires nowhere: the fade artifact's rows end 15:43Z, three minutes before the gap; the cascade verdict page carries no span.
4. **Basis windows**: none opened inside the gap; 1,764 overlapping windows carry `coverage` 0.61-0.99 (avg 0.74). Nothing is measured from stale prices - the schema marks the hole. No fix needed; recorded on the gap page.

**R119-1.B - hardening, staged on `feat/collector-hardening` (worktree; the live tree never changed)**
- `_sync_universe_metadata` every 60 context polls (~10 min) and at once after any pass skipped rows for a coin unknown to `assets`.
- `insert_snapshots` returns `{written, skipped}`; on `IntegrityError` falls back to row-by-row, skips offenders, logs them by name.
- Supervisor watchdog on the 15-min report cadence: **restart** (terminate the child; the run loop relaunches and counts it) when the newest snapshot is older than 900 s while the child is alive, at most once per hour; coverage below 60% or a drop over 5 pts is **warn only**. `measure_snapshot_age()` added.
- 8 tests; HL suite **1,118 passed** on the branch. Commit `70bd232`. **Not merged, not deployed.**

**R120-1.C - relocation**: the four `lead_lag_tier{2,2b}_*_verdict.json` moved to `cross_market/experiments/` (tracked; the experiments ingest skips them - no `experiment` key). Re-ingested at the ORIGINAL instants (`--at 2026-09-07T02:30:18/23/29/34Z`): same four page stems, regime history still 5 rows, `sources[].resource` updated. `cross_market.lead_lag --json` now writes the R102-2 `_artifact` envelope for every future run.

**Telemetry**: knowledge **385 passed**; cross-market 211; HL 1,118 on the branch (master HL unchanged). Real vault **507 pages, lint CLEAN**; idempotent across `lead_lag` (pinned) / `experiments --force` / `data_gaps` / `seed`. No daemon restarted.

**Timing**: clock read 03:14:27Z; quoted 60 (50-75); master commit fc021f6 at 03:46Z = **32 min** (under the band; the idempotence loop cost less than budgeted).

---

## 2. Deviations and findings

### (a) Watchdog trigger (R121-1.A)
R119-1.B item 3 said alert/restart when `coverage_pct` drops > 5 pts or < 60% with `restarts == 0`. `coverage_pct` is measured over the last 24 h: after today's gap it read 62% while the restarted collector was writing 442 rows every 10 s, and it will sit under 60% for most of tomorrow. A restart on that number would have restarted a healthy collector every cooldown. The branch restarts on the direct signal (newest snapshot age) and logs coverage decay as a warning. If you want the coverage trigger anyway, it is one line in `watchdog_decision`.

### (b) Three adapter defects, all found by hashing the vault twice
1. `dev.tests_run` on a lead-lag registration had two writers: `knowledge.ingest.lead_lag` (count of verdict pages -> 2) and `knowledge.ingest.experiments --force` (`setdefault` on a fresh dict -> 0). One owner now: `lead_lag_verdict_count`, imported by both.
2. A verdict page's `tests_run` counted itself once it existed: all four read 2 after the relocation re-ingest; they read 1 now (excluding the page's own stem).
3. The lead-lag ingest appended a `log.md` line on every run, changed or not. R104-3 applied; it was the last adapter still doing it.

### (c) The gap reaches Round 120 (R121-1.C)
`cross_market.lead_lag` takes BTC marks from `asset_snapshots`; the Tier 2/2b window contains the 9.3 h hole (~39% of the price minutes). The registration's readiness bar looks only at the tagged stamps. The readings stand; the gap page lists them; the 3-run consensus you directed will settle it on windows without the hole.

### (d) Where L12 cannot see (R121-1.D)
Lead-lag verdict pages carry no price-series span, so L12 cannot flag them; the gap page names them explicitly instead. If `lead_lag --json` recorded `price_first_utc/last_utc`, the adapter could set `dev.measurement` and L12 would cover it.

---

## 3. Independent cross-check requested

1. `Get-ScheduledTask Monarch_FOMC_Drill | % Settings` -> both battery flags False; trigger still `2026-09-16T13:58:00`; `Get-ScheduledTask | ? TaskName -like Monarch*` -> one task.
2. `python -m knowledge.drills.fomc_rehearsal --online` -> 33 checks, three `* stream` PASS lines, `battery flags` PASS, W32Time the only WARN.
3. `python -m knowledge.drills.event_json --bps 0 --out <scratch>/e.json` then again without `--force` -> `[REFUSE]`; the file's `confidence` is 0.995 and `kind` fed_rate.
4. `git -C <worktree or checkout> show --stat 70bd232` -> 4 files on `feat/collector-hardening`; `git branch --contains 70bd232` -> the branch only; the live tree's `repository.py` is unchanged (`git diff master feat/collector-hardening --stat`).
5. Relocation: `ls cross_market/experiments/*verdict.json` -> 4; `grep -c "page:" obsidian_vault/wiki/regimes/btc_macro_regime.md` -> 5 rows; every verdict page's `sources[0].resource` starts with `cross_market/experiments/`; `tests_run` is 1 on each verdict page and 2 on each registration.
6. Lint -> 507 CLEAN; L12 fires on none today; then, in a scratch copy, set a fade verdict's `dev.data_gaps: []` and confirm exactly one L12.
7. Knowledge suite -> 385.

## 4. Round 122 candidates
- Deploy the hardening (operator's window) and watch the first `silent_failure_watchdog` report lines.
- R120-1.B run 2 of 3 when the next tagged 24 h window closes (~22:20 EDT 09-07); pause-and-flag only under the REGISTERED 60-min gap bar, gaps over 15 min reported.
- R121-1.D: price-series span in `lead_lag --json` so L12 covers lead-lag verdicts.
- Reading intake for the next project once the operator names its aim.
