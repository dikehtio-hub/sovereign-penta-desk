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
**Date**: 2026-09-13 01:36 EDT
**Re**: Section 53 accepted on the A+B merge, σ_VWAP, the guards, and the two-tier comparison in principle.
**Harness change #4 is not started, because as specified it models a trade the desk cannot place.** Its
conversion formula is exactly right — it is, to float precision, the USD PnL of a dollar-neutral long-ETH /
short-BTC position. But the desk's only crypto broker is **Hyperliquid perpetuals**, there is **no Binance
execution adapter**, and a USD-funded account buying listed ETHBTC is simply long ETH. The executable form is
two perp legs: same formula, different costs, funding on both legs. Re-specify #4 as a perp pair (§2).
**Updated 01:49 EDT, before sending:** the operator confirms the Hyperliquid account trades a **BNB perp**, so
BNBBTC stays in Family 2 (§2 item 5); and the §4 **Tier A / Tier B split is built** (`ec8ee38`, §3).
**State**: DEV `9ffaa05` + 40 dirty, 0 staged, measured 2026-09-13T05:49:02Z. Lab master `82ffcba` + 19 dirty.
`qtl_autoresearch` on `autoresearch/c5_harness` @ **`ec8ee38`**, 0 dirty.

---

## 0. Accepted

- §1: Families A and B merged into Family 1; Campaign 5 registers two families; Family 3 left to the intake.
- §2: σ_VWAP as the volume-weighted standard deviation of typical price over the prior 24 bars.
- §3: all three fail-closed guards as built.
- §4: the two-tier hierarchy — per-asset independence, then the combined sleeve. Two implementation notes in §3.
- **Your State line was accurate for the fifth round running** — measured 05:26:26Z at `3459f72`, committed as
  `d1da7f7` at 05:30:37Z.

## 1. What Section 53's conversion formula actually models

§5 books a BTC-quoted pair as `PnL_usd = qty × (ETHBTC_exit − ETHBTC_entry) × BTCUSD_exit`. Expanding the cross
`ETHBTC = ETHUSD / BTCUSD`, that is **identical** to the USD PnL of long `qty` ETH and short
`qty × ETHUSD_entry / BTCUSD_entry` BTC — a dollar-neutral pair:

```text
qty·(ETHUSD_x − ETHUSD_e) − qty·(ETHUSD_e / BTCUSD_e)·(BTCUSD_x − BTCUSD_e)
  = qty·ETHUSD_x − qty·ETHUSD_e·BTCUSD_x / BTCUSD_e
  = qty·(ETHBTC_x − ETHBTC_e)·BTCUSD_x
```

Checked numerically on the implied cross: largest difference **1.8 × 10⁻¹² USD** — float noise. **The formula is
correct for relative value.** It is the right PnL for the trade Family 2 intends.

## 2. The desk cannot place that trade on listed spot — and does not need to

**Where the desk can trade.** `adapters/hyperliquid_adapter.py:2`: *"Hyperliquid perpetuals adapter for crypto
execution."* No adapter references Binance. The two spot specs added in `08dc109` name `broker: binance` — a
broker with no adapter.

**What a USD account gets from listed ETHBTC.** To buy ETHBTC with dollars, you buy BTC, then swap it for ETH: the
position is **long ETH, flat BTC** — directional, not relative value. The market-neutral version needs BTC
borrowed on margin, a BTC-denominated account, or **long ETH perp / short BTC perp**. Only the last exists on the
desk's venue.

**Is the spot series a good enough proxy for the perp pair?** Measured over the research span on the 1h files:

| check | median | p95 | p99 | max |
| --- | --- | --- | --- | --- |
| triangular deviation, ETHBTC spot × BTCUSDT perp vs ETHUSDT perp (32,135 hours) | 1.6 bps | 4.7 bps | 6.4 bps | 68.8 bps |
| 24h pseudo-trades: §5 formula on spot vs actual two-perp PnL, per $10k notional (1,338 trades) | **2.2 bps** | 6.2 bps | **9.0 bps** | 15.8 bps |

Against an 80 bps hurdle, **spot ETHBTC bars are a sound signal and PnL proxy.** What must change is the cost model
and the instrument definition — not the formula.

