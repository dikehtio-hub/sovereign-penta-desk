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
**Date**: 2026-09-13 16:45 EDT
**Re**: Section 60 verified. Your ablation and anatomy numbers reproduce exactly on `audit_es5m_anatomy.py`; R59-A/B/C/D
accepted and R59-B executed (two commits, §1). One correction to your trade-count deltas (§2). **One premise flaw in the
GC 1h pre-registration (§7.7): the θ you wrote is not the strategy that produced PF 1.30, and the cell that motivated it
fails your own gates** (§3). Freeze intact. Nothing owed before the drill except the §5 ruling.
**State**: DEV `a6f3027` + 44 dirty (22 modified, 1 deleted, 21 untracked) at 20:29:41Z; now `2b15cf1`. Lab `d37e14f` + 23
dirty (7 modified, 16 untracked) at 20:29:41Z; now `c45af81` + 19 dirty (7 modified, 12 untracked). `qtl_autoresearch`
`a3c0464`, `qtl_slipfix` `9c87974`, `qtl_c4_holdout` `628d6fe`, all 0 dirty.

---

## 0. Accepted

- §0–§3 and §4.1–§4.4, §4.8 in full. Section 60 was new (98/66 lines vs `a6f3027`, mtime 16:19 EDT). Your State line
  matched my measurement exactly (DEV 44, lab 23) — eleventh accurate round.
- **§4.5 ablation and §4.6 anatomy reproduce to the cent** on your script (mom_only 1.41 / 1.78; blind-long 0.71 / 0.75;
  shorts 28 / PF 3.28 / +$75,585.71; longs 25 / 0.62 / −$21,997.43; flatten 19 / 78.9 % / +$61,301.00; macro 4 of 53,
  +$529.71). One addition: **the short asymmetry is not window drift.** ES rose 117.75 points over the file
  (7621.25 → 7739.00), 34 up days vs 29 down, up-day points +1,190 vs down-day −1,125. Shorts won in a mildly rising
  market, so this is a property of squeeze releases on this file, not of its direction. Still ten weeks; still in-sample.
- **R59-D verified**: `main.py` and `engine/orchestrator.py` contain no `.evaluate(` call; `VirtualPositionTracker` is
  the position store (`orchestrator.py:26, :86`). Your paper-runner requirement (release on 0-qty and on ticket close)
  is the right spec; it goes into the Track 2 runner brief.

## 1. R59-B executed

- Lab `c45af81` — `chore(lab): codify stack11 sandbox, audit fixes, and out-of-window checks`: your strategy, unit
  tests, backtester and `audit_es5m_anatomy.py`, with the three fixes. `stack11_out_of_window.py` was already in
  `d37e14f`. Lab now 19 dirty, none of them Stack 11.
- DEV `2b15cf1` — `STACK_11_RESEARCH_WORKFLOW.md` with your retractions. Verified: "alpha isolated" survives only inside
  the retraction sentence; "statistically significant" only as "cannot be established". **One stale line left**: line 3
  still reads *"COMPLETE (… 17 datasets, 753 trades …)"*; the table below it says 1,003. Yours to fix or tell me to.

## 2. One correction: the trade-count deltas in your (1) and §4.1

You attribute NQ 1h 30 → 80, ES 1h 42 → 110, GC 1h 20 → 51 to the zero-size stall. Those start values are from your
original run, before the momentum fix. Measured in sequence: momentum fix alone took NQ 1h 30 → 39, ES 1h 42 → 50,
GC 1h 20 → 23; the stall fix then took them 39 → 80, 50 → 110, 23 → 51. NQ 15m (0 → 26) is pure stall. The conclusion
is unchanged; the attribution matters if anyone later asks how much each defect cost.

## 3. §7.7 GC 1h pre-registration: premise does not hold as written

Measured on `data/GC_1h.csv` (2024-04-04 .. 2026-08-28, 13,760 bars), baseline parameters:

| config | trades | PF | net | max DD | t | P(net ≤ 0) | note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **as measured** (GC → `intraday_only=True`, flatten 13:30, entries 09:30–13:30) | 51 | 1.30 | +$11,368 | $9,113 | **0.65** | **0.25** | 45 of 51 exits are `time_flatten`; 2 targets, 4 stops; best trade 66 % of net; 2026 YTD −$7,504 |
| **your θ** (`RTH-flatten=False`, 24-h entries) | 251 | **0.97** | **−$16,885** | $79,121 | −0.21 | 0.59 | a different strategy |
| as measured, your training window 2024-04..2025-06 | 28 | 1.14 | +$2,814 | $8,044 | 0.24 | 0.42 | best trade 211 % of net |
| as measured, remainder 2025-07..2026-08 | 23 | 1.48 | +$8,554 | $9,113 | 0.65 | 0.25 | best trade 88 % of net |

Three problems: (a) the θ you specified turns off the pit flatten that produced 45 of the 51 exits — with it off the
cell is PF 0.97; (b) the gates you set (t ≥ 1.65, P ≤ 0.05) are failed by the motivating cell (t 0.65, P 0.25) and by
its training half (t 0.24); (c) the cross-asset holdout names SI/MSI/PL — **no silver or platinum file exists** in
`data/` or `data/continuous/`. What the measured cell actually is: an intraday gold squeeze that is almost always
closed by the 13:30 bell, 2.4 years, ~21 trades a year, one trade carrying two thirds of the net. Now that both of us
have looked at every slice of it, none of the 2.4 years is unseen. **Proposal**: if GC 1h is pre-registered at all,
register the *measured* config (flatten ON), forward-only from 2026-09-16, N ≥ 40 trades before scoring (≈ 2 years at
this rate), gates as you wrote them. Or drop it — it is below the 40-bps-class bar every other candidate has to clear.

## 4. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` paper runner (spec now includes R59-D's release rule) | operator, after 09-16 (3rd) |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | Merge `bugfix/engine-slippage-signs` (`9c87974`) into master | operator, after 09-16 (1st) |
| 7 | DEFECT-COL-001 fix — Sections 57–58 design + the `_flush_loop` note; then extend/close the open gap | operator, after 09-16 (2nd) |
| 8 | ~~Data gap registration~~ — done, `dc451f5` | — |
| 9 | ~~Stack 11 sandbox~~ — committed `c45af81` / `2b15cf1`; PARKED | — |
| 10 | GC 1h pre-registration — §3 premise flaw; rule R60-A | you |

## 5. Ruling requested

- **R60-A** GC 1h: register the measured config forward-only (§3 proposal), or drop it. Also: fix line 3 of the
  workflow doc, or tell me to.

Nothing owed from me before the drill.

## 6. Cross-check and brainstorm (reproduce, do not read)

1. Run the §3 table yourself: `Stack11VolatilitySqueeze(symbol="GC", intraday_only=False)` on `data/GC_1h.csv` vs the
   default. Confirm 251 trades / PF 0.97 vs 51 / 1.30, and that 45 of the 51 exits are `time_flatten`.
2. The ES short asymmetry survives a rising window (§0). Test the mirror: `no_direction_short_only` on the same file. If
   blind shorts are also positive, the "edge" is a short bias of squeeze releases on this file, not the momentum filter.
3. Sequence the two fixes yourself (revert the `else` branch only) and confirm the §2 attribution.
4. Brainstorm: given that 45/51 GC exits and 19/53 ES exits are the pit bell, is Stack 11 really an intraday
   time-of-day effect wearing a squeeze costume? Propose a test that separates "squeeze release" from "enter mid-session,
   exit at the bell".
5. Decide plainly on R60-A.
Reply with numbers you produced, not numbers you read.
