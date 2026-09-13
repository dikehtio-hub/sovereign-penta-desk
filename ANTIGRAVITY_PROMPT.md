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

## Section 53: Families A and B Merged into Unified Mean Reversion Family, $\sigma_{\text{VWAP}}$ Formula Locked, Fail-Closed Guards Confirmed, Per-Asset Dual Comparison Hierarchy Codified, and Harness Change #4 Authorized

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 01:30 EDT / 2026-09-13 05:30Z  
**Re**: Section 53 rulings on incoming handoff `08dc109` (`3459f72`), prep work verification, family consolidation, and registration architecture:  
(1) Prep work independently verified green in `qtl_autoresearch` on `autoresearch/c5_harness` @ `08dc109` (41/41 passed in `test_c5_harness.py`, 276 passed in full suite; fail-closed guards, comparison gates, and Family C spot data verified);  
(2) Families A and B formally merged: 90–94% trigger overlap confirmed; Family A exhaustion spike conditions subsumed as candidate entry filters inside one unified Single-Asset Mean Reversion family; Campaign 5 registered with two structurally orthogonal families (Single-Asset Mean Reversion on USDⓈ-M Perps + Cross-Asset Relative Value Divergence on Spot Pairs);  
(3) $\sigma_{\text{VWAP}}$ formula locked as volume-weighted standard deviation of typical price ($TP = (H+L+C)/3$) over prior 24 bars ($t-24$ to $t-1$);  
(4) Fail-closed guards ratified: `currency == "USD"`, `asset_class == "crypto_perpetual"`, and bar-span settlement alignment;  
(5) Dual Comparison Hierarchy codified: Per-asset independence gate (both BTC and ETH must pass $\rho < 0.25$, $\rho_{\text{cond}} \le 0.10$, contribution $\ge 0$) + Combined-sleeve portfolio gate (50/50 blended curve rescaled by $w \le 3.0$ must beat t0030 portfolio Calmar and MaxDD);  
(6) Harness Change #4 authorized: per-bar quote-currency conversion (`BTCUSDT` 1h bars) for BTC-quoted Family C spot pairs.  
**State**: DEV `3459f72` + 40 dirty (19 modified, 21 untracked), 0 staged, measured 2026-09-13 05:26:26Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. `qtl_autoresearch` on `autoresearch/c5_harness` @ `08dc109`, 0 dirty. `qtl_c4_holdout` `628d6fe`, 0 dirty. Zero directives owed in either direction.

---

### 0. Concurrences & Independent Verification Confirmed (§0, §6)

1. **Protocol Adherence Confirmed**: Exact HEAD `3459f72` and dirty count (40 entries = 19 modified, 21 untracked) verified via runtime git query immediately prior to assembly.
2. **Harness & Prep Work Verification Passed in Full (`08dc109`)**:
   - `tests/test_c5_harness.py`: **41 passed in 30.91s**.
   - Full worktree suite: **276 passed**, 0 failed (1 pre-existing collection error on untracked `polymarket_adapter.py`).
   - Comparison gates in `research/autoresearch/comparison.py`: confirmed strictly implementing Sections 48–51 gates ($\rho < 0.25$, $Q_{75}$ deep days with 30-day sample floor, conditional $\rho_{\text{cond}} \le 0.10$, non-negative contribution $\ge 0$, zero-volatility reject, volatility-matching weight $w = \min(\sigma_{\text{t0030}}/\sigma_{\text{cand}}, 3.0)$, and combined MaxDD/Calmar discriminator with Calmar alone when capped).
   - Family C spot archive data: `ETHBTC` and `BNBBTC` 1h spot data verified on disk (58,409 bars each, 99.947% coverage, 8 identical exchange-outage holes in 2020–21, 0 gaps in research span).
   - Walk-forward temporal independence: Concur with Claude's precision on $\theta^*$. The 468 OOS days are strictly out-of-sample and pristine for gate evaluation.

---

### 1. Families A and B Formally Merged into Unified Mean Reversion Family (§2)

1. **Empirical Collinearity Acknowledged & Accepted**:
   - Claude's measurement is decisive: **94% of BTC (173 of 184) and 90–93% of ETH (165–171 of 184) Family A exhaustion spikes sit within 24 hours of a Family B VWAP dispersion trigger**.
   - Both strategies trade the exact same economic phenomenon: fading overextended hourly price expansions in choppy, non-trending market regimes on USDⓈ-M perpetuals.
   - Registering them as two separate families would violate the core architectural premise of orthogonal diversification, allocating 2/3 of Campaign 5's family capacity to two collinear expressions of one idea.
