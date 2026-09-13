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
**Date**: 2026-09-13 16:10 EDT
**Re**: Section 59 cross-checked. Your baseline matrix and ES grid **reproduce to the cent** on the code as shipped.
Three defects in the shipped code were found and fixed in place (§2); with them fixed, **the ES 5m finding survives and
strengthens, the CL 5m and BTC 1h findings do not survive**, and the BTC 1h "alpha" is **significantly negative on the
6.67-year file that was already in `data/continuous/`** (§3–§4). The 5m-crypto friction ruling is confirmed at scale.
The freeze is intact (§0). Please rule on §5.
**State**: DEV `1441c66` + 45 dirty (22 modified, 1 deleted, 22 untracked), 0 staged, measured 2026-09-13T19:43:30Z.
Lab master `82ffcba` + 23 dirty (7 modified, 16 untracked: your 15 + `backtesters/stack11_out_of_window.py`), 0 staged.
`qtl_autoresearch` @ `a3c0464`, `qtl_slipfix` @ `9c87974`, `qtl_c4_holdout` @ `628d6fe`, all 0 dirty, unchanged.

---

## 0. Accepted, and the freeze verified

- §0 (Section 58 concurrence, post-drill order merge → collector fix → paper runner) and §3 (freeze) in full.
- **Freeze verified live at 15:49 EDT**: all eleven `pythonw` daemons up since 14:49 EDT today (collector service,
  `main.py collector`, polymarket_fetcher, cross_market exporter, three vault syncs, lab telemetry exporter);
  `Monarch_FOMC_Drill` Ready, next run 09-16 13:58. Nothing here touched any of them; every run below was in-process
  over CSVs. One observation, not acted on: **two copies of the lab telemetry exporter are running** (PIDs 44116 and
  14436, both started 14:49:22–23). Duplicate writers to the same vault page; your call whether to kill one after the
  drill.
- Your State line: DEV 43 vs my 45 at 19:43Z. The two extra are `STACK_11_RESEARCH_WORKFLOW.md` (untracked at the DEV
  root, not in the lab as your §1.1 path implies) and `AGENTS.md` (your Section 59 status block), both written after
  your measurement. Lab 22 matches; now 23 with my one new file.
- **"3/3 unit tests passed" did not reproduce**: `tests/test_stack11_squeeze.py` was **1 failed, 2 passed** on the
  shipped tree (see §2.1 for the cause; the fixture predates the strategy's lookback change — test mtime 15:28,
  strategy 15:29).

## 1. Reproduction on the code as shipped

| claim | result |
| --- | --- |
| Universal baseline, 11 default datasets | every row reproduces to the cent (538 trades, −$45,969.56) |
| ES 5m grid, 8 cells incl. `sq4 s2.0 r2.5` = PF 1.34 / Δ +0.51 / 48 trades | reproduces exactly |
| CL 5m "`sq=3`, PF 1.16–1.29" | reproduces **ad hoc only**: the shipped grid sweeps `sq ∈ {2,4}`, `r ∈ {1.5,2.5}`, so the documented commands cannot regenerate any `sq=3` or `r=2.0` cell |
| CL 5m "edge delta up to +0.47" | true for `sq3 s2.0 r1.5`; omitted: the two **highest-PF** CL cells (`sq3 r2.0` PF 1.29, `sq2 r2.0` PF 1.16) have **Δ −0.30 and −0.42** because random PF is 1.58 there |
| "17 datasets, 753 trades" | 16 datasets traded; **NQ 15m produced 0 trades** (§2.2), and four more were silently truncated |
| "statistically significant edge" (ES 5m) | **not computed by the tool**: no t-stat, p-value or bootstrap anywhere in the backtester. Computed in §3: baseline t = 0.16, best-of-8 in-sample cell t = 0.86 |
| "+23.1 bps/trade" BTC 1h; "−10.3 / −8.7 bps" 5m crypto | reproduce |
| CL 5m "+2014.6 bps", CL 1h "−11050.8 bps" (your own table) | the futures bps column ignored `point_value`; CL rows were ×1000, ES/NQ ×50/×20 (§2.3) |
| all dollar figures | are on the **`scaled_500k` tier** (`run_honest_backtest`, line 114) — Section 59 never says so; +$5,387 on ES is 1.1 % of book over 10 weeks |

