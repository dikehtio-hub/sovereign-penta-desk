# Desk
* [Desk 1: HyperLiquid Monarch](wiki/desks/Desk_01_HyperLiquid_Monarch.md) - Perp DEX desk: delta-neutral funding harvester, whale cascade sweeper, L2 order-book sampler, liquidation engine and the collector that feeds a 4.9 GB snapshot warehouse.
* [Desk 2: Sports Desk](wiki/desks/Desk_02_Sports_Desk.md) - Sportsbook desk: multi-book odds ingestion, Shin/Power devigging to fair value, after-tax edge hurdle, execution CLV, stale-quote guard and the Polymarket drop watcher that feeds Item 18.
* [Desk 3: Cross-Market Desk](wiki/desks/Desk_03_Cross_Market_Desk.md) - Cross-venue desk: Polymarket vs sportsbook dutching arb, Titan correlator and lead-lag research, latency sniper (paper), AMM rewards simulator (paper), risk-of-ruin simulator, C2 bot.
* [Desk 4: Quant Trading Lab](wiki/desks/Desk_04_Quant_Trading_Lab.md) - CME futures desk: nine strategy stacks, ICT session clocks, Risk Sentinel invariants, walk-forward and grid-search research over stitched continuous contracts; its own git repository.
* [Desk 5: Tax Reserve Agent](wiki/desks/Desk_05_Tax_Reserve_Agent.md) - The accountant every desk asks before sizing: lot engine, IRC 1256 60/40, IRC 165(d) gambling, NJ apportionment, tax escrow and the safe-bankroll gating hook.

# Item
* [Item 1: Sports Odds Ingestion & Fair-Value (No-Vig) Engine](wiki/items/Item_01_Sports_Odds_Ingestion_Fair_Value_No.md) - Pulls multi-bookmaker odds (Pinnacle, Circa, retail books).
* [Item 2: Sports Gambling Tax & Loss Deduction Module](wiki/items/Item_02_Sports_Gambling_Tax_Loss_Deduction_Module.md) - Computes statutory tax liability under IRC §61 and §165(d). Implements New Jersey state tax netting (Union NJ 07083: 24% Fed + 6.37% NJ + 2% buffer = 32.37% composite).
* [Item 3: Multi-Market Bankroll Hurdle & Gating Hook](wiki/items/Item_03_Multi_Market_Bankroll_Hurdle_Gating_Hook.md) - Centralized pre-flight gate.
* [Item 4: Section 1256 Futures Tax Ingestion (60/40 Rule)](wiki/items/Item_04_Section_1256_Futures_Tax_60_40.md) - Ingests CME futures trade confirmations (CME MES, MNQ, ES, NQ) from Tradovate/NinjaTrader.
* [Item 5: Fractional Kelly Staking Engine](wiki/items/Item_05_Fractional_Kelly_Staking_Engine.md) - Dynamic bet sizing engine implementing Quarter-Kelly staking scaled against the net after-tax hurdle rate.
* [Item 6: Cross-Market Arbitrage Engine (Polymarket Vs Sportsbooks)](wiki/items/Item_06_Cross_Market_Arbitrage_Engine_Polymarket_Vs.md) - Matches sports event outcomes on Polymarket's CLOB against sharp and retail sportsbook odds.
* [Item 7: Automated Headless Sports Execution Agent](wiki/items/Item_07_Automated_Headless_Sports_Execution_Agent.md) - Headless browser automation (Playwright) navigating to bookmaker betslips to execute +EV wagers before lines move.
* [Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester (Basis Bot)](wiki/items/Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester.md) - Fully automated cash-and-carry harvester.
* [Item 9: Live Process Supervisor & Health Watchdog Daemon](wiki/items/Item_09_Live_Process_Supervisor_Health_Watchdog_Daemon.md) - Robust process daemon managing the 24/7 background collector. Holds Windows OS keep-awake flags (ES_CONTINUOUS | ES_SYSTEM_REQUIRED), tracks coverage every 15 minutes, auto-restarts failed children with backoff, and isolates crashes.
* [Item 10: Centralized Telegram / Discord Command & Control (C2) Bot](wiki/items/Item_10_Centralized_Telegram_Discord_Command_Control_C2.md) - Mobile interactive C2 for remote /bankroll, /positions, and /killall.
* [Item 11: Automated Prop Firm / Cme Futures Execution Gateway](wiki/items/Item_11_Automated_Prop_Firm_CME_Futures_Execution.md) - Live execution bridge connecting Quant Lab ICT/Killzone to Tradovate.
* [Item 12: Polymarket Breaking News & Oracle Latency Sniper](wiki/items/Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper.md) - Sub-second news scraper hitting stale limit orders on Polymarket CLOB.
* [Item 13: Polymarket Automated Market Maker & Rewards Bot](wiki/items/Item_13_Polymarket_Automated_Market_Maker_Rewards_Bot.md) - Two-sided liquidity quoting capturing spread + farming USDC rewards.
* [Item 14: Hyperliquid Whale Cascade Sweeper](wiki/items/Item_14_Hyperliquid_Whale_Cascade_Sweeper.md) - Gated, non-trading passive accumulation module.
* [Item 15: Closing Line Value (Clv) Tracker & Soft-Book Health Monitor](wiki/items/Item_15_Closing_Line_Value_CLV_Tracker_Soft.md) - Measures achieved execution odds against Pinnacle closing lines to verify true mathematical edge.
* [Item 16: Fast Time-Series Warehouse & Incremental Persistence](wiki/items/Item_16_Fast_Time_Series_Warehouse_Incremental_Persistence.md) - Measures and aggregates tick data into permanent summary tables (`basis_realised_windows` and `cascade_excursions`) before deleting raw rows. Enables reaching 720h+ analytical retention standards within a 192h raw DB window.
* [Item 17: Automated Tax-Loss Harvesting Auto-Executor](wiki/items/Item_17_Automated_Tax_Loss_Harvesting_Auto_Executor.md) - Scans tax lot ledgers across crypto and prediction markets to identify underwater positions, calculate exact tax alpha, and recommend statutory loss harvesting while avoiding wash-sale pitfalls.
* [Item 18: Cross-Market Titan Correlator (Macro -> Crypto -> Predictions)](wiki/items/Item_18_Cross_Market_Titan_Correlator_Macro_Crypto.md) - Correlates top HyperLiquid whale wallets against Polymarket sharp traders.
* [Item 19: Multi-Desk Monte Carlo Risk-Of-Ruin Simulator](wiki/items/Item_19_Multi_Desk_Monte_Carlo_Risk_Of_Ruin.md) - 100,000-path joint simulation of the trading bankroll across the basis book (funding level decaying from the measured mean toward a long-run APR, hourly AR(1) noise, Student-t perp moves, liquidation past 1/leverage - maintenance), quarter-Kelly sports wagers on the desk's edge distribution, Poisson
* [Item 20: Sovereign Master Cockpit Ui (War Room Dashboard & Canvas)](wiki/items/Item_20_Sovereign_Master_Cockpit_UI_War_Room.md) - Real-time visual interface rendering the entire penta-desk ecosystem.

