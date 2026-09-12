# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Campaign 4 Baseline Ratified, Hurdle Mechanics Clarified, and Tactical Search Priorities Mandated

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 23:25 EDT / 03:25Z  
**Re**: Claude Code's report on baseline t0003, `S_baseline` mechanics clarification, and search allocation (`HANDOFF_PROMPT.md`)  
**State**: Baseline trial t0003 logged. BTC 4/4 clean. ETH sole blocker. Folds healthy (16–21 trades). Lab master untouched at `33ebe81`.

---

### 0. Clarification on Hurdle Baseline Mechanics Ratified

Your correction regarding the baseline anchoring mechanics is **100% factually accurate and confirmed**:

- **Discarded Trials Do Not Anchor the Baseline**:
  Because t0003 was discarded, `best_kept_score` remains `None`. 
  The **first candidate that passes all 12 gates** simultaneously establishes the initial incumbent $S_{\text{best}}$ and anchors $S_{\text{baseline}}$.
- **Decoupled Hurdle Operation**:
  The ratified formula:
  $$S_{\text{threshold}}(n) = \max\left(S_{\text{best}} \times (1 + \delta_{\text{step}}), \; S_{\text{baseline}} \times \left(1 + \Delta_{\text{min}}(n)\right)\right)$$
  operates exactly as designed:
  1. Every new keep must beat the incumbent by at least $\delta_{\text{step}} = 2\%$.
  2. The cumulative statistical deflation floor $\Delta_{\text{min}}(n) = \max(0.05, 0.05\sqrt{\ln(1+n)})$ scales strictly from the first kept baseline $S_{\text{baseline}}$, rather than compounding exponentially upon prior keeps.
  3. This completely prevents the ratchet choking that discarded valid candidates t0018 and t0030 in Campaign 3.

The behavior as currently written in `ledger.py` is formally approved without modification.

---

### 1. Analysis of Baseline State (t0003)

The baseline run provides the cleanest diagnostic signal in the history of this project:

| Asset | $\theta^*$ | Folds | Plateau | Trades / Fold | Fold Profit Factors |
|---|---|---|---|---|---|
| **BTCUSDT** | donchian 60, eff 0.15 | **4/4** | 0.8405 | 18, 21, 17, 19 | 1.70, 1.17, 1.37, 1.14 |
| **ETHUSDT** | donchian 168, eff 0.10 | 3/4 | 0.5738 | 18, 17, 17, 16 | 1.88, **0.41**, 2.62, 3.08 |

#### Key Takeaways
1. **The BTC Foundation is Rock-Solid**:
   - Bitcoin passes every single gate on unoptimized baseline parameters.
   - 4 out of 4 positive folds, well-sampled ($17-21$ trades/fold), with balanced profit factors ($1.14 - 1.70$) and a healthy plateau ratio ($0.8405$).
2. **Sample Starvation is Permanently Solved**:
   - All folds across both assets carry $16-21$ trades. The trade count minimum is $15 \gg 5$, completely eliminating the sentinel zeroing risk.
3. **The Single Tactical Blocker is ETH Fold 1 (2023 Regime)**:
   - Ethereum Folds 0, 2, and 3 are exceptionally strong ($PF = 1.88, 2.62, 3.08$).
   - The sole impediment to a campaign keep is Fold 1 ($PF = 0.41$, spanning the hostile 2023 chop).

---

### 2. Tactical Search Priorities for the 40-Trial Budget

Claude Code's proposed search vector is **FORMALLY RATIFIED AS THE CAMPAIGN 4 DIRECTIVE**:

#### Prioritize Trade Handling Over Entry Filters
Across 80 trials in Campaigns 2 and 3, entry-side admission filters (volatility expansion, RSI thresholds, volume gates) consistently failed to generalize out-of-sample or starved trade counts. In contrast, **trade handling** was the only mechanism that reliably captured macro right-tail trend extensions.

The loop should spend its 40-trial budget focused on:

1. **Level-Anchored Uncapped Target (The t0031 Mechanism)**:
   - Anchor target to breakout level: $\text{target} = \text{entry} \pm K \times \text{channel\_width}$.
   - Keep position uncapped (letting winners run via ATR trailing stop once target is cleared).
   - In Campaign 3, this specific mechanism lifted BTC's hostile 2023 fold from unprofitable to $PF = 1.34$, generating the only $8/8$ fold run. Applying this to ETH is the most statistically promising path to lifting Fold 1 from $0.41 \to > 1.0$.
2. **ATR Trailing Stop Multiplier**:
   - Explore $[1.5, 1.75, 2.0, 2.25] \times \text{ATR}$.
   - Ensure the stop gives the trade sufficient room to absorb initial breakout retests without surrendering excessive open profit on macro reversals.
3. **Preserve BTC's Pristine 4/4 Foundation**:
   - Do not introduce restrictive entry filters that risk suppressing trade frequency on BTC below the 15-trade mark or breaking its 4/4 fold consistency.

---

### 3. Formal Authorization to Launch Campaign 4

All specifications are locked. All engine defects are resolved. Gate Zero is verified. The virgin holdout is secured.

**Claude Code and Operator are fully authorized to launch the 40-trial execution of Campaign 4 (`c4_donchian_crypto_1h`) immediately.**
