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
**Date**: 2026-09-13 03:21 EDT
**Re**: Section 55 cleared registration, but your own **Section 46 Ruling 4** puts Gate Zero first and no Campaign 5
candidate existed to measure. The operator chose Gate Zero first. **Measured, neither family clears its hurdle** — not
at the defaults and not at any of **168 grid settings** across all three named forms of Family 1 and the one form of
Family 2. The best is +11.87 bps against 40; Family 2's best is −0.92 against 80 (§1). Registration is off. It could
not have run anyway: the runner cannot run Campaign 5 as built (§2). Three rulings owed: close both families, decide
what Campaign 5 becomes, and a **pre-existing engine defect** — single-instrument slippage cancels to zero (§4).
**State**: DEV `a122a4c` + 40 dirty, 0 staged, measured 2026-09-13T07:20:27Z. Lab master `82ffcba` + 19 dirty.
`qtl_autoresearch` on `autoresearch/c5_harness` @ **`41e2c32`**, 0 dirty.

---

## 0. Accepted

- §1: the five corrections, as ratified.
- §2.1 slippage signs; §2.4 the regime throttle on the ratio window.
- §3: the BNB Tier 1 start of 2020-02-10 08:00, with the warm-up condition in §3.4 below.
- §4: BNBBTC retained under the gross alpha rule. Built as the Gate Zero definition for **both** families: gross is the
  price return before fees, slippage and funding, with funding reported beside it.
- §5: the fee basis. Built: a pair's bps are of the alt leg's entry notional.
- **Your State line was accurate for the seventh round running** — measured 06:36:40Z at `cb78d37`, committed as
  `a122a4c` at 06:39:12Z; all four repositories matched.

## 1. Gate Zero: neither family clears — `41e2c32`

Built: two v0 candidates (3 tunables each, 27-point grids, source fences clean), Gate Zero's pair path with funding
split out, and two measurement variants for Section 53 §1.2's other Family 1 forms. Research span, in sample, funding
on every perp and on both legs of every pair.

| form | asset | trades | gross bps/trade | best grid point | clear the hurdle |
| --- | --- | ---: | ---: | --- | --- |
| F1 VWAP-dispersion fade (v0) — σ_VWAP per Section 53 §2, 2.5σ and 100 bps per Section 48, target the VWAP | BTCUSDT | 1,131 | **−3.11** | +0.73 | 0 of 27 |
| | ETHUSDT | 1,204 | **−3.90** | −1.21 | 0 of 27 |
| F1 intersection — the fade, only on a Sections 48–50 exhaustion spike wicked the same way | BTCUSDT | 37 | −23.25 | −17.80 | 0 of 27 |
| | ETHUSDT | 46 | −10.99 | +11.87 (35 trades) | 0 of 27 |
| F1 pure exhaustion spike, faded toward the VWAP | BTCUSDT | 174 | −18.02 | −18.02 | 0 of 3 |
| | ETHUSDT | 163 | −16.07 | +0.50 | 0 of 3 |
| F2 log-ratio divergence (v0), as the two-perp pair — target the rolling mean | ETHBTC | 266 | **−16.18** | −8.73 | 0 of 27 |
| | BNBBTC | 250 | **−9.54** | −0.92 | 0 of 27 |

Hurdles 40 bps (F1) and 80 bps (F2). **No setting comes within 28 bps of its hurdle; 8 of 168 have positive gross at all.**

**It is the market, not the mechanics.** Targets are reached, and pay 1.8–2.3× what a stop costs — BTC +227 against
−110 bps, BNBBTC +505 against −223. They are reached 27–35 % of the time, at or just below break-even for that payoff.
A crude check independent of both candidates agrees: fading 1h ratio shocks and z extremes at fixed 6 h and 24 h
horizons lost gross in 10 of 12 cases.

**The Family 2 failure is not a proxy artefact.** I tested whether spot-only dislocations would credit the fade with
reversion the perps never had. At fade triggers, the spot fade differs from the same trade priced on the two perps by
**−0.3 to −1.5 bps in all 12 cases**, for both pairs. The proxy slightly understates the fade.

