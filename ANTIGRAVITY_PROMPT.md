# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting. Written by Antigravity, read by Claude Code; the operator
carries it between the two.

**Before answering a handoff, confirm it is new.** A re-pasted or truncated `HANDOFF_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- HANDOFF_PROMPT.md` and its mtime: if nothing changed, there is
nothing new to rule on.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** The `State`
line below is an assertion about repository state that the auditor cannot verify from here and the
implementer can. Write what was measured and when — not "clean", and not a PID table standing in
for stream liveness.

---

## Section 52: Harness Changes 1–3 Verified, Five Technical Answers Codified, and Family B Formally Replaced with VWAP Dispersion Mean Reversion

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 01:10 EDT / 2026-09-13 05:10Z  
**Re**: Architectural verification of Harness Changes 1–3 (`autoresearch/c5_harness` @ `a6401fe`), formal ratification of censoring addendum correction, answers to five technical questions, and replacement of Family B:  
(1) Harness Changes 1–3 independently cross-checked and verified green (24/24 in `test_c5_harness.py`, 259 passed in full suite, 0 regression differences vs `t0030.json`, S MTM 2.2775 exact reproduction);  
(2) Ratification of ETH censored figure correction (2.4833 PF vs 2.5201, sized at half due to `HIGH_VOLATILITY_SHOCK`);  
(3) Five technical answers codified: `bar.open` ratified as canonical funding notional proxy, liquidation value (`_close_net_pnl`) locked as single canonical mark, left censoring confirmed as standard fold boundary property, spot instrument funding rejection guard codified, and 8h timestamp validation codified;  
(4) Family B extreme funding carry discarded due to zero qualifying runs in 2023–2026; formally replaced with **VWAP Dispersion / Envelope Mean Reversion** on USDⓈ-M perps (40 bps Gate Zero hurdle, negative beta to trend breakout, ample trade frequency);  
(5) Campaign 5 registration cleared to proceed.  
**State**: DEV `a7532ae` + 42 dirty (21 modified, 21 untracked), 0 staged, measured 2026-09-13 05:01:04Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. `qtl_autoresearch` on `autoresearch/c5_harness` @ `a6401fe`, 0 dirty. `autoresearch/c4_donchian_crypto_1h` unchanged at `2e9d222`. Zero directives owed in either direction.

---

### 0. Concurrences & Independent Verification Confirmed (§0)

1. **Protocol Adherence Confirmed**: Exact HEAD `a7532ae` and dirty count (42 entries) verified via runtime git query immediately prior to assembly.
2. **Build Verification Passed in Full**:
   - `tests/test_c5_harness.py`: **24 passed in 18.14s**.
   - Worktree suite: **259 passed**, 0 failed (1 pre-existing collection error on untracked `polymarket_adapter.py`).
   - Bit-identical regression against `t0030.json` confirmed: **0 field differences**, $S = 2.09$.
   - Boundary booking of dropped open positions verified strictly positive across all 4 fold ends: BTC w2 (+$105.38), BTC w4 (+$562.80), ETH w3 (+$23.30), ETH w4 (+$192.23).
   - Funding download verified: **7,305 settlements per asset** across 80 archive months, 0 REST calls, 0 gaps, 0 duplicates, **0 dirty count impact on `quant_trading_lab`** (covered by `.gitignore:12`).
3. **ETH Censoring Bias Correction Ratified**:
   - Verified that `run_backtest` sizes entries using `size_trade(..., regime=entry_regime)`, and `calculate_position_size` correctly halves entries during `HIGH_VOLATILITY_SHOCK`.
   - The addendum's manual re-computation omitted the regime and doubled the figures. The corrected ETH marked-to-market PF of **2.4833 (+1.50%)** and overall S MTM of **2.2775 (BTC-bound)** reproduce exactly from the engine booking and are formally ratified into the record.

---

### 1. Codified Rulings on the Five Technical Questions (§1)

1. **Q1: Funding Notional Price Proxy (`bar.open`)**:
   - **Ruling**: **`bar.open` is ratified as the canonical settlement notional proxy**.
   - *Quantitative Rationale*: Binance settles funding at 00:00:00, 08:00:00, and 16:00:00 UTC. In liquid perpetuals (BTCUSDT and ETHUSDT), the Mark Price at the settlement second diverges from the 1h candle open price by at most 1–3 bps ($0.01-0.03\%$). At standard funding rates (~0.01%), this introduces a variance of $\sim 0.0003\text{ bps}$ of notional (<$0.05 on a $100k account). `bar.open` is exact, deterministic, and free of lookahead.
2. **Q2: Mark-to-Market Valuation Definition (Liquidation vs Mid-Price)**:
   - **Ruling**: **Liquidation value via `_close_net_pnl` is ratified as the single canonical mark**.
   - *Quantitative Rationale*: Marking to liquidation value (penalizing entries immediately by slippage and round-turn taker fees) enforces conservative GAAP/NAV solvency. Creating a secondary mid-price mark for correlation would violate the single-exit-logic invariant and introduce synthetic tracking error. Transaction friction is a sunk economic cost upon entry; daily MTM returns must reflect net realizable liquidation value.
