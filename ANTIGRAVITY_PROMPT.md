# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Campaign 4 Fourth Keep Ratified (t0025, S=1.9800), t0029 Discard Audited, Sentinel Diagnostic Decoded, and Standing Directives for the Final 11 Trials

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 17:15 EDT / 21:15Z  
**Re**: `t0025` KEEP ratification ($S = 1.9800$), `t0029` DISCARD audit ($S = 1.6400$), quantitative deconstruction of the `plateau_ratio = 0.0000` fail-closed sentinel, and definitive architectural rulings on the four outstanding items (mark-to-market, MAX_HOLDING_BARS, fold_stability gate, and campaign completion).  
**State**: 29 trials logged, 11 remain. Incumbent is `t0025` ($S_{\text{best}} = 1.9800$). Next hurdle is $\max(1.9800 \times 1.02, 1.3000 \times (1 + \delta(29))) = \mathbf{2.0196}$. Lab master untouched at `33ebe81`.

---

### 0. Fourth Keep Ratified (`t0025`, S = 1.9800) & Fold Stability Preserved

1. **Fourth Keep Ratified**: `t0025` delivered $S = \mathbf{1.9800}$ (`channel_target_multiple = 1.70`), clearing the $1.8870$ hurdle by $+4.9\%$. ALL 12 GATES PASS CLEANLY (`failed: []`). S_best is firmly anchored at $1.9800$.
2. **Full Fold Stability Preserved**: Both selected points held 100% fold stability across all offsets ($0, 168, 336, 504$ hours):
   - BTC (72, 0.15): `STABLE all-positive` (4/4, 4/4, 4/4, 4/4)
   - ETH (84, 0.10): `STABLE all-positive` (4/4, 4/4, 4/4, 4/4)
3. **Module Caching Retraction Noted**: We acknowledge Claude's correction on the multi-process sweep vs in-process re-importing. Multiples above $1.70$ are non-monotone (breaking at $1.80$ on BTC w4), confirming that **$1.70$ is the genuine global empirical optimum** for channel target expansion.

---

### 1. Audit of `t0029` Discard & The `plateau_ratio = 0.0000` Fail-Closed Sentinel

Claude's diagnosis of `t0029` is an exemplary piece of quantitative research:

