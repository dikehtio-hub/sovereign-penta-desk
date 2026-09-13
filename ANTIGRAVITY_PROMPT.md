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

## Section 48: Correlation Gate Quantile Conditioning, Drawdown Contribution Gate, 6.8-Year Binance Funding Horizon, and Multi-Leg Friction Codified

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 00:15 EDT / 2026-09-13 04:15Z  
**Re**: Re-ruling §1–§3 and formalizing the four smaller notes: replacement of absolute drawdown threshold with top-quartile empirical conditioning and 30-day floor, addition of the non-negative drawdown contribution gate, elevation of Pillar 5 combined-curve improvement as binding arbiter, codification of the 6-year 8-month (2020–2026) historical horizon with keyless Binance archive backfill, OHLCV-only formulation of Family A exhaustion spikes, directly listed ETHBTC pair preference for Family C, and multi-leg friction scaling for Gate Zero.  
**State**: DEV `8d04b4d` + 40 dirty (20 modified, 20 untracked), 0 staged, measured 2026-09-13 04:05Z. Lab master `82ffcba` + 19 dirty, 0 staged. Genuinely clean: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Concurrences Confirmed (§0)

1. **Accepted as Ruled**: §1 conditional ratification (untrusted-content clause, runtime socket blocker, static AST checks), §2.1 distinct GitHub stems, §2.2 exit 1 only for new failures, and §3 remote-privacy pivot with `raw/fetched/` local/uncommitted.
2. **Empirical Fact Ratified**: Claude's trade-by-trade drawdown measurement is accepted: t0030 single-asset max drawdowns ($687.49 / 0.69% BTC, $903.54 / 0.90% ETH OOS; 1.46% BTC, 1.98% ETH holdout) never cross 2.0%. A fixed 2.0% conditioning set on the research span was empty.

---

### 1. Correlation Gate Re-Ruled: Quantile Conditioning & 30-Day Sample Floor (§1)

An arbitrary absolute threshold (2.0%) is discarded. The conditioning set is formally redefined from t0030's **empirical drawdown distribution on the research span**:

1. **Conditioning Set Definition**:
   $$\mathcal{D}_{\text{deep}} = \left\{ t \in \text{Research Span} \;\Big|\; \text{Drawdown}_{t0030}(t) \ge Q_{75}(\text{Drawdown}_{t0030}) \right\}$$
   where $Q_{75}$ is the 75th percentile (deepest quartile) of t0030's daily marked-to-market drawdown curve.
2. **Sample Size Floor**:
   $$|\mathcal{D}_{\text{deep}}| \ge 30 \text{ trading days}$$
   If $|\mathcal{D}_{\text{deep}}| < 30$, Metric 2 evaluates to `INCONCLUSIVE`, never `PASS`.
3. **The Conditional Correlation Threshold**:
   $$\rho\left(r_{\text{cand}}^{\text{MTM}}, r_{t0030}^{\text{MTM}} \;\Big|\; t \in \mathcal{D}_{\text{deep}}\right) \le 0.10$$

---

### 2. The Anti-Inactivity Floor & Binding Combined-Curve Gate (§2)

To prevent a strategy that sits flat from passing on zero variance ($ho \approx 0$):

1. **Drawdown Contribution Condition**:
   The candidate's mean daily MTM return during t0030's deepest drawdown quartile must be non-negative:
   $$\mathbb{E}\left[r_{\text{cand}}^{\text{MTM}} \;\Big|\; t \in \mathcal{D}_{\text{deep}}\right] \ge 0.0\text{ bps/day}$$
2. **The Binding Gate: Campaign 5 Pillar 5 Combined Equity Curve**:
   Correlation and contribution are intake screening filters. **The binding arbiter for candidate promotion is Portfolio Risk Improvement**:
   $$\text{MaxDD}\left(0.5 \cdot \text{t0030} + 0.5 \cdot \text{Candidate}\right) < \text{MaxDD}(\text{t0030})$$
   $$\text{Calmar}\left(0.5 \cdot \text{t0030} + 0.5 \cdot \text{Candidate}\right) > \text{Calmar}(\text{t0030})$$
   evaluated at an identical total capital risk budget ($100k basis). A candidate that cancels t0030's winners or fails to reduce portfolio drawdown is rejected regardless of correlation.

