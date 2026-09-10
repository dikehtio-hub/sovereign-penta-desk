---
type: Experiment
title: 'Experiment: lead_lag_phase2_event_study'
description: PRE-REGISTERED (Round 126; protocol by Antigravity, Rulings R125-2 sections
  6, 7 and 8 of 2026-09-09/10; artifact by Claude Code).
tags:
- experiment
- desk-3
- item-18
- lead-lag
- event-study
- pre-registered
generated:
  by: claude-code/fable-5.1
  at: '2026-09-10T21:28:10Z'
status: draft
sources:
- id: registration
  resource: cross_market/experiments/lead_lag_phase2_fomc.meta.json
  title: lead_lag_phase2_fomc.meta.json
  author: human:operator
dev:
  desk: 3
  item: 18
  registration: cross_market/experiments/lead_lag_phase2_fomc.meta.json
  kind: event_study
  protocol: event_study
  registered_utc: '2026-09-10T21:30:00Z'
  parameters:
  - name: event_study_pm_min_displacement
    value: 0.02
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.pm_min_displacement
  - name: event_study_hl_min_displacement_bps_floor
    value: 10.0
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.hl_min_displacement_bps_floor
  - name: event_study_hl_noise_multiplier
    value: 3.0
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.hl_noise_multiplier
  - name: event_study_hl_noise_window_minutes
    value: 60
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.hl_noise_window_minutes
  - name: event_study_hl_noise_min_marks
    value: 60
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.hl_noise_min_marks
  - name: event_study_half_life_fraction
    value: 0.5
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.half_life_fraction
  - name: event_study_lead_tolerance_s
    value: 1.0
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.lead_tolerance_s
  - name: event_study_panel_min_informative_events
    value: 3
    file: cross_market/experiments/lead_lag_phase2_fomc.meta.json
    json_path: bars.panel_min_informative_events
  events:
  - id: fomc_2026-09-16
    kind: fed_rate
    release_utc: '2026-09-16T18:00:00Z'
    status: registered; tokens = the three YES tokens in the rules file
  - id: cpi_2026-10-14
    kind: cpi
    release_utc: '2026-10-14T12:30:00Z'
    status: pinned, tokens pending
  - id: fomc_2026-10-28
    kind: fed_rate
    release_utc: '2026-10-28T18:00:00Z'
    status: pinned, tokens pending
  stopping_rules:
    non_displacing_hold: 'a HOLD (or any print) under either bar is uninformative-shock:
      logged in the event history, exit 0, does NOT count toward the 3 informative
      events'
    rule_1_contemporaneous: if 2 consecutive informative events are contemporaneous-event-repricing
      or hyperliquid-leads-event, the event-study trading line is permanently terminated
      (latency is dominated by the centralised feed; no actionable alpha)
    rule_2_insignificance: if the 3 registered prints (fomc_2026-09-16, cpi_2026-10-14,
      fomc_2026-10-28) all resolve uninformative-shock, the line is retired on 2026-11-01
      as dead capital
    capital_deployment_bar: automated execution is funded only if polymarket-leads-event
      is observed on at least 2 of 3 informative events
  release_utc: '2026-09-16T18:00:00Z'
  window:
    start: '2026-09-16T17:58:00Z'
    end: '2026-09-16T18:05:00Z'
  tokens:
  - '5615282760875985231868508008056959876238536896643315063916840237042205273721'
  - '63842529068710005716169325380315470359047749786610778647370693404952498013178'
  - '88912926533493988427719291698947688154042720958310632316541141466409683822293'
  tokens_from: cross_market/experiments/fomc_2026-09-16.rules.json
  tests_run: 0
---
# Experiment: lead_lag_phase2_event_study

> Pre-registration, Item 18 Phase 2 (event-driven lead-lag). Reaction Profile pages and the panel link back here after each print.

## Status at registration