# Ruling
* [R1 - never issued (deprecated placeholder)](wiki/rulings/Ruling_R01.md) - Part of the R1-R6 numbering but never issued: no ruling text exists in AGENTS.md, COMMANDS.txt, any module docstring or any commit message. Confirmed by Antigravity in Round 97; kept so the numbering has a home.
* [R2 - record the CLOB around a scheduled print](wiki/rulings/Ruling_R02.md) - One read-only GET per token per interval from T-2 to T+5 around a scheduled release, so the seconds a resting book survives after the print can be measured before anything is built on it.
* [R3 - never issued (deprecated placeholder)](wiki/rulings/Ruling_R03.md) - Part of the R1-R6 numbering but never issued: no ruling text exists anywhere in the repository. Confirmed by Antigravity in Round 97; kept so the numbering has a home.
* [R4 - neg_risk books skip the NO side](wiki/rulings/Ruling_R04.md) - On a negative-risk Polymarket book only the winning outcome's YES asks are lifted; a NO outcome on a neg_risk book is deferred to Phase 2 and never traded by the sniper.
* [R5 - record the rewards pool rate (pending)](wiki/rulings/Ruling_R05.md) - The AMM rewards estimator treats the daily pool rate as an ASSUMED input until a ruling records it from live markets. That ruling has not been issued; the module names it as the one input left.
* [R6 - competitor Q is measured from recorded books](wiki/rulings/Ruling_R06.md) - The programme score of every resting level inside the rewards window is computed from a recorded CLOB stamp; competitor liquidity is a measurement, not an input. The pool rate stays the one input (R5).
* [R95 - Ratification of the knowledge layer (R95-A to R95-G)](wiki/rulings/Ruling_R95.md) - Antigravity's seven rulings on the Round 95 blueprint: placement, constitution, OKF depth, verification actor, git tracking (deferred), journal debrief scope and module numbering.

# Experiment
* [Experiment: latency_sniper_fomc_2026-09-16](wiki/experiments/fomc_2026-09-16_rules.md) - PRE-REGISTERED (Ruling R2c).
* [Experiment: lead_lag_tier2_subfamilies](wiki/experiments/lead_lag_tier2_meta.md) - PRE-REGISTERED - runs only AFTER the Tier 1 maiden run has written its verdict to Cross_Market_Titans.md
* [Experiment: lead_lag_tier2b_dual_tag_membership](wiki/experiments/lead_lag_tier2b_meta.md) - PRE-REGISTERED - runs only after (1) the Tier 1 maiden verdict is in Cross_Market_Titans.md, (2) the watcher has been restarted with the Round 76 code, and (3) the TAGGED macro series clears the readiness bar on its own

# Concept
* [Experiments register](wiki/concepts/experiments_register.md) - Index of the 3 Experiment page(s): pre-registrations and measured verdicts.
