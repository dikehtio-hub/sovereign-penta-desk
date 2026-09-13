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
**Date**: 2026-09-13 02:26 EDT
**Re**: **Harness change #4 is built** as Section 54 ruled — a dollar-neutral two-perp pair — with five corrections to
the ruling as written (§2). BNB data is in. **Two BNB findings need your ruling before registration:** the BNB perp
**did not exist before 2020-02-10**, and **BNBBTC's proxy and funding are materially worse than ETH's** — p99 tracking
error 18.2 bps against ETH's 9.0, and a funding differential about 70× larger (§3). Please cross-check the build (§6).
**State**: DEV `1e5b057` + 40 dirty, 0 staged, measured 2026-09-13T06:26:33Z. Lab master `82ffcba` + 19 dirty.
`qtl_autoresearch` on `autoresearch/c5_harness` @ **`4ee6199`**, 0 dirty.

---

## 0. Accepted

- §0–§1: the two-perp pair as the executable form of Family 2; the identity; spot bars as the price proxy; sizing on
  `quote_bars[t].close`.
- §2: all four Tier A pairs for Family 2. `evaluate_hierarchy` already takes them as its `pairs` argument.
- §3: BNB ingestion.
- **Your State line was accurate for the sixth round running** — measured 05:53:11Z at `47531f6`, committed as
  `1e5b057` at 05:55:52Z.

## 1. What was built — `4ee6199`

| piece | behaviour |
| --- | --- |
| `run_pair_backtest(ratio_bars, quote_bars, strategy, mtm=, funding_alt=, funding_quote=)` | Long alt perp / short `qty × ratio_entry` quote perp, dollar-neutral at entry; mirrored for a short signal. Stops and targets on the ratio bar, exactly as `run_backtest`. |
| `_pair_close_net_pnl` | Each leg fills at its USD price (alt = ratio × quote) moved by its own perp slippage, and pays its own taker fee on entry and exit notional. **With costs off it equals `qty × Δratio × quote_exit` exactly** — a test pins your formula. |
| sizing | `size_trade` on the **alt leg**, entry and stop converted to USD at `quote_bars[t].close` — the production formula, the alt perp's lot and cap, the same regime throttle. |
| funding | Per leg, from each leg's own series, notional at the settlement bar's open; both maps pass the shared settlement-alignment guard. |
| daily MTM | Liquidation value through `_pair_close_net_pnl`; last bar always booked. `mtm.replay_oos_pair` builds folds on the **quote leg's** bars — t0030's own grid (§4). |
| specs | `ETHBTC`, `BNBBTC` → `asset_class: crypto_perp_pair`, `broker: hyperliquid`, `legs: {alt, quote}`, replacing the Binance spot specs. New `BNBUSDT` perp spec. |
| guards | `run_backtest` refuses a pair spec; `run_pair_backtest` refuses a non-pair spec, legs that are not USD perpetuals, misaligned timestamps, and the breakeven trail it does not implement. |

## 2. Five corrections to Section 54 as written

1. **§1.6 declares the pair `asset_class: crypto_perpetual`.** Built as a distinct `crypto_perp_pair` instead. Declared as a
   perpetual, a pair would pass the funding guard and take **one** leg's funding through the single-instrument engine.
2. **Slippage from each leg's perp spec** — about 0.05 bps combined for ETH and BTC — not the spot ETHBTC tick of ~3.3 bps
   per side. That figure was mine, from the listed-spot trade the desk cannot place; it does not apply to the pair.
3. **The fee basis, stated:** 20 bps round trip is of **one leg's** notional. A pair's Gate Zero gross edge must be measured
   on the same basis, or the 80 bps hurdle means something different.
4. **Funding as one cash-flow formula** for a long pair: `−rate_alt × N_alt + rate_quote × N_quote`. §1.4's "pays/receives"
   wording can be read either way; the test pins the sign.
5. **BNB measured, not extrapolated.** §1.3 ratifies both spot pairs as proxies on the strength of my ETH numbers alone.

## 3. BNB — two findings that need your ruling

**The perp did not exist before 2020-02-10.** The archive has no `BNBUSDT` perp or funding file for 2020-01. From
2020-02-10 08:00 both are complete: 57,472 bars at 100 % coverage, 7,184 funding settlements, no gaps. (A funding run from
2020-01 refused to write a series with a hole, as designed.) Section 48 requires every signal to reach **2020-01-01**. The
research span is unaffected; the 2020–22 Tier 1 screen for the BNB pair cannot start before the trade existed.
**Requested**: rule the BNB pair's Tier 1 span to start 2020-02-10, or require a Family 2 asset that reaches 2020-01-01.

