---
type: Desk
title: 'Desk 3: Cross-Market Desk'
description: 'Cross-venue desk: Polymarket vs sportsbook dutching arb, Titan correlator
  and lead-lag research, latency sniper (paper), AMM rewards simulator (paper), risk-of-ruin
  simulator, C2 bot.'
tags:
- desk
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T01:10:25Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
- id: round-95-blueprint
  resource: LLM_WIKI_BLUEPRINT.md
  title: Round 95 five-desk audit
  author: claude-code/fable-5.1
dev:
  desk: 3
  asserts:
  - file: cross_market/latency_sniper.py
    pattern: def record_loop
    claim: Ruling R2's recording loop exists
  parameters:
  - name: lead_lag_min_abs_corr
    value: 0.2
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    pattern: '"min_abs_corr":\s*([0-9.]+)'
  - name: lead_lag_latency_minutes_crypto
    value: 5.0
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    pattern: '"latency_minutes_crypto":\s*([0-9.]+)'
  - name: kelly_fraction
    value: 0.25
    file: cross_market/latency_sniper.py
    pattern: ^KELLY_FRACTION = ([0-9.]+)
  - name: confidence_floor
    value: 0.99
    file: cross_market/latency_sniper.py
    pattern: ^MIN_CONFIDENCE = ([0-9.]+)
  - name: fee_rate
    value: 0.0
    file: cross_market/latency_sniper.py
    pattern: '^\s+fee_rate: float = ([0-9.]+)$'
---
# Desk 3: Cross-Market Desk

Cross-venue desk: Polymarket vs sportsbook dutching arb, Titan correlator and lead-lag research, latency sniper (paper), AMM rewards simulator (paper), risk-of-ruin simulator, C2 bot.

**Domain**: Polymarket, Hyperliquid and sportsbooks together

## Code roots

- `cross_market`
- `Polymarket/Polymarket_Monarch`

## Raw streams (federated, read-only)

- `cross_market/data/clob_books/ (CLOB stamps)`
- `cross_market/experiments/*.json (pre-registrations)`
- `cross_market/data/paper_receipts/`
- `cross_market/titan_identities_cache.json`
- `Polymarket/Polymarket_Monarch/data/polymarket_whales.db`

## Vault surface (exporter-owned, never written by the knowledge layer)

- `Cross_Market_Arb.md`
- `Cross_Market_Titans.md`
- `Risk_Sentinel.md`
- `Polymarket_Monarch.md`
- `Wallets/`

## Items

- [[Item_06_Cross_Market_Arbitrage_Engine_Polymarket_Vs|Item 6: Cross-Market Arbitrage Engine (Polymarket Vs Sportsbooks)]] · deployed
- [[Item_10_Centralized_Telegram_Discord_Command_Control_C2|Item 10: Centralized Telegram / Discord Command & Control (C2) Bot]] · roadmap
- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]] · roadmap
- [[Item_13_Polymarket_Automated_Market_Maker_Rewards_Bot|Item 13: Polymarket Automated Market Maker & Rewards Bot]] · roadmap
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator (Macro -> Crypto -> Predictions)]] · deployed
- [[Item_19_Multi_Desk_Monte_Carlo_Risk_Of_Ruin|Item 19: Multi-Desk Monte Carlo Risk-Of-Ruin Simulator]] · deployed

## Rulings

- [[Ruling_R01|R1 - never issued (deprecated placeholder)]]
- [[Ruling_R02|R2 - record the CLOB around a scheduled print]]
- [[Ruling_R03|R3 - never issued (deprecated placeholder)]]
- [[Ruling_R04|R4 - neg_risk books skip the NO side]]
- [[Ruling_R05|R5 - record the rewards pool rate (pending)]]
- [[Ruling_R06|R6 - competitor Q is measured from recorded books]]
- [[Ruling_R95|R95 - Ratification of the knowledge layer (R95-A to R95-G)]]

## Registers (machine-maintained)

- [[registers_register|Registers catalogue]]

## Compiled pages (Phase 2 adapters)

- [[btc_macro_regime|BTC macro regime]] - lead-lag classification history

## Other desks

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]
- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## Related

- [[Monarch_Hub|Monarch Hub]] (exporter-owned dashboard index)