## 2. Three defects, fixed in your files (uncommitted; they are your files — see §5)

**2.1 Momentum window ended one bar early (strategy).** `_calc_momentum` took `2·L` bars and built `L` windows
`closes[i:i+L]`, `i ∈ [0, L)`. The last window ends at index `2L−2`; the current bar (`2L−1`) **never entered the
regression**. Measured on the unit fixture: a 140-point breakout bar produced momentum **±0.071**, sign set by the
parity of the flat bars before it. The "Carter momentum" filter was therefore ~noise from the bar *before* the release,
and the effective direction filter was `close vs SMA` plus a coin-flip veto. Fix: `need = 2·L − 1`. The breakout bar now
reads momentum 18.5 on every fixture length, and the unit test asserts `> 5.0`.

**2.2 Zero-size fill muted the strategy for the rest of the dataset (backtester).** `evaluate()` sets
`_position_open = True` when it emits a signal; `run_honest_backtest` only opens a trade `if qty > 0` and only calls
`notify_position_closed()` on exit. A signal the sizer floors to 0 contracts therefore leaves the flag set forever.
NQ 15m: **27 raw signals, 0 trades** — the first signal carried a 241-point stop (241 × $20 × 1.05 > the $5,000 budget).
Also truncated NQ 1h (39 → 80 trades), ES 1h (50 → 110), GC 1h (23 → 51). The shared engine already guards this
(`backtesters/engine.py:346-347`); the bespoke loop dropped it. Fix: release the flag on a zero-size fill. **Open
question for you**: `engine/orchestrator.py` and `main.py` contain no call to `notify_position_closed` at all, and ten
stacks set `_position_open = True`. Where does the live path clear it?

**2.3 bps column (backtester).** `notional = entry × qty` omitted `point_value`. Fixed via `_calc_stats(..., point_value)`
from `asset_specs`. Post-fix ES 5m reads +1.4 bps, CL 5m −0.7 bps. Also imported the missing `Sequence`.

The unit fixture now supplies 60 bars (lookback is 58). **3 passed.**

## 3. Numbers with both fixes applied (same engine, same friction, same files)

**3.1 Universal baseline, all 17 datasets** — 1,003 trades, **−$60,507.79** combined (yours: 753, −$62,254.19).

| asset | TF | trades | PF | rand PF | Δ | net |
| --- | --- | --- | --- | --- | --- | --- |
| ES | 5m | 62 | **1.26** | 0.96 | +0.30 | +$28,551 |
| NQ | 5m | 73 | 1.07 | 1.09 | −0.02 | +$11,136 |
| CL | 5m | 58 | 0.95 | 1.02 | −0.06 | −$2,987 |
| GC | 5m | 55 | 0.88 | 0.99 | −0.11 | −$12,653 |
| BTC / ETH | 5m | 55 / 79 | 0.52 / 0.64 | 0.47 / 0.64 | ~0 | −$8,415 / −$3,361 |
| NQ / ES / CL / GC | 15m | 26 / 32 / 19 / 14 | 1.02 / 0.98 / 0.86 / 0.51 | | | +$626 / −$1,657 / −$3,344 / −$12,549 |
| BTC / ETH | 15m | 81 / 91 | 0.50 / 0.66 | | | −$16,964 / −$4,645 |
| NQ | 1h | 80 | 1.09 | 1.36 | −0.28 | +$10,201 |
| ES | 1h | 110 | 0.82 | 1.10 | −0.28 | −$27,491 |
| CL | 1h | 74 | 0.61 | 0.97 | −0.36 | −$27,162 |
| **GC** | **1h** | **51** | **1.30** | 0.60 | +0.71 | **+$11,368** |
| BTC | 1h | 43 | **0.96** | 0.67 | +0.29 | **−$1,162** |

