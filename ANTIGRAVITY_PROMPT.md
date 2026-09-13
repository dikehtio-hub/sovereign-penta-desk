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

## Section 50: Family A Wick Definition Locked (50% Range), Tier 2 6-Month Floor Reaffirmed, MTM Boundary Booking & Volatility Cap, and Funding Archive Host Ratified

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 00:35 EDT / 2026-09-13 04:35Z  
**Re**: Ruling on four precision points and implementation authorization from Claude Code's handoff:  
(1) Family A wick rule locked strictly to $\ge 50\%$ of range (71 BTC / 71 ETH OOS events, eliminating two-wick indecision bars; frequency-only snooping boundary recorded);  
(2) Tier 2 sovereign promotion gate realigned to registry floor ($\ge 6.0$ months, $\ge 50$ forward trades) with dedicated candidate paper sleeve requirement (`config/paper_<strategy_id>.yaml`);  
(3) Harness Change #3 (Daily MTM) three conditions codified: boundary open position booking at fold ends, bit-identical closed-trade score regression invariant ($S = 2.0900$), and guarded volatility weight with division-by-zero rejection and leverage cap ($w_{\max} = 3.0$);  
(4) Funding backfill path locked to `quant_trading_lab/data/continuous/` (`.gitignore` compliant) and primary archive host locked to `https://data.binance.vision/data` (keyless, non-geoblocked);  
(5) Family B 8-day run duration hurdle noted as first empirical test;  
(6) Implementation plan on new `qtl_autoresearch` branch ratified, awaiting operator go-ahead.  
**State**: DEV `fb8e7e9` + 42 dirty (21 modified, 21 untracked), 0 staged, measured 2026-09-13 04:16:51Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. Genuinely clean: `qtl_autoresearch` `2e9d222` on `autoresearch/c4_donchian_crypto_1h`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Concurrences & Protocol Verification (§0)

1. **Protocol Adherence Confirmed**: Exact HEAD `fb8e7e9` and dirty count (42 entries) verified via runtime git query immediately prior to assembly.
2. **Empirical Measurements Ratified**:
   - Claude's wick rule differentiation verified: "$\ge 50\%$ of range" yields 71 BTC / 71 ETH OOS events, while "$\ge \text{body}$" yields 89 BTC / 79 ETH.
   - Trade arrival rates verified: t0030 generates ~9.6 trades/month; Family A ceiling is ~0.30 events/day. Reaching 50 forward trades requires > 5 months in both cases, making a 60-day floor non-binding.
   - Backfill gitignore alignment verified: `data/continuous/*.csv` is ignored; `data/funding/` is unignored.
   - Archive host verified: `data.binance.vision` is accessible without geo-blocking, whereas `fapi.binance.com` is subject to geographic IP filters.

---

### 1. Family A: Wick Definition Formally Locked to 50% of Range (§1)

1. **Single Canonical Rule Registered**:
   The candidate trigger is formally locked to **rejection wick $\ge 50\%$ of total bar range**:
   $$\text{Wick}_{\text{rejection}} \ge 0.50 \times (\text{High} - \text{Low})$$
   - Upper wick for short fade: $\text{High} - \max(\text{Open}, \text{Close}) \ge 0.50 \times (\text{High} - \text{Low})$
   - Lower wick for long fade: $\min(\text{Open}, \text{Close}) - \text{Low} \ge 0.50 \times (\text{High} - \text{Low})$
2. **Elimination of Two-Wick Indecision**:
   The alternative formulation ($\text{wick} \ge \text{body}$) is rejected because it permits spinning tops / dojis where an upper wick of 35%, body of 30%, and lower wick of 35% satisfies $\text{wick} \ge \text{body}$ despite indicating two-sided market indecision rather than directional liquidity exhaustion. The 50% range rule strictly demands that a single wick exceeds the sum of the body and the opposing wick.
3. **Audit Trail on Snooping Boundary**:
   We formally register that the 50% threshold was selected exclusively from **OOS-window event frequency counts (71 BTC / 71 ETH)** without inspecting trade returns, expectancy, or PnL, confining search degrees of freedom strictly to sample adequacy.

---

### 2. Tier 2: Registry Alignment (6 Months) & Isolated Candidate Sleeves (§2)

1. **Promotion Horizon Realigned**:
   The sovereign promotion floor is formally reconciled with `campaign.meta.json`:
   $$\text{Forward Incubation Floor} = \ge 6.0\text{ months AND } \ge 50\text{ forward trades}$$
   Both criteria are joint conditions. No candidate may be promoted to live Desk 1 capital deployment in under 6 months.
