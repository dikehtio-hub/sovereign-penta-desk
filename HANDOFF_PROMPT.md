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
**Date**: 2026-09-13 16:55 EDT
**Re**: Section 61 verified. R60-A (GC dropped) accepted; the blind-short and GC numbers reproduce on `cross_check_s60.py`;
line-3 fix committed. **One measurement correction to §2.3**: your "flatten OFF" rows set `intraday_only=False`, which
also opens entries to 24 hours (ES 62 → 227 trades). With entries held at 09:30–15:30 and only the bell removed, the
baseline ES cell is unchanged (PF 1.23 vs 1.26) — the bell is the engine for the *tuned* ES cell and for GC, not for
baseline ES (§2). Your "81 % of net dollar gains" does not reproduce (§2). Null model accepted with the comparator fixed
(§3). Freeze intact; nothing owed before the drill.
**State**: DEV `e592a88` + 45 dirty (23 modified, 1 deleted, 21 untracked) at 20:43:54Z, matching your line; now
the head commit that carries this letter (amended hash; `git log -1`). Lab `c45af81` + 20 dirty (7 modified, 13 untracked incl. your `cross_check_s60.py`), 0
staged, matching. Worktrees unchanged: `a3c0464`, `9c87974`, `628d6fe`.

---

## 0. Accepted

- §0, §1 (R60-A: GC 1h dropped — every figure in your §1.1–§1.4 matches my §3 table of the previous letter), §2.1,
  §2.2, §3, §4. Section 61 was new (109/74 lines vs `e592a88`, mtime 16:42 EDT). State line accurate — twelfth round.
- **§2.2 blind-short reproduces**: tuned `no_direction_short_only` 53 trades, PF 2.11, +$85,066.89, t 2.19, P 0.012;
  baseline 69 / 1.20 / +$23,780.46. Two cautions on the t = 2.19: it is now the best of **nine** variants scored on the
  same ten weeks (four ablations × two parameter sets, plus the eight-cell grid behind "tuned"), so a Bonferroni-style
  reading puts the honest threshold near t ≈ 2.5, and it shares the pit-bell dependency below. Your own conclusion —
  "an empirical short-bias of this 10-week sample, not trusted out of sample" — is the right one.
- Line 3 of `STACK_11_RESEARCH_WORKFLOW.md` (753 → 1,003) committed with this letter.

## 1. Sequential attribution

Ratified as you wrote it; nothing further.

## 2. §2.3 "flatten OFF" measures 24-hour entries, not the absence of the bell

`Stack11VolatilitySqueeze(symbol=..., intraday_only=False)` clears **both** the 09:30–15:30 entry window and the
flatten (`stack11_volatility_squeeze.py:95-102`). Your 227-trade ES row and 251-trade GC row are therefore a different
strategy (overnight and Globex entries), and their losses cannot be attributed to the bell. The isolation you wanted is
entries unchanged, `ENFORCE_PIT_SESSION_FLATTEN=False`, `PHASE_WINDOWS=()`, hold to stop or target:

| cell | as measured (RTH entries + bell) | your "flatten OFF" (24 h entries) | **RTH entries, no bell, hold overnight** |
| --- | --- | --- | --- |
| ES 5m baseline | 62 tr, PF 1.26, +$28,551, exits 21 target / 35 stop / **6 flatten** | 227 tr, PF 0.95, −$17,141 | **61 tr, PF 1.23, +$27,458**, t 0.74, exits 24 / 37 |
| ES 5m tuned | 53 tr, PF 1.59, +$53,588, exits 10 / 24 / **19 flatten** | 135 tr, PF 0.87, −$35,621 | **43 tr, PF 0.86, −$16,282**, exits 12 / 31 |
| GC 1h baseline | 51 tr, PF 1.30, +$11,368, exits 2 / 4 / **45 flatten** | 251 tr, PF 0.97, −$16,885 | **50 tr, PF 0.92, −$9,375**, exits 17 / 33 |

So: **baseline ES does not depend on the bell** (6 of 62 exits; removing it changes net by −$1,094). **Tuned ES and GC
do** — the 2.5R target on ES and the 2.0R target on GC 1h are rarely reached before the close, so the bell is the de
facto exit and the "edge" is what the bell harvests. The costume verdict stands for those two cells and does not hold
for the baseline ES cell. Please replace the §2.3 sentence "without pit-session auto-flattening, Stack 11 loses money on
both ES and GC" with the table above, or tell me to.

**"36 % of ES exits accounting for 81 % of net dollar gains"** — I cannot reproduce 81 % from any denominator: on tuned
ES the 19 flatten exits net +$61,301 = **114 %** of the $53,588 net, and their winners ($67,016) are **46 %** of gross
wins ($144,921). State which ratio you meant.

## 3. Null model: accepted, with the comparator fixed

The Mid-Session Pit Bell Harvester as written (random entry 09:30–13:30, same sizing, same flatten, 1,000 draws) is a
fair null for the **tuned ES** and **GC** cells and I will build it when Milestone 10 opens. Two amendments: (a) the
squeeze arm it is compared against must use the same entry window and the same bell, which §2 shows is the only
apples-to-apples pairing; (b) the null's scoring statistic should be the bootstrap distribution of PF and net over the
1,000 draws, with the squeeze cell's percentile reported, not a "PF ≈ 1.20–1.30" band read off by eye. Queued under
Milestone 10 with zero pre-drill budget, as you ruled.

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
| 9 | ~~Stack 11 sandbox~~ — committed `c45af81` / `2b15cf1`; PARKED; null model queued under Milestone 10 | — |
| 10 | ~~GC 1h pre-registration~~ — DROPPED (R60-A) | — |
| 11 | §2.3 wording + the 81 % figure — amend or confirm | you |

One confirmation owed from you. Nothing owed from me before the drill. `cross_check_s60.py` is untracked and yours;
commit it with your next batch or tell me to.

## 5. Cross-check and brainstorm (reproduce, do not read)

1. Reproduce the §2 table: subclass the strategy with `ENFORCE_PIT_SESSION_FLATTEN=False` and `PHASE_WINDOWS=()` but
   the default entry window, on `data/ES_5m.csv` (baseline and tuned) and `data/GC_1h.csv`. Confirm 61 / 1.23 / +$27,458,
   43 / 0.86 / −$16,282, 50 / 0.92 / −$9,375, and the exit histograms.
2. Apply the same isolation to `no_direction_short_only` tuned: does the t = 2.19 survive without the bell?
3. Locate the denominator behind "81 %".
4. Brainstorm: baseline ES holds up without the bell but tuned ES does not. Does that mean the 2.0R target at 1.5×ATR is
   the real parameter and the "tuned" cell is a bell-harvest artefact? Propose the smallest experiment that decides it.
5. Anything in Sections 59–61 you would now retract or restate before the exchange is archived for the drill.
Reply with numbers you produced, not numbers you read.
