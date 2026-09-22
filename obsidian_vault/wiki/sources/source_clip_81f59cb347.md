---
type: Source Summary
title: 'mattleonard16/nflalgorithm: NFL Algorithm started end of may'
description: 'not-a-strategy: sports_player_props - Gamma yardage / Poisson TD projections
  vs devigged retail prop lines, ranked by EV, Kelly-capped'
tags:
- source-summary
- reading-intake
- clip
- desk-4
- strategy-family-search
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:16:14Z'
status: draft
sources:
- id: origin
  resource: https://github.com/mattleonard16/nflalgorithm
  title: 'mattleonard16/nflalgorithm: NFL Algorithm started end of may'
- id: snapshot
  resource: obsidian_vault/raw/fetched/source_clip_81f59cb347.txt
  title: fetched text snapshot
  author: process:knowledge.fetch_reading
dev:
  kind: reading_source
  desk: 4
  aim: Find a second strategy family for the autoresearch loop
  source_kind: clip
  url: https://github.com/mattleonard16/nflalgorithm
  canonical: https://github.com/mattleonard16/nflalgorithm
  inbox_file: mattleonard16nflalgorithm NFL Algorithm started end of may.md
  fetch_status: ok
  fetched_at: '2026-09-20T07:11:08Z'
  fetcher: clip
  chars: 12595
  sha256: c359baa9aded7f615706de4fc80225ff0f61f6c9d99e53d95da22278e53a76c7
  review_status: reviewed
  verdict: not-a-strategy
  family: sports_player_props
  mechanism: Gamma yardage / Poisson TD projections vs devigged retail prop lines,
    ranked by EV, Kelly-capped
  data_needed: Weekly player stats, rosters, snap counts (nflverse, free); prop odds
    from The Odds API (metered spend); a projector - the repo's own is private
  horizon: Weekly
  tunables: Position-specific projection models, sigma calibration, edge threshold,
    Kelly cap
  evidence: 'One graded week: 447 bets, +0.17% ROI (SE ~4.5%), CLV -11.5 bp, edge
    buckets inverted (25%+ edge: -25.7% ROI). Walk-forward backtest covers projection
    accuracy only (MAE 26.88 yd, 68.2% one-sigma coverage); no betting backtest reported.
    Author calls it break-even.'
  reason: 'Out of scope for the autoresearch loop (not OHLCV). Desk 2: parked - no
    projector in the public clone, no prop odds feed without paid data, and nothing
    clears the 18.22% after-tax hurdle; the buckets above it lost. Borrow the ingestion
    gates and the inversion diagnostic.'
  reviewed:
    by: claude-code/fable-5.1
    at: '2026-09-20T07:16:14Z'
---
# mattleonard16/nflalgorithm: NFL Algorithm started end of may

> **Clipped article** · [open the source](https://github.com/mattleonard16/nflalgorithm) · from `raw/inbox/mattleonard16nflalgorithm NFL Algorithm started end of may.md`
> Operator note: -

## Summary

Weekly NFL (and NBA) player-prop pipeline. It ingests player stats, rosters, schedules and snap counts from nflverse, trains position-specific models walk-forward on strictly earlier weeks, and projects a mean and a standard deviation per player and market. Yardage markets are priced off a gamma curve matched to that mean and sd (a normal curve ran 4 to 11 points long on real data); anytime touchdown prices off Poisson survival. Prop lines come from The Odds API, the bookmaker margin is stripped from each two-sided quote, and disagreements are ranked by expected value with Kelly-capped stakes. Every bet is graded afterwards on result and on closing line value.

**What the evidence says.** One graded week (2026 week 1): 453 bets, 238-209-6, +0.17% ROI, average CLV -11.5 bp. At -110 the standard error on 447 bets is about +/-4.5% ROI, and 453 bets on 87 players are heavily correlated, so the effective sample is far smaller. Negative CLV means the card was priced worse than the close: no evidence of edge. The edge buckets run BACKWARDS - 8-16% computed edge returned about +8.5%, 20-25% returned -12.6%, 25%+ returned -25.7% - which is selection on model error (a large disagreement with a liquid market is more often the projection being wrong), and the README says so itself. The walk-forward backtest reports projection accuracy only (5,117 predictions, MAE 26.88 yards, one-sigma coverage 68.2%); no betting backtest is reported.

**What a public clone lacks.** Four modules are gitignored and supplied by the deployment: `data_pipeline.py`, `value_betting_engine.py`, `models/position_specific/weekly.py` and a `config.py` override. `weekly.py` is the projector. The pricing maths is tracked (`utils/nfl_markets.py`, `nfl_sigma.py`, `two_sided_odds.py`, `clv.py`, `market_blend.py`) and the repository is MIT licensed, so pricing can be reused but projections cannot be obtained from it.

**Fit.** Not a strategy for the autoresearch loop, which scores continuous OHLCV bars. For Desk 2 it is background: under the desk's NJ casual treatment the -110 after-tax breakeven is a 61.93% win rate (18.22% gross edge), and the only buckets of this model that clear 18% are the ones that lost. Worth borrowing: the Odds API ingestion gates (staleness, coverage, minimum books) as the template for the desk's missing odds shim, gamma pricing if props are ever priced, and the edge-bucket inversion table as a standing diagnostic.

## Strategy family screen

| Check | Answer |
|---|---|
| Verdict | **not-a-strategy** |
| Family | sports_player_props |
| Mechanism | Gamma yardage / Poisson TD projections vs devigged retail prop lines, ranked by EV, Kelly-capped |
| Data needed | Weekly player stats, rosters, snap counts (nflverse, free); prop odds from The Odds API (metered spend); a projector - the repo's own is private |
| Horizon | Weekly |
| Tunables | Position-specific projection models, sigma calibration, edge threshold, Kelly cap |
| Evidence | One graded week: 447 bets, +0.17% ROI (SE ~4.5%), CLV -11.5 bp, edge buckets inverted (25%+ edge: -25.7% ROI). Walk-forward backtest covers projection accuracy only (MAE 26.88 yd, 68.2% one-sigma coverage); no betting backtest reported. Author calls it break-even. |
| Reason | Out of scope for the autoresearch loop (not OHLCV). Desk 2: parked - no projector in the public clone, no prop odds feed without paid data, and nothing clears the 18.22% after-tax hurdle; the buckets above it lost. Borrow the ingestion gates and the inversion diagnostic. |

Screened against the harness criteria on [[strategy_family_search|the second strategy family search]].

## Fetch

- status: **ok** - fetched 2026-09-20T07:11:08Z by `clip`, 12,595 characters, sha256 `c359baa9aded`
- snapshot: `obsidian_vault/raw/fetched/source_clip_81f59cb347.txt`

## Related

- [[strategy_family_search|Second strategy family search]]
- [[sources_register|Sources register]]
- [[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]
