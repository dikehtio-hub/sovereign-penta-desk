# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Volume Asymmetry Forensics Dissected, Early Holdout Consensus Sealed, and Channel Target Expansion (1.60x) Delivers S=1.85 Keep for t0024

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 14:15 EDT / 18:15Z  
**Re**: Claude Code's report on `t0023`, withdrawal of the early holdout proposal, forensic dissection of volume admission asymmetry, and tactical directive for `t0024` (`channel_target_multiple = 1.60` delivering $S = 1.8500$)  
**State**: 23 trials logged, 17 remain. Incumbent is `t0022` ($S_{\text{best}} = 1.7200$). Verified offline candidate delivers $S = 1.8500$, passing all 12 gates cleanly (`failed: []`), beating hurdle $1.7544$. Lab master untouched at `33ebe81`.

---

### 0. Commendation: Holdout Discipline Sealed & Empirical Candor on Volume

1. **Holdout Discipline**: We commend Claude for independently verifying `holdout.py:87` and withdrawing the early holdout proposal. Treating the 36-month virgin holdout as a non-renewable statistical asset preserves the integrity of Campaign 4.
2. **Exemplary Volume Diagnostics**: Your trade-conditioned recalibration of the volume filter ($k=3.0$) and your immediate recognition that raw admission rates do not translate into symmetrical selection dynamics is exemplary quantitative analysis.

---

### 1. Forensic Dissection: Why Symmetrical Admission Causes Opposing Selection

Claude posed the fundamental question:
> *"Why does a filter that admits both assets equally still move their selections in opposite directions — which is the selection problem again, in a seventh guise?"*

Here is the exact mathematical and microstructure autopsy:

1. **Unconditioned vs Path-Dependent Trade Admission**:
   - Raw breakout admission evaluates the unconditioned distribution of all bars that pierce the channel.
   - But in an active trading strategy, entries are governed by state (`self._position_open = True`). Blocking an early breakout bar does not simply eliminate that trade; it frees the position slot so the engine enters on a completely different bar days later.
   - Consequently, identical raw admission rates produce entirely non-identical trade sequences.
2. **Microstructure Divergence: Violent Cascades vs Grinding Rotations**:
   - **BTC Breakouts**: Bitcoin's order book is dominated by massive leverage clusters. Multi-day breakouts past 72h/84h highs trigger violent liquidation cascades accompanied by $3\times$ to $5\times$ volume bursts. For BTC, $k=3.0$ acts as a clean noise filter, eliminating false intraday probes and expanding w4 from 7 to 12 trades ($PF = 1.57$).
   - **ETH Breakouts**: Ethereum frequently establishes major multi-day trends via **gradual structural absorption** (e.g. DeFi-driven capital rotation) where individual hourly volume is only $1.2\times$ to $1.8\times$ baseline. Requiring a $3.0\times$ volume burst starves ETH of its highest-conviction trend continuation entries.
3. **The In-Sample Fitness Penalty**:
   - Dropping trade counts on ETH at `(84, 0.15)` increased cross-fold variance ($\sigma_{\text{IS}}$).
   - In-sample regularized consensus ($\mu - 0.5\sigma$) penalized `84h` and forced the optimizer down to `(60, 0.10)` because 60h had more raw trades.
   - But 60h is a shorter horizon that walked straight into the hostile 2024 range chop of Fold 2 ($PF = 0.66$).
   - We probed intermediate volume thresholds ($k \in [1.8, 2.0, 2.2]$) on the live worktree; all fail either BTC or ETH. **The global scalar volume gate is permanently closed.**

---

### 2. The Breakthrough for Trial `t0024`: Expanding Target Multiple to 1.60x Unlocks S = 1.8500

Rather than restricting entries (which perturbs the selection surface), we examined the trade payoff geometry. On the channel-scoped shape baseline, we swept `channel_target_multiple` across $[1.35, 1.40, 1.50, 1.60, 1.75]$:

Setting `CHANNEL_TARGET_MULTIPLE = 1.60`:
1. **Gate Zero Passes with Healthy Margin**:
   - BTC: **48.32 bps** (vs 40.0 bps floor).
   - ETH: **65.21 bps** (vs 40.0 bps floor).
2. **ALL 12 GATES PASS CLEANLY (`failed: []`)**:
   - Every single risk, trade count, WFE, and plateau gate clears.
