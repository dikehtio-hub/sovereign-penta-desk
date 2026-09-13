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

## Section 49: Campaign 5 Holdout Architecture, OOS-Only Daily MTM Gates, Family A Wick Calibration, Matched-Volatility Combined Curve, and Dynamic Friction Hurdle Codified

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 00:25 EDT / 2026-09-13 04:25Z  
**Re**: Ruling on four measured facts and two corrections from Claude Code's handoff:  
(1) Holdout doctrine: Two-tier validation architecture (2020–2022 historical invariance stress screen vs. Forward Desk 1 incubation for sovereign promotion);  
(2) OOS-only evaluation of daily MTM gates across pooled fold test windows (~468 days) with high-water mark continuity;  
(3) Family A baseline convention locked to prior 24 bars ($t-24$ to $t-1$) and pre-registration wick threshold calibrated from $\ge 60\%$ to $\ge 50\%$ (wick-to-body $\ge 1.0$) to guarantee $> 40$ OOS trade robustness on ETH;  
(4) Combined-curve gate hardened with volatility matching ($w = \sigma_{t0030}/\sigma_{\text{cand}}$) to eliminate cash/low-volatility dilution loopholes;  
(5) Venue-specific Gate Zero friction scaling ($4 \times \text{Friction}_{\text{round-trip}}$) and Family C pair substitution (`BNBBTC` for unlisted `SOLBTC`);  
(6) Safe directory specification for keyless Binance funding backfill.  
**State**: DEV `6bd9d6d` + 42 dirty (21 modified, 21 untracked), 0 staged, measured 2026-09-13 04:05:36Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. Genuinely clean: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Concurrences & Protocol Verification (§0)

1. **Protocol Adherence Confirmed**: Exact HEAD `6bd9d6d` and dirty count (42 entries) verified via runtime git query immediately prior to assembly.
2. **Empirical Measurements Ratified**:
   - 2020–2022 span evaluated tonight by t0030 (`holdout_t0030.json`).
   - Backtest engine output is currently limited to `ClosedTrade` without a daily marked-to-market series.
   - Genuine OOS returns for t0030 exist only on ~468 days across the 4 walk-forward fold test windows (~65% of the 1,339-day research span is in-sample fitted).
   - Family A's 60% wick filter clears ETH trade floor by only +3 (43 events), and fails (37 events) if bar $t$ is included in baseline.
   - Halving t0030 allocation halves its MaxDD, allowing an inactive or low-variance candidate to pass `MaxDD(0.5·t0030 + 0.5·cand) < MaxDD(t0030)`.
   - Binance standard taker friction: Spot is ~20 bps round-trip (0.10%/side), USDⓈ-M perp is ~10 bps round-trip (0.05%/side).
   - SOL was unlisted on Binance on 2020-01-01; BNB was listed in 2017.

---

### 1. Campaign 5 Holdout Architecture & Sovereign Promotion Gate (§1)

1. **Doctrine Maintained**: We strictly uphold the econometric principle stated in `campaign.meta.json`'s `span_note`: *"Calendar direction is irrelevant to statistical independence; exposure is what matters."* Because 2020–2022 was evaluated by t0030, the entire 2020–2026 span has been exposed to the research ecosystem. It will NOT be dishonestly relabeled "virgin" for Campaign 5.
2. **Two-Tier Validation Framework Codified**:
   - **Tier 1 (Historical Invariance Screen — 2020-01-01 to 2023-01-01)**: Mandatory pre-promotion backtest obstacle course. Any candidate strategy must demonstrate regime invariance across the March 2020 Covid liquidity cascade, the 2021 bull run, and the 2022 Luna/3AC/FTX deleveraging regime ($PF > 1.20$, $\ge 40$ trades, $\text{MaxDD} < 8.0\%$). *Clearing Tier 1 is a necessary filter, but is NOT sufficient for live capital allocation.*
   - **Tier 2 (Sovereign Promotion Gate — Forward Desk 1 Paper Incubation)**: True sovereign promotion to live risk capital is governed strictly by **Forward Out-of-Sample Incubation** on Desk 1 (post-2026-09-01 continuous execution via the isolated `paper_donchian_t0030.yaml` runner). Minimum promotion criteria: $\ge 50$ forward trades, $\ge 60$ days tracking, positive Sharpe, and continuous Gate Zero edge clearance ($> 4\times$ round-trip friction).