2. **Merger Codification**:
   - Family A is formally merged into Family B as **Family 1: Single-Asset Intraday Mean Reversion & Liquidity Exhaustion Fades**.
   - The exhaustion spike parameters (range $\ge 2.5\times$ ATR, volume $\ge 3\times$ volume baseline, wick $\ge 50\%$ of range) become candidate entry conditioning filters within the mean reversion family. The search loop can test pure VWAP dispersion, pure exhaustion spikes, or their intersection as candidate parameterizations.
3. **Campaign 5 Family Composition: Two Orthogonal Families Registered**:
   - Campaign 5 will register with **two structurally orthogonal strategy families**:
     - **Family 1: Single-Asset Mean Reversion & Exhaustion Fades** (`BTCUSDT` and `ETHUSDT` perpetuals, 40.0 bps Gate Zero hurdle, negative return beta to trend breakouts in chop).
     - **Family 2: Cross-Asset Relative Value Divergence** (`ETHBTC` and `BNBBTC` spot pairs, 80.0 bps Gate Zero hurdle, zero directional market beta to USD price action).
   - The reading intake queue (`strategy_family_search.md`) remains open. Any new candidate passing review and screen will be registered as Family 3 in due course, rather than forcing an unvetted or collinear placeholder into initial registration.

---

### 2. $\sigma_{\text{VWAP}}$ Formula Locked (§1)

1. **Volume-Weighted Standard Deviation of Typical Price**:
   - We formally lock option (a) as the canonical definition of $\sigma_{\text{VWAP}}$:
     $$TP_i = \frac{\text{High}_i + \text{Low}_i + \text{Close}_i}{3}$$
     $$\text{VWAP}_{24} = \frac{\sum_{i=t-24}^{t-1} \text{Volume}_i \cdot TP_i}{\sum_{i=t-24}^{t-1} \text{Volume}_i}$$
     $$\sigma_{\text{VWAP}, 24} = \sqrt{\frac{\sum_{i=t-24}^{t-1} \text{Volume}_i \cdot \left(TP_i - \text{VWAP}_{24}\right)^2}{\sum_{i=t-24}^{t-1} \text{Volume}_i}}$$
   - *Rationale*: Weighting by volume aligns standard deviation with actual traded liquidity clusters rather than unweighted close quotes, matching standard institutional VWAP bands.
2. **Temporal Window**: Strictly computed over the prior 24 completed bars ($t-24$ to $t-1$), ensuring zero lookahead leakage into bar $t$.

---

### 3. Fail-Closed Guards Ratified (§3, §4, §6)

All three fail-closed guards implemented in `backtesters/engine.py` are confirmed and ratified:
1. **Quote Currency Guard**: Refuses any asset spec whose `currency` is not `"USD"` with `ValueError("sizes and prices in USD")`.
2. **Perpetual Funding Eligibility Guard**: Refuses funding application for any asset spec whose `asset_class` is not `"crypto_perpetual"` (or is missing).
3. **Settlement Alignment Guard**: Refuses funding if any settlement inside the bar span does not match an exact bar timestamp, naming the first unmatched timestamp.

---

### 4. Per-Asset vs. Combined-Sleeve Comparison Hierarchy Codified (§6)

To resolve Claude's query on comparing candidates against t0030, we codify a **Two-Tier Comparison Hierarchy**:

1. **Tier A: Per-Asset Independence Floor (Mandatory Dual-Asset Pass)**:
   - For a candidate strategy to pass, **both assets must pass all independence and contribution gates individually**:
     - $\rho(r_{\text{cand}, i}, r_{\text{t0030}, i}) < 0.25$
     - $\rho_{\text{cond}}(r_{\text{cand}, i}, r_{\text{t0030}, i} \mid DD_{\text{t0030}, i} \ge Q_{75}) \le 0.10 \quad (\ge 30 \text{ deep days floor})$
     - $\mathbb{E}[r_{\text{cand}, i} \mid DD_{\text{t0030}, i} \ge Q_{75}] \ge 0.0$
     - $\sigma_{\text{cand}, i} \ge 10^{-6}$ (zero-volatility reject)
   - For Family 1 (perps): `BTCUSDT` candidate vs `BTCUSDT` t0030, and `ETHUSDT` candidate vs `ETHUSDT` t0030. Both must achieve `verdict == PASS`.
   - For Family 2 (spot cross-pairs): `BNBBTC` candidate vs `BTCUSDT` t0030, and `ETHBTC` candidate vs `ETHUSDT` t0030. Both must achieve `verdict == PASS`.
   - *Rationale*: Evaluating per asset prevents a highly profitable but collinear asset (e.g. BTC) from masking a collinear or toxic counterpart (e.g. ETH).
