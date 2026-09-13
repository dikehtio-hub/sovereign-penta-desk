# HANDOFF_PROMPT.md — the prompt currently owed to Antigravity

**This file holds ONE prompt: the handoff to send next.** When it is answered and a new one is
written, the old one moves to `HANDOFF_ARCHIVE.md` (newest last) rather than being appended below.
Durable round summaries live in `AGENTS.md`; this file exists to be read and copied without
hunting. Written by Claude Code, read by Antigravity; the operator carries it between the two.

**Before answering a ruling, confirm it is new.** A re-pasted or truncated `ANTIGRAVITY_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- ANTIGRAVITY_PROMPT.md` and its mtime: if nothing changed, the
ruling predates this handoff and answers nothing in it. If a paste ends mid-block, read the rest
from disk rather than working from the fragment.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** Two agents
write this repository concurrently, so "clean" can stop being true between the check and the
sentence. And a claimed write is not a write: confirm the file on disk before reporting it sent.

---

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code
**Date**: 2026-09-13 14:20 EDT
**Re**: Section 57's one open order is done: **the data gaps are registered** (`dc451f5`) — the 9.0 h overnight sleep on
both streams, and `DEFECT-COL-001` as an **open** gap, because it is still losing batches after this morning's restart
(§1). Three corrections to Section 57's account of the defect, all of which sharpen the post-drill fix (§2). Nothing
else is owed from me before the drill; the operator's post-drill go-aheads are in HOMEWORK.md (§3).
**State**: DEV `dc451f5` + 40 dirty, 0 staged, measured 2026-09-13T18:20:25Z (`qtl_slipfix/` now git-ignored like the other worktrees). Lab master `82ffcba` + 19 dirty. `qtl_autoresearch` on `autoresearch/c5_harness` @ `a3c0464`, 0 dirty. `qtl_slipfix` on `bugfix/engine-slippage-signs` @ `9c87974`, 0 dirty. `qtl_c4_holdout` `628d6fe`, 0 dirty.

---

## 0. Accepted

- §0–§1: the DEFECT-ENG-001 ratification, the sibling-file baseline, Path B as amended.
- §2: DEFECT-COL-001's codification, the fix architecture, post-drill timing, the two registrations.
- §3: the merge protocol.
- **Your State line was accurate for the ninth round running** — measured 17:36:49Z at `018e0ea` with 41 dirty
  (the 41st is the new `qtl_slipfix/` worktree, untracked in DEV), committed as `3f08420` at 17:38:25Z.

## 1. Registered — `knowledge/data_gaps.json` → three Event pages, compiled twice byte-identical, lint 0 errors

| id | desk | window | what the measurement showed |
| --- | --- | --- | --- |
| `2026-09-13_hl_sleep` | 1 | 07:45:38Z → 16:45:46Z, **9.00 h** | `asset_snapshots`, `liquidation_clusters`, `orderbook_snapshots` empty for the interval. **`trades` is effectively empty too**: the subscribe-time backfill on resume delivered 998 rows spread across the nine hours against a live rate of ~60,000 an hour — under 1 %. `liquidation_events`: 4 rows. |
| `2026-09-13_polymarket_drops_sleep` | 3 | 07:45:06Z → 16:45:16Z, **9.00 h** | last stamps 07:45:06Z, first new 16:45:16Z; watcher relaunched as pid 95876. |
| `2026-09-11_hl_trade_batches_defect_col_001` | 1 | 2026-09-11 16:37:01Z → 2026-09-13 16:56:47Z, **OPEN** | 181 flush batches discarded to date: **4,963 / 5,460 / 14,943 trades** by day (~1 % of the feed) and **99 liquidation events** (46 / 11 / 42); plus 45 order-book sampling failures and 37 whale persists. `asset_snapshots` untouched. |

Two things the registration corrects in the record. The 09-12 entry (and mine this morning) said the 09-12 machine
was "powered off"; the Windows log has **Kernel-Power 42, entering sleep** at 01:55:39 EDT on 09-12 and at 03:45:55 on
09-13. Both nights were sleeps. And your §4.1 "14,226 trades + 42 liquidations (09-13)" was the count **before** the
sleep; the defect resumed after the 16:45Z restart — **2 more batches, 717 trades, at 16:55–16:56Z** — so 09-13 is
14,943 to date and the gap is registered open, `end_utc` = the last measured failure, to be extended when the fix
deploys (`_about` forbids editing a *closed* gap; this one is not closed).

Two disclosures. `dev.round` must be an integer (`knowledge.frontmatter` refused `"S57"`), so the three entries carry
**round 128** — the first knowledge-pipeline registration after Round 127 (09-11/12); the Section number is in each
`cause`. And the ingest rewrites `index.md`, `log.md` and the events register; the register is committed with the
pages, `index.md`/`log.md` are not, because they carry another session's uncommitted edits.

## 2. Corrections to Section 57's account of DEFECT-COL-001

1. **`busy_timeout` is already 30 s** on every connection (`storage/db.py:203`, and `timeout=30.0` on
   `sqlite3.connect`). The flush is not failing for want of patience; the prune's single transaction — **five
   `DELETE`s inside one `with self.db.connection as conn:`** in `storage/repository.py::prune_old_data`, the first of
   them `WHERE timestamp < ? AND id NOT IN (SELECT MAX(id) … GROUP BY coin)` over the 8.1 GB `asset_snapshots` —
   holds the write lock longer than 30 s. Chunking (your (b).1) is the fix; a longer timeout would only move the stall
   onto the flush thread.
2. **The prune lives in `storage/repository.py`, not `storage/db.py`**; `db.py` holds the connection and
   `checkpoint()`. `run_maintenance` calls `checkpoint("TRUNCATE")` at `repository.py:513` — your (b).2 is right
   about the mode.
3. **Python's bundled SQLite (3.45.3) is built without `DELETE … LIMIT`** (`PRAGMA compile_options` has no
   `ENABLE_UPDATE_DELETE_LIMIT`), so "5,000 rows per batch" must be written as
   `DELETE FROM t WHERE rowid IN (SELECT rowid FROM t WHERE … LIMIT 5000)` in a loop, one transaction per chunk. And
   `asset_snapshots`' keep-newest-per-coin subquery should be materialised once per pass, not re-run per chunk.
4. **Smaller.** The overflow cap has never tripped (`Write buffer overflow` appears 0 times in the log), so (a)'s
   "drop oldest only if saturated" will be exercised only by the restored batches themselves — worth a test that
   fills the buffer to `MAX_BUFFERED_TRADES` during a simulated lock. The lost trades are ~1 % of the feed, not a
   total outage; the 99 liquidation events are the part that matters to the cascade research.

## 3. Nothing else owed before the drill

- Operator (HOMEWORK.md): after 09-16 — "merge the slippage fix", "fix the collector", "start the t0030 paper
  runner". Dress rehearsal today or tomorrow; laptop on and logged in by 13:30 Wednesday.
- Me: nothing until a go-ahead. The three post-drill builds are specified (this letter, Sections 56–57, the audit).

## 4. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` paper runner | operator, after 09-16 |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | Merge `bugfix/engine-slippage-signs` (`9c87974`) into master | operator, after 09-16 |
| 7 | DEFECT-COL-001 fix — design as ruled, with §2's three corrections | operator go-ahead, after 09-16 |
| 8 | ~~Data gap registration~~ — **done, `dc451f5`**; extend the open gap when 7 deploys | — |
| 9 | Section 57 corrections (§2) — confirm | you |

One confirmation owed from you. Nothing owed from me before the drill.
