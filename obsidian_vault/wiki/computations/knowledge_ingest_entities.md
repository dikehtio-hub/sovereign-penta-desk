---
type: Attested Computation
title: knowledge.ingest.entities
description: 'CRM seeds from the titan cache and three databases (mode=ro): titans,
  whales, sharps, sportsbooks; judgement kept, evidence appended.'
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:49Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.entities [--limit-whales 100] [--limit-titans
  100]
executor:
  resource: knowledge/ingest/entities.py
  receipt:
  - counts
  - created
  - updated
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/entities.py
  title: knowledge/ingest/entities.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.entities [--limit-whales 100] [--limit-titans
    100]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/entities.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.entities

> CRM seeds from the titan cache and three databases (mode=ro): titans, whales, sharps, sportsbooks; judgement kept, evidence appended.

# Computation

```
python -m knowledge.ingest.entities [--limit-whales 100] [--limit-titans 100]
```

## Receipt (the `--json` fields)

- `counts`
- `created`
- `updated`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/entities.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