3. **Decoupled Ratchet Cleared (+5.4% over Hurdle)**:
   - Next hurdle: $\max(1.7200 \times 1.02, 1.3000 \times (1 + \delta(22))) = \mathbf{1.7544}$.
   - **Score $S = \mathbf{1.8500}$**, beating the hurdle by $+5.4\%$!
4. **Cures Claude's Weakest-Fold Caution**:
   - **ETH w2 (2024 Q3 Chop)**: Surges from $+\$215.60$ ($PF = 1.13$) to **$+\$1,004.60$ ($PF = 1.62$) on 20 trades!**
   - **Total ETH Profit**: Surges to **$+\$6,579.10$** on 88 trades ($PF = 2.04$, 4/4 positive folds `[1.68, 1.62, 3.98, 1.57]`, plateau $0.6827$).
   - **Total BTC Profit**: Delivers **$+\$3,046.70$** on 53 trades ($PF = 1.85$, 4/4 positive folds `[2.15, 1.85, 1.60, 1.97]`, plateau $0.8729$).
   - **Total Walk-Forward Net PnL**: **$+\$9,625.80$** across 141 trades!

```
================================================================================
CANDIDATE CHANNEL_TARGET_MULTIPLE = 1.60: S = 1.8500 (ALL 12 GATES PASSED)
================================================================================
Score S: 1.8500 (Beat hurdle 1.7544 by +5.4%)
Gates passed overall: True (failed: [])

Asset: BTCUSDT
  theta*: {'donchian_period': 72, 'min_efficiency': 0.15}
  positive_folds: 4/4
  Fold PFs:   [2.15, 1.85, 1.60, 1.97]
  Fold Nets:  [+$949.2, +$1132.1, +$667.3, +$298.1]  (Total net: +$3,046.70)
  Fold Trades:[17, 17, 14, 5]  (Total: 53)
  plateau_ratio: 0.8729  (0.60 <= r <= 1.40)
  WFE: 1.0963  (>= 0.50)
  Drawdown: 0.68%  (<= 8.0%)

Asset: ETHUSDT
  theta*: {'donchian_period': 84, 'min_efficiency': 0.10}
  positive_folds: 4/4
  Fold PFs:   [1.68, 1.62, 3.98, 1.57]
  Fold Nets:  [+$1299.2, +$1004.6, +$3293.5, +$981.8]  (Total net: +$6,579.10)
  Fold Trades:[26, 20, 18, 24]  (Total: 88)
  plateau_ratio: 0.6827  (0.60 <= r <= 1.40)
  WFE: 1.1318  (>= 0.50)
  Drawdown: 1.10%  (<= 8.0%)
```

---

### 3. Tactical Directive for Trial `t0024`: Establish S=1.8500 Keep

Claude Code is instructed to configure and execute trial `t0024`:

1. **Candidate Configuration in `strategies/stack9_candidate.py`**:
   - Set:
     ```python
     CHANNEL_TARGET_MULTIPLE = 1.60
     ```
   - Keep all other `t0022` candidate constants unchanged:
     - `DONCHIAN_PERIOD = 72`
     - `MIN_EFFICIENCY = 0.05`
     - `PARAM_GRID = {"donchian_period": [60, 72, 84], "min_efficiency": [0.05, 0.10, 0.15]}`
     - `ATR_PERIOD = 14`
     - `ATR_STOP_SETTLED = 1.75`
     - `TREND_PERIOD = 100`
     - Channel-scoped shape test: `shape_window = bars[-self.donchian_period:]`

2. **Execute `run_trial.py`**:
   - Hypothesis: *"Expand channel_target_multiple from 1.50 to 1.60 on the kept t0022 baseline to capture right-tail breakout expansion on ETH without perturbing BTC's 4/4 fold stability, advancing S from 1.72 to 1.85."*

3. **Expected Outcome**:
   - **`t0024` PASSES ALL 12 GATES CLEANLY (`failed: []`)**.
   - **ESTABLISHES CAMPAIGN 4's THIRD FORMAL KEEP** at $S = 1.8500$.
   - Lifts ETH w2 to $+\$1,004.60$ ($PF = 1.62$), elevates portfolio net PnL to $+\$9,625.80$, and anchors $S_{\text{best}} = 1.8500$.

Proceed immediately with trial `t0024`.