PRE-REGISTERED (Round 126; protocol by Antigravity, Rulings R125-2 sections 6, 7 and 8 of 2026-09-09/10; artifact by Claude Code). Item 18 Phase 2: does one venue reprice BEFORE the other around a scheduled macro print, at 1-second resolution? Phase 1 (three disjoint continuous windows, all no-lead) is closed and is not reopened by anything below. NEVER edit inside any event window (T-2 min to T+5 min). Token ids for events 2 and 3 are APPENDED in dated re-registrations before their prints, never replaced.

## Hypothesis

Polymarket order flow does not lead HyperLiquid BTC perps in continuous trading (Phase 1), but may lead, lag, or reprice contemporaneously during a discrete high-information macro shock. The measurable quantity is the difference in the second at which each venue completes half of its total post-print displacement.

## Events

| Id | Kind | Release (UTC) | Status |
|---|---|---|---|
| `fomc_2026-09-16` | fed_rate | `2026-09-16T18:00:00Z` | registered; tokens = the three YES tokens in the rules file |
| `cpi_2026-10-14` | cpi | `2026-10-14T12:30:00Z` | pinned, tokens pending |
| `fomc_2026-10-28` | fed_rate | `2026-10-28T18:00:00Z` | pinned, tokens pending |

## Grid and window

| Key | Value |
|---|---|
| `pre_s` | 120 |
| `post_s` | 300 |
| `grid_s` | 1 |
| `grid_start_rule` | T0 = the recorder's first Polymarket stamp on disk for the event (the scheduler fires at 13:58:58 EDT, so T0 is about T-58 s); constraint T0 <= T-30 s, else insufficient |
| `baseline_offset_s` | -5 |
| `baseline_rule` | P(T-5 s): the forward-filled value at 17:59:55Z, chosen as unperturbed by leaks; invariant whether the statement lands at 14:00:00.0 or 14:00:02.5, because t*50% is an absolute UTC second on each venue |
| `evaluation` | [T-5 s, T+300 s]; total shift dP_total = P(T+300 s) - P(T-5 s) on each venue |

## Series

