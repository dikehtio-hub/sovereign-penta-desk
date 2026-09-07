# Rounds 119-120 Handoff: collector incident (restarted) + Tier 2 / 2b lead-lag results; rulings needed

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-06 22:45 EDT (commits `9b59bae` Round 119, `419f11d` gate, `d47fdd0` Round 120, this handoff in `git log -1`)
**Subject**: Two rounds since your 20:35 Round 119 prompt, neither seen by you. Round 119: the HL collector wrote no `asset_snapshots` from 11:46 to 21:05 EDT; root cause found, restart executed on the operator's word, one launcher bug fixed, hardening requested. Round 120: the Tier 2b gate closed at 22:25 EDT and the four pre-registered Tier 2 / 2b commands were run; one subfamily disagrees between tiers and the registration says that disagreement is the finding. Section 0 is the standing checklist, updated. Section 3 is a brainstorm of what is still missing; four of its items can start on the operator's word alone.

---

## 0. THE STANDING CHECKLIST (authoritative as of 2026-09-06 22:45 EDT; mirrors HOMEWORK.md)

### Dated - the operator, in order
- [x] ~~Tonight ~22:20 EDT - Tier 2b gate~~ - CLOSED 22:25 EDT (286 stamps, 24.0 h, largest gap 5.1 min, 0 breaks); Tier 2 / 2b runs done (section 1).
- [ ] **Any day before the 16th, ~3 min** - scheduler probe: `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1` (logged in, on AC). PROBE OK proves Task Scheduler -> batch -> recorder; "never ran" on battery is the battery-flag decision showing itself.
- [ ] **Daily until the 16th, 10 s** - `python -m knowledge.drills.fomc_rehearsal --online` (catches a replaced or resolved Fed market early enough to re-register).
- [ ] **2026-09-13 or 14** - `python -m knowledge.drills.fomc_live_rehearsal` (60 s of real books into scratch; nothing real written). Send the output to Claude if any line says FAIL.
- [ ] **2026-09-15** - Q3 estimated tax: `python -m Tax_Reserve_Agent.main calendar`. Also verify the Round 30 health schedule exists (`Tax_Reserve_Agent.main health`).
- [ ] **2026-09-16 morning** - `fomc_rehearsal --online`, then `fomc_live_rehearsal` once more.
- [ ] **2026-09-16 13:58 EDT** - laptop on, logged in, ON AC (or flags cleared). T-2: `python -m knowledge.query --drill-card fomc-2026-09-16`. 14:00: a HUMAN reads the statement and writes `./event.json`. Then the survival curve -> `knowledge.ingest.clob`, per the card.

### Operator decisions - one line each back to Claude, or two commands
- [ ] **Start W32Time**: `Start-Service W32Time; w32tm /resync` (elevated). Pre-flight WARNs until done.
- [ ] **Battery flags on `Monarch_FOMC_Drill`**: clear (Claude can, on your word) or commit to AC. Claude's recommendation if undecided by the 15th: clear them - they guard against drain, irrelevant to a 7-minute recording; a drill that never starts is the worse outcome.
- [ ] **Desk 4 packages**: `uvicorn` / `hyperliquid-python-sdk` - yes to one, both, or neither.
- [ ] **Delete the stale one-off tasks** `Monarch_Maiden_Protocol_A/B/C` and `Monarch_Watcher_Restart` (last ran 09-05, no next run) so nothing re-fires by accident. Claude can, on your word.
- [ ] **Send this handoff to Antigravity.**
- [x] ~~Collector restart window~~ - DONE 21:04 EDT (Round 119); the R104-1 spread gate is now live.

### Antigravity - open
- [ ] **Cross-check Round 120** (section 1): re-run any of the four commands with `--json` and diff against its artifact; read the regime page's Disagreements section.
- [ ] **R120-1.A / B / C** (section 1): acknowledge the readings; replication policy; artifact location.
- [ ] **Cross-check Round 119** (section 2.4).
- [ ] **R119-1.A** - ratify the `stop_collector.bat` fix (delayed expansion; supervisor first; honest failure line).
- [ ] **R119-1.B** - direct the collector hardening (section 2.3). Daemon code: not touched without you. Proposal: Claude stages it on a branch that is not checked out.
- [ ] **R120-1.D** - the two-writer handoff (section 3, item 11): you write `ANTIGRAVITY_PROMPT.md`, Claude writes `HANDOFF_PROMPT.md`.
- [x] R118-1.A / R118-1.B - ratified in your 20:35 prompt. Nothing further.

### Claude - can start on the operator's word alone (no ruling needed)
- [ ] Daemon health line covering all four processes (section 3, item 1).
- [ ] `event.json` writer for 14:00 (item 2).
- [ ] Data-gap page for 11:46-21:05 + lint rule (item 8).
- [ ] Query of basis windows opened inside the gap (item 9).

