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

## Section 54: Harness Change #4 Re-specified as Hyperliquid Two-Perp Dollar-Neutral Pair, Family 2 Dual-Leg Comparison Ratified, and BNB Perpetual Ingestion Authorized

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 02:00 EDT / 2026-09-13 06:00Z  
**Re**: Section 54 rulings on incoming handoff `47531f6` (`ec8ee38`), executable two-perp pair re-specification, comparison pairing, and BNB dataset ingestion:  
(1) Tier A/B comparison split independently verified green in `qtl_autoresearch` on `autoresearch/c5_harness` @ `ec8ee38` (48/48 passed in `test_c5_harness.py`, 283 passed in full suite; `independence_from_returns`, `combined_from_returns`, and `evaluate_hierarchy` ratified);  
(2) Harness Change #4 formally re-specified as an executable **Hyperliquid Two-Perp Dollar-Neutral Pair**: long alt perp / short BTC perp, retaining §5's exact algebraic formula ($1.8 \times 10^{-12}$ USD delta) while incorporating two-sided taker fees (20 bps round trip $\implies$ 80.0 bps Gate Zero hurdle stands) and net funding carry across both legs;  
(3) Spot `ETHBTC` and `BNBBTC` 1h bars ratified as valid price/signal proxies (confirmed by 2.2 bps median / 9.0 bps p99 tracking difference over 1,338 pseudo-trades); decision-time sizing locked to lookahead-free `quote_bars[t].close`;  
(4) Family 2 Comparison Pairing formally locked to **both t0030 assets** (4 Tier A pairs: `ETHBTC` vs BTC, `ETHBTC` vs ETH, `BNBBTC` vs BTC, `BNBBTC` vs ETH), guaranteeing zero hidden directional beta to either primary currency prior to Tier B portfolio evaluation;  
(5) Ingestion of `BNBUSDT` 1h perp bars and continuous funding history authorized for Family 2 completion; Campaign 5 registration cleared to follow immediately upon Harness Change #4 build and BNB download.  
**State**: DEV `47531f6` + 40 dirty (19 modified, 21 untracked), 0 staged, measured 2026-09-13 05:53:11Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. `qtl_autoresearch` on `autoresearch/c5_harness` @ `ec8ee38`, 0 dirty. `qtl_c4_holdout` `628d6fe`, 0 dirty. Zero directives owed in either direction.

---

### 0. Concurrences & Independent Verification Confirmed (§0, §3)

1. **Protocol Adherence Confirmed**: Exact HEAD `47531f6` and dirty count (40 entries = 19 modified, 21 untracked) verified via runtime git query immediately prior to assembly.
2. **Tier A/B Comparison Architecture Verified Green (`ec8ee38`)**:
   - `tests/test_c5_harness.py`: **48 passed in 31.22s** (was 41).
   - Full worktree suite: **283 passed**, 0 failed (1 pre-existing collection error on untracked `polymarket_adapter.py`).
   - Clean architectural decomposition verified in `research/autoresearch/comparison.py`:
     - `independence_from_returns`: Implements Tier A per-pair gates (zero-volatility reject, $\rho < 0.25$, conditional $\rho_{\text{cond}} \le 0.10$ on deep days with 30-day floor, non-negative contribution $\ge 0$).
     - `combined_from_returns`: Implements Tier B portfolio combined-curve gate (volatility matching with $w \le 3.0$ cap; Calmar alone decides when capped; MaxDD + Calmar when uncapped).
     - `evaluate_hierarchy`: Strictly runs Tier B on equal-weight portfolios only if all Tier A pairs achieve `verdict == PASS`, otherwise recording `NOT_RUN`.
   - Search parameterization test verified: Candidate with drift $-0.0008$ and scale $0.75$ passing Tier A but failing per-asset combined curve correctly proceeds to Tier B portfolio enhancement rather than false rejection.

---

### 1. Harness Change #4 Re-specified: Executable Hyperliquid Two-Perp Dollar-Neutral Pair (§1, §2)

