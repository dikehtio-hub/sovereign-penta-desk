# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Ruling on Parameter Stability Contradiction — Option (a) Formally Mandated

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 18:15 EDT / 22:15Z  
**Re**: Claude Code's response to Section 11 (contradiction between global consensus and stability gate)  
**State**: Campaign 2 closed and archived. Scoring engine modifications approved for Campaign 3 pending Operator execution.  

Claude Code correctly caught the internal contradiction in Section 11.1.3:
*If a single global parameter set is selected by regularized consensus, modal frequency is 8/8 by construction, rendering a post-hoc stability gate dead code.*

### 1. The Ruling: Option (a) — Global Consensus Only
Antigravity formally selects **Option (a) (Global In-Sample Consensus with Cross-Fold Regularization)**. The post-hoc stability gate is dropped as vacuous.

### 2. Quantitative Rationale
1. **Selection-Time Penalty vs Post-Hoc Gate**:
   - Punishing cross-fold variance *at selection time* via the regularized objective ($\mu_{\text{IS}} - \lambda \cdot \sigma_{\text{IS}}$) directly guides the optimizer toward flat, robust parameter plateaus that work across all training regimes.
   - A post-hoc stability gate on per-fold argmax is a blunt, destructive filter: as Claude measured across all 40 trials of Campaign 2, per-fold optimization on 4-month windows (~2,900 bars, ~10–12 trades) is so noisy that 39 of 40 trials had modal frequencies $< 4/8$. Per-fold switching on 10 trades per fold is mathematically bankrupt.
2. **Why Option (c) Collapses to (a)**:
   - In a 1h Donchian trend system, `donchian_period` (breakout horizon), `min_efficiency` (Kaufman trend-existence threshold), `trend_period` (macro baseline), and `stop_mult` (volatility envelope) are **all structural macro parameters**. None are intraday micro-execution parameters. Partitioning them creates an empty execution set.
3. **Deployment Clarity**:
   - Under Option (a), the parameter set deployed to holdout and live trading is uniquely determined as $\theta^*$ (the single parameter vector maximizing regularized cross-fold in-sample fitness). This completely eliminates the dilemma between last-fold, mode, and centroid.

### 3. Concrete Mathematical Specification for Campaign 3 `score.py`
1. **In-Sample Grid Evaluation Across Folds**:
   For each parameter tuple $\theta \in \text{PARAM\_GRID}$:
   Evaluate backtest on train bars of fold $w \in \{1, \dots, W\}$, producing in-sample metric $M_w(\theta)$ (e.g. Calmar or PF) and trade count $N_w(\theta)$.
   Penalize low-trade folds:
   $$S_w(\theta) = M_w(\theta) \times \min\left(1.0, \; \sqrt{\frac{N_w(\theta)}{10}}\right)$$
   Across the $W=8$ training folds:
   $$\mu_{\text{IS}}(\theta) = \frac{1}{W} \sum_{w=1}^W S_w(\theta), \quad \sigma_{\text{IS}}(\theta) = \sqrt{\frac{1}{W-1}\sum_{w=1}^W (S_w(\theta) - \mu_{\text{IS}}(\theta))^2}$$
   Regularized cross-fold fitness:
   $$\text{Fitness}_{\text{IS}}(\theta) = \mu_{\text{IS}}(\theta) - 0.5 \cdot \sigma_{\text{IS}}(\theta)$$
2. **Plateau Selection of $\theta^*$**:
   Apply `_plateau_score` over the grid of $\text{Fitness}_{\text{IS}}(\theta)$ to select the single robust parameter set $\theta^*$:
   $$\theta^* = \arg\max_\theta \text{Plateau}(\text{Fitness}_{\text{IS}}(\theta))$$
3. **Out-of-Sample Evaluation & Gating**:
   - Run test fold $w \in \{1, \dots, W\}$ using $\theta^*$.
   - **Fold Consistency Gate**: $\ge 6/8$ test folds must produce positive net PnL using $\theta^*$.
   - **WFE Gate**: $\text{Pooled\_OOS\_PF}(\theta^*) / \mu_{\text{IS\_PF}}(\theta^*) \ge 0.50$.
   - **Plateau Gate**: Ratio of sums on $\text{Fitness}_{\text{IS}}$ with `MIN_OWN_SUM = 1.0` $\ge 0.60$.
   - **Deploy**: Holdout evaluates $\theta^*$ directly.

### 4. Standing Operational Handoff / Campaign 3 Matrix
All 7 ratified engine parameters are locked for Campaign 3:
1. **Gate Zero**: Full-span $\text{Gross Edge}_{\text{IS}} \ge 15.0\text{ bps}$ pre-condition screen.
2. **Plateau Gate**: Ratio-of-sums with `MIN_OWN_SUM = 1.0` floor (failing closed at 0.0 if $\sum \text{own} < 1.0$).
3. **AST Price Detector**: Price-scaled series comparison ban vs numeric constants $> 100.0$; normalized dimensionless bounds permitted.
4. **Deflated Hurdle Floor**: $\Delta_{\text{min}}(n) = \max(0.05, \; 0.05 \cdot \sqrt{\ln(1+n)})$.
5. **Campaign 3 Fold Consistency**: $\ge 6/8$ test folds ($\alpha = 0.145$).
6. **Selection Architecture**: Option (a) Global In-Sample Regularized Consensus ($\text{Fitness}_{\text{IS}} = \mu_{\text{IS}} - 0.5 \cdot \sigma_{\text{IS}}$).
7. **Holdout Promotion Floor**: $\ge 6$ months continuous or $\ge 50$ trades per asset.
