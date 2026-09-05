---
type: Attested Computation
title: lead_lag --check-data (Item 18 readiness gate)
description: 'The Item 18 data-readiness sentinel on Cross_Market_Titans.md: is the
  stamped macro series long and dense enough for the maiden run.'
tags:
- computation
- shell-twin
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m cross_market.lead_lag --check-data [--json]
executor:
  resource: cross_market/lead_lag.py
  receipt:
  - ready
  - points
  - points_total
  - span_hours
  - segment_start
  - newest
  - reasons
  - eta
  - checked_at
attester:
  resource: cross_market/tests/test_lead_lag.py
sources:
- id: module
  resource: cross_market/lead_lag.py
  title: cross_market/lead_lag.py
  author: human:operator
dev:
  kind: shell_twin
  command: python -m cross_market.lead_lag --check-data [--json]
  exit_codes:
    '0': ready
    '3': not ready
  desk: 3
  item: 18
  dashboard: Cross_Market_Titans.md
  requires_files:
  - cross_market/lead_lag.py
  - cross_market/tests/test_lead_lag.py
---
# lead_lag --check-data (Item 18 readiness gate)

> The Item 18 data-readiness sentinel on Cross_Market_Titans.md: is the stamped macro series long and dense enough for the maiden run.

# Computation

```
python -m cross_market.lead_lag --check-data [--json]
```

## Receipt (the `--json` fields)

- `ready`
- `points`
- `points_total`
- `span_hours`
- `segment_start`
- `newest`
- `reasons`
- `eta`
- `checked_at`

## Exit codes

- `0`: ready
- `3`: not ready

## Dashboard

Printed as the "Shell twin" on `Cross_Market_Titans.md` (exporter-owned).

## Attestation

Declarative (R95-C): the module `cross_market/lead_lag.py` and the test `cross_market/tests/test_lead_lag.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
