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
**Date**: 2026-09-13 00:48 EDT
**Re**: **Harness changes 1–3 are built, verified and committed.** t0030 re-scores on the modified engine with
**0 field differences**. The new data produced two findings that need your ruling before Campaign 5
registers: **Family B as ruled has nothing to trade in the research span**, and **my censoring addendum
doubled ETH's figures**. Please cross-check the build independently (§6).
**State**: DEV `0245412` + 41 dirty, 0 staged, measured 2026-09-13T04:47:47Z. Lab master `82ffcba` + 19 dirty,
unchanged. `qtl_autoresearch` on **`autoresearch/c5_harness` @ `a6401fe`**, 0 dirty.
`autoresearch/c4_donchian_crypto_1h` unchanged at `2e9d222`.

---

## 1. What was built

On a new branch from `2e9d222`, as Sections 49–51 ruled. Full record:
`qtl_autoresearch/research/autoresearch/C5_HARNESS_BUILD.md`.

| change | where | behaviour |
| --- | --- | --- |
| #1 funding fetcher | `scripts/fetch_binance_funding.py` | Monthly `fundingRate` zips from `data.binance.vision`, sha256-verified; REST only for a month the archive lacks; refuses to write a series with a hole |
| #2 funding PnL | `run_backtest(funding=)` | An open position pays `direction × rate × bar.open × point_value × qty` at each settlement. Entry bar's settlement not owed; exit bar's owed. In `net_pnl_usd`; recorded in `ClosedTrade.funding_usd` |
| #3 daily MTM | `run_backtest(mtm=)`, `research/autoresearch/mtm.py` | One row per UTC day: realised PnL + the open position valued by `_close_net_pnl`. The last bar is always marked, so a position open at a window's end is **booked without a ClosedTrade**. `pool_mtm` carries equity and the high-water mark across fold seams |

Both options are keyword-only and default to `None`. The exit arithmetic moved into `_close_net_pnl`
without reordering an operation, and every real exit and every mark now go through it (Section 51 §2).

## 2. Verification

| check | result |
| --- | --- |
| Candidate on the branch is t0030 | sha256 matches after CRLF→LF (autocrlf checks it out as CRLF — a naive hash mismatches) |
| `score_campaign` on the modified engine vs `t0030.json` | **0 field differences**, S = 2.09 |
| Trades with `mtm` on vs off | **0 mismatches** at full float precision, 134 trades |
| Positions booked at fold ends | nonzero on exactly BTC w2, BTC w4, ETH w3, ETH w4 — the four the censoring finding named; all positive |
| `tests/test_c5_harness.py` | 24 passed; the real-data regression loads its targets from `t0030.json` at test time |
| Full worktree suite | **259 passed, 0 failed.** One pre-existing collection error: `tests/test_multivenue_execution.py` imports `adapters/polymarket_adapter.py`, never tracked on this branch |
| Funding download 2020-01 → 2026-08 | **7,305 settlements per symbol**, 80/80 archive months, 0 REST, 0 gaps, largest snap 47 ms |

## 3. A correction to my own record

The booking disagreed with `C4_CENSORING_BIAS_FINDING.md` on ETH by a clean factor of two.

| censored position | regime at entry | addendum | engine booking | quantity ratio |
| --- | --- | --- | --- | --- |
| BTC w2 | TRENDING_EXPANSION | +$105 | +$105.38 | 1.000 |
| BTC w4 | TRENDING_EXPANSION | +$563 | +$562.80 | 1.000 |
| ETH w3 | **HIGH_VOLATILITY_SHOCK** | +$47 | **+$23.30** | **2.002** |
| ETH w4 | **HIGH_VOLATILITY_SHOCK** | +$385 | **+$192.23** | **2.001** |

`run_backtest` sizes with `size_trade(..., regime=entry_regime)`, and `calculate_position_size` halves a
shock-regime entry. My addendum's re-computation omitted the regime. **ETH marked to market is 2.4833
(+1.50 %), not 2.5201 (+3.0 %).** S marked to market, 2.2775, is BTC-bound and reproduces exactly from the
booking. The correction is appended to the document on the c5 branch.

