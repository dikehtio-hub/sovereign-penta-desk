# Round 119 Handoff: INCIDENT - collector snapshots dead 9 h; operator-authorised restart; rulings needed

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-06 21:20 EDT (commit in `git log -1`)
**Subject**: Your 20:35 Round 119 prompt (R118-1.A/B ratified, holding directives) is acknowledged; this supersedes it with an incident. The HL collector wrote no `asset_snapshots` from 11:46:10 to 21:05:10 EDT. Root cause found, restart executed on the operator's word, one launcher bug fixed. Section 0b is the standing checklist. Section 3 asks for the hardening directives; this is daemon code and I did not change it without you.

---

## 0b. THE STANDING CHECKLIST (authoritative as of 2026-09-06 21:20 EDT; mirrors HOMEWORK.md)

### Dated - the operator, in order
- [ ] **Tonight ~22:20 EDT** - Tier 2b gate closes (series verified unbroken at 20:55: 268 stamps, largest gap 5.1 min). Laptop on, plugged in, logged in.
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
