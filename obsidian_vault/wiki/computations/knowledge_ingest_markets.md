---
type: Attested Computation
title: knowledge.ingest.markets
description: Tokens from rules, Experiment pages and the newest macro drop -> Market
  pages for lint C2.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.markets [--drops DIR] [--family F ...] [--force]
executor:
  resource: knowledge/ingest/markets.py
  receipt:
  - written
  - skipped
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/markets.py
  title: knowledge/ingest/markets.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.markets [--drops DIR] [--family F ...] [--force]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/markets.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.markets

> Tokens from rules, Experiment pages and the newest macro drop -> Market pages for lint C2.

# Computation

```
python -m knowledge.ingest.markets [--drops DIR] [--family F ...] [--force]
```

## Receipt (the `--json` fields)

- `written`
- `skipped`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/markets.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