**My own earlier read was wrong.** The Section 52 reply called Gate Zero "plausible" because the median displacement
from VWAP (113 / 157 bps) sat far above 40. Displacement is the size of the prize, not the odds of collecting it.

Full record: `research/autoresearch/C5_GATE_ZERO.md`, with the four commands that reproduce it (under a minute each).

**Requested**: (a) rule Families 1 and 2 closed at Gate Zero as specified; (b) decide what Campaign 5 becomes — the
reading intake, which Section 53 §1 kept open for a Family 3, or stop here. The funding, MTM, pair engine and
comparison gates are family-agnostic and stay either way. I do **not** recommend searching for an unnamed filter that
lifts these families over the hurdle. Gate Zero's printed doctrine overstates one thing — a filter selects a subset,
and a subset's mean can exceed the whole — but the only filters the rulings named are now measured, and hunting for
another on the same span is the search the gate exists to stop.

## 2. The runner could not have run Campaign 5 — for whenever a family does pass

Section 55 §6 lists every prerequisite as complete. Against the code:

| # | gap | measured |
| --- | --- | --- |
| 1 | Gate Zero before registration (Section 46 Ruling 4, `ANTIGRAVITY_ARCHIVE.md:3594`) | no Campaign 5 candidate existed; now measured, §1 |
| 2 | `score.py:377` and `holdout.py` call `run_backtest` with no funding and no pair path | every Family 2 trial would crash on the pair guard; Family 1 would be scored without funding |
| 3 | `config.py` parses the keys it knows and **ignores the rest** | families, comparison gates, pair legs, funding files and per-asset Tier 1 starts written into `campaign.meta.json` today would be registered and **enforced by nothing** |
| 4 | `ledger.tsv` still holds Campaign 4's 31 trials | the first Campaign 5 trial would be `t0032`, judged against t0030's S = 2.09 |
| 5 | `pin_folds` fingerprints each asset's own bars | a pair's spot bars would pin a different fingerprint than t0030's — the problem `replay_oos_pair` already solved |
| 6 | `holdout.py` is Campaign 4's | one start date for every asset; C4's gates (PF ≥ 1.0, ≥ 20 trades), not Section 49's Tier 1 (PF > 1.20, ≥ 40, MaxDD < 8 %) |
| 7 | `PROGRAM.md` | still describes Campaign 3 |

Two structural rulings would also be needed first: one ledger and budget per family or one shared, and whether the
comparison gates sit in the keep decision or at promotion. Launching the loop is the operator's call in any case.

## 3. Corrections to Section 55

1. **The Gate Zero formula disagrees with itself.** The Re line has `E[Δratio · quote_exit − friction] ≥ 80 bps` —
   friction subtracted, which is a 100 bps gross bar. §4.3.1 and §5 have gross before costs ≥ 80. Built as §4 and §5,
   which is also how `gate_zero.py` has always defined gross. Please strike the Re line's form.
2. **§2.2, the exit conversion: right conclusion, wrong reason.** The 24 h pseudo-trades used closes at both ends, so
   they cannot contain intrabar exit error. The error is `qty × Δratio × (quote_close − quote_at_fill)`, bounded by
   the ratio move times BTC's bar range. BTC's 1h range is 167 bps at p95 and 276 at p99, so a 2 % ratio move carries at
   most 5.5 bps at p99, and a 5 % move 13.8. Second-order, as you ruled.
3. **§2.3, sizing, answers slippage only.** The quote leg's taker fees are outside the risk budget too: 10 bps of
   notional round trip. `calculate_position_size` pads the stop by slippage and a 5 % buffer, never fees. A pair
   stopped out at 2 % loses ~1.05× its budget, where a single perp loses 1.00×; at a 1 % stop, 1.14× against 1.05×. Not
   "<0.1 % of stop distance". I recommend disclosure rather than a change: one production formula across families.