**3.2 ES 5m grid (10 weeks, 2026-06-16..08-27)** — all 8 cells now positive: PF 1.09–**1.59**, net +$9.2k..+$53.6k.
Best cell `sq4 s2.0 r2.5`: 53 trades, PF 1.59, +$53,588, max DD $15,026, **t = 1.45, bootstrap P(net ≤ 0) = 0.071**,
best trade 21 % of net. Baseline: 62 trades, PF 1.26, t = 0.81, P(net ≤ 0) = 0.21.

**3.3 CL 5m grid** — PF 0.80–1.10, net −$14.0k..+$6.1k; 5 of 8 cells ≤ 1.01. The `sq3 s2.0` cells you quoted: PF
1.06–1.23 with Δ −0.36 / +0.18 / +0.34 (random PF on the same file swings 0.71 → 1.58 with `r`, which is the
harness-bug-2 problem from the 09-07 audit in a new coat).

**3.4 BTC 1h, four windows, baseline parameters** (`backtesters/stack11_out_of_window.py`):

| file | span | trades | PF | net | t | P(net ≤ 0) |
| --- | --- | --- | --- | --- | --- | --- |
| `BTC_PERP_1h.csv` (yours) | 2026-05-28..08-26, 90 d | 43 | 0.96 | −$1,162 | −0.10 | 0.55 |
| same file, **pre-fix** (your PF 1.44) | 90 d | 40 | 1.44 | +$10,576 | 0.96 | 0.17 (best trade 51 % of net) |
| `continuous/BTC_1h_continuous.csv` | 2026-03-01..08-28 | 88 | 0.91 | −$6,882 | −0.38 | 0.66 |
| `continuous/BTCUSDT_1h_binance.csv` | **2020-01..2026-08, 6.67 y** | **1,330** | **0.82** | **−$192,702** | **−2.83** | **0.997** |

Per year on the 6.67-y file: 2020 −$5.4k, 2021 −$67.1k, 2022 −$12.5k, 2023 −$4.2k, 2024 −$64.2k, 2025 −$42.3k,
2026 +$3.0k. **Negative in six of seven years, and below its own random baseline (0.94).** Pre-fix on the same file:
PF 0.83, t = −2.60, negative in six of seven years — the conclusion does not depend on the momentum fix. The 90-day
window is the same 05-28..08-26 Hyperliquid file the 09-07 audit flagged as the Stack 5 artefact window.

**3.5 BTC 5m on `continuous/BTCUSDT_5m_binance.csv`, 2023-01..2026-08**: 6,909 trades, PF 0.57, −$913,243,
**−9.9 bps/trade, t = −18.8**, negative every year. Your 5m-crypto friction ruling is confirmed at scale; gross ≈ 0,
net ≈ −(round-trip taker + slippage).

**3.6 ES 1h, 2024-04..2026-08 (2.4 y)**: baseline 110 trades PF 0.82 −$27.5k; with the 5m-tuned cell 90 trades
PF 1.07 +$6.5k, t = 0.23, best trade 178 % of net.

## 4. Rulings on Section 59's four findings

1. **(2) 5m intraday alpha.** *ES 5m: survives, and is stronger once the momentum filter reads the firing bar* — but
   it is 53–78 trades over ten weeks, the quoted cell is the best of eight on the same data, the best honest t is 1.45,
   and **no longer 5m ES history exists** (`ES_5m_continuous.csv` is the same 10 weeks; Milestone 10 / Databento gap).
   "Statistically significant" was asserted, never computed, and is not established. Verdict: *promising, untestable
   out of sample until 5m history exists.* **CL 5m: does not survive** (baseline 0.95; grid 0.80–1.10). NQ 5m:
   PF 1.07, Δ −0.02, no verdict change.
2. **(3) BTC 1h alpha: does not survive.** It was a 90-day window effect on top of a stale momentum filter; on 6.67
   years the family is significantly *negative*. Retract "1h BTC alpha isolated". The 5m-crypto friction barrier
   (§3.5) stands, strengthened.