3. **Family B (Funding Rate Carry) Resolution**:
   - Retrospective funding rate backfill (2020–2026) feeds 4-fold walk-forward research and Tier 1 historical stress testing.
   - Because perpetual funding data does not exist prior to late 2019, Family B's promotion path is exclusively forward incubation on Desk 1. This removes any requirement for retrospective pre-2020 data.

---

### 2. Daily MTM Engine Output & OOS-Only Gate Evaluation (§2)

1. **Harness Change #3 Formally Authorized**: The backtest engine's `run_backtest` must be modified to output a daily marked-to-market (MTM) portfolio equity time series at 00:00 UTC daily (capturing cash balance + realized PnL + unrealized PnL of open positions evaluated at the daily close).
2. **Strict OOS Test Window Pairing**:
   - Comparative gates against t0030 must NOT be evaluated against in-sample t0030 returns.
   - Unconditional correlation ($\rho < 0.25$), drawdown-conditioned correlation ($\rho_{\text{cond}} \le 0.10$), contribution floor ($\mathbb{E}[R_{\text{cand}} \mid DD_{t0030} \in Q_{75}] \ge 0$), and combined curve metrics are evaluated **exclusively on the pooled ~468 out-of-sample fold test days** (`t0030.json` Folds 1–4).
   - Campaign 5 walk-forward grid will register with the **exact same fold test windows** as Campaign 4:
     - Fold 1: 2023-08-06 → 2023-12-01
     - Fold 2: 2024-07-06 → 2024-10-31
     - Fold 3: 2025-06-06 → 2025-10-01
     - Fold 4: 2026-05-06 → 2026-08-31
3. **High-Water Mark Continuity Across Folds**:
   - Equity curves across the 4 OOS fold windows are concatenated into a contiguous 468-day realization: Fold $k+1$ inherits the terminal equity and high-water mark of Fold $k$.
   - Drawdowns carry across fold boundaries without artificial resets.
   - Conditioning set check: The deepest 25% of ~468 pooled OOS days is ~117 days, comfortably exceeding the 30-day sample floor.

---

### 3. Family A Baseline Convention & Pre-Registration Wick Calibration (§3)

1. **Baseline Convention Locked**: The baseline is strictly defined as the **preceding 24 bars** ($t-24$ to $t-1$), ensuring zero lookahead bias and preventing the spike bar itself from distorting its own rolling reference frame.
2. **Pre-Registration Wick Calibration ($\ge 50\%$)**:
   - Ratifying Claude's empirical measurement: A 60% wick filter yields only 43 events on ETH (+3 above the 40 floor), which is too fragile once trade holding periods or execution constraints are layered.
   - Pre-registration adjustment: The wick rejection threshold is calibrated from $\ge 60\%$ to **$\ge 50\%$** (i.e. wick-to-body ratio $\ge 1.0:1$, where the upper shadow for shorts or lower shadow for longs constitutes at least $50\%$ of the total bar range $[High - Low]$).
   - Quantitative justification: A 50% wick on a bar exhibiting Range $\ge 2.5\times \text{ATR}_{24}$ and Volume $\ge 3.0\times \text{VolSMA}_{24}$ represents an unmistakable exhaustion pin bar / price rejection, while expanding ETH candidate triggers by ~35–45% to ~60–65 OOS events. This provides a robust buffer above the $\ge 40$ trade floor.

---

### 4. Matched-Volatility Combined-Curve Gate Codified (§4)

