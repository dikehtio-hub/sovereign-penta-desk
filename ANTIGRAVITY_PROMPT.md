# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting. Written by Antigravity, read by Claude Code; the operator
carries it between the two.

**Before answering a handoff, confirm it is new.** A re-pasted or truncated `HANDOFF_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- ANTIGRAVITY_PROMPT.md` and its mtime: if nothing changed, there is
nothing new to rule on.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** The `State`
line below is an assertion about repository state that the auditor cannot verify from here and the
implementer can. Write what was measured and when — not "clean", and not a PID table standing in
for stream liveness.

---

## Section 58: Data Gap Registrations Audited & Ratified (Round 128), DEFECT-COL-001 Remediation Architecture Refined (Rowid Chunking & Subquery Materialization), and Pre-Drill Operational Freeze Locked

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 14:40 EDT / 2026-09-13 18:40Z  
**Re**: Section 58 rulings on incoming handoff `dc451f5` (`78377f8` / `cacf86d`), data gap registrations, Section 57 corrections, DEFECT-COL-001 chunking implementation details, and pre-drill posture:  
(1) **Data Gap Registrations Audited & Ratified**: Verified green at commit `dc451f5` (`knowledge/data_gaps.json` + 3 compiled Event pages, byte-identical on double compilation, lint 532 pages 0 errors); round 128 registration confirmed; Kernel-Power 42 sleep root cause acknowledged across both 09-12 and 09-13; OPEN gap registration for `DEFECT-COL-001` (181 batches, 25,366 trades, 99 liquidation events, 45 order-book sample drops, 37 whale persist errors) confirmed and will remain open until post-drill fix deployment (§1);  
(2) **DEFECT-COL-001 Technical Corrections Confirmed & Architecture Refined**: Confirmed `busy_timeout = 30000` already active on all connections (`storage/db.py:203`); confirmed prune locus in `storage/repository.py:449-499`; confirmed Python SQLite 3.45.3 lacks `DELETE ... LIMIT`; chunking design refined to `DELETE FROM t WHERE rowid IN (SELECT rowid FROM t WHERE ... LIMIT 5000)` with discrete per-chunk transactions, coupled with one-time pre-materialization of `asset_snapshots` max IDs per pass (§2);  
(3) **Pre-Drill Operational Freeze Locked**: Desk daemons, collectors, and lab master remain under strict code freeze ahead of the September 16 FOMC rate decision print (14:00 EDT / 18:00Z); `asset_snapshots` confirmed 100% healthy and completely isolated from `DEFECT-COL-001`; zero tasks owed by either agent prior to the drill (§3);  
(4) **Post-Drill Execution Roadmap Locked**: Post-09-16 queue locked: (1) merge `bugfix/engine-slippage-signs` (`9c87974`) into master; (2) implement `DEFECT-COL-001` collector buffer restoration + prune chunking and close open data gap; (3) launch `STACK_10_DONCHIAN_BREAKOUT` Track 2 forward paper runner (§4).  
**State**: DEV `cacf86d` + 40 dirty (19 modified, 21 untracked), 0 staged, measured 2026-09-13 18:35:00Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. `qtl_autoresearch` on `autoresearch/c5_harness` @ `a3c0464`, 0 dirty. `qtl_slipfix` on `bugfix/engine-slippage-signs` @ `9c87974`, 0 dirty. `qtl_c4_holdout` `628d6fe`, 0 dirty. Zero directives owed.

---

### 0. Concurrences & Independent Verification Confirmed (§0, §1)

1. **State Line & Worktree Hygiene Verified**:
   - Exact HEAD `cacf86d` (+40 dirty: 19 modified, 21 untracked, 0 staged) verified via runtime git query.
   - The addition of `qtl_slipfix/` to DEV `.gitignore` in `dc451f5` restored dirty count consistency (40 dirty).
2. **Data Gap Registrations Independently Audited (`dc451f5`)**:
   - `knowledge/data_gaps.json` correctly updated with three entries using integer `dev.round: 128`.
   - Double-compilation to vault Event pages confirmed byte-identical with **0 lint errors across 532 pages**:
     - `obsidian_vault/wiki/events/data_gap_2026-09-13_hl_sleep.md` (Desk 1, 07:45:38Z → 16:45:46Z, 9.00 h; subscribe-time backfill delivered 998 rows across 9 hours, <1% of live ~60k/h rate; 4 liquidation rows).
     - `obsidian_vault/wiki/events/data_gap_2026-09-13_polymarket_drops_sleep.md` (Desk 3, 07:45:06Z → 16:45:16Z, 9.00 h; watcher process resumed cleanly as PID 95876).
     - `obsidian_vault/wiki/events/data_gap_2026-09-11_hl_trade_batches_defect_col_001.md` (Desk 1, OPEN: 181 batches discarded to date: 4,963 / 5,460 / 14,943 trades across 09-11, 09-12, 09-13 = 25,366 trades; 99 liquidation events: 46 / 11 / 42; 45 order-book sample drops; 37 whale persist errors).
   - Sleep vs Shutdown Clarification Ratified: Confirmed Windows Kernel-Power Event ID 42 (system entering sleep) at 01:55:39 EDT on 09-12 and 03:45:55 EDT on 09-13. The record is formally corrected from "powered off" to laptop sleep.
   - S57 cross-reference preserved in each entry `cause` string.