### Engineering queue - blocked on a line above
- [ ] Collector hardening (after R119-1.B) - deploys at the next restart.
- [ ] Lead-lag replication cadence and artifact relocation (after R120-1.B/C).
- [ ] Desk 4 installs and the four skipped test modules (after the operator's word).
- [ ] Watching: fade window gate now later than 09-08 by the 9 h gap; whale share gate 20.08% vs 20%. Both registration pages show every gate on every ingest.

### Standing rules (one addition)
- Laptop awake while a 24 h series accumulates (none is, tonight); clean shutdown only; never kill daemons by hand; never seed the live tax ledger; `DEV/HALT.flag` is the kill switch. **New: after any stop script, verify the old PIDs are gone before starting a replacement.**
- Daemons now: watcher 17688, exporter 62760, supervisor 24504, collector 60756.

---

## 1. Round 120 - Tier 2 / Tier 2b lead-lag, as registered

- **Gate**: `lead_lag --check-data --subfamily-from tags` at 22:25 EDT -> 286 tagged stamps, span 24.0 h, largest gap 5.1 min, 0 breaks, READY. All three preconditions in `lead_lag_tier2b.meta.json` held (Tier 1 verdict in Cross_Market_Titans.md; watcher on the Round 76 code since 2026-09-05 22:20; tagged series ready).
- **Runs**: exactly the two commands in each registration, `--json`, no `--force`, artifacts at `cross_market/data/lead_lag_tier{2,2b}_{fed-rates,crypto}_verdict.json`, ingested with `knowledge.ingest.lead_lag --tier 2|2b`. Four verdict pages `wiki/experiments/lead_lag_tier2*_macro_*_20260907T0230Z.md`; `wiki/regimes/btc_macro_regime.md` history now 5 rows. Operator authorisation: "lets do what we can".
- **Results (from the regime page's own table, not transcribed)**:

| tier | scope | membership | class | lag min | corr | n |
|---|---|---|---|---|---|---|
| 2 | macro/fed-rates | first tag wins | no-lead | -10 | +0.052 | 2,416 |
| 2 | macro/crypto | first tag wins | no-lead | 38 | -0.138 | 2,389 |
| 2b | macro/fed-rates | every tag | no-lead | 58 | +0.135 | 890 |
| 2b | macro/crypto | every tag | **polymarket-leads** | 38 | **-0.325** | 910 |

- **Reading, in the registration's words**: "Where they disagree, that disagreement IS the finding: the dual-tagged markets carry it, and neither tier is 'the' answer. Tier 2b never overrides Tier 2." The crypto subfamily disagrees; fed-rates agrees. Bars (min_abs_corr 0.2, min_events 5, min_points 60) met on every subfamily. The lag is the same 38 minutes in both crypto runs and the sign is negative in both: membership changes the magnitude, not the lag - the one structural detail worth your attention. One 24 h window, one coin, an endogenous subfamily by construction, not independent of Tier 2. A reading, not an edge; nothing trades on it.
- **Rulings requested**: **R120-1.A** acknowledge the four readings and the crypto disagreement as recorded. **R120-1.B** replication policy - the registrations are silent on repetition; direct whether the four commands re-run on each further 24 h of tagged stamps (B14's tests_run counter is now 2 per tier-scope and will keep counting). **R120-1.C** the lead-lag artifacts sit in git-ignored `cross_market/data/` like Tier 1's; R114-1.D moved HL artifacts beside their registrations - direct whether these move to `cross_market/experiments/` too (a re-ingest, not a re-run).

---

## 2. Round 119 - the collector incident

### 2.1 Timeline (EDT, 2026-09-06)
11:46:10 last `asset_snapshots` row. 11:46:21 first `Error in market context polling loop: FOREIGN KEY constraint failed`; then one every ~10 s (~360/h, 3,300+ total). 16:12 the only network-profile event of the day (the operator's VPN) - five hours after onset, unrelated. 20:55 the operator asks for a check. 21:04 restart authorised and executed. 21:05:10 first `Persisted 442 market snapshots`. 21:06 old pair killed by PID. 21:07 zero FK errors in the trailing minute; newest snapshot 5 s old.

### 2.2 Root cause
`asset_snapshots.coin` REFERENCES `assets.coin` and `storage/db.py` sets `PRAGMA foreign_keys = ON`. `MarketCollector._sync_universe_metadata` - the only call to `repo.upsert_assets` - is awaited once, in `run()`. A coin listed on the exchange after the collector started - **`para:CIFR`** on the tracked `para` DEX; its first snapshot ever is 2026-09-07T01:04:32Z (1788743072280), the first pass after the restart - was in every REST context and never in `assets`. `insert_snapshots` writes the whole pass in one transaction, so SQLite rejected all 442 rows on the one violating row, every pass, for 9 h 18 min. The process never crashed, so the supervisor's restart-on-crash policy never fired; `coverage_pct` sliding 66 -> 62 was the only visible signal.

**Not the cause.** The exchange universe is 514 instruments across 11 DEXes; the collector tracks 442. The other 72 (a whole new `hyna` DEX; new `mkts`, `vntl`, `io` listings) never enter its contexts. The VPN produced one disconnect event and nothing else; the Tier 2b series, the exporter and the watcher were untouched.

**Consequences of the gap.** Incremental persistence measured no excursions for 9 h (`persisted 0 windows / 0 events` on every maintenance pass); the whale and fade samples did not grow; `latest_snapshots` was 9 h stale; basis windows that opened in the gap have no price series.

### 2.3 Actions taken, one thing that went wrong, and the hardening requested (R119-1.B)
- Restart via the documented launchers, on the operator's word. **`stop_collector.bat` did not stop anything**: `set /p PID=<file` inside an `if exist (...)` block followed by `%PID%` - cmd expands `%VAR%` when it parses the block, so `taskkill` ran with an empty pid, failed under `>nul 2>&1`, the pid files were deleted, and success printed. `start_collector.bat` then launched a **second** supervisor+collector pair against the same database. Caught by checking the old PIDs rather than trusting the line; old pair killed by PID (supervisor 46740 first, then collector 38548).
- **Fixed** `stop_collector.bat`: `setlocal EnableDelayedExpansion`, `!PID!`, supervisor first, `(taskkill reported no such process)` instead of success. Tested offline against bogus pids 999998/999999; NOT run against the live pair.
- **Verified after**: one `run_collector_service.py` (24504), one `main.py collector` (60756); `assets` 441 -> 442; 442 snapshots per pass; 0 FK errors; watcher and exporter untouched.
- **Hardening requested - daemon code, yours to direct**: (1) `_sync_universe_metadata` on a schedule, not only at startup; (2) `insert_snapshots` upserts unknown coins first, or falls back to row-by-row on `IntegrityError` and logs the offenders by name; (3) supervisor alert / restart when `coverage_pct` decays with `restarts == 0` and the child alive; (4) a snapshot-age check (> 15 min = FAIL) in the pre-flight's `--online` and as a daily line. All deploy at the next restart. Proposal: Claude stages them on a branch that is not checked out, for your review.

### 2.4 Independent cross-check requested
1. `grep -c "FOREIGN KEY" HyperLiquid/HL_Monarch/data/collector.log`; first/last timestamps -> onset 11:46:21, last before 21:06.
2. `SELECT MIN(timestamp) FROM asset_snapshots WHERE coin='para:CIFR'` -> 1788743072280; `SELECT coin FROM assets WHERE coin='para:CIFR'` -> present.
3. `Get-Process -Id 24504,60756` alive; `-Id 46740,38548` not found; exactly one `main.py collector`.
4. The snapshot-age one-liner (COMMANDS.txt, Round 119) -> under 1 minute.
5. The stop script: read it; in a temp tree with bogus pid files, run it; confirm it names the pids and removes the files. Do NOT run it against the live pair.
6. Brainstorm: what else in the four daemons has a "keeps running but stops doing its job" mode the supervisor cannot see? Section 3 item 1 is my answer; add yours.

---

## 3. Brainstorm - what is still missing (nothing here is started)

**Before the 16th**
1. A daemon health line covering all four processes (collector snapshot age exists; add watcher newest-drop age and exporter newest-write age; carry all three in the pre-flight's `--online`). *Startable on the operator's word.*
2. An `event.json` writer for 14:00: takes only the basis-point change from the human, writes schema, timestamp and confidence correctly. The decision stays human; the typing does not. *Startable on the operator's word.*
3. Market-replacement risk: `--online` catches an unresolvable token, not a replaced market; hence the daily `--online` line on the checklist.
4. The HTTP 429 back-off path has never run live; provoking it against a public API needs your word, and I would rather not.
5. Battery flags: recommendation on the checklist.
6. Stale one-off tasks: on the checklist (operator).
7. Tax Reserve health schedule: on the checklist (operator).

**Data integrity after the outage**
8. The 11:46-21:05 gap should be a PAGE - a data-gap register (interval, affected tables) with a lint rule flagging any verdict whose window overlaps an unmarked gap. *Startable on the operator's word.*
9. Basis windows opened inside the gap: check whether they read as unmeasured or as measured from stale `latest_snapshots` before anything is graded on them. *Startable on the operator's word.*
10. The fade window gate clears later than the 8th by the gap's length; the pages show it.

**Process**
11. THE HANDOFF FILE HAS TWO WRITERS. Your 20:35 prompt and my Round 119 handoff went to the same path; I avoided overwriting yours only by reading first. Round 110's double-writer lesson, applied to us. -> R120-1.D.
12. Stage the collector hardening on a git branch that is not checked out: reviewable, deployable at the next restart, touches nothing that runs. -> R119-1.B.

**Next project**
13. The 500-page embeddings / hybrid-retrieval revisit the backlog deferred is due (506 pages).
14. A reading intake for the operator's links: `raw/inbox/READING.md` + a Source-page adapter with provenance and a lint rule for sources cited nowhere. Needs the project's one-sentence aim and a go-ahead to fetch.

---

## 4. Telemetry
Knowledge suite 342 (unchanged since Round 118; Rounds 119-120 changed no knowledge code). Real vault 506 pages, lint CLEAN. Registrations idempotent. Daemons: only the collector pair restarted, on the operator's word.

## 5. Operational reminders
- W32Time still stopped; battery flags undecided; the pre-flight WARNs on both until resolved.
- The next dated item is the scheduler probe (any day), then the 13th/14th rehearsal, the 15th tax payment, the 16th drill.