---

### 3. Historical Horizon Codified: 6 Years 8 Months (2020–2026) & Binance Backfill (§3)

1. **The 80-Month Continuous Horizon**:
   The autoresearch loop spans **2020-01-01 to 2026-09-01 (6 years 8 months)** across both segments:
   - Virgin Holdout: 2020-01-01 to 2023-01-01 (36 months)
   - Research Span: 2023-01-01 to 2026-09-01 (44 months)
   Any signal evaluated by the loop MUST have continuous data reaching back to 2020-01-01. Hyperliquid's local database (`hyperliquid_data.db`, 8 days) cannot supply the loop and is reserved for Desk 1 live execution.
2. **Keyless Binance Archive Backfill Mandated**:
   - Tooling to construct: `scripts/fetch_binance_funding.py`, downloading free, keyless historical 8h funding rate data for BTCUSDT and ETHUSDT from Binance's public data repository (which dates back to late 2019).
   - Engine Extension: Implement funding rate PnL cashflow accretion into the backtest engine.
   - Cost: $0. Paid third-party APIs (e.g. Moon Dev) are prohibited for backfill data.

---

### 4. Strategy Screen & Intake Refinements (§4)

1. **Family A (Exhaustion Fades) Defined Strictly via OHLCV**:
   Because liquidation tick data is only 8 days deep, the autoresearch track must define exhaustion spikes purely from 1h OHLCV bars:
   - Range Expansion: Bar range $(H - L) \ge 2.5 \times \text{ATR}_{24}(1h)$.
   - Volume Spike: Bar volume $V \ge 3.0 \times \text{SMA}_{24}(V)$.
   - Rejection Wick: Upper or lower wick $\ge 60\%$ of total bar range.
2. **Family C (Cross-Asset Divergence) Pair Selection**:
   - Prefer directly listed pairs on Binance (e.g. `ETHBTC` spot/perp) over synthetic ratios to pay a single leg of friction (10 bps round-trip instead of 20 bps).
   - To preserve cross-asset validation ($S = \min(PF_1, PF_2)$), register a second listed cross pair (e.g. `SOLBTC` or `BNBBTC`).
3. **Multi-Leg Friction Scaling for Gate Zero**:
   Gate Zero hurdle scales directly with trade execution legs:
   $$\text{Hurdle}_{\text{bps}} = 4 \times (10\text{ bps} \times N_{\text{legs}}) = 40\text{ bps} \times N_{\text{legs}}$$
   Single-leg directional perps: 40.0 bps. Two-leg cash-and-carry or cross-currency spreads: 80.0 bps.
4. **URL Normalization Fixes**:
   - Stable query sort: `sorted(parse_qsl(q), key=lambda x: x[0])` (preserves relative order of repeated parameters like `?id=1&id=2`).
   - Scheme normalized to `https:`; `www.` stripped uniformly.

---

### 5. Standing Ledger: Reconciled (§5)

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Remote Privacy Choice | Active | Operator | "Will remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | **NEXT** | Intake Session | Injection defense clause, runtime socket blocker, GitHub path fix, stable sort. |
| 6 | Funding Backfill Tooling | **QUEUED** | Implementation | `fetch_binance_funding.py` (free 2020–2026 data) + engine funding cashflow hook. |
| 7 | Reading Inbox Submissions | **READY** | Operator | Operator drops links in `READING.md` across Families A (OHLCV spikes), B (carry), C (ETHBTC). |

All rulings finalized and quantified. Systems standing by for Sunday's lead-lag gate closure at **15:21Z (~11:21 EDT)**.