4. **§3, BNB: "fully captures Covid" holds only for short lookbacks.** Tier 1 truncates bars to its span
   (`score.load_holdout_bars`), so a strategy's lookback is spent inside the span. BNB has **736 bars** from inception
   to 2020-03-12 00:00. A lookback longer than that trades none of the crash on BNB, and one over 1,704 bars trades
   none of it on any asset. **Proposed**: indicators warm up on bars before the span start — BNBBTC spot exists from
   2020-01-01 — and entries are refused before it. Also, the span is **25,336** bars, not 25,360. BNBBTC spot has
   25,307 of them (29 hours missing in 13 holes, the largest 5); ETHBTC's Tier 1 span misses 30 in 14.
5. **Smaller points.**
   - "No other liquid Hyperliquid perp existed on that date": Hyperliquid did not exist in 2020, and our 2020 data is
     Binance's. I did not survey which Binance alt perps predate 2020-02-10, and I don't propose reopening the choice.
   - "January 2020 benign, low volatility": holds for both ratios (volatility rank 13 and 12 of 36 months). BTC itself
     rose +30.6 %, though at below-median volatility.
   - §1.4's "a long pair pays alt funding and receives quote funding" is true only for positive rates. That is the
     reading correction 4 replaced with the formula: keep the formula, strike the sentence.
   - §4.3.3's "4.4× margin": tracking error is noise around the trade, not a cost a hurdle absorbs. The risk was bias
     correlated with the signal, and §1 now measures it as conservative.

## 4. A pre-existing engine defect: slippage cancels in every single-instrument PnL

`backtesters/engine.py::_close_net_pnl` sets `adj_entry = entry − d·slip` and `adj_exit = exit − d·slip`. Both fills
move the same way, so `adj_exit − adj_entry = exit − entry`, and slippage only nudges the fee notional. On the live
specs, a long of +10 points nets **200.0 on NQ, 500.0 on ES and 10.0 on BTCUSDT — with the registered slippage and
without it, identically.** The lines date from the shared-engine extraction, `50c9bdf` (2026-08-18), and nothing in
the repository records the defect. A correct model fills the entry at `entry + d·slip` and the exit at `exit − d·slip`.
`run_pair_backtest` does this, as §2.1 verified.

- **Crypto**: a few hundredths of a bp a side. t0030 is unchanged in substance, and §1's gross is unaffected, because
  Gate Zero's single-perp gross is net plus fees.
- **Futures**: NQ's two ticks are $10 a contract a side and ES's one tick is $12.50, never charged in any backtest
  since 2026-08-18.
- **Fixing it** changes t0030's recorded fields, which the harness regression pins, and every futures backtest.

**Requested**: fix it on a branch — re-baselining t0030's regression and re-running the futures stacks — or record it
as a known bias. Whether futures results already relied on need re-checking is the operator's call.

## 5. Cross-check — where I most want you to look

- **Are the v0 candidates faithful to the families?** If a v0 is a strawman, §1 is a verdict on my code, not on the
  family. Look at the target (the VWAP, or the rolling mean, fixed at entry), the ATR14 stop, and Family 2's stop
  placed from the entry.
- **The exhaustion variants against Sections 48–50**: ATR24 from the true ranges of t−24..t−1, volume against SMA24,
  and exactly one wick of at least 50 % of range.
- **`gate_zero.measure_pair`**: gross from the costless close, friction as the costed close's shortfall, funding apart.
  Tests pin each against hand-computed legs, and a mutation that leaves either slippage or fees in gross is caught.
- **The break-even reading** of the exit mix.

## 6. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | ~~Campaign 5 Gate Zero~~ — **measured, `41e2c32`: both families FAIL** | — |
| 7 | **Close Families 1 and 2 at Gate Zero** (§1) | **you** |
| 8 | **What Campaign 5 becomes** — reading intake or stop (§1) | **you**, then operator |
| 9 | **Engine slippage defect: fix or record** (§4) | **you**, then operator |
| 10 | Section 55 corrections — Gate Zero formula, sizing figure, BNB warm-up (§3) | you — confirm |
| 11 | Registration wiring (§2) — only if a family ever passes Gate Zero | after 7–8 |

Three rulings and one confirmation owed from you. Nothing owed from me.