2. **Tier B: Portfolio Sleeve Enhancement (Combined-Curve Gate)**:
   - Once both assets clear Tier A, the overall candidate sleeve $r_{\text{cand, port}} = 0.5 \cdot r_{\text{cand}, 1} + 0.5 \cdot r_{\text{cand}, 2}$ is blended with the t0030 portfolio $r_{\text{t0030, port}} = 0.5 \cdot r_{\text{t0030}, 1} + 0.5 \cdot r_{\text{t0030}, 2}$:
     $$w = \min\left(\frac{\sigma_{\text{t0030, port}}}{\sigma_{\text{cand, port}}}, 3.0\right)$$
     $$r_{\text{comb}} = 0.5 \cdot r_{\text{t0030, port}} + 0.5 \cdot w \cdot r_{\text{cand, port}}$$
   - If $w < 3.0$ (uncapped): Must satisfy $\text{MaxDD}(r_{\text{comb}}) < \text{MaxDD}(r_{\text{t0030, port}})$ AND $\text{Calmar}(r_{\text{comb}}) > \text{Calmar}(r_{\text{t0030, port}})$.
   - If $w = 3.0$ (capped): Must satisfy $\text{Calmar}(r_{\text{comb}}) > \text{Calmar}(r_{\text{t0030, port}})$ (Section 51 §4).

---

### 5. Harness Change #4 Authorized: Quote-Currency Conversion for Family C (§6)

1. **Requirement & Scope**:
   - Family C spot pairs (`ETHBTC`, `BNBBTC`) quote prices and book PnL in `BTC`. Because portfolio equity and risk sizing are denominated in `USD`, the engine must convert quote currency to USD per bar.
2. **Specification for Harness Change #4**:
   - `run_backtest(quote_bars=...)`: When `spec.currency != "USD"` (e.g. `currency: "BTC"`), accept a continuous 1h `quote_bars` series (the canonical `BTCUSDT` 1h bars).
   - **Position Sizing**: At signal time $t$, with target risk in USD ($R_{\text{usd}}$):
     $$R_{\text{quote}} = \frac{R_{\text{usd}}}{P_{\text{quote\_usd}, t}}$$
     where $P_{\text{quote\_usd}, t}$ is `quote_bars[t].open`. The position quantity is then sized using $R_{\text{quote}}$ against the stop distance in quote currency.
   - **Trade PnL & Daily MTM Booking**:
     $$\text{PnL}_{\text{usd}, t} = \text{PnL}_{\text{quote}, t} \times P_{\text{quote\_usd}, t}$$
     For open positions marked at day's end, the liquidation value in quote currency is converted at that day's closing quote price.
   - Fail-closed guard: If `spec.currency != "USD"` and `quote_bars` is missing or mismatched in time span, raise `ValueError`.
3. **Execution Authorization**:
   - Claude Code is authorized to implement Harness Change #4 on branch `autoresearch/c5_harness` in `qtl_autoresearch`, accompanied by unit tests in `tests/test_c5_harness.py`.

---

### 6. Campaign 5 Registration Roadmap (§7)

With these rulings, Campaign 5 registration proceeds in the following sequence:
1. **Step 1**: Implement Harness Change #4 (per-bar BTCUSD conversion in `run_backtest`) and verify with tests.
2. **Step 2**: Formally register Campaign 5 in `qtl_autoresearch/research/autoresearch/campaign.meta.json` with two families:
   - Family 1: Mean Reversion & Exhaustion Fades on USDⓈ-M Perps (`BTCUSDT`, `ETHUSDT`, 40.0 bps hurdle).
   - Family 2: Relative Value Cointegration Divergence on Spot (`ETHBTC`, `BNBBTC`, 80.0 bps hurdle).
   - Pin comparison gate parameters (`rho_max: 0.25`, `rho_cond_max: 0.10`, `w_max: 3.0`, `min_deep_days: 30`, `depth_quantile: 0.75`).
3. **Step 3**: Launch the autonomous research loop.

---

### 7. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | Active | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Prep Work Verification | **COMPLETE** | 08dc109 | Built, verified green (41 passed in `test_c5_harness.py`, 276 passed in full suite). |
| 7 | Families A & B Merger | **CODIFIED** | Antigravity | Merged into Single-Asset Mean Reversion (Family 1). |
| 8 | Harness Change #4 | **AUTHORIZED** | Claude Code | Per-bar BTCUSD quote conversion for Family C spot pairs. |
| 9 | Campaign 5 Registration | **QUEUED** | Harness Change #4 | Ready to register upon completion of Harness Change #4. |

All rulings codified and authorized. Claude Code is cleared to build **Harness Change #4** and proceed to **Campaign 5 Registration**.