1. **Cash Dilution Loophole Sealed**: Accepted Claude's proof that a cash-heavy or low-volatility candidate can trivially pass `MaxDD(0.5·t0030 + 0.5·cand) < MaxDD(t0030)` simply by diluting t0030's risk.
2. **Matched-Volatility Combined Curve**:
   - Prior to blending, the Candidate sleeve's daily MTM returns $R_{\text{cand}, t}$ over the 468 OOS days are rescaled to match t0030's realized volatility:
     $$\sigma_{t0030} = \text{std}(R_{t0030}^{\text{OOS}}), \quad \sigma_{\text{cand}} = \text{std}(R_{\text{cand}}^{\text{OOS}}), \quad w = \frac{\sigma_{t0030}}{\sigma_{\text{cand}}}$$
     $$R_{\text{cand}, t}^* = w \times R_{\text{cand}, t}$$
   - The combined portfolio is constructed at equal risk weight:
     $$R_{\text{comb}, t} = 0.5\, R_{t0030, t} + 0.5\, R_{\text{cand}, t}^*$$
   - The combined curve gate requires:
     1. $\text{MaxDD}(R_{\text{comb}}) < \text{MaxDD}(R_{t0030})$
     2. $\text{Calmar}(R_{\text{comb}}) > \text{Calmar}(R_{t0030})$
   - Under this formulation, low-volatility strategies have their drawdowns magnified proportionally to their risk budget, preventing cash-dilution exploits while rewarding true non-collinear diversification.

---

### 5. Dynamic Gate Zero Friction Hurdle & Family C Pair Substitution (§5)

1. **Venue-Specific Round-Trip Friction Scaling**:
   - Gate Zero hurdle formula codified:
     $$\text{Gate Zero Hurdle} = 4 \times \text{Friction}_{\text{round-trip}}$$
   - USDⓈ-M Perps (10 bps round-trip taker): **40.0 bps** hurdle (Family A, Family B perp leg).
   - Binance Spot Listed Pairs (20 bps round-trip taker): **80.0 bps** hurdle (Family C spot pairs).
   - Multi-leg Cash-and-Carry (Spot long + Perp short = 30 bps round-trip taker): **120.0 bps** hurdle.
2. **Family C Pair Substitution (`BNBBTC`)**:
   - Acknowledged that SOL was not listed on Binance on 2020-01-01.
   - `BNBBTC` (listed in 2017) is formally designated as the second asset alongside `ETHBTC`. Both pairs provide continuous 1h OHLCV across the entire 2020–2026 horizon, maintaining the 2-asset minimum robustness standard.

---

### 6. Funding Backfill Path & Execution Approval (§6)

1. **Dedicated Isolated Path**: To avoid contaminating `quant_trading_lab/data/continuous/` (fenced tree with uncommitted work), `fetch_binance_funding.py` must save funding rate archives to an isolated dedicated path: `quant_trading_lab/data/funding/` or `research/data/funding/`.
2. **Keyless Execution Approved**: The script is authorized to proceed using Binance's public, keyless REST endpoint (`fapi.binance.com/fapi/v1/fundingRate`) across BTCUSDT and ETHUSDT for 2020–2026.

---

### 7. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | **NEXT** | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Harness Changes 1–3 | **AUTHORIZED** | Claude Implementation | (1) Funding fetcher (`data/funding/`), (2) funding PnL, (3) daily MTM time series. |
| 7 | Campaign 5 Registration | Queued | Harness Ready | Two-tier holdout, 468-day OOS MTM gates, matched-volatility combined curve. |
| 8 | Operator Reading Inbox | **READY** | Operator | Family A (prior 24b, $\ge 50\%$ wick), Family B (funding carry), Family C (`ETHBTC` + `BNBBTC`). |

All items ruled. Systems standing by for Sunday's lead-lag gate closure at **15:21Z (~11:21 EDT)**.
