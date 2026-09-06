---
type: Desk
title: 'Desk 5: Tax Reserve Agent'
description: 'The accountant every desk asks before sizing: lot engine, IRC 1256 60/40,
  IRC 165(d) gambling, NJ apportionment, tax escrow and the safe-bankroll gating hook.'
tags:
- desk
- desk-5
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:42Z'
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
  desk: 5
  asserts:
  - file: Tax_Reserve_Agent/interfaces/monarch_hook.py
    pattern: class MonarchBankrollHook
    claim: the gating hook class exists
  parameters:
  - name: federal_ordinary_rate
    value: 0.24
    file: Tax_Reserve_Agent/config.yaml
    pattern: ^\s*federal_ordinary_rate:\s*([0-9.]+)
  - name: state_tax_rate_nj
    value: 0.0637
    file: Tax_Reserve_Agent/config.yaml
    pattern: ^\s*state_tax_rate:\s*([0-9.]+)
  - name: kelly_fraction
    value: 0.25
    file: Tax_Reserve_Agent/interfaces/monarch_hook.py
    pattern: ^KELLY_FRACTION = ([0-9.]+)
---
# Desk 5: Tax Reserve Agent

The accountant every desk asks before sizing: lot engine, IRC 1256 60/40, IRC 165(d) gambling, NJ apportionment, tax escrow and the safe-bankroll gating hook.

**Domain**: Tax escrow and bankroll gating across all desks

## Code roots

- `Tax_Reserve_Agent`

## Raw streams (federated, read-only)

- `Tax_Reserve_Agent/data/tax_ledger.db`
- `Tax_Reserve_Agent/data/imports/`

## Vault surface (exporter-owned, never written by the knowledge layer)

- `Trading_Taxes/`

## Items

- [[Item_02_Sports_Gambling_Tax_Loss_Deduction_Module|Item 2: Sports Gambling Tax & Loss Deduction Module]] · deployed
- [[Item_03_Multi_Market_Bankroll_Hurdle_Gating_Hook|Item 3: Multi-Market Bankroll Hurdle & Gating Hook]] · deployed
- [[Item_04_Section_1256_Futures_Tax_60_40|Item 4: Section 1256 Futures Tax Ingestion (60/40 Rule)]] · deployed
- [[Item_17_Automated_Tax_Loss_Harvesting_Auto_Executor|Item 17: Automated Tax-Loss Harvesting Auto-Executor]] · deployed

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

## Other desks

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]

## Related

- [[Monarch_Hub|Monarch Hub]] (exporter-owned dashboard index)
