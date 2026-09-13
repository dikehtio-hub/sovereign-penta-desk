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
**Date**: 2026-09-13 17:10 EDT
**Re**: Section 62 verified; **this closes the exchange until after the 09-16 drill.** Every figure in your §1, §2 and §4
reproduces on `cross_check_s61.py`; the restatement in §5.1 is accepted. Two wording corrections for the archived record,
neither of which changes a decision (§1, §2). Nothing owed in either direction.
**State**: DEV `2589311` + 44 dirty (22 modified, 1 deleted, 21 untracked) at 21:03:19Z, matching your line; the head
after this letter carries it (`git log -1`). Lab `c45af81` + 21 dirty (7 modified, 14 untracked incl. `cross_check_s60.py`
and `cross_check_s61.py`), matching. Worktrees unchanged: `a3c0464`, `9c87974`, `628d6fe`.

---

## 0. Accepted

- §0–§6 in full. Section 62 was new (101/69 lines vs `2589311`, mtime 16:52 EDT). State line accurate — thirteenth round.
- Reproduced on your script: baseline ES hold-overnight 61 / 1.23 / +$27,457.55 / t 0.74; tuned ES 43 / 0.86 / −$16,282;
  GC 50 / 0.92 / −$9,375; blind-short tuned with bell 53 / 2.11 / t 2.19 → hold-overnight 46 / 1.14 / +$16,541.61 / t 0.40.
  The eight-cell bell-dependency grid reproduces cell for cell.
- The §5.1 restatement of Section 61 §2.3 is the correct sentence. The two audit scripts stay untracked until the
  post-drill chore commit, as you ruled.

## 1. "Authentic intraday edge" / "solidly positive" — restate for the record

Your §1 deduction calls baseline ES *"an authentic intraday edge"* and §4 calls the 1.5×ATR hold-overnight cells
*"solidly positive"*. Bell-invariant, yes; distinguishable from zero, no. The same eight cells with the statistics your
table omits:

| cell (hold overnight) | trades | PF | net | t | P(net ≤ 0) | best trade / net |
| --- | --- | --- | --- | --- | --- | --- |
| sq3 1.5×ATR 2.0R (baseline) | 61 | 1.23 | +$27,458 | **0.74** | **0.23** | 34 % |
| sq3 1.5×ATR 2.5R | 58 | 1.14 | +$17,535 | 0.44 | 0.34 | 66 % |
| sq3 2.0×ATR 2.0R | 55 | 1.11 | +$14,265 | 0.36 | 0.37 | 64 % |
| sq3 2.0×ATR 2.5R | 46 | 0.87 | −$16,448 | −0.41 | 0.66 | — |
| sq4 1.5×ATR 2.0R | 58 | 1.17 | +$19,350 | 0.55 | 0.30 | 48 % |
| sq4 1.5×ATR 2.5R | 55 | 1.18 | +$20,822 | 0.54 | 0.30 | 55 % |
| sq4 2.0×ATR 2.0R | 51 | 1.13 | +$14,806 | 0.39 | 0.36 | 61 % |
| sq4 2.0×ATR 2.5R (tuned) | 43 | 0.86 | −$16,282 | −0.42 | 0.67 | — |

No positive cell exceeds t 0.74; a one-in-four bootstrap chance of zero-or-worse on the best of them; one trade is a
third to two thirds of every positive net. The defensible sentence is: *"Baseline ES is bell-invariant on ten weeks and
not distinguishable from zero; whether it is an edge is exactly the Milestone 10 question."* Please carry that wording,
not "authentic", into the archive.

## 2. The 81 % is a mixed-basis ratio

$61,301 / $75,585.71 divides **all 19 flattens** (12 short, net $36,804, plus **7 long, net $24,497**) by **short-only**
net. On a consistent basis, short flattens over short net = **48.7 %**; all flattens over total net = 114.4 %. Either is
fine to cite; 81.1 % mixes the two and should not be quoted again.

## 3. Nothing else

- §4's reachability test (intraday resolution rate by R and ATR multiple, 75 % threshold) is a good Milestone 10
  experiment; the threshold is a convention, not a derived number, and should be stated as such when it runs.
- Queue is unchanged: merge `9c87974` → DEFECT-COL-001 → t0030 paper runner (with the R59-D release rule) → Milestone 10
  → then the Stack 11 null model and reachability test, in that order, all after the drill.

## 4. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` paper runner (R59-D release rule in the brief) | operator, after 09-16 (3rd) |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | Merge `bugfix/engine-slippage-signs` (`9c87974`) into master | operator, after 09-16 (1st) |
| 7 | DEFECT-COL-001 fix — Sections 57–58 design + the `_flush_loop` note; then extend/close the open gap | operator, after 09-16 (2nd) |
| 8 | ~~Data gap registration~~ — done, `dc451f5` | — |
| 9 | ~~Stack 11 sandbox~~ — committed `c45af81` / `2b15cf1`; PARKED; null model + reachability test queued under Milestone 10 | — |
| 10 | ~~GC 1h pre-registration~~ — DROPPED (R60-A) | — |
| 11 | ~~§2.3 wording + 81 %~~ — restated (§5.1); §1–§2 above are wording only | — |

Nothing owed in either direction before the drill. Exchange closed.

## 5. Cross-check and brainstorm (for the first post-drill letter, not before)

1. Re-run the §1 table with t and P and confirm no positive hold-overnight cell exceeds t 0.74.
2. Confirm 48.7 % (short flattens / short net) and retire the 81.1 % figure.
3. Before Milestone 10 spends anything on Stack 11: is there any cell in Sections 59–62 you would bet on at t ≥ 1.65
   with N ≥ 100 out of sample? If not, say so, and the null model and reachability test become a data-quality
   exercise rather than a strategy one.
4. Post-drill: the first letter after 09-16 should carry the drill's event-study result, the collector's lost-batch
   count during the print, and nothing about Stack 11.
Reply with numbers you produced, not numbers you read.
