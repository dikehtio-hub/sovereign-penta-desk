# Desk 1: HyperLiquid Monarch
* [Hyperliquid snapshot warehouse](../../HyperLiquid/HL_Monarch/data/hyperliquid_data.db) - SQLite, 13 tables (asset_snapshots, orderbook_snapshots, trades, liquidation_events, liquidation_clusters, cascade_excursions, basis_realised_windows, whale_wallets, cross_market_titans, measurement_watermarks). Open read-only: file:...?mode=ro (writer: `process:HL_Monarch.collector`)
* [Collector service log](../../HyperLiquid/HL_Monarch/data/collector_service.jsonl) - JSONL coverage reports (uptime, coverage_pct, samples) from the supervised collector (writer: `process:HL_Monarch.run_collector_service`)
* [HL experiments](../../HyperLiquid/HL_Monarch/data/experiments/) - pre-registered basis experiments: the N=12 unfiltered baseline (never overwritten) and *.meta.json registrations (writer: `human:operator`)
* [Paper trading state](../../HyperLiquid/HL_Monarch/data/paper_trading_state.json) - paper account state written by the paper trader (writer: `process:HL_Monarch.paper_trader`)

# Desk 2: Sports Desk
* [Sports market database](../../Sports_Desk/data/sports_market.db) - SQLite: fair_odds_measurements, edge_opportunities, placed_bets, settled_results, brier_snapshots, processed_*_files (writer: `process:Sports_Desk.odds_watcher`)
* [Polymarket drops](../../Sports_Desk/data/polymarket_drops/) - stamped polymarket_macro_*.json and polymarket_sports_*.json (one record per question: token_id, condition_id, yes_price, yes_bid, fetched_at, tags after Round 76) plus the canonical polymarket_macro.json / polymarket_sports.json; the Item 18 series; lint C2 reads the newest (writer: `process:cross_market.ingestors.polymarket_fetcher`)
* [Odds and results drops](../../Sports_Desk/data/odds_drops/) - CSV odds drops (processed/ once imported) and results_drops/ for settlements (writer: `human:operator`)

# Desk 3: Cross-Market Desk
* [CLOB book stamps](../../cross_market/data/clob_books/) - one JSON per token per stamp: market, asset_id, hash, bids, asks, neg_risk, fee_rate, observed_at; drill folders below it (fomc_2026-09-16/) from --record-loop (writer: `process:cross_market.latency_sniper`)
* [Pre-registrations](../../cross_market/experiments/) - lead_lag_tier2.meta.json, lead_lag_tier2b.meta.json, fomc_2026-09-16.rules.json (+ sniper_rules.sample.json placeholder); never edited inside a window; ingested by knowledge.ingest.experiments (writer: `human:operator`)
* [Paper receipts](../../cross_market/data/paper_receipts/) - PAPER receipts (paper:1) from execution_log --paper, latency_sniper --paper, amm_rewards --paper; the journal's Executions source (R95-F) (writer: `process:cross_market.execution_log`)
* [Titan identity cache](../../cross_market/titan_identities_cache.json) - Hyperliquid EOA -> Polymarket proxy wallet + pseudonym, resolved by titan_correlator --resolve; the crm/titans seed (writer: `process:cross_market.titan_correlator`)
* [Exporter and protocol logs](../../cross_market/data/cross_market_exporter.log) - the Cross-Market Arb exporter loop log (lead-lag gate telemetry every ~15 s); maiden_protocol_*.log and fomc_drill_*.log sit beside it (writer: `process:cross_market.interfaces.obsidian_exporter`)
* [Polymarket whale database](../../Polymarket/Polymarket_Monarch/data/polymarket_whales.db) - SQLite: sharp_traders, tracked_wallets, whale_trades; the crm/sharps seed (writer: `process:Polymarket_Monarch.whale_collector`)

# Desk 4: Quant Trading Lab
* [Continuous futures and crypto OHLCV](../../quant_trading_lab/data/continuous/) - stitched continuous contracts (NQ ES GC CL) and BTC/ETH perps at 1m-1d; gitignored, re-fetchable (writer: `process:quant_trading_lab.scripts.fetch_historical_continuous`)
* [Runtime state](../../quant_trading_lab/state/runtime_state.json) - Risk Sentinel state (daily and cumulative P&L, halts, consecutive losses) and virtual ticket sequence (writer: `process:quant_trading_lab.engine.state_manager`)

# Desk 5: Tax Reserve Agent
* [Tax ledger](../../Tax_Reserve_Agent/data/tax_ledger.db) - SQLite: transactions, tax_lots, realized_pnl, agent_meta; the escrow and safe-bankroll source of truth (writer: `process:Tax_Reserve_Agent.main`)
* [Receipt imports](../../Tax_Reserve_Agent/data/imports/) - CSV receipts the watcher ingests (samples/ committed, live files ignored) (writer: `human:operator`)

# Not present on this machine
> not present: Statements (`obsidian_vault/raw/statements/`) - pasted statement text (FOMC, BLS) ingested into Event and Source Summary pages
> not present: Memos (`obsidian_vault/raw/memos/`) - operator voice-memo transcripts and notes
> not present: Post-mortems (`obsidian_vault/raw/postmortems/`) - dated post-mortem write-ups, one per incident
