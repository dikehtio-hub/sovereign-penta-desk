---
type: Item
title: 'Item 18: Cross-Market Titan Correlator (Macro -> Crypto -> Predictions)'
description: 'Correlates top HyperLiquid whale wallets against Polymarket sharp

  traders.'
tags:
- item
- desk-3
- tier-4
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T20:05:15Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 3
  item: 18
  tier: 4
  registry_checked: true
---
# Item 18: Cross-Market Titan Correlator (Macro -> Crypto -> Predictions)

> Tier 4: Analytics, Optimization & Master Cockpit · deployed · [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]

## What it does

Correlates top HyperLiquid whale wallets against Polymarket sharp
traders. Analyzes cross-venue positioning, conviction scores, and lead-lag
relationships between prediction markets and crypto perpetuals.

## Where it lives

- `cross_market/titan_correlator.py   (macro block MEASURED since Round 51 — 2026-09-04 20:15 EDT:`
- `Polymarket probability from whale_trades / drop files, HyperLiquid flow from`
- `the snapshot tables; a missing market prints [NO LIVE MARKET FOUND])`
- `cross_market/lead_lag.py           (Item 18 research half: lag between`
- `probability shifts and perp returns; offline, read-only, refuses thin data)`

## How to activate

```
# Run Titan correlation scan and update Obsidian note:
python -m cross_market.titan_correlator --scan
# Print CLI conviction report to terminal without modifying vault:
python -m cross_market.titan_correlator --report
# Run against custom databases:
python -m cross_market.titan_correlator --scan --hl-db <PATH> --pm-db <PATH>
# Feed BOTH desks from one Polymarket watcher (Round 52 — 2026-09-04 20:35 EDT): sports for the arb desk,
# crypto + fed-rates for the Titan macro block; stamped copies feed Item 18:
python -m cross_market.ingestors.polymarket_fetcher --live --watch --interval 300 --tags sports,crypto,fed-rates --keywords "fed,rate cut,bitcoin,btc"
# Round 55 (2026-09-04 22:10 EDT): --watch holds <folder>\polymarket_watcher.pid (override --pid-file). A second
# watcher on the same folder prints already_running and exits 0. Stale locks are swept.
# Round 56 (2026-09-04 22:33 EDT): operator status (exit 0 running / 3 stopped) and the Item 18 data sentinel:
python -m cross_market.ingestors.polymarket_fetcher --status [--json]
python -m cross_market.lead_lag --check-data [--family macro] [--json]   # exit 0 ready / 3 not
# Round 57 (2026-09-04 22:51 EDT): the same verdict as a card in obsidian_vault/Cross_Market_Titans.md (between
# lead-lag-sentinel markers), refreshed by the Cross-Market Arb Obsidian Sync every cycle.
python -m cross_market.lead_lag [--coin BTC]      # live dirs are GATED: exit 3 until READY, --force to override
# Round 73: the Cross-Market Arb exporter loop runs this by itself once the sentinel is READY
# (--lead-lag-coin BTC, --lead-lag-cooldown-hours 24, --no-lead-lag) and writes the result into
# Cross_Market_Titans.md ("## ⚡ Lead-Lag Predictive Horizon (Item 18)", lead-lag-horizon markers).
# Round 73 review: the automated run reads --family macro; detached launchers (pythonw + log files):
start_polymarket_watcher.bat            # Sports_Desk/data/polymarket_watcher.log
start_cross_market_exporter.bat         # cross_market/data/cross_market_exporter.log (runs the maiden regression)
# Round 74: one exporter loop (pid lock, --status exit 0/3 + Item 18 state); Tier 2 pre-registered.
python -m cross_market.interfaces.obsidian_exporter --status [--json]
python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates          # after Tier 1
python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --latency-minutes 5
# cross_market/experiments/lead_lag_tier2.meta.json - the registration; do not amend.
# Round 75: the verification protocol (Directives 75-1/75-2) as one command - run at ~01:40Z 2026-09-06.
python -m cross_market.maiden_protocol [--no-tier2] [--json]     # exit 0 passed / 3 not yet / 1 failed
# Round 76: drop questions carry `tags` once the watcher is restarted AFTER the maiden verdict:
#   fetcher --status (pid) -> taskkill /F /PID <pid> -> start_polymarket_watcher.bat   (inside 60 min)
# Round 79: the above as ONE command (--stop guards the kill; --status ends with the tags line):
restart_polymarket_watcher.bat
# Round 77: Tier 2b (cross_market/experiments/lead_lag_tier2b.meta.json, do not amend) - after the restart + 24 h:
python -m cross_market.lead_lag --check-data --subfamily-from tags
python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --subfamily-from tags --latency-minutes 5
# Round 58 (2026-09-04 23:21 EDT — Item 19): multi-desk Monte Carlo risk-of-ruin; writes obsidian_vault/Risk_Sentinel.md
python -m cross_market.risk_simulator --iterations 100000 [--json] [--no-vault] [--assume-defaults]
# Round 59 (2026-09-04 23:41 EDT): --stress-correlation 0..1 [--stress-day-prob 0.02] [--stress-vol-multiplier 3] -> baseline vs
# stressed VaR99 / ruin / buffer in the report and the card. The Arb exporter loop refreshes the card
# every --risk-every cycles (60 = 15 min) or when the paper book moves: --risk-iterations 20000,
# --risk-grid-iterations 5000, --risk-stress 0.0, --risk-every 0 = off.
# Round 60 (2026-09-05 00:00 EDT): stress_day_prob / vol multiplier are MEASURED from hyperliquid_data.db once >= 14 days of
# marks exist (shock = daily vol > 3x median); sports cadence / win rate / odds from placed_bets once
# >= 20 settled wagers exist (pushes excluded). Until then the report labels them assumed.
# The sync bat's Arb exporter runs with --risk-stress 0.5 so the card keeps its stress table.
# Round 61 (2026-09-05 00:49 EDT): shock days are judged per coin against ITS median (>= 14 days each, averaged); sports
# cadence is settled / calendar days spanned; arb rate / return / capital come from >= 10
# fills_polymarket_dutched_arb*.csv receipts (Tax_Reserve_Agent/data/imports + processed). Audit:
python -m cross_market.risk_simulator --calibration-report [--json]
# Round 62 (2026-09-05 02:20 EDT): record an executed cross-market dutch (Polymarket receipt + placed_bets wager, one arb_group):
python -m cross_market.execution_log --pm-market SYM --pm-price P --pm-shares N --book B --selection S --odds O --stake $ --event-id E --sport NFL [--json]
# --calibration-report shows the last 7 daily rows per coin; --last-days N / --all.
# Round 63 (2026-09-05 02:36 EDT): Monarch Shark menu [x] cross-market -> Betslip.stake_cross_market(result, pair) -> record_dutch;
# --paper writes both legs to cross_market/data/paper_receipts and touches no ledger; explicit
# --sports-db / --imports-dir that do not exist are refused (exit 2). Sports history excludes arbitrage legs.
# Round 64 (2026-09-05 02:54 EDT): closed-loop paper drill (paper receipts only, cleaned afterwards unless --keep):
python -m cross_market.paper_drill [--count 10] [--keep] [--json]
# Stale-quote / latency-arb groundwork (no execution): Sports_Desk/engine/stale_quotes.py;
# NOTE: the master list's ITEM 11 is the prop-firm gateway - this engine is filed under the Sports Desk.
# Round 65 (2026-09-05 03:05 EDT): the panel (display only) -
python -m Sports_Desk.interfaces.monarch_shark --stale [--lookback-minutes 180]   # menu: [t] stale quotes
# Round 66 (2026-09-05 03:22 EDT): header shows the newest quote age; "[WARN] feed stale / ..." when > 15 min or older than the
# lookback; --json prints the scan dict; Sports_Desk.md carries the section on every sync.
# Round 67 (2026-09-05 03:37 EDT): Sports_Desk.md header "Feed Liveness: X ago [ACTIVE|STALE]"; section capped at 8 + overflow line;
# FEED_STALE_SECONDS (pipeline) and MAX_QUOTE_AGE_SECONDS (quote) are separate knobs (both 900 s today).
# Round 68 (2026-09-05 03:48 EDT): elapsed ages in Sports_Desk.md are <VOLATILE_TIME> for the change hash; verdicts/counts still rewrite.
# Round 69 (2026-09-05 04:04 EDT): HL notes too - "Ns ago", `NN.Nh` durations and the Realised APR cell (<VOLATILE_APR>) are
# volatile in analytics/obsidian_links.normalize_for_hash; PIDs, equity, accruals, entry APRs stay hashed.
# Round 70 (2026-09-05 04:20 EDT): `main.py obsidian --watch --throttle-seconds N` rewrites HyperLiquid_Monarch.md at most once per N s
# (mtime-judged, full precision, other notes unaffected; 0 = unthrottled; optional, not in the sync bat).
# Round 71 (2026-09-05 04:32 EDT): the sync bat and start_obsidian_sync.bat pass --throttle-seconds 60 (Ruling 70-1); CLI default stays 0.
# Item 18 lead-lag (offline research; needs timestamped Polymarket drops):
python -m cross_market.lead_lag --coin BTC
python -m cross_market.lead_lag --coin ETH --drops <DIR> --db <PATH> --max-lag 60 --min-shift 0.02
python -m cross_market.lead_lag --events my_events.csv     # ts,key,probability
```

## Test

```
python -m unittest cross_market.tests.test_titan_correlator cross_market.tests.test_lead_lag cross_market.tests.test_risk_simulator cross_market.tests.test_execution_log Sports_Desk.tests.test_stale_quotes cross_market.tests.test_c2_bot cross_market.tests.test_latency_sniper cross_market.tests.test_amm_rewards
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline; macro measured Round 51: 2026-09-04 20:15 EDT, readiness gate Rounds 56-57: 2026-09-04 22:33-22:51 EDT)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
