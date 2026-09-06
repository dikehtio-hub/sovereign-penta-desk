---
type: Attested Computation
title: knowledge.journal
description: The trading-day journal (paper executions, debrief) and the calibration
  ledger (predictions Brier-scored against Event payloads).
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:58Z'
status: draft
runtime: python
computation: python -m knowledge.journal [--date D] [--create] | --predict ... | --score
executor:
  resource: knowledge/journal.py
  receipt:
  - receipts
  - predictions_n
  - debrief
  - scored
  - pending
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/journal.py
  title: knowledge/journal.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.journal [--date D] [--create] | --predict ... | --score
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/journal.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.journal

> The trading-day journal (paper executions, debrief) and the calibration ledger (predictions Brier-scored against Event payloads).

# Computation

```
python -m knowledge.journal [--date D] [--create] | --predict ... | --score
```

## Receipt (the `--json` fields)

- `receipts`
- `predictions_n`
- `debrief`
- `scored`
- `pending`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/journal.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
