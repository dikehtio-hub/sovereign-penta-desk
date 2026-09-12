# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Tasks 1–3 Ratified Clean, Commendation on Task 4 Halt, and Architectural Ruling on Circuit Breakers & Champion Paper Deployment

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 20:00 EDT / 2026-09-13 00:00Z  
**Re**: Full ratification of Roadmap Tasks 1, 2, and 3. Commendation on halting Task 4 before violating live safety limits. Architectural ruling on the circuit breaker incompatibility between trend-breakout and mean-reversion stacks, and the decoupled paper-trading deployment path for Champion `t0030`.  
**State**: DEV clean. Lab master untouched at `33ebe81`. Tasks 1–3 complete. Task 4 resolved by architectural ruling below.

---

### 0. Commendation on Halting Task 4

We commend Claude Code for exemplary discipline in refusing to make unilateral modifications to [`quant_trading_lab/config/portfolio_config.yaml`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/config/portfolio_config.yaml). 

Stopping execution when a prompt's literal instructions conflict with hard safety fences, comments, or live risk limits is the highest standard of quantitative engineering. You correctly caught three distinct violations:
1. **Candidate Slot Prohibition**: `STACK_9_CANDIDATE` is strictly a research sizing slot; holdout survivors must never usurp it.
2. **Research Gate vs Live Stop**: The $8.0\%$ drawdown ceiling was an acceptance gate over a 44-month walk-forward research sample, not an operating trailing stop. Conflating it with live risk would loosen the active $5.0\%$ trailing HWM stop.
3. **The Global Circuit Breaker Trap**: At a $21.7\%$ win rate ($q = 0.783$), three consecutive losses occurs $(0.783)^3 = \mathbf{48.0\%}$ of the time (roughly every other 3-trade sequence). Applying `max_consecutive_losses: 3` to `t0030` would keep the portfolio permanently halted. Conversely, raising the global breaker to 25 would destroy the safety fence for Stacks 0, 4, and 5.

---

### 1. Architectural Ruling: The Circuit Breaker & Champion Paper Deployment

#### A. The Multi-Strategy Circuit Breaker Principle
A shared portfolio-level consecutive loss counter (`_consecutive_losses` in `RiskSentinel`) is mathematically incompatible with a mixed portfolio of high-win-rate intraday mean reversion (55–65% WR) and low-win-rate trend breakout (20–25% WR):
- For Stacks 0/4/5, 3 consecutive losses is an anomaly ($0.40^3 pprox 6.4\%$) indicating toxic flow or execution degradation.
- For `t0030`, a 10-loss streak is an $8.8\%$ routine occurrence, and the measured portfolio max loss streak is **22**.

#### B. The Production Core 3 Portfolio Remains Untouched
`portfolio_config.yaml` and the live Core 3 portfolio (Stacks 0, 4, 5) shall **NOT** be altered. Live limits (`trailing_hwm_drawdown_stop_pct: 5.0`, `daily_drawdown_stop_pct: 3.5`, `max_consecutive_losses: 3`) remain strictly enforced for the production futures sleeve.

#### C. The Decoupled Paper-Trading Path for `t0030`
To deploy Champion `t0030` to forward paper trading safely:
1. **Isolated Paper Config**: Create an independent paper configuration file:
   [`quant_trading_lab/config/paper_donchian_t0030.yaml`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/config/paper_donchian_t0030.yaml)
2. **Dedicated Risk Sentinel Instance**: Run paper trading with its own isolated `RiskSentinel` instance:
   - Account equity: `$3,000` (matching `retail_3k` tier) or `$100,000` simulated.
   - `circuit_breaker.max_consecutive_losses: 25` (calibrated to the measured 22 streak).
   - `circuit_breaker.cooldown_minutes_after_trip: 60`.
   - `trailing_hwm_drawdown_stop_pct: 5.0` (unloosened).
   - Sizing: Track 2 sizing rules honoring single-trade risk caps.
3. **Future Multi-Stack Enhancement (Track 2 R&D)**:
   When `t0030` is eventually ported into the core portfolio as `STACK_10_DONCHIAN_BREAKOUT`, `RiskSentinel` will be enhanced with **per-stack circuit breakers** (`self._stack_consecutive_losses: dict[str, int]`), tripping only the offending stack while leaving the rest of the portfolio operational.

---

### 2. Ratification of Roadmap Tasks 1, 2, and 3

1. **Task 1a (Online Pre-Flight)**: Decisive pass (33/33 checks, 0 FAIL). The `Interactive` logon warning is confirmed: on Wednesday 09-16, the machine must be actively logged in for the 13:58 task to fire.
2. **Task 1b (Exporter & Stream Accumulation)**: Verified. Exporter PID 32392 running cleanly; continuous lead-lag series accumulating toward ETA 2026-09-13T15:21Z (~11:21 EDT Sun 09-13).
3. **Task 2 (Credential Scrubbing)**: Commended. Scrubbed across all 4 files across both repos (`poly_whale_monitor.py`, `poly_traders_tracker.py`, `MASTER_COMMANDS_GUIDE.txt`, and `quant_trading_lab/AGENTS.md`). `Phem_key.py` blanked; `*_key.py` and `*.key` added to `.gitignore`. Remote push remains locked until operator rotates credentials.
4. **Task 3 (FOMC Live Dress Rehearsal)**: Decisive pass (21 checks, 0 FAIL, 0 WARN). 180 of 180 stamps (100% yield, 0 drop, max gap 1.00s vs 3.0s ceiling). Real vault, real books dir, and root `event.json` confirmed untouched (sha256 identical). The weekend rehearsal requirement is **formally satisfied early**.

---

### 3. Directives for Claude Code

1. **Clean Stale Metadata**: Update the comment in [`quant_trading_lab/config/portfolio_config.yaml:459`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/config/portfolio_config.yaml#L459) from `"5m perps"` to `"1h perps"` to reflect Campaign 4's proven timeframe. Do not alter any values, weights, or flags.
2. **Draft Isolated Paper Configuration**: Create [`quant_trading_lab/config/paper_donchian_t0030.yaml`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/config/paper_donchian_t0030.yaml) implementing the decoupled paper sleeve per Section 1.C.
3. **Standing Liveness**: Maintain daemon monitoring through Sunday's lead-lag gate closure (15:21Z). Stand by for Monday 09-15 tax settlement and code freeze.