3. **(4) Sizing rule.** Accepted in intent (micros under $250k). The mechanism you observed — signals "flooring to 0"
   — was also muting whole datasets (§2.2); the two are the same event.
4. **(1) "Built & verified".** Squeeze detection is sound and non-repainting; the momentum filter was stale, not
   repainting; the unit suite did not pass; 1 of 17 datasets was dead and 4 truncated. Fixed; the strategy is now
   what the workflow doc describes.

One multi-year positive cell exists that neither of us has looked at: **GC 1h, 51 trades, PF 1.30, +$11,368 over
2.4 years, max DD $9,113, random 0.60.** Small, in-sample, but the only row in the matrix with both >50 trades and >1
year. If Stack 11 gets any further budget, that is the cell to pre-register, not ES 5m.

## 5. Rulings requested

- **R59-A** Retract the "1h BTC alpha" and "statistically significant" language from `STACK_11_RESEARCH_WORKFLOW.md`
  §1, §3 and §5.2, or tell me to patch it (I did not edit your document).
- **R59-B** The four Stack 11 files are yours and untracked. Commit them (with the three fixes now in the tree) or
  tell me to; I committed only `backtesters/stack11_out_of_window.py`, which imports from your backtester.
- **R59-C** Stack 11 status: I propose *research sandbox, not a Track 2 candidate*; ES 5m parked on the Milestone 10
  data gap; GC 1h optional pre-registration after the drill. Confirm or amend.
- **R59-D** §2.2's live-path question: where does the orchestrator clear `_position_open`?

## 6. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` paper runner | operator, after 09-16 (3rd) |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | Merge `bugfix/engine-slippage-signs` (`9c87974`) into master | operator, after 09-16 (1st) |
| 7 | DEFECT-COL-001 fix — Sections 57–58 design + the `_flush_loop` note; then extend/close the open gap | operator, after 09-16 (2nd) |
| 8 | ~~Data gap registration~~ — done, `dc451f5` | — |
| 9 | Stack 11 — cross-checked; 3 fixes in tree; ES 5m only survivor, untestable; BTC 1h retracted | you: R59-A..D |

Four rulings owed from you. Nothing owed from me before the drill.

## 7. Cross-check and brainstorm (reproduce, do not read)

CODE:
1. Run `venv\Scripts\python.exe -m pytest tests	est_stack11_squeeze.py -q` on the current tree (expect 3 passed). Then
   temporarily revert `need = length * 2 - 1` to `length * 2` in `_calc_momentum` and confirm the fixture's momentum
   collapses to ±0.07. Is 2L−1 the right window against the TTM/LazyBear reference formula?
2. Verify the zero-size stall independently: on the shipped loop (without the `else` branch) count raw signals vs
   trades on `data/NQ_15m.csv`. Then answer R59-D from the orchestrator source.
3. Confirm the bps fix on one ES trade by hand: net / (entry × qty × 50).
4. Run `backtesters/stack11_out_of_window.py --btc5m`; check the per-year BTC 1h table. Attack the random baseline:
   is entry_prob = trades/bars clamped to 0.01 a fair comparator, or should ΔPF be replaced by the t/bootstrap columns?

STRATEGY:
5. Pre-fix the momentum filter was effectively random and ES 5m still showed PF 1.05; post-fix 1.26. Is the squeeze
   release itself the edge? Test close-vs-SMA only, and momentum only.
6. What would distinguish "ES 5m is real" from "ES 5m is a ten-week regime" without 5m history: session-of-day split,
   long/short split, time_flatten vs target exits, and how many of the 53 tuned trades fall on FOMC/CPI days.
7. GC 1h is the only multi-year positive cell (51 trades, PF 1.30). Design a pre-registration that cannot be tuned on
   the same 2.4 years.
8. Decide plainly: does Stack 11 deserve any budget before the Milestone 10 (5m history) gap closes, or is it parked?

Reply with numbers you produced, not numbers you read.
