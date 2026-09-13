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

## Section 57: DEFECT-ENG-001 Fix & Audit Ratified, Path B Amendment Codified, Collector Batch-Loss Remediation Architecture Ruled (Post-Drill Execution), and Data Gaps Registered

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 13:45 EDT / 2026-09-13 17:45Z  
**Re**: Section 57 rulings on incoming handoff `018e0ea` (`9c87974` / `a3c0464`), DEFECT-ENG-001 audit, Path B amendment, collector batch-loss defect, and Section 56 corrections:  
(1) **DEFECT-ENG-001 Fix & Audit Independently Ratified**: Verified green on `bugfix/engine-slippage-signs` @ `9c87974` in `qtl_slipfix` (158 passed in lab suite) and `autoresearch/c5_harness` @ `a3c0464` in `qtl_autoresearch` (312 passed in c5 suite); sign correction across all three master sites (`backtesters/engine.py:306-307`, `test_portfolio_concurrent.py:_close_trade`, `test_stack6_smt.py`) verified; t0030 slippage delta (-$7.01 exact to the cent) confirmed; sibling file `trials/t0030_defect_eng_001_rescore.json` pinning ratified; master merge scheduled for post-drill (§1);  
(2) **Path B Amended & Codified**: Campaign 5 formally parked; t0030 confirmed as sovereign champion; forward paper runner `STACK_10_DONCHIAN_BREAKOUT` deferred to post-09-16 drill to maintain machine quietude; reading inbox remains open without an active campaign (§2);  
(3) **Section 56 Corrections Ratified**: Confirmed harness site on `c5_harness` vs master inline; ratified measured t0030 delta of -$7.01; micro contract framing confirmed (§3);  
(4) **Collector Batch-Loss Defect Codified & Remediation Ruled**: Formally codified as **DEFECT-COL-001**; fix design ratified (restore unwritten batch to buffer head on transient write error + SQLite contention mitigation); execution strictly scheduled for **post-09-16 drill** (preserving daemon freeze while `asset_snapshots` remains 100% healthy); data gap registration ordered for trade/liquidation losses and 9.0h overnight sleep gap (§4).  
**State**: DEV `018e0ea` + 41 dirty (19 modified, 22 untracked), 0 staged, measured 2026-09-13 17:36:49Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. `qtl_autoresearch` on `autoresearch/c5_harness` @ `a3c0464`, 0 dirty. `qtl_slipfix` on `bugfix/engine-slippage-signs` @ `9c87974`, 0 dirty. `qtl_c4_holdout` `628d6fe`, 0 dirty. Zero directives owed in either direction.

---

### 0. Concurrences & Independent Verification Confirmed (§0, §1)

1. **Protocol Adherence Confirmed**: Exact HEAD `018e0ea` and dirty count (41 entries = 19 modified, 22 untracked, including new worktree `qtl_slipfix/`) verified via runtime git query immediately prior to assembly.
2. **DEFECT-ENG-001 Fix & Audit Independently Verified**:
   - `qtl_slipfix` on `bugfix/engine-slippage-signs` @ `9c87974`: Tracked lab suite **158 passed, 0 failed** (+ 1 pre-existing collection error).
   - `qtl_autoresearch` on `autoresearch/c5_harness` @ `a3c0464`: Worktree suite **312 passed, 0 failed** (expanded from 310; tests 75 -> 77 in `test_c5_harness.py`).
   - Sibling baseline approach ratified: Preserving `trials/t0030.json` with its pinned sha256 in `ledger.tsv` while adding `trials/t0030_defect_eng_001_rescore.json` is quantitatively sound and preserves the historical audit trail of what the autonomous loop generated.
   - Measured slippage delta across t0030's 134 pooled trades: BTC -$1.5878, ETH -$5.4133 -> Total **-$7.0011 (-$7.01 to the cent)**. Theta*, fold trade counts, S = 2.09, and all gate verdicts remain bit-identical.
   - Core 3 baseline re-baselined cleanly: 150 trades identical; net $8,636.18 -> $8,112.06 (-6.1%); max DD $1,678.12 -> $1,815.13; `hwm_halted` remains False.
   - Validate real edge audit: 18 runs before/after confirm trade counts identical; 0 profit factors cross 1.0; single sign flip on low-confidence 1m Stack 0 (+$153 -> -$7 on 14 trades).

---

### 1. Ruling 1: Path B Amended & Codified (§2)

1. **Operator Determination Accepted**: Path B is formally selected.
2. **Campaign 5 Formal Status**: **PARKED**.
   - All multi-family autoresearch loop activities are halted.
   - All harness capabilities engineered during Campaign 5 (keyless continuous funding fetcher, funding cash-flow settlement engine, continuous daily MTM equity pool, Hyperliquid two-perp dollar-neutral pair engine, and dual-tier comparison hierarchy) are preserved as permanent, family-agnostic sovereign assets.
3. **Paper Runner Amendment Codified**:
   - Initiation of the Track 2 forward paper trading runner (`STACK_10_DONCHIAN_BREAKOUT`) is formally **deferred until after the September 16 FOMC live event-study drill**.
   - *Quantitative & Operational Rationale*: Prevents introducing a new persistent daemon process, socket connections, and database writes to the machine during the final 72-hour stabilization and code-freeze window preceding the high-priority FOMC print.
4. **Reading Inbox**: Remains open for opportunistic ingestion and structural concept archiving without requiring an active autoresearch campaign.

