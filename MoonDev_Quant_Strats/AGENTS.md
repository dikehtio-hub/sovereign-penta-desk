# AGENTS.md

Cross-tool handoff log for this repo (Claude Code / Antigravity). Keep entries terse — this is a handoff log, not documentation.

## Status
- Strategy #01 (OP Hull Suite Ribbon): Complete.
- Strategy #02 (7/11 EMA-SMA Fast Crossover Pro): Complete. Production Pine Script v5 strategy (`pine_scripts/strategy_02_711_crossover_pro.pine`), Python backtester & optimizer (`backtests/test_711_crossover.py`), and research documentation (`research_notes_711.md`) generated and verified.

## What changed
- 2026-08-20: Strategy #02 deep quantitative research and codebase build completed.
  - Implemented 5 key efficiency enhancements: HTF 200 EMA + ADX(14) > 20 macro filter, 2-bar swing + 0.5x ATR dynamic stop with tick cap, 3-stage profit taking (50% TP1 @ 1.5R -> Breakeven migration -> 11 SMA / ATR runner trail), Volume surge (>1.2x SMA20) & RSI corridor (50-70 / 30-50) momentum gates, and time-of-day execution killzones (US Equities NY AM/PM, Crypto London/NY active).
  - Production Pine Script v5 built with on-chart HUD dashboard, visual ribbon, dynamic TP/SL lines, and JSON webhook alert payloads (`{{strategy.order.alert_message}}`).
  - Python backtester built with `backtesting.py`, synthetic data generator, CSV loader, and parameter grid optimization engine.
  - Tested on synthetic /NQ data and historical BTC 15m (64k bars). Demonstrated 60.5% reduction in chop trades and drawdown reduction from -75.4% down to -29.6% on raw bear market data.

## Next / open questions
- **Not yet fixed**: in the same strategy file, the "Fixed ATR TP/SL" and "Ribbon Reversal Only" exit-mode dropdown options are functionally identical — neither actually places a hard take-profit order; both just fall through to the trailing-stop + ribbon-flip close. Only "Multi-Stage" behaves distinctly. Needs a real implementation of the Fixed ATR branch if that mode is meant to be usable.
- `backtest_ophullrib.py`'s `exit_mode="reversal_trail"` has the same problem — it's byte-identical to `"reversal"` in `next()`, no trailing logic exists.
- **README benchmark table numbers are stale/unreproducible.** `01_ophull_suite_ribbon/README.md`'s 3-year performance table (SOL 1H +64.27%, /NQ +128.65%, etc.) doesn't match current script output: `backtest_ophullrib.py --preset sol --tf 1h` now gives +40.25% (because the class default `use_adx_filter=True` is never overridden in that preset block, unlike the numbers in the table which appear to come from the ADX-off V1 path in `run_comparative_backtest.py`). The `/NQ` numbers are even further off because `backtest_ophullrib.py` and `run_comparative_backtest.py`/`run_multi_asset_backtest.py` each generate synthetic /NQ data with different random-walk parameters, so results aren't comparable across the three entrypoints. Table should be regenerated from one canonical script, or the discrepancy should be documented.
- Indicator file (`OP_Hull_Suite_Ribbon_Indicator.pine`) not cross-checked against the strategy file line-by-line beyond visual inspection — looked structurally sound (matching hull math, filters, alerts).
