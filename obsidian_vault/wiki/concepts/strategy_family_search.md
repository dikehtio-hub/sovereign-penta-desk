---
type: Concept
title: Second strategy family search
description: 'The operator''s research aim: find a second strategy family for the
  autoresearch loop. Harness criteria, families already measured, and every source
  ranked by verdict. 0 live, 3 awaiting review.'
tags:
- concept
- strategy-family-search
- autoresearch
- desk-4
- reading-intake
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:16:14Z'
status: draft
sources:
- id: campaign
  resource: qtl_autoresearch/research/autoresearch/campaign.meta.json
  title: current autoresearch campaign registration
  author: human:operator
dev:
  kind: strategy_family_search
  desk: 4
  aim: Find a second strategy family for the autoresearch loop
  sources_n: 4
  pending_n: 3
  history:
  - stem: source_clip_81f59cb347
    verdict: not-a-strategy
    family: sports_player_props
    source_kind: clip
  parameters:
  - name: autoresearch_timeframe
    value: 1h
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: timeframe
  - name: autoresearch_gate_zero_hurdle_bps
    value: 40.0
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: gate_zero.hurdle_bps
  - name: autoresearch_max_tunables
    value: 6
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: gates.max_tunables
  - name: autoresearch_max_grid_combinations
    value: 27
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: gates.max_grid_combinations
  - name: autoresearch_min_oos_trades_per_asset
    value: 40
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: gates.min_oos_trades_per_asset
  - name: autoresearch_max_oos_drawdown_pct
    value: 8.0
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: gates.max_oos_drawdown_pct_of_equity
  - name: autoresearch_holdout_promotion_min_trades
    value: 50
    file: qtl_autoresearch/research/autoresearch/campaign.meta.json
    json_path: holdout_gates.promotion_min_trades
---
# Second strategy family search

> **Aim:** find a second strategy family for the autoresearch loop - a market mechanism other than the Donchian channel breakout behind champion t0030, that the fenced harness can score.
> Maintained by `knowledge.ingest.reading`; hand edits are overwritten. Summaries and verdicts live on each source page.

## How to feed it

1. Drop links in `obsidian_vault/raw/inbox/READING.md`: one per line, the URL first, then an optional ` — note`. Or clip a whole article into `raw/inbox/` (a `source:` property marks it as clipped).
2. `python -m knowledge.fetch_reading` fetches every new link (YouTube transcripts, articles, arXiv papers, GitHub READMEs, PDFs) into `raw/fetched/` and recompiles this page.
3. Ask Claude Code to review the reading inbox: it reads each snapshot and records a summary and verdict with `knowledge.ingest.reading --review`.

## What a second family has to clear

Read from `qtl_autoresearch/research/autoresearch/campaign.meta.json` (campaign `c4_donchian_crypto_1h`).

| Criterion | Harness value |
|---|---|
| A different mechanism | not a channel or trend breakout: that is family 1 (below) |
| Diversifies family 1 | its trades should not win and lose with a trend breakout's. Time-series momentum, moving-average crossovers and volatility-scaled trend are the SAME bet renamed, and Campaign 5's portfolio drawdown gate judges the combined equity curve |
| Data inside the strategy | the traded symbol's OHLCV bars only: the import fence refuses file, network and data access, so funding, open interest, order books, on-chain or news signals are `needs-harness-change` |
| Assets | BTCUSDT, ETHUSDT |
| Bar timeframe the loop scores | `1h` |
| Gate Zero: in-sample GROSS edge per trade, bps, at least (friction is ~10 bps round trip; checked before any campaign) | `40.0` |
| Tunable constructor kwargs, at most | `6` |
| In-sample grid points, at most | `27` |
| Pooled out-of-sample trades per asset, at least | `40` |
| Out-of-sample max drawdown, % of equity, at most | `8.0` |
| Holdout trades before promotion, at least | `50` |

> Campaign 5's charter (per-asset parameters and grids, boundary mark-to-market, holding-period hooks, a portfolio drawdown gate) is not registered yet. When it is, these numbers move and lint C1 flags this page until the next ingest.

## Already measured (do not re-propose)

| Family | Where | Result |
|---|---|---|
| Donchian channel breakout, 5m bars | campaign 1 (`ledger_c1_5m_closed.tsv`) | friction about 15x the gross edge: dead by timeframe, not by idea |
| Follow, fade, reversion and campaign-2 signals, 5m bars | 5-minute gross-edge screen (`qtl_holdout/research/autoresearch/gross_edge_screen.py`) | no family cleared 10 bps gross per trade at 5m; closes the TIMEFRAME, not reversion or fading at 1h and slower |
| Donchian channel breakout, 1h bars | campaign 2 (`campaign2_1h_closed.meta.json`) | the kept trial failed its holdout |
| Donchian breakout, 1h, global consensus selection, ~24h horizon | campaign 3 (`campaign3_c3_closed.meta.json`) | out-of-sample gross edge below the ~10 bps friction |
| Donchian breakout, 1h, multi-day horizon | campaign 4 (`campaign.meta.json`, holdout commit 628d6fe) | champion t0030 passed the 2020-2022 holdout: THIS IS FAMILY 1 |

## Candidate families

_None yet._ Drop links in the inbox and ask for a review.

## Rejected or background

- **not-a-strategy** - [[source_clip_81f59cb347|mattleonard16/nflalgorithm: NFL Algorithm started end of may]]: Out of scope for the autoresearch loop (not OHLCV). Desk 2: parked - no projector in the public clone, no prop odds feed without paid data, and nothing clears…

## Awaiting review

- [[source_clip_5aada95123|moondevonyt/Trading-View-MCP-for-AI-by-Moon-Dev: Trading view MCP for AI so you…]] - Clipped article, fetch ok
- [[source_clip_7786712f7d|I Gave Claude Fable 5.1 Full Access to TradingView… Here’s What Happened]] - Clipped article, fetch ok
- [[source_clip_9bdcfe9321|How to Connect Claude to TradingView (AI Trading Setup)]] - Clipped article, fetch ok

4 source(s): 0 live, 1 rejected or background, 3 awaiting review.

## Related

- [[sources_register|Sources register]]
- [[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]
- [[experiments_register|Experiments register]]