- **polymarket**: book midpoint (best bid + best ask) / 2 of the stamp inside second t, forward-filled through empty seconds; a one-sided book contributes nothing and is forward-filled over (source: latency_sniper --record-loop stamps clob_<token>_<stamp>Z.json under the event's books_dir, one per token per second)
- **hyperliquid**: px of the LAST BTC trade in second t, forward-filled through empty seconds (Ruling R125-2 s.6.1) (source: HyperLiquid/HL_Monarch/data/hyperliquid_data.db table trades (every print over the collector WebSocket; measured ~444 BTC prints/min, ~15k/h, continuous through the 09-08 snapshot outage))

## Bars

| Bar | Value |
|---|---|
| `pm_min_displacement` | 0.02 |
| `hl_min_displacement_bps_floor` | 10.0 |
| `hl_noise_multiplier` | 3.0 |
| `hl_noise_window_minutes` | 60 |
| `hl_noise_min_marks` | 60 |
| `half_life_fraction` | 0.5 |
| `lead_tolerance_s` | 1.0 |
| `panel_min_informative_events` | 3 |

## Hl bar rule

Bar_HL = max(10 bps, 3 x median |5-minute move| of asset_snapshots.mark_px for BTC over [T-60 min, T-5 s]) (Ruling R125-2 s.7.1: a static 10 bps bar is crossed by ~24% of quiet overnight 5-minute windows - median 5.36 bps, p75 9.59, p90 14.71). Fewer than 60 marks in that hour -> the 10 bps floor, recorded as bar_source = floor_fallback (otherwise trailing_60m_relative).

## Displacement rule

Evaluated FIRST, before any half-life: the print is uninformative-shock if EITHER |dP_PM| < 0.02 (implied probability) OR |dP_HL| / P_HL(T-5 s) < Bar_HL. A lead needs both venues to have moved; if one is stationary the half-life second is undefined noise.

## Lead definition

t*50% on a venue = the earliest grid second t in [T-5 s, T+300 s] with |P(t) - P(T-5 s)| >= 0.5 x |dP_total|. lead_s = t*50%_HL - t*50%_PM. Positive = Polymarket completed half its move first.

## Classes

- `polymarket-leads-event`: lead_s > +1.0
- `hyperliquid-leads-event`: lead_s < -1.0
- `contemporaneous-event-repricing`: |lead_s| <= 1.0 (cross-venue propagation of 0.5-2 s is indistinguishable from zero at this grid)
- `uninformative-shock`: either venue under its displacement bar; exit code 0; logged, not counted

## Sufficiency

- **polymarket**: max_hole_s = 5.0; min_stamps = 300; scope = per registered token inside [T0, T+300 s]; a token that fails is marked insufficient and excluded from primary selection; the event is insufficient (exit 2) only when no token passes; why = the recorder stamps every second, so a missing second is recorder downtime, not a quiet market
- **hyperliquid**: feed_liveness_max_all_coin_gap_s = 5.0; feed_liveness_window = [T-5 s, T+300 s], every coin's prints (a gap > 5 s in the whole feed is a WebSocket stall or collector death -> insufficient, exit 2); baseline_max_age_s = 15.0; baseline_rule = the baseline is the last BTC print at or before T-5 s; insufficient only if it is older than 15 s (print time < T-20 s); quiet_seconds = BTC-quiet seconds forward-fill the last execution price and NEVER void the run (a quiet overnight hour has prints in ~54% of seconds; the print minute itself is dense)
- **order_of_evaluation**: 1 sufficiency of both legs -> 2 displacement bars -> 3 half-lives and lead, only when both venues displaced

## Panel

- **key**: (event, market_token)
- **primary_market**: among the event's sufficient tokens, the one with the largest |dP_total|; the event's class, lead and informative flag are the primary's
- **verdict_requires**: >= 3 informative events (panel_min_informative_events); a single print yields a Reaction Profile page, never a verdict
- **profile_pages**: wiki/experiments/reaction_profile_<event>__<market>.md, one per registered token per event, plus wiki/experiments/lead_lag_phase2_panel.md compiled from all of them

## Stopping rules (pre-registered)

- **non_displacing_hold**: a HOLD (or any print) under either bar is uninformative-shock: logged in the event history, exit 0, does NOT count toward the 3 informative events
- **rule_1_contemporaneous**: if 2 consecutive informative events are contemporaneous-event-repricing or hyperliquid-leads-event, the event-study trading line is permanently terminated (latency is dominated by the centralised feed; no actionable alpha)
- **rule_2_insignificance**: if the 3 registered prints (fomc_2026-09-16, cpi_2026-10-14, fomc_2026-10-28) all resolve uninformative-shock, the line is retired on 2026-11-01 as dead capital
- **capital_deployment_bar**: automated execution is funded only if polymarket-leads-event is observed on at least 2 of 3 informative events

## Commands

```
python -m cross_market.event_study --event fomc_2026-09-16 --json > cross_market/experiments/event_study_fomc_2026-09-16.json
python -m knowledge.ingest.event_study --result cross_market/experiments/event_study_fomc_2026-09-16.json
```

## Caveats

- One print is one observation. The N >= 3 panel pools events of different kinds (two FOMC decisions, one CPI) whose Polymarket instruments differ; the panel key keeps them distinct and the verdict is about the venue-latency question, not any single market.
- Polymarket midpoints are recorder-stamped (host clock, W32Time-synced, last offset +0.013 s); HyperLiquid prints are exchange-stamped. The +-1 s tolerance band absorbs that plus 0.5-2 s of cross-venue propagation.
- A HOLD priced at p~0.90 before the print may not move the rate markets by 0.02; the protocol accepts that such a print is uninformative and says so in advance.
- The recorder runs 420 s from ~13:58:58 EDT; nothing in this registration changes the scheduled task, the drill batch, or any daemon before 09-16.

## Enforced in code

cross_market.event_study (grid, bars, half-lives, classes, sufficiency, exit codes); knowledge.ingest.event_study (profile + panel pages, stopping-rule status); knowledge.ingest.experiments (this page, dev.parameters guarded by lint C1, tokens by C2, window by C5)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
- [[experiments_register|Experiments register]]
