# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Campaign 4 Formally Concluded & Ratified — Virgin Holdout PASSES (S=1.8305), Dual Accounting Audited, Verify-Branch Procedure Confirmed, and Campaign 5 Commissioned

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 18:25 EDT / 22:25Z  
**Re**: Campaign 4 final formal ratification. The virgin 36-month holdout (2020–2022) passes decisively ($S_{\text{holdout}} = \mathbf{1.8305}$, +$23,075.66 net). Ratification of the verify-branch protocol (`holdout/c4_verify`), audit of the Dual Accounting segmentation bias proof, acceptance of factual corrections, and commissioning of Campaign 5.  
**State**: Campaign 4 concluded. Loop stopped. 31 trial IDs used, 9 unspent by decision. Champion is **`t0030` ($S_{\text{research}} = 2.0900$, $S_{\text{MTM}} = 2.2775$, $S_{\text{holdout}} = 1.8305$)**. Lab master clean and untouched at `33ebe81`.

---

### 0. The Virgin Holdout Pass Formally Ratified ($S_{\text{holdout}} = 1.8305$)

The virgin 36-month holdout evaluation (`2020-01-01` to `2023-01-01`, span never touched by any trial, strictly prior to research span with zero lookahead) is **FORMALLY RATIFIED AS AN UNQUALIFIED PASS**:

1. **Performance Across the Virgin 36-Month Span**:
   - **BTCUSDT**: 157 trades, **PF 1.8305**, Net PnL **+$10,229.90**, MaxDD **1.46%** (vs 8.0% ceiling), Sharpe 2.43, Calmar 7.01.
   - **ETHUSDT**: 188 trades, **PF 1.9132**, Net PnL **+$12,845.76**, MaxDD **1.98%** (vs 8.0% ceiling), Sharpe 2.78, Calmar 6.50.
   - **Combined Holdout Net PnL**: **+$23,075.66** on $100,000 equity (+23.08% return) with portfolio MaxDD under 2.0%.
   - **Holdout Score**: $S_{\text{holdout}} = \min(1.8305, 1.9132) = \mathbf{1.8305}$ (BTC binds).
2. **Promotion Criteria Exceeded**:
   - Sample size: 157 seen vs 50 required ($\approx 3\times$ statistical power over research folds).
   - Duration: 36.01 months seen vs 6.0 months required ($6\times$ duration requirement).
   - Decay: $S$ declined only 12.4% ($2.0900 \to 1.8305$), exhibiting textbook stationary out-of-sample edge with zero structural breakdown.
   - Verdict: **`PASS`** (promotable).

---

### 1. Dual Accounting & The Segmentation Bias Insight

Claude's empirical comparison between the research folds and the holdout run delivers a foundational statistical insight:
- **Research Censoring (+8.9% on BTC)**: In the 4-fold walk-forward research backtest, the data was sliced into 4 discrete windows per asset (8 boundary interfaces). Because the stop is tight (1.65x ATR) and the target is wide (~7.5R), multi-day winners were frequently severed mid-run at window endpoints, creating a structural undercounting of profit factor.
- **Holdout Censoring (0.0% on BTC, +0.7% on ETH)**: In the 3-year continuous holdout run, there is only a single terminal boundary at 2023-01-01. BTC happened to have no open position, yielding byte-identical closed and marked-to-market PF ($1.8305$). ETH had a single modest open runner (+$183), edging MTM PF from $1.9132 \to 1.9262$.
- **Architectural Takeaway**: Right-censoring bias is an artifact of **fold segmentation granularity**, not an inherent property of the strategy logic. This distinction will be formally embedded into Campaign 5's pre-registration.

---

### 2. Verify-Branch Holdout Protocol Ratified & PROGRAM.md Correction

We fully ratify Claude's execution of the holdout on `holdout/c4_verify` (commit `628d6fe`):
1. **Repository Fencing Upheld**:
   Claude correctly diagnosed that `master` in `quant_trading_lab` tracks zero files under `research/autoresearch/` or `strategies/stack9_candidate.py`. Attempting a git cherry-pick onto `master` would produce modify/delete conflicts or contaminate the clean production master with experimental research scaffolding.
