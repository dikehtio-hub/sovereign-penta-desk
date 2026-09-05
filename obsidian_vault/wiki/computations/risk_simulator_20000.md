---
type: Attested Computation
title: risk_simulator --iterations 20000 --json (Item 19)
description: 'The multi-desk Monte Carlo behind Risk_Sentinel.md: ruin probabilities
  and drawdown VaR over the shared bankroll.'
tags:
- computation
- shell-twin
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m cross_market.risk_simulator --iterations 20000 --json
executor:
  resource: cross_market/risk_simulator.py
  receipt:
  - iterations
  - horizon_days
  - short_horizon_days
  - seed
  - start_equity
  - ruin_fraction
  - ruin
  - max_drawdown
attester:
  resource: cross_market/tests/test_risk_simulator.py
sources:
- id: module
  resource: cross_market/risk_simulator.py
  title: cross_market/risk_simulator.py
  author: human:operator
dev:
  kind: shell_twin
  command: python -m cross_market.risk_simulator --iterations 20000 --json
  exit_codes:
    '0': ok
    '3': HALT.flag
  desk: 3
  item: 19
  dashboard: Risk_Sentinel.md
  requires_files:
  - cross_market/risk_simulator.py
  - cross_market/tests/test_risk_simulator.py
---
# risk_simulator --iterations 20000 --json (Item 19)

> The multi-desk Monte Carlo behind Risk_Sentinel.md: ruin probabilities and drawdown VaR over the shared bankroll.

# Computation

```
python -m cross_market.risk_simulator --iterations 20000 --json
```

## Receipt (the `--json` fields)

- `iterations`
- `horizon_days`
- `short_horizon_days`
- `seed`
- `start_equity`
- `ruin_fraction`
- `ruin`
- `max_drawdown`

## Exit codes

- `0`: ok
- `3`: HALT.flag

## Dashboard

Printed as the "Shell twin" on `Risk_Sentinel.md` (exporter-owned).

## Attestation

Declarative (R95-C): the module `cross_market/risk_simulator.py` and the test `cross_market/tests/test_risk_simulator.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