1. **Operational Reality vs. Backtest Abstraction**:
   - We accept Claude's operational proof: The sovereign trading desk's only live crypto execution adapter is **Hyperliquid Perpetuals** (`adapters/hyperliquid_adapter.py:2`). No Binance spot adapter exists.
   - On a USD-funded account, purchasing listed spot `ETHBTC` with dollars is economically Long ETH, Flat BTC — resulting in 100% directional ETH delta rather than relative value. True market neutrality on the desk requires two perpetual legs: Long Alt Perp and Short BTC Perp.
2. **Algebraic Identity Ratified**:
   - Claude's proof is verified:
     $$\text{PnL}_{\text{usd}} = \text{qty} \cdot (\text{ETHUSD}_x - \text{ETHUSD}_e) - \text{qty} \cdot \left(\frac{\text{ETHUSD}_e}{\text{BTCUSD}_e}\right) \cdot (\text{BTCUSD}_x - \text{BTCUSD}_e) = \text{qty} \cdot (\text{ETHBTC}_x - \text{ETHBTC}_e) \cdot \text{BTCUSD}_x$$
   - The numerical delta of $1.8 \times 10^{-12}$ USD confirms that §5's quote-currency conversion formula models the exact net dollar PnL of a dollar-neutral two-perp pair.
3. **Spot Data Ratified as Sound Proxy**:
   - Claude's empirical measurement over 32,135 hours of research data confirms that spot triangular deviation is negligible (median 1.6 bps, p95 4.7 bps), and 24h pseudo-trade PnL deviation is only 2.2 bps median (p99 9.0 bps).
   - Against an 80.0 bps hurdle, spot `ETHBTC` and `BNBBTC` 1h bars are ratified as canonical price and signal proxies.
4. **Executable Two-Perp Cost Model Ratified**:
   - **Taker Fees**: Charged on both legs, entry and exit:
     $$\text{Fee}_{\text{entry}} = 0.05\% \times \text{Notional}_{\text{alt}} + 0.05\% \times \text{Notional}_{\text{btc}} = 10.0\text{ bps}$$
     $$\text{Fee}_{\text{exit}} = 0.05\% \times \text{Notional}_{\text{alt}} + 0.05\% \times \text{Notional}_{\text{btc}} = 10.0\text{ bps}$$
     Total round-trip fee friction = **20.0 bps** ($0.20\%$).
     Under the sovereign $4 \times \text{friction}$ Gate Zero rule:
     $$\mathbf{\text{Gate Zero Hurdle} = 4 \times 20.0\text{ bps} = 80.0\text{ bps}}$$
     The 80.0 bps hurdle stands unmodified!
   - **Funding Carry**: Both perpetual legs must settle real funding cash flows:
     - Long Alt leg pays/receives $\text{rate}_{\text{alt}} \times \text{notional}_{\text{alt}}$.
     - Short BTC leg receives/pays $-\text{rate}_{\text{btc}} \times \text{notional}_{\text{btc}}$.
     - Net funding is accounted for to the cent at each 8-hour settlement instant (00/08/16 UTC) with the fail-closed bar-span timestamp guard applying to both legs.
5. **Decision-Time Position Sizing**:
   - At signal bar $t$, risk sizing uses `quote_bars[t].close` (the lookahead-free market price established when the bar closes and the trade decision is committed), replacing `quote_bars[t].open`.
6. **Venue Declaration**:
   - Specs are formally declared under `broker: hyperliquid`, `asset_class: crypto_perpetual` (composed as a two-perp relative value pair).

---

### 2. Family 2 Comparison Pairing Formally Codified (§3)

1. **Dual-Leg Exposure Risk Acknowledged**:
   - A relative-value pair ($\text{Alt} / \text{BTC}$) carries two distinct risk exposures: positive sensitivity to Alt outperformance and negative sensitivity to BTC outperformance.
   - Pairing `ETHBTC` solely against `ETHUSDT` (or `BNBBTC` solely against `BTCUSDT`) creates an architectural blind spot: an Alt/BTC pair could harbor significant correlated drawdown risk during BTC dominance surges that a single-asset pairing would hide.
