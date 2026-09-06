---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py'
description: The strategy this module describes has already been built, traded on
  paper, measured against a pre-registered bar, and RETIRED. It is not an untested
  idea. `execution/strategies/liquidation_fade_strategy.py` traded exactly this thesis
  - detect a forced-sell cascade, compute a reb…
tags:
- concept
- thesis
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
  title: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
  headings:
  - READ THIS BEFORE ENABLING ANYTHING HERE
  - TIGHT POST-FILL TRAILING STOPS MAKE THAT WORSE, NOT BETTER
  - WHAT IS ACTUALLY OPEN, AND IT IS NARROWER THAN IT SOUNDS
  - WHAT THIS MODULE THEREFORE DOES
  asserts:
  - file: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
    pattern: READ\ THIS\ BEFORE\ ENABLING\ ANYTHING\ HERE
    claim: the docstring still carries the section 'READ THIS BEFORE ENABLING ANYTHING
      HERE'
  - file: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
    pattern: TIGHT\ POST\-FILL\ TRAILING\ STOPS\ MAKE\ THAT\ WORSE,\ NOT\ BETTER
    claim: the docstring still carries the section 'TIGHT POST-FILL TRAILING STOPS
      MAKE THAT WORSE, NOT BETTER'
  - file: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
    pattern: WHAT\ IS\ ACTUALLY\ OPEN,\ AND\ IT\ IS\ NARROWER\ THAN\ IT\ SOUNDS
    claim: the docstring still carries the section 'WHAT IS ACTUALLY OPEN, AND IT
      IS NARROWER THAN IT SOUNDS'
  - file: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
    pattern: WHAT\ THIS\ MODULE\ THEREFORE\ DOES
    claim: the docstring still carries the section 'WHAT THIS MODULE THEREFORE DOES'
  requires_files:
  - HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/strategies/whale_sweeper.py

> 4 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Read This Before Enabling Anything Here

The strategy this module describes has already been built, traded on paper, measured against a pre-registered bar, and RETIRED. It is not an untested idea. `execution/strategies/liquidation_fade_strategy.py` traded exactly this thesis - detect a forced-sell cascade, compute a rebound zone, rest a limit order in it - and `config/settings.py` records why it stopped:

 MFE/MAE 0.513 against a random-entry control of 1.092 n=466, 98% coverage, 30m horizon paired MFE-MAE per event: t = -10.52 MAE exceeded MFE in 72.7% of events 0 of 20,000 bootstrap resamples produced a non-negative mean

 A ratio BELOW the random control means entering on this signal was worse than entering at random. Forced liquidations are MOMENTUM drivers, not mean-reverting wicks: price ran about twice as far against the fade as for it. Rounds 9 through 15 of execution refinement - better geometry, tighter stops, regime filters - never moved the number, because no amount of execution work fixes a sign error.

## Tight Post-Fill Trailing Stops Make That Worse, Not Better

Against a momentum driver the fill arrives precisely because price is still travelling against you, and a tight stop then converts the adverse excursion from paper into realised loss. The retired strategy's own history is the evidence: it is the configuration rounds 9-15 kept trying.

## What Is Actually Open, And It Is Narrower Than It Sounds

`data/experiments/passive_fade_rebenchmark.meta.json` records a live pre-registration, and it is honest about the retirement's weakness: the 0.513 came from 15.2 hours in which two microcaps supplied 83% of all events (HHI 0.360), and the broad-market effect was 0.849 - still sub-random, but far less damning. Only the 30-minute horizon clears p<0.05 under a cluster bootstrap; at 5m and 15m the retirement is NOT statistically significant.

 So the honest position is: probably no edge, not proven across the broad market, and under active re-measurement with execution DISABLED. The reopening bar was set deliberately asymmetric - retiring took p=0.024 on a narrow sample, so coming back costs more than leaving did:

 >= 500 events, >= 20 coins, no coin over 20% of the sample then P(ratio >= 1.25) > 0.90 under a CLUSTER bootstrap resampling coins

## What This Module Therefore Does

Everything the sweeper needs except the part that would violate the pre-registration: cluster identification, rebound-zone geometry, order sizing, and the `hl_whale_sweep` bankroll bucket. Execution is held behind `EvidenceGate`, which reads the live benchmark and refuses until the bar is cleared. Nothing here is a placeholder - the day the measurement clears, `WHALE_SWEEP_EXECUTION_ENABLED` flips and the path is already wired and tested.

 The gate is the deliverable. A sweeper that trades a signal measured at half of random is not a strategy, it is a way to pay fees faster.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