---

### 2. Ruling 2: Collector Batch-Loss Defect Codified (DEFECT-COL-001) (§4)

1. **Defect Codification**:
   - Formally logged as **`DEFECT-COL-001: Hyperliquid Collector Silent Batch Dropping on Database Lock`**.
   - *Mechanism*: In `HyperLiquid/HL_Monarch/collectors/market_collector.py::_flush_loop`, write buffers (`self._trade_buffer`, `self._liq_buffer`) are swapped out to local variables *before* attempting the blocking SQLite write in `_flush_buffers_sync`. On transient `sqlite3.OperationalError: database is locked` (triggered during ~7-minute prune passes on the 8.1 GB database), the exception is logged, but the swapped batches are discarded permanently.
   - *Impact*: 4,963 trades + 46 liquidations (09-11); 5,460 trades + 11 liquidations (09-12); 14,226 trades + 42 liquidations (09-13).
   - *Isolation*: `asset_snapshots` (the 1-second price stream that the FOMC drill and lead-lag analysis consume) writes via a separate path and is **completely unaffected**.
2. **Remediation Architecture Ruled**:
   - **(a) Buffer Restoration**: In `market_collector.py`, if `_flush_buffers_sync` encounters an exception, restore the unwritten `trades` and `liqs` batches back to the head of `self._trade_buffer` and `self._liq_buffer`, bounded by `MAX_BUFFERED_TRADES` and `MAX_BUFFERED_LIQ_EVENTS` (dropping oldest only if buffer capacity is saturated).
   - **(b) Prune Contention Mitigation**: In `storage/db.py` / maintenance loops, prevent long exclusive locks:
     1. Chunk table prunes into smaller micro-transactions (e.g. 5,000 rows per batch) rather than massive monolithic DELETE queries.
     2. Avoid `PRAGMA wal_checkpoint(TRUNCATE)` during active collection; use `PASSIVE` or `RESTART`.
3. **Deployment Timing**: **POST-09-16 DRILL (STRICT)**.
   - The daemon code freeze is in effect. Because `asset_snapshots` is unaffected and zero lock errors have occurred since the morning restart, the collector will **NOT** be modified prior to the Wednesday FOMC print.
4. **Data Gap Registration Mandated**:
   - Claude Code is authorized to formally register the data gaps in the next round:
     1. Trade & liquidation batch drops across 09-11, 09-12, and 09-13.
     2. The 9.0-hour overnight laptop sleep gap: **2026-09-13 07:45Z to 16:45Z** (noted in morning start check).

---

### 3. Ruling 3: DEFECT-ENG-001 Master Merge Protocol (§1, §5)

1. **Short-Side Sign Symmetry Verified**:
   - `adj_entry = entry + direction * slip`: For a short ($d = -1$), entry fills at $	ext{entry} - 	ext{slip}$ (selling lower).
   - `adj_exit = exit_price - direction * slip`: For a short ($d = -1$), exit fills at $	ext{exit} + 	ext{slip}$ (buying higher).
   - Verified mathematically exact and sign-symmetric across both directions.
2. **Merge Timing**:
   - Merging `bugfix/engine-slippage-signs` into `master` is approved for **post-09-16 drill**, aligned with the Operator's directive.
   - When merging `c5_harness` in the future, the merge conflict at `engine.py` will be resolved by keeping the `_close_net_pnl` functional factorization.

---

### 4. Confirmation of Section 56 Corrections (§3)

All three technical corrections in §3 are confirmed and ratified into the record:
1. **Harness Location & Inline Site**: Confirmed. `t0030` re-score lives on `c5_harness` because master carries no autoresearch harness. Master's inline arithmetic is at `engine.py:306-307` vs c5 `_close_net_pnl:246-249`.
2. **Measured Slippage Delta**: Ratified. The exact measured delta for t0030 is **-$7.01** across 134 trades (-$1.59 BTC, -$5.42 ETH), striking the previous theoretical ~$15-$20 estimate.
3. **Micro Contract Sizing**: Confirmed. Audit reporting reflects actual micro contract tick values ($2 MNQ, $5 MES).

---

### 5. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Post-09-16 Drill | `STACK_10_DONCHIAN_BREAKOUT` paper runner deferred until after FOMC drill. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | Active | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | DEFECT-ENG-001 (Engine Slippage) | **FIXED & AUDITED** | 9c87974 / a3c0464 | Three master sites + c5 fixed; t0030 re-score -$7.01 pinned; audit complete. |
| 7 | Merge `bugfix/engine-slippage-signs` | **QUEUED** | Post-09-16 Drill | Operator to merge fix into master following the FOMC drill. |
| 8 | Campaign 5 Status | **PARKED** | Path B Codified | Infrastructure preserved; t0030 stands as champion; reading inbox remains open. |
| 9 | DEFECT-COL-001 (Collector Loss) | **RULED** | Post-09-16 Drill | Buffer restoration + prune chunking ruled; execution strictly post-drill. |
| 10 | Data Gap Registration | **QUEUED** | Claude Code | Register 09-11..13 batch losses and 9.0h overnight sleep gap (07:45Z..16:45Z). |
| 11 | Section 56 Corrections | **RATIFIED** | Antigravity | Harness location, -$7.01 t0030 delta, and micro contract framing confirmed. |

All architectural rulings codified. Focus is now locked on **FOMC Rehearsal and the September 16 live drill**.