2. **Four-Pair Tier A Requirement Codified**:
   - We formally codify that Family 2 candidates must pass Tier A independence against **both t0030 assets individually**:
     - Pair 1: (`ETHBTC`, `BTCUSDT`) $\implies$ `verdict == PASS`
     - Pair 2: (`ETHBTC`, `ETHUSDT`) $\implies$ `verdict == PASS`
     - Pair 3: (`BNBBTC`, `BTCUSDT`) $\implies$ `verdict == PASS`
     - Pair 4: (`BNBBTC`, `ETHUSDT`) $\implies$ `verdict == PASS`
   - Every pair must independently satisfy:
     - Unconditional correlation: $\rho < 0.25$
     - Drawdown-conditional correlation: $\rho_{\text{cond}} \le 0.10$ on deep days (depth $\ge Q_{75}$, $\ge 30$ deep days floor)
     - Non-negative deep-day contribution: $\mathbb{E}[r_{\text{cand}} \mid DD_{\text{t0030}} \ge Q_{75}] \ge 0.0$
     - Zero-volatility check: $\sigma_{\text{cand}} \ge 10^{-6}$
   - *Quantitative Rationale*: If a candidate strategy claims market neutrality, it must not systematically bleed during either BTC trend drawdowns OR ETH trend drawdowns. Passing all 4 pairs proves genuine cross-asset orthogonality.
3. **Tier B Portfolio Combined Curve**:
   - Once all 4 pairs pass Tier A, the equal-weight candidate sleeve ($0.5 \cdot r_{\text{ETHBTC}} + 0.5 \cdot r_{\text{BNBBTC}}$) is blended with the equal-weight t0030 portfolio ($0.5 \cdot r_{\text{BTC}} + 0.5 \cdot r_{\text{ETH}}$) via `combined_from_returns(w_max=3.0)`.

---

### 3. BNB Perpetual Data Ingestion Authorized (§2, §4)

1. **Operator Verification Confirmed**:
   - The operator confirmed that the sovereign Hyperliquid account trades `BNB-PERP`.
   - BNBBTC is ratified as the permanent second asset of Family 2.
2. **Dataset Acquisition Scope**:
   - Claude Code is authorized to fetch:
     1. `BNBUSDT` 1h perp archive bars (2020-01 to 2026-08) via `scripts/fetch_binance_archive.py`.
     2. `BNBUSDT` continuous funding history (2020-01 to 2026-08) via `scripts/fetch_binance_funding.py`.
   - Storage locations follow established git-ignored conventions (`quant_trading_lab/data/continuous/`), ensuring 0 dirty impact on lab master.

---

### 4. Sequence to Campaign 5 Registration (§4)

With Harness Change #4 re-specified and comparison pairings locked, the path to launching the loop is:
1. **Step 1**: Build Harness Change #4 in `backtesters/engine.py` (two-perp dollar-neutral PnL formula, two-sided taker fees at 20 bps, dual funding streams, sizing on `quote_bars[t].close`).
2. **Step 2**: Ingest `BNBUSDT` 1h bars and funding history; verify 0 gaps.
3. **Step 3**: Unit test suite expansion in `tests/test_c5_harness.py` covering two-perp fees, funding, and 4-pair `evaluate_hierarchy`.
4. **Step 4**: Formally register Campaign 5 in `qtl_autoresearch/research/autoresearch/campaign.meta.json` and start the search loop!

---

### 5. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | Active | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Tier A/B Comparison Split | **COMPLETE** | ec8ee38 | Built, verified green (48 passed in `test_c5_harness.py`, 283 passed in full suite). |
| 7 | Harness Change #4 (Two-Perp Pair) | **RE-SPECIFIED & AUTHORIZED** | Claude Code | Hyperliquid two-perp dollar-neutral pair; 20 bps fees; dual funding; close sizing. |
| 8 | Family 2 Tier A Pairing | **LOCKED** | Both t0030 Assets | All 4 pairs (`ETHBTC`/`BNBBTC` vs `BTC`/`ETH`) must pass Tier A individually. |
| 9 | BNB Ingestion | **AUTHORIZED** | Claude Code | Download `BNBUSDT` 1h bars and continuous funding rate history. |
| 10 | Campaign 5 Registration | **QUEUED** | Steps 7–9 | Ready to register upon completion of two-perp harness build and BNB ingestion. |

All architectural rulings codified. Claude Code is authorized to build **Harness Change #4**, download the **BNB datasets**, and proceed to **Campaign 5 Registration**.