This is the argument for Section 51 §2 in miniature: a re-computation of the engine drifted from the
engine by one parameter; the booking calls the engine and cannot.

## 4. Family B as ruled has nothing to trade in the research span — ruling needed

Section 50 §5 made this the first test. Runs are consecutive settlements at or beyond ±0.05 %/8h, same side:

| asset | span | at/beyond trigger | runs ≥ 8 days | runs reaching 120 bps | richest run |
| --- | --- | --- | --- | --- | --- |
| BTCUSDT | holdout 2020–22 | 9.6 % | 2 | 5 | 331 bps / 9.0 d (Feb 2021) |
| BTCUSDT | **research 2023–26** | **0.6 %** | **0** | **0** | **37 bps** / 2.0 d |
| ETHUSDT | holdout 2020–22 | 13.0 % | 0 | 8 | 334 bps / 7.3 d (Feb 2020) |
| ETHUSDT | **research 2023–26** | **0.7 %** | **0** | **0** | **26 bps** / 1.3 d |

Extreme funding was a 2020–21 regime. In the research span no run reaches a third of the hurdle, so an
extremes-triggered carry cannot produce Gate Zero trades, let alone 40 OOS trades per asset.

**Requested — before registration, not after:** replace Family B, or redefine its trigger and re-screen
it as the new family that is. I would not register it as ruled. This measures the trigger as specified; a
lower trigger is a different strategy with its own hurdle arithmetic (at a 0.01 %/8h baseline, 120 bps is
about 40 days of carry).

## 5. Funding barely moves t0030

Diagnostic replay of t0030's OOS folds at the recorded θ\* with funding charged — not a re-score:
BTC **+$18.39** (PF 2.0917 → 2.1117, net +0.5 %), ETH **−$98.84** (2.4465 → 2.4232, net −1.2 %). t0030
trades both directions (BTC 31 long / 22 short, ETH 43 / 38), so the flows largely cancel. The closed-trade
score was not flattered by ignoring funding.

## 6. Cross-check the build — reproduce, do not accept

From `qtl_autoresearch` on `autoresearch/c5_harness`, with
`AUTORESEARCH_DATA_ROOT=C:/Users/ixis1/Desktop/DEV/quant_trading_lab/data/continuous` and
`..\quant_trading_lab\venv\Scripts\python.exe`:

1. `-m pytest tests/test_c5_harness.py -q` → 24 passed. Then `-m pytest tests -q --continue-on-collection-errors`
   → 259 passed plus the one collection error.
2. Read `git diff 2e9d222 -- backtesters/engine.py` and confirm the moved exit arithmetic is operation-for-
   operation identical. The regression says it is; the diff is the proof.

**Where I most want you to look for mistakes:**

- **Funding timing.** Entry bar's settlement not owed, exit bar's owed. Right for a signal filled at the
  bar's close and a stop or target filled inside a later bar — but is `bar.open` an acceptable notional
  when Binance settles on the mark price?
- **What a mark is.** A mark is the *liquidation* value — exit slippage and both taker fees deducted. Daily
  equity therefore drops by one round trip of friction on an entry day, before price moves. Conservative
  and consistent with the booking, but it adds a step to daily returns that a mid-price mark would not.
  Which should the correlation gates use?
- **Left censoring.** Every fold starts flat on its own test bars, so a position that would have been open
  at `test_start` does not exist in the series — the mirror image of the right censoring this build now
  books. The pooled series inherits it. Does Campaign 5 need to address it, or only record it?
- **Funding on the wrong instrument.** The engine charges funding to any symbol it is handed a map for.
  Family C's spot pairs must never receive one. A guard, or a documented caller rule?
- **Snap to the hour.** The largest snap applied was 47 ms. Settlements are matched to bars by exact
  timestamp, so a series on a different interval grid would silently charge nothing. Should a funding
  instant with no matching bar be an error?

## 7. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | ~~Harness changes 1–3~~ — **built, `a6401fe`** | — |
| 7 | **Family B: replace or re-trigger** (§4) | **you** |
| 8 | Independent cross-check of the build and the five questions (§6) | **you** |
| 9 | Campaign 5 registration on the new engine | after 7 and 8 |

Two rulings and one cross-check owed from you. Nothing owed from me.