1. **The Fail-Closed Sentinel**:
   In [`score.py:plateau_ratio_from_sums`](file:///c:/Users/ixis1/Desktop/DEV/qtl_autoresearch/research/autoresearch/score.py#L465), when cross-fold $\sum \text{own} < \text{min\_own\_sum}$ ($1.0$), the function returns exactly `0.0000`. This is an intentional fail-closed sentinel meaning **"UNMEASURABLE"** (insufficient in-sample signal density to take a valid ratio), not a flat surface. On ETH under $R^2$, $\sum \text{own} = 0.95$, missing the floor by 5%.
2. **Train/Test Divergence Caught by Design**:
   ETH's test folds appeared positive ($[1.93, 1.42, 2.23, 1.15]$, 4/4), but its in-sample penalised scores were near zero ($[-0.02, 0.55, 0.05, 0.37]$). Apparent out-of-sample profitability without in-sample regularization is textbook phantom edge. The plateau gate caught this divergence and rejected the candidate.
3. **Ruling**: $R^2$ linear fit admission is permanently closed.

---

### 2. Definitive Architectural Ruling on Mark-to-Market at Span End

We commend Claude for generalizing Antigravity's BTC w4 censoring autopsy into [`C4_CENSORING_BIAS_FINDING.md`](file:///c:/Users/ixis1/Desktop/DEV/qtl_autoresearch/research/autoresearch/C4_CENSORING_BIAS_FINDING.md):

1. **The Censoring Asymmetry**:
   Because stops sit close ($1.75\times$ ATR) while targets sit far ($\sim 7.5R$), losers exit rapidly while winners run. Right-censoring at fold and span boundaries systematically discards open runners, causing reported closed-trade profit factors to be structurally deflated. Across the incumbent's 8 fold-asset pairs, **4 end with open winners** (BTC w2 $+1.46\%$, BTC w4 $+9.77\%$, ETH w3 $+1.14\%$, ETH w4 $+11.20\%$).
2. **Marked-to-Market Score**:
   When marked to market, incumbent `t0025` delivers **$S = \mathbf{2.1598}$** (BTC PF $2.1598$, ETH PF $2.4275$), which already exceeds the $2.0196$ successor hurdle!
3. **Three-Tier Policy**:
   - **For Campaign 4**: The scoring engine ([`backtesters/engine.py`](file:///c:/Users/ixis1/Desktop/DEV/qtl_autoresearch/backtesters/engine.py)) is pre-registered and immutable. All 40 trials must remain strictly comparable under the closed-trade rule. The engine will NOT be altered mid-campaign.
   - **For Trial 40 Holdout**: A **Dual Accounting Protocol** is formally mandated. The holdout evaluation will report both the official registered closed-trade score AND the marked-to-market score.
   - **For Campaign 5**: Mark-to-market at fold/span boundaries will be incorporated into the engine pre-registration before Trial 0001.

---

### 3. Definitive Rulings on `MAX_HOLDING_BARS` and `fold_stability` Gate

1. **`MAX_HOLDING_BARS` (Time-Based Exit)**:
   - In [`backtesters/engine.py:270-335`](file:///c:/Users/ixis1/Desktop/DEV/qtl_autoresearch/backtesters/engine.py#L270), `evaluate()` is only invoked when `open_trade is None`. While a trade is active, the only hook is `should_force_flatten(local_time, prev_time)`, which receives no bar count, no bar index, and no trade metadata.
   - Modifying open positions from [`strategies/stack9_candidate.py`](file:///c:/Users/ixis1/Desktop/DEV/qtl_autoresearch/strategies/stack9_candidate.py) is mechanically impossible without rewriting `engine.py`.
   - **Ruling**: Formally closed for Campaign 4. Prioritized for Campaign 5 engine interface design.
2. **`fold_stability` as an Online Gate**:
   - Adding a gate to `campaign.meta.json` breaks `registration_sha256` and renders the entire ledger invalid.
   - Furthermore, `t0024` and `t0025` demonstrate that the strategy achieves 100% fold stability ($4/4$ on both BTC and ETH) organically.
   - **Ruling**: Formally closed as an online gate. Preserved as an offline validation screen on keeps.

---

### 4. Strategic Directive for the Final 11 Trials (Trials 30–40): Convergence & Holdout

Claude asks:
> *"Should the campaign end?"*

With 29 trials spent and 11 remaining:
- The candidate represents an exceptionally mature, multi-dimensional optimum:
  - All four scalar constants (`donchian_period=72`, `atr_stop_multiple=1.75`, `channel_target_multiple=1.70`, `trend_period=100`) are verified interior optima.
  - The admission side is exhausted (trend filter decides 0 signals, shape test decides $2\text{--}5\%$, R² fails in-sample measurability).
  - Both assets are 100% fold-stable ($4/4$ across all 4 offsets).
  - The true economic score (marked to market) is $S = 2.1598$.

**Directives for Claude Code & Operator**:
1. **Option A (Autonomous Exhaustion to Cap)**: Claude has full autonomy to run the remaining 11 trials on any final exploratory variations (e.g. fine-grained stop intervals $[1.70, 1.80]$, minor efficiency ladder adjustments) until the harness prints `CAMPAIGN_CAP_REACHED` at Trial 40.
2. **Option B (Early Convergence Declaration)**: If Claude and the Operator conclude that all physical mechanisms are exhausted and further trials would be unproductive churn, the Operator is authorized to declare Campaign 4 search converged at `t0025` ($S = 1.9800$).
3. **The Champion Stands**: Under either option, **`t0025` stands as the formal Campaign 4 champion**. At Trial 40 / conclusion, `t0025` will be promoted to `master` for the virgin 2020–2022 holdout under the Dual Accounting Protocol.

Proceed with full autonomy into Trial 30.
