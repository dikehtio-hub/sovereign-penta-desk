---
type: Concept
title: 'Thesis: Polymarket/Polymarket_Monarch/consensus_scanner.py'
description: '--------------------------------------------------------------------------------
  The specified bar was win_rate >= 60% and realized_pnl >= $5,000. Applied to the
  live table that selects 12 wallets - and the top one has a 100% win rate on ONE
  closed position. Several others sit at…'
tags:
- concept
- thesis
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Polymarket/Polymarket_Monarch/consensus_scanner.py
  title: Polymarket/Polymarket_Monarch/consensus_scanner.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Polymarket/Polymarket_Monarch/consensus_scanner.py
  headings:
  - THE FILTER PROBLEM YOU MUST UNDERSTAND BEFORE TRUSTING ANY SIGNAL
  - WHAT THIS DOES NOT MODEL
  asserts:
  - file: Polymarket/Polymarket_Monarch/consensus_scanner.py
    pattern: THE\ FILTER\ PROBLEM\ YOU\ MUST\ UNDERSTAND\ BEFORE\ TRUSTING\ ANY\ SIGNAL
    claim: the docstring still carries the section 'THE FILTER PROBLEM YOU MUST UNDERSTAND
      BEFORE TRUSTING ANY SIGNAL'
  - file: Polymarket/Polymarket_Monarch/consensus_scanner.py
    pattern: WHAT\ THIS\ DOES\ NOT\ MODEL
    claim: the docstring still carries the section 'WHAT THIS DOES NOT MODEL'
  requires_files:
  - Polymarket/Polymarket_Monarch/consensus_scanner.py
  desk: 3
---
# Thesis: Polymarket/Polymarket_Monarch/consensus_scanner.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Filter Problem You Must Understand Before Trusting Any Signal

-------------------------------------------------------------------------------- The specified bar was win_rate >= 60% and realized_pnl >= $5,000. Applied to the live table that selects 12 wallets - and the top one has a 100% win rate on ONE closed position. Several others sit at 100% on 1-5. A win rate over a handful of closed positions is noise, and ranking by it selects whoever got lucky recently, which is the classic way to build a copy-trading system that tracks survivorship instead of skill.

 So MIN_CLOSED_POSITIONS exists and defaults to 10. The cost is honest and steep:

 closed >= 1 -> 12 wallets closed >= 20 -> 4 wallets closed >= 5 -> 9 wallets closed >= 30 -> 2 wallets closed >= 10 -> 7 wallets closed >= 50 -> 0 wallets

 The directive asked for the "top 20 sharp wallets". Twenty do not exist at this bar - seven do. Widening the filter to reach twenty would mean filling the roster with 100%-on-one-trade wallets, which is worse than a smaller roster.

 --------------------------------------------------------------------------------

## What This Does Not Model

-------------------------------------------------------------------------------- * LATENCY. We see a trade only after it settles and the API serves it. The copy fills at the CURRENT ask, not the sharp's price, and `slippage_pct` records the gap. A signal whose slippage exceeds its edge is not tradeable, and the paper engine records that rather than hiding it. * Sharps exiting. Activity gives BUY and SELL; a consensus of SELLs on an outcome is treated as a consensus AGAINST it, not ignored. * Correlated wallets. Two wallets under one operator look like consensus and are indistinguishable from it at this level of data. * win_rate here is 7-day and recomputed by pnl_scanner; it is a rolling quality estimate, not a lifetime record. ================================================================================

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