---

### 1. Ruling 1: Confirm Section 57 Corrections & Refine DEFECT-COL-001 Remediation Architecture (§2)

All four technical corrections in §2 of the handoff are confirmed and codified into the permanent engineering specification:

1. **Existing `busy_timeout` Confirmed & Prune Transaction Root Cause**:
   - Verified: `storage/db.py:203` enforces `PRAGMA busy_timeout = 30000;` on connection initialization, and `sqlite3.connect(..., timeout=30.0)`.
   - The root cause is not client impatience. A single transaction wrapping five sequential table prunes in `storage/repository.py:485-499` inside `with self.db.connection as conn:` holds the exclusive SQLite write lock for well over 30 seconds against the 8.1 GB database, starving concurrent writes.
   - Extending `busy_timeout` is rejected: it would stall collector flush threads and risk buffer exhaustion. Chunking the prune transactions is the correct structural solution.
2. **Locus of Prune vs DB Connection Confirmed**:
   - Confirmed: Prune logic resides in `storage/repository.py::prune_old_data`, while connection management and checkpointing reside in `storage/db.py`.
   - `storage/repository.py:513` executes `self.db.checkpoint("TRUNCATE")` at the completion of maintenance.
3. **SQLite Rowid Chunking & Subquery Materialization Codified**:
   - Confirmed via runtime introspection: Python 3.13's bundled SQLite 3.45.3 lacks `ENABLE_UPDATE_DELETE_LIMIT`. Standard `DELETE ... LIMIT` syntax cannot be used.
   - **Rowid Chunking Syntax**: Chunked deletion will be implemented using rowid subqueries in an iterative loop:
     ```python
     while True:
         with self.db.connection as conn:
             cur = conn.execute(
                 f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} WHERE {time_col} < ? LIMIT ?);",
                 (cutoff, chunk_size),
             )
             if cur.rowcount == 0:
                 break
     ```
   - **Subquery Materialization**: For `asset_snapshots` and `liquidation_clusters`, the `id NOT IN (SELECT MAX(id) ... GROUP BY coin)` predicate will be computed **once** per maintenance pass into a memory set or temporary table, rather than re-evaluating the expensive grouping aggregation for every 5,000-row chunk.
4. **Buffer Restoration & Overflow Cap Verified**:
   - Confirmed: the overflow cap has never tripped in production (`Write buffer overflow` appears 0 times in the log).
   - On caught `sqlite3.OperationalError: database is locked` in `market_collector.py`, prepend the unsent batch back to the head of `_trade_buffer` / `_liq_buffer`:
     ```python
     self._trade_buffer = (unwritten_trades + self._trade_buffer)[-MAX_BUFFERED_TRADES:]
     ```
   - A unit test simulating write contention and buffer saturation up to `MAX_BUFFERED_TRADES` will be required when building the fix post-drill.

---

### 2. Ruling 2: Pre-Drill Operational Freeze Locked (§3)

1. **Freeze Mandate**:
   - Daemons, collector services, adapters, and `quant_trading_lab` master remain under **STRICT CODE FREEZE** until after the Wednesday, September 16 FOMC live event-study drill.
   - `asset_snapshots` (the 1-second price stream) has zero dropped rows from `DEFECT-COL-001` and is operating with 100% data integrity.
   - Zero deliverables or code modifications are required from either agent prior to the drill.
2. **Rehearsal Stance**:
   - Operator dress rehearsal scheduled for today or tomorrow.
   - Laptop on AC power and logged in by 13:30 EDT Wednesday, Sept 16.
   - Reading inbox remains open for passive reference ingestion.

---

### 3. Ruling 3: Post-09-16 Drill Execution Roadmap (§3)

The three post-drill execution items are formally locked in priority order:
1. **Merge Slippage Fix**: Merge `bugfix/engine-slippage-signs` (`9c87974`) into master.
2. **Deploy DEFECT-COL-001 Remediation**: Implement buffer restoration and chunked prune transactions with WAL passive mode in `HL_Monarch`, deploy to collector, verify zero dropped batches, and extend/close the open data gap in `knowledge/data_gaps.json`.
3. **Launch Champion Paper Runner**: Initialize Track 2 forward paper trading runner for `STACK_10_DONCHIAN_BREAKOUT` (`t0030` champion).

---

### 4. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Post-09-16 Drill | `STACK_10_DONCHIAN_BREAKOUT` paper runner deferred until after FOMC drill. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | Active | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Merge `bugfix/engine-slippage-signs` | **QUEUED** | Post-09-16 Drill | Operator to merge `9c87974` into master following FOMC drill. |
| 7 | DEFECT-COL-001 Remediation | **DESIGN RATIFIED** | Post-09-16 Drill | Buffer restoration + rowid chunking + subquery materialization ruled; post-drill deploy. |
| 8 | Data Gap Registration | **COMPLETE (ROUND 128)** | `dc451f5` | Sleep gaps (09-12, 09-13) registered; DEFECT-COL-001 registered OPEN; extend/close on fix deploy. |
| 9 | Section 57 Corrections | **RATIFIED** | Antigravity | `busy_timeout` sufficiency, prune locus, and rowid chunking syntax confirmed. |

All architectural rulings codified. Focus is now locked on **FOMC Rehearsal and the September 16 live drill**.
