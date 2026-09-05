---
type: Attested Computation
title: knowledge.ingest.lead_lag
description: A lead_lag --json verdict -> Experiment page + Regime history row (latest_verdict,
  regime_consensus_3).
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.lead_lag --result verdict.json --tier 1|2|2b
executor:
  resource: knowledge/ingest/lead_lag.py
  receipt:
  - classification
  - history
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/lead_lag.py
  title: knowledge/ingest/lead_lag.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.lead_lag --result verdict.json --tier 1|2|2b
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/lead_lag.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.lead_lag

> A lead_lag --json verdict -> Experiment page + Regime history row (latest_verdict, regime_consensus_3).

# Computation

```
python -m knowledge.ingest.lead_lag --result verdict.json --tier 1|2|2b
```

## Receipt (the `--json` fields)

- `classification`
- `history`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/lead_lag.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