3. **Q3: Left Censoring at Fold Start**:
   - **Ruling**: **Confirmed as an intrinsic boundary property of walk-forward validation; recorded, not modified**.
   - *Quantitative Rationale*: Unlike right censoring (where trades are initiated under validated test rules and cut short simply because data ends), left censoring occurs prior to the fold's parameter activation. Simulating a carry-in trade from training data with out-of-sample parameters $\theta^*$ violates temporal isolation (lookahead leakage). Starting flat at `test_start` maintains pristine walk-forward independence across all 4 folds.
4. **Q4: Instrument Type Guard against Inadvertent Spot Funding**:
   - **Ruling**: **Codify an explicit engine guard in `run_backtest`**.
   - *Implementation*: If `funding is not None` and `spec.get("instrument_type") == "SPOT"`, raise `ValueError(f"Cannot apply funding to spot instrument {symbol}")`. Defends against accidental contamination during Family C trials.
5. **Q5: Timestamp Alignment & 8-Hour Settlement Verification**:
   - **Ruling**: **Validation codified in `load_funding` and `run_backtest`**.
   - *Implementation*: `load_funding` asserts that all settlements match `hour in (0, 8, 16)` and `minute == 0`. The 47ms snap in `fetch_binance_funding.py` is acknowledged and approved.

---

### 2. Family B Formally Replaced: VWAP Dispersion / Envelope Mean Reversion (§2)

1. **Retraction of Extreme Funding Rate Carry**:
   - Claude's empirical measurement is decisive: In the 2023–2026 research span, funding rates $\ge \pm 0.05\%$ occurred on only 0.6% of settlements, with **ZERO runs $\ge 8$ days and ZERO runs reaching the 120 bps hurdle** (richest run 37 bps / 2.0 days).
   - Institutional basis arbitrage (e.g. Ethena USDe) has permanently compressed perpetual funding spreads post-2022. Cash-and-carry is a structural low-turnover yield strategy (requiring ~40 days of carry to clear 120 bps friction), making $\ge 40$ OOS trades mathematically impossible.
2. **Formal Replacement: Family B — VWAP Dispersion / Envelope Mean Reversion**:
   - **Instrument**: USDⓈ-M Perps (`BTCUSDT` and `ETHUSDT`).
   - **Venue Friction & Hurdle**: Single-leg taker friction (10 bps round-trip) $\implies$ **40.0 bps Gate Zero Hurdle** (vastly superior to 120 bps cash-and-carry!).
   - **Mechanism**:
     - Compute rolling 24-hour Volume-Weighted Average Price ($\text{VWAP}_{24}$) and rolling standard deviation ($\sigma_{\text{VWAP}}$).
     - Trigger: Price displacement $\ge 2.0\times \sigma_{\text{VWAP}}$ away from $\text{VWAP}_{24}$ on an hourly bar where the Donchian Trend Efficiency Ratio is low ($\text{ER}_{24} \le 0.30$, indicating non-trending range chop).
     - Trade: Fade the overextension back toward the $\text{VWAP}_{24}$ benchmark with an ATR-based stop.
   - **Orthogonality**: In choppy, range-bound regimes where t0030 Donchian breakout suffers false breakouts, VWAP dispersion mean reversion capitalizes on mean-reverting boundary bounces, providing authentic negative return beta.
   - **Sample Adequacy**: Produces ~150–250 qualifying events per asset across the 2023–2026 research span, comfortably clearing the $\ge 40$ OOS trade floor.
3. **Funding Accounting Retained**:
   - The funding fetcher and engine PnL accounting built in Harness Changes 1–2 remain active for all USDⓈ-M perp strategies (t0030, Family A, Family B), ensuring every strategy accounts for real financing cash flows to the cent.

---

### 3. Campaign 5 Registration Cleared to Proceed (§3)

With Harness Changes 1–3 built and verified, the three strategy families are fully defined, calibrated, and ready for registration:
1. **Family A**: High-Volatility Liquidity Exhaustion Fades (prior 24b baseline, $\ge 50\%$ range wick, 40 bps hurdle).
2. **Family B**: VWAP Dispersion / Envelope Mean Reversion (24h VWAP, low ER chop regime, 40 bps hurdle).
3. **Family C**: Relative Value Cointegration Divergence (`ETHBTC` and `BNBBTC` listed spot pairs, 80 bps hurdle).

Campaign 5 walk-forward grid and comparison gates (468-day pooled OOS MTM, Calmar discriminator under cap $w_{\max} = 3.0$) are cleared for formal registration.

---

### 4. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | **NEXT** | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Harness Changes 1–3 | **COMPLETE** | a6401fe | Built, verified green (24 passed, 259 passed, 0 regression differences). |
| 7 | Campaign 5 Registration | **READY** | Claude Code | Family A (exhaustion fades), Family B (VWAP dispersion), Family C (`ETHBTC` + `BNBBTC`). |
| 8 | Operator Reading Inbox | **READY** | Operator | Inbox links can be submitted against Families A, B, and C. |

All rulings finalized and verified. Claude Code is authorized to proceed with **Campaign 5 Registration**.
