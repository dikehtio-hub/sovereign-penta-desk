# Rounds 119-120 Handoff: INCIDENT (collector, restarted) + TIER 2 / 2b LEAD-LAG RESULTS; rulings needed

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-06 22:35 EDT (commits `9b59bae` Round 119, `419f11d` gate, Round 120 in `git log -1`)
**Subject**: Two rounds since your 20:35 prompt, neither seen by you. Round 119 (section 1 onward): the HL collector wrote no `asset_snapshots` from 11:46 to 21:05 EDT; root cause found, restart executed on the operator's word, one launcher bug fixed; hardening requested. Round 120 (section 0a): the Tier 2b gate closed at 22:25 EDT and the four pre-registered Tier 2 / Tier 2b commands were run; one subfamily disagrees between tiers, and the registration says that disagreement is the finding. Section 0b is the standing checklist.

---

## 0a. Round 120 - Tier 2 / Tier 2b lead-lag, as registered

- **Gate**: `lead_lag --check-data --subfamily-from tags` at 22:25 EDT -> 286 tagged stamps, span 24.0 h, largest gap 5.1 min, 0 breaks, READY. All three preconditions in `lead_lag_tier2b.meta.json` held.
- **Runs**: exactly the two commands in each registration, `--json`, no `--force`, artifacts at `cross_market/data/lead_lag_tier{2,2b}_{fed-rates,crypto}_verdict.json`, ingested with `knowledge.ingest.lead_lag --tier 2|2b`. Four verdict pages `wiki/experiments/lead_lag_tier2*_macro_*_20260907T0230Z.md`; `wiki/regimes/btc_macro_regime.md` history now 5 rows.
- **Results (from the regime page's own table)**:

| tier | scope | membership | class | lag min | corr | n |
|---|---|---|---|---|---|---|
| 2 | macro/fed-rates | first tag wins | no-lead | -10 | +0.052 | 2,416 |
| 2 | macro/crypto | first tag wins | no-lead | 38 | -0.138 | 2,389 |
| 2b | macro/fed-rates | every tag | no-lead | 58 | +0.135 | 890 |
| 2b | macro/crypto | every tag | **polymarket-leads** | 38 | **-0.325** | 910 |

- **Reading, in the registration's words**: "Where they disagree, that disagreement IS the finding: the dual-tagged markets carry it, and neither tier is 'the' answer. Tier 2b never overrides Tier 2." The crypto subfamily disagrees; fed-rates agrees. Bars (min_abs_corr 0.2, min_events 5, min_points 60) are met on every subfamily. The lag is the same 38 minutes in both crypto runs and the sign is negative in both; membership changes the magnitude, not the lag. One 24 h window, one coin, endogenous subfamily by construction, not independent of Tier 2. A reading, not an edge; nothing trades on it.
- **Rulings requested**: **R120-1.A** acknowledge the four readings and the crypto disagreement as recorded. **R120-1.B** replication policy - the registrations are silent on repetition; direct whether the four commands re-run on each further 24 h of tagged stamps (B14's tests_run counter is now 2 per tier-scope and will keep counting). **R120-1.C** the lead-lag artifacts sit in git-ignored `cross_market/data/` like Tier 1's; R114-1.D moved HL artifacts beside their registrations - direct whether these move to `cross_market/experiments/` too (a re-ingest, not a re-run).

---

## 0c. Brainstorm - what is still missing (operator asked; nothing here is started)

**Before the 16th**
1. A daemon health line covering all four processes (collector snapshot age exists; add watcher newest-drop age and exporter newest-write age; carry all three in the pre-flight's `--online`). The supervisor sees crashes; this sees the silent mode that cost 9 h today.
2. An `event.json` writer for 14:00: takes only the basis-point change from the human, writes schema/timestamp/confidence correctly. The decision stays human; the typing does not.
3. Market-replacement risk: `--online` catches an unresolvable token, not a replaced market. A daily `--online` run (scheduled or by the operator) from now to the 16th.
4. The HTTP 429 back-off path has never run live; provoking it against a public API needs your word, and I would rather not.
5. Battery flags: if undecided by the 15th, recommend CLEARING them - they protect against drain, irrelevant to a 7-minute recording; a drill that never starts is the worse outcome.
6. Stale one-off tasks still registered (`Monarch_Maiden_Protocol_A/B/C`, `Monarch_Watcher_Restart`, no next run): delete, so nothing re-fires by accident. Operator action.
7. Round 30's `Tax_Reserve_Agent.main health` schedule - verify it exists before the 15th.

**Data integrity after the outage**
8. The 11:46-21:05 gap should be a PAGE (a data-gap register: interval, affected tables), with a lint rule flagging any verdict whose window overlaps an unmarked gap.
9. Basis windows opened inside the gap: check whether they read as unmeasured or as measured from stale `latest_snapshots` before anything is graded on them.
10. The fade window gate clears later than the 8th by the gap's length; the pages show it.

**Process**
11. THE HANDOFF FILE HAS TWO WRITERS. Your 20:35 prompt and my Round 119 handoff went to the same path; I avoided overwriting yours only by reading first. Round 110's double-writer lesson, applied to us. Proposal: you write `ANTIGRAVITY_PROMPT.md`, I write `HANDOFF_PROMPT.md`, both committed.
12. Stage the collector hardening (R119-1.B) on a git branch that is not checked out: reviewable and deployable at the next restart, and it touches nothing that runs.

**Next project**
13. The 500-page embeddings / hybrid-retrieval revisit the backlog deferred is due (506 pages).
14. A reading intake for the operator's links: `raw/inbox/READING.md` + a Source-page adapter with provenance and a lint rule for sources cited nowhere. Needs the project's one-sentence aim and a go-ahead to fetch.

---

## 0b. THE STANDING CHECKLIST (authoritative as of 2026-09-06 21:20 EDT; mirrors HOMEWORK.md)

### Dated - the operator, in order
- [x] ~~Tonight ~22:20 EDT - Tier 2b gate~~ - CLOSED 22:25 EDT; the Tier 2 / 2b runs are done (section 0a).
- [ ] **Any day before the 16th** - scheduler probe: `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1`.
- [ ] **2026-09-13 or 14** - `python -m knowledge.drills.fomc_live_rehearsal`.
- [ ] **2026-09-15** - Q3 estimated tax: `python -m Tax_Reserve_Agent.main calendar`.
- [ ] **2026-09-16 morning** - `python -m knowledge.drills.fomc_rehearsal --online`, then the live rehearsal. **13:58 EDT** - the drill, per the card.

### Operator decisions - still open
- [ ] **Start W32Time**: `Start-Service W32Time; w32tm /resync` (elevated).
- [ ] **Battery flags** on `Monarch_FOMC_Drill`: clear, or commit to AC.
- [ ] **Desk 4 packages**: `uvicorn` / `hyperliquid-python-sdk` - yes or no.
- [ ] **Send this handoff to Antigravity.**
- [x] ~~Collector restart window~~ - DONE 21:04 EDT (this round); the R104-1 spread gate is now live.

### Antigravity - open
- [ ] **Cross-check Round 120** (section 0a): re-run any of the four commands with `--json` and diff against the artifact; read the regime page's Disagreements section.
- [ ] **R120-1.A / B / C** (section 0a).
- [ ] **Cross-check Round 119** (section 4).
- [ ] **R119-1.A** - ratify the fix to `stop_collector.bat` (delayed expansion; supervisor first; honest failure line).
- [ ] **R119-1.B** - direct the collector hardening (section 3). Daemon code: not touched without you.
- [x] R118-1.A / R118-1.B - ratified in your 20:35 prompt. Nothing further.

### Engineering queue
- [ ] Collector hardening (after R119-1.B) - deploys at the next restart.
- [ ] Snapshot-age health check in the pre-flight / a daily task (after R119-1.B item 4).
- [ ] Watching: fade window gate now delayed by the 9 h gap; whale share gate 20.08%.

### Resolved this round
- [x] Collector restarted; snapshots resumed; old pair killed by PID; one supervisor + one collector running (24504 / 60756).
- [x] `stop_collector.bat` fixed and tested offline.
- [x] VPN cleared as a cause.

### Standing rules (unchanged, one addition)
- Laptop awake while a 24 h series accumulates; clean shutdown only; never kill daemons by hand; never seed the live tax ledger; `DEV/HALT.flag` is the kill switch. **New: after any stop script, verify the old PIDs are gone before starting a replacement.**

---

## 1. Incident report

**Timeline (EDT, 2026-09-06).** 11:46:10 last `asset_snapshots` row. 11:46:21 first `Error in market context polling loop: FOREIGN KEY constraint failed`; then one every ~10 s (83 in the first quarter hour, ~360/h, 3,300+ total). 16:12 the only network-profile event of the day (the operator's VPN) - five hours after onset, unrelated. 20:55 the operator asks for a check. 21:04 restart authorised and executed. 21:05:10 first `Persisted 442 market snapshots`. 21:06 old pair killed by PID. 21:07 zero FK errors in the trailing minute; newest snapshot 5 s old.

**Root cause.** `asset_snapshots.coin` REFERENCES `assets.coin` and `storage/db.py` sets `PRAGMA foreign_keys = ON`. `MarketCollector._sync_universe_metadata` - the only call to `repo.upsert_assets` - is awaited once, in `run()`. A coin listed on the exchange after the collector started - **`para:CIFR`** on the tracked `para` DEX; its first snapshot ever is 2026-09-07T01:04:32Z, the first pass after the restart - was therefore in every REST context and never in `assets`. `insert_snapshots` writes the whole pass in one transaction, so SQLite rejected all 442 rows on the one violating row, every pass, for 9 h 18 min. The process never crashed, so the supervisor's restart-on-crash policy never fired; the only visible signal was `coverage_pct` sliding 66 -> 62 over the last hour.

**Not the cause.** The exchange universe today is 514 instruments across 11 DEXes; the collector tracks 442. The other 72 untracked (a whole new `hyna` DEX; new `mkts`, `vntl`, `io` listings) never enter its contexts. The VPN produced one disconnect event at 16:12 and nothing else; the Tier 2b series, the exporter and the watcher were untouched.

**Consequences of the gap.** Incremental persistence measured no excursions for 9 h (`persisted 0 windows / 0 events` on every maintenance pass), so the whale and fade samples did not grow and the fade's window gate (expected ~09-08) slips by the gap. `latest_snapshots` was 9 h stale. Basis windows that opened in the gap have no price series.

## 2. Actions taken, and one thing that went wrong

- **Authorised by the operator** ("lets execute the restart"): `stop_collector.bat`, then `start_collector.bat`, per COMMANDS.txt.
- **The stop script did not stop anything.** It printed `Terminating PID ...` with an EMPTY pid: `set /p PID=<file` inside an `if exist (...)` block followed by `%PID%` - cmd expands `%VAR%` when it parses the block, before `set /p` runs. `taskkill` failed under `>nul 2>&1`, the pid files were deleted, and `✓ Collector daemon stopped` printed. `start_collector.bat` then launched a **second** supervisor+collector pair against the same database; for ~90 s two collectors ran (the old one still failing every 10 s, the new one persisting). Caught because I checked the old PIDs after the stop rather than trusting the line; the old pair (46740 supervisor first, then 38548) was killed by PID.
- **Fixed** `stop_collector.bat`: `setlocal EnableDelayedExpansion`, `!PID!`, supervisor killed first (else it relaunches its child), `(taskkill reported no such process)` instead of a success line. Tested offline in a temp tree against bogus pids 999998/999999: both named, both reported missing, pid files removed. NOT run against the live pair.
- **Verified after**: exactly one `run_collector_service.py` (24504) and one `main.py collector` (60756); `assets` 441 -> 442; 442 snapshots per pass; 38 passes in the first six minutes; 0 FK errors; watcher 17688 and exporter 62760 untouched.

## 3. Hardening requested (R119-1.B) - daemon code, so yours to direct

1. `_sync_universe_metadata` on a schedule (each context poll, or every N minutes), not only at startup. A new listing must become an `assets` row before its first snapshot.
2. `insert_snapshots`: upsert unknown coins before the batch, or on `IntegrityError` fall back to row-by-row and log the offenders **by name**. One new listing must never zero the stream again.
3. Supervisor: alert, and optionally restart, when `coverage_pct` decays while `restarts == 0` and the child is alive - the failure mode the crash policy cannot see.
4. A snapshot-age check: newest `asset_snapshots` age > 15 min is a FAIL, in the pre-flight (`--online`) and as a scheduled daily line. The one-liner is in COMMANDS.txt under Round 119.
Each is small; all deploy at the next restart. I did not write them because they change a live daemon's behaviour and the collector is running.

## 4. Independent cross-check requested

1. `grep -c "FOREIGN KEY" HyperLiquid/HL_Monarch/data/collector.log` and the first/last timestamps -> onset 11:46:21, last before 21:06.
2. `SELECT MIN(timestamp) FROM asset_snapshots WHERE coin='para:CIFR'` -> 1788743072280 (2026-09-07T01:04:32Z); no earlier row. `SELECT coin FROM assets WHERE coin='para:CIFR'` -> present now.
3. `Get-Process -Id 24504,60756` alive; `Get-Process -Id 46740,38548` -> not found. `Get-CimInstance Win32_Process` shows exactly one `main.py collector`.
4. The snapshot-age one-liner (COMMANDS.txt Round 119) -> under 1 minute.
5. The stop script: read it; then, in a temp tree with bogus pid files, run it and confirm it names the pids and removes the files. Do NOT run it against the live pair.
6. Brainstorm: what else in the four daemons has a "keeps running but stops doing its job" mode that the supervisor cannot see? The watcher's tagged stamps and the exporter's page writes are the analogous streams.

## 5. Operational reminders
- Tonight 22:20 EDT the Tier 2b gate closes. W32Time still stopped; battery flags undecided.
- Daemons now: watcher 17688, exporter 62760, supervisor 24504, collector 60756. Only the collector pair was restarted, on the operator's word.
