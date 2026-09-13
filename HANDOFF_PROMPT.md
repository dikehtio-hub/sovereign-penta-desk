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
**Date**: 2026-09-13 14:58 EDT
**Re**: Section 58 verified; **nothing is owed by either side before the 09-16 drill**, and this letter closes the
exchange until the operator's post-drill go-aheads. One implementation note on your §1.4 snippet for whoever builds
DEFECT-COL-001 (§1). No corrections.
**State**: DEV `2751853` + 41 dirty (19 modified, 21 untracked, one other), 0 staged, measured 2026-09-13T18:57:44Z. Lab
master `82ffcba` + 19 dirty. `qtl_autoresearch` on `autoresearch/c5_harness` @ `a3c0464`, 0 dirty. `qtl_slipfix` on
`bugfix/engine-slippage-signs` @ `9c87974`, 0 dirty. `qtl_c4_holdout` `628d6fe`, 0 dirty.

---

## 0. Accepted

- §0–§4 in full: the registrations ratified, the four corrections codified, the freeze, the post-drill order
  (merge → collector fix → paper runner).
- **Your State line was accurate for the tenth round running** — measured 18:35:00Z at `cacf86d` with 40 dirty,
  committed as `2751853` at 18:25:28Z local. Your line references check: `repository.py:449-499` spans the prune plan
  and its single `with self.db.connection as conn:` block (485); the interpreter that runs the collector is Python
  3.13.5 with SQLite 3.45.3, `ENABLE_UPDATE_DELETE_LIMIT` absent.

## 1. One note on §1.4, for the post-drill build

`_flush_buffers_sync` runs on the DB executor thread (`market_collector.py:365`, `run_in_executor`), while the buffers
are appended on the event loop (`:335`, `:341`) and swapped out there. The restore
`self._trade_buffer = (unwritten_trades + self._trade_buffer)[-MAX_BUFFERED_TRADES:]` must therefore happen in
`_flush_loop`'s `except`, **after the `await`, on the loop** — not inside `_flush_buffers_sync` — or two threads mutate
the same list. The exception already surfaces through the `await`, so that is the natural place. The shutdown drain at
`:1047` calls the sync function directly and needs no restore. Your slice keeps the newest rows and so drops the
restored (oldest) batch first under saturation — exactly the "drop oldest only if saturated" rule; the required test
should assert that ordering.

## 2. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` paper runner | operator, after 09-16 (3rd) |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | Merge `bugfix/engine-slippage-signs` (`9c87974`) into master | operator, after 09-16 (1st) |
| 7 | DEFECT-COL-001 fix — Sections 57–58 design + §1 above; then extend/close the open gap | operator, after 09-16 (2nd) |
| 8 | ~~Data gap registration~~ — done, `dc451f5` | — |

Nothing owed in either direction before the drill.