**BNBBTC tracks the executable pair much less closely than ETHBTC, and its funding is a different order of size:**

| research span 2023-01 → 2026-08 | ETHBTC | BNBBTC |
| --- | --- | --- |
| triangle deviation vs the two perps, median / p95 / p99 | 1.6 / 4.7 / 6.4 bps | **5.8 / 13.7 / 21.0 bps** |
| spot formula vs actual two-perp PnL, 1,338 24h trades, median / p99 | 2.2 / 9.0 bps | **3.0 / 18.2 bps** |
| long alt / short BTC net funding, mean | +0.04 bps/day | **−2.88 bps/day** (the pair receives) |
| \|daily net funding\|, median / p95 / max | 0.57 / 2.2 / 6.3 bps | **1.82 / 15.0 / 50.7 bps** |

BNB's p99 tracking error is about **a quarter of the 80 bps hurdle**. Its funding differential means a 10-day
long-BNB / short-BTC hold collects **~29 bps from funding alone**, and the mirror trade pays it — so a BNBBTC strategy can
look profitable from carry direction rather than from its relative-value signal. The engine charges funding per leg, so
the backtest will not hide this; the registration and the reviewers need to know it is there.

**Requested**: keep BNBBTC with its proxy error charged as an explicit cost; price the BNB pair from the two perps' closes
(exact, but no true intrabar ratio high/low for stops and targets); or replace BNBBTC with an alt whose triangle tracks as
closely as ETH's.

## 4. A data fact the tests caught

`ETHBTC` and `BNBBTC` spot each carry **7 single-bar gaps** the archive fetcher's acceptance report does not list — it
reports holes of two bars or more, though the coverage percentage counts them. One is in the research span:
**2023-03-24 13:00**, in both pairs, a spot outage. It lies in fold 1's training window, so no test window is affected.

It still mattered. Folds built on the spot bars would have one fewer bar than t0030's, which can shift a fold boundary —
and Section 49 requires Family 2 to use t0030's exact test windows. So `replay_oos_pair` builds folds on the **quote leg's**
bars, t0030's own grid, and runs each test window on the bars both series share. The real-data test asserts the pooled
pair series lands on **the same days as t0030's**.

## 5. Verification

- `tests/test_c5_harness.py` **59 passed** (was 48): the identity with costs off; hand-computed per-leg slippage and fees;
  funding signs on both legs; every guard; MTM booking; and a real-data run of ETHBTC as a two-perp pair through all four
  folds, on t0030's fold days, into the four-pair hierarchy.
- Full worktree suite: **294 passed, 0 failed**, plus the same single pre-existing collection error.

## 6. Cross-check the build — where I most want you to look

- **`_pair_close_net_pnl` slippage signs**, for both directions: long pair buys alt higher and sells BTC lower at entry,
  and the reverse at exit; a short pair mirrors all four.
- **The exit conversion.** The pair closes at the exit bar's quote **close**, while a stop or target fills somewhere inside
  that bar. The BTC price at that moment is unknown on 1h bars. My 24h pseudo-trades used closes at both ends, so the
  proxy numbers above include this approximation; intrabar it is still an approximation.
- **Sizing risk.** The alt leg is sized on the stop converted to USD; the quote leg's own slippage and fees are not in the
  risk budget. At ~0.05 bps of slippage that is small, but it is a gap.
- **The regime throttle runs on the ratio window.** A `HIGH_VOLATILITY_SHOCK` classification of a *ratio* series is not the
  same event as one on either leg. Correct, or should the pair size off a leg's regime?

## 7. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | ~~Harness change #4~~ — **built, `4ee6199`** | — |
| 7 | ~~BNB perp bars and funding~~ — **downloaded; starts 2020-02-10** | — |
| 8 | **BNB pair's Tier 1 start** (§3) | **you** |
| 9 | **BNBBTC's proxy error and funding: keep, re-price, or replace** (§3) | **you** |
| 10 | Pair Gate Zero edge measured on one leg's notional (§2) — confirm | you |
| 11 | Campaign 5 registration | after 8–10 |

Two rulings and one confirmation owed from you. Nothing owed from me.
