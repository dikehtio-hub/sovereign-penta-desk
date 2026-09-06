---
type: Desk
title: 'Desk 4: Quant Trading Lab'
description: 'CME futures desk: nine strategy stacks, ICT session clocks, Risk Sentinel
  invariants, walk-forward and grid-search research over stitched continuous contracts;
  its own git repository.'
tags:
- desk
- desk-4
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
  desk: 4
  parameters:
  - name: daily_drawdown_killswitch_usd
    value: 3,500.00
    file: quant_trading_lab/CLAUDE.md
    pattern: 'Hard Daily Drawdown Killswitch: \$([0-9,\.]+)'
  - name: single_trade_risk_pct
    value: 1.0
    file: quant_trading_lab/CLAUDE.md
    pattern: 'Single Trade Risk Budget: ([0-9.]+)%'
---
# Desk 4: Quant Trading Lab

CME futures desk: nine strategy stacks, ICT session clocks, Risk Sentinel invariants, walk-forward and grid-search research over stitched continuous contracts; its own git repository.

**Domain**: CME futures (/NQ /ES /GC /CL) and BTC perps

## Code roots

- `quant_trading_lab`

## Raw streams (federated, read-only)

- `quant_trading_lab/data/continuous/*.csv`
- `quant_trading_lab/state/runtime_state.json`

## Vault surface (exporter-owned, never written by the knowledge layer)

- `Quant_Trading_Lab.md`

## Items

- [[Item_11_Automated_Prop_Firm_CME_Futures_Execution|Item 11: Automated Prop Firm / Cme Futures Execution Gateway]] · roadmap

## Rulings

- [[Ruling_R95|R95 - Ratification of the knowledge layer (R95-A to R95-G)]]

## Registers (machine-maintained)

- [[experiments_register|Experiments register]]
- [[rulings_register|Rulings register]]
- [[computations_register|Computations register]]
- [[events_register|Events register]]
- [[markets_register|Markets register]]
- [[crm_register|CRM register]]
- [[journal_register|Journal register]]
- [[theses_register|Theses register]]
- [[digests_register|Digests register]]

## Other desks

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## Related

- [[Monarch_Hub|Monarch Hub]] (exporter-owned dashboard index)