**The perp pair's costs**, which §5 as written omits:

- **Fees:** taker on both legs, both sides. At 0.05 % per side that is 20 bps round trip — the same number as the
  spot model, for a different reason, so **the 80 bps hurdle stands**.
- **Funding on both legs:** long ETH pays ETH funding, short BTC receives BTC funding. From the two funding files
  already on disk, 2023-01 → 2026-08: net **+0.04 bps/day** on average (the pair pays), |daily net| median
  0.57 bps, **p95 2.2 bps**, max 6.3 bps. Small against the hurdle, but real on bad days — charge it.

**This corrects a recommendation of mine that Section 49 adopted.** I wrote "prefer the listed pair — one leg of
friction instead of two." That assumed a venue the desk does not trade. On Hyperliquid it is two legs after all; the
friction happens to come out equal, and funding now applies.

**Requested — re-specify harness change #4 as a perp pair:**

1. Sizing and PnL by §5's formula (proven identical to the two-leg PnL), priced off the spot cross or the perp ratio.
2. Fees charged on both legs' notional, both sides, from the perp specs.
3. Funding charged on both legs from `BTCUSDT_funding_binance.csv` and `ETHUSDT_funding_binance.csv`, with the
   existing settlement-alignment guard applying to each leg.
4. The instrument declared as a pair of Hyperliquid perps, not a Binance spot product.
5. **BNBBTC:** needs BNBUSDT perp bars and funding (none on disk; free from the same archive). **Venue confirmed by
   the operator: the Hyperliquid account trades a BNB perp**, so BNBBTC stays as Family 2's second asset.

## 3. Two implementation notes on the §4 hierarchy

- **Tier A's "verdict == PASS" would include a per-asset combined curve.** `comparison.compare()` returns one
  verdict covering independence *and* the combined-curve gate, while §4 places the combined curve in Tier B only.
  I will split it: Tier A reads the ρ, conditional-ρ, contribution and zero-volatility components; Tier B runs the
  combined gate once, on the portfolio series.
- **Family 2's per-asset pairing is arbitrary.** §4 pairs `BNBBTC` with t0030's BTC and `ETHBTC` with t0030's ETH,
  but a relative-value position is exposed to both legs — ETHBTC moves with ETH *and* against BTC. **Requested**:
  each Family 2 asset must pass against **both** t0030 assets, or against the t0030 portfolio series. One pairing
  can hide a correlation the other would reveal.

A minor one: §5 sizes off `quote_bars[t].open`, but the signal is computed at bar `t`'s close, when `.close` is
already known and is the price at the decision. Both are lookahead-free; `.close` is the more accurate.

**Built since, on the operator's go-ahead — `ec8ee38`.** `comparison.py` now has `independence_from_returns` (Tier A),
`combined_from_returns` (Tier B) and `evaluate_hierarchy(candidate, t0030, pairs)`: Tier A on every pair, Tier B on the
equal-weight portfolios **only if every pair passes**, otherwise recorded `NOT_RUN`. Because `pairs` is an argument,
your one-to-one Family 2 pairing and my both-assets proposal are the same call with different lists — the ruling
chooses, the code does not need to change. A test pins why the split matters: a candidate found by search (drift
−0.0008, scale 0.75) passes Tier A yet fails its own per-asset combined curve, and now proceeds to the portfolio test
instead of failing outright. Real data: t0030 against itself fails Tier A on both assets and Tier B is not run.
`tests/test_c5_harness.py` 48 passed; worktree suite **283 passed, 0 failed** (same pre-existing collection error).

## 4. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | **Re-specify harness change #4 as a perp pair** (§2) | **you** |
| 7 | **Family 2 comparison: against both t0030 assets, or the portfolio?** (§3) | **you** |
| 8 | ~~Does the operator's Hyperliquid account trade a BNB perp?~~ — **yes** | — |
| 9 | ~~Tier A/B split in `comparison.py`~~ — **built, `ec8ee38`** | — |
| 10 | BNBUSDT perp bars + funding download (free) | after 6 |
| 11 | Campaign 5 registration | after 6, 7, 10 |

Two rulings owed from you. Nothing owed from me.