2. **Dedicated Paper Configuration per Candidate**:
   `config/paper_donchian_t0030.yaml` is exclusively reserved for champion t0030 (`STACK_10_DONCHIAN_BREAKOUT`, streak breaker 25, 5.0% HWM trailing stop).
   Any candidate reaching Tier 2 forward incubation must be deployed with **its own dedicated paper configuration file** (e.g. `config/paper_<strategy_id>.yaml`) assigned to its own isolated strategy stack ID (e.g. `STACK_9_CANDIDATE` or dedicated stack), parameterized with its own empirical losing streak breaker and risk budget.

---

### 3. Harness Change #3: Three Conditions Codified (§3)

1. **Condition 1 (Boundary Position Booking with Friction)**:
   At the terminal bar of each walk-forward fold test window, any open position dropped by `run_backtest` must be marked to market at the final bar's close price less exit taker friction ($10\text{ bps}$ for perps, venue-specific for spot). The high-water mark for the subsequent fold carries over from this adjusted equity balance, ensuring continuous mark-to-market accounting across fold seams.
2. **Condition 2 (t0030 Closed-Trade Score Invariant)**:
   The addition of the daily MTM series output must preserve the existing closed-trade evaluation engine with zero side effects: t0030's benchmark score must remain **bit-identical** ($S = 2.0900$, BTC $PF = 2.1287$, ETH $PF = 2.0900$, 752 IS trades, 258 OOS trades across the 4 folds). This serves as the primary regression acceptance test.
3. **Condition 3 (Guarded Volatility Weight & Leverage Ceiling)**:
   The candidate volatility scaling factor $w = \sigma_{t0030} / \sigma_{\text{cand}}$ must be strictly bounded:
   - **Zero / Near-Zero Volatility Guard**: If $\sigma_{\text{cand}} < 10^{-6}$ (flat equity curve or inactive candidate), the strategy is immediately rejected: `verdict: reject`, `reason: zero_volatility`. No division by zero.
   - **Leverage Ceiling**: To prevent low-volatility delta-neutral sleeves (such as Family B funding carry) from assuming mathematically unbounded leverage that exceeds Desk 1 margin constraints, the scaling factor is capped:
     $$w = \min\left(\frac{\sigma_{t0030}}{\sigma_{\text{cand}}}, w_{\max}\right), \quad \text{with } w_{\max} = 3.0$$
     A candidate sleeve may contribute at most $3\times$ notional leverage relative to its baseline variance.

---

### 4. Funding Backfill Path & Archive Host Locked (§4)

1. **Path Locked to Git-Ignored Continuous Root**:
   Funding CSVs will be saved to:
   - `quant_trading_lab/data/continuous/BTCUSDT_funding_binance.csv`
   - `quant_trading_lab/data/continuous/ETHUSDT_funding_binance.csv`
   This leverages the existing `.gitignore:12` rule (`data/continuous/*.csv`), ensuring zero untracked file proliferation, zero dirty state impact, and seamless collocation with existing 1h OHLCV data.
2. **Host Locked to Binance Vision Archive**:
   `fetch_binance_funding.py` must use `https://data.binance.vision/data` as its primary download host (keyless, free, and free of geo-blocking restrictions), falling back to `fapi.binance.com` only if the vision archive is missing specific monthly chunks.

---

### 5. Family B 8-Day Run Hurdle Acknowledged (§5)

- Accepted Claude's calculation: With a 120 bps Gate Zero hurdle on cash-and-carry (30 bps 2-leg taker $\times 4$) and a $\pm 0.05\%/8\text{h}$ funding rate yielding 15 bps/day, funding carry alone requires $\sim 8$ consecutive days at or above the extreme rate.
- As soon as the backfill is complete, measuring the empirical distribution of extreme funding run lengths ($\ge 8$ days) and basis convergence dynamics will serve as the initial feasibility filter for Family B.

---

### 6. Architectural Approval of Claude's Build Plan (§6)

- The proposed build branch in `qtl_autoresearch` (branching from `2e9d222`, preserving `autoresearch/c4_donchian_crypto_1h` sealed) is **architecturally ratified**.
- Sequence: (1) Vision funding fetcher $\to$ (2) daily MTM series with boundary booking and bit-identical regression $\to$ (3) funding PnL.
- The operator is presented with the prompt to provide the final execution go-ahead.

---

### 7. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | **NEXT** | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Harness Changes 1–3 Build | **READY** | **Operator Go-Ahead** | New branch off `2e9d222`; vision fetcher $\to$ continuous root $\to$ MTM $\to$ funding PnL. |
| 7 | Campaign 5 Registration | Queued | Harness Ready | Two-tier holdout, 468-day OOS MTM gates, matched-volatility combined curve. |
| 8 | Operator Reading Inbox | **READY** | Operator | Family A (50% range wick), Family B (funding carry), Family C (`ETHBTC` + `BNBBTC`). |

All four rulings finalized. Systems standing by for the **Operator's Go-Ahead** on Harness Changes 1–3 and Sunday's lead-lag gate closure at **15:21Z (~11:21 EDT)**.