2. **Campaign 3 Precedent Honored**:
   Campaign 3 similarly preserved `master` by running holdouts on `holdout/c3_verify`. Creating `holdout/c4_verify` off `a2490dd` perfectly preserves the immutable firewall around `quant_trading_lab` `master` (`33ebe81`).
3. **PROGRAM.md Mandate**:
   [`PROGRAM.md`](file:///c:/Users/ixis1/Desktop/DEV/qtl_autoresearch/research/autoresearch/PROGRAM.md) line 83 will be formally updated to replace the inaccurate cherry-pick instruction with the canonical verify-branch procedure:
   `git checkout -b holdout/<campaign>_verify <campaign_branch> && python -m research.autoresearch.holdout --trial <trial_id>`

---

### 3. Factual Corrections Accepted with Appreciation

We commend Claude Code for unwavering vigilance on the quantitative record:
1. **CLI Flag**: Accepted. The canonical flag is `--trial` (not `--trial-id`).
2. **ETH w2 Narrative Baseline**: Accepted. In `t0030`, ETH w2 net was +$1,552, meaning the drop to +$112 in `t0031` was a -$1,440 collapse (even more dramatic than the +$1,005 baseline referenced from `t0024`).
3. **Fold List Accuracy**: Section 33 fold list typo noted and corrected. In all future campaigns, values will be cross-referenced against trial JSON files rather than running handoff transcripts.

---

### 4. Campaign 4 Final Summary: The Complete Ledger

Campaign 4 stands as the benchmark standard of disciplined quantitative exploration:
- **Incumbent / Champion**: `t0030`
- **Parameters**: `donchian_period=72`, `min_efficiency=0.15` (BTC) / `donchian_period=84`, `min_efficiency=0.10` (ETH); Global Constants: `ATR_PERIOD=14`, `ATR_STOP_SETTLED=1.65`, `CHANNEL_TARGET_MULTIPLE=1.70`, `TREND_PERIOD=100`.
- **Search Progression**: 5 Keeps ($1.3000 \to 1.7200 \to 1.8500 \to 1.9800 \to \mathbf{2.0900}$).
- **Fold Stability**: 100% stable all-positive across all offsets ($0, 168, 336, 504$ hours) on both assets.
- **Gates**: All 12 gates cleanly passed on every keep.
- **Trial Budget**: 31 consumed, 9 deliberately unspent under Pathway 1 Formal Search Convergence.
- **Holdout**: **PASS** ($S_{\text{holdout}} = 1.8305$, 36 months, 345 total trades, +$23,075.66 net, <2% maxDD).
- **Durable IP Generated**:
  - 6 formal finding documents (`C4_SELECTION_FINDING.md`, `C4_HOLDING_TIME_FINDING.md`, `C4_SCALAR_AXES_CLOSED.md`, `C4_CENSORING_BIAS_FINDING.md`, etc.).
  - 10 mechanism inventory addenda.
  - Proof of the two-sided ATR responsiveness effect and shared multi-axis structural cliff ($1.55$).
  - Mathematical deconstruction of non-local grid topology rewiring.
  - The 4-Dimensional BTC/ETH Asset Asymmetry Architecture.

---

### 5. Commissioning Campaign 5: Architecture & Pre-Registration Blueprint

With Campaign 4 successfully closed and ratified, all forward engineering efforts shift to **Campaign 5**. The 4 core architectural pillars are locked:
1. **Decoupled Asset Tunables**: Independent per-asset parameter dictionaries (`theta_star[asset]`), eliminating the $S = \min()$ compromise across efficiency thresholds, horizons, stops, and ATR periods.
2. **Decoupled Per-Asset Parameter Grids**: Separate parameter grids ($G_{\text{BTC}} \neq G_{\text{ETH}}$), eliminating topological rewiring cross-contamination.
3. **Continuous Span / MTM Accounting**: Fold-boundary open-runner mark-to-market accounting pre-registered into the core scoring engine.
4. **Lifecycle Hooks in `engine.py`**: Adding `max_holding_bars` and time-decay exit callbacks directly into the engine's position monitoring loop.

Campaign 4 is formally closed. Outstanding work on both sides is complete.
