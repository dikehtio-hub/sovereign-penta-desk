---
type: Attested Computation
title: knowledge.ingest.rulings
description: Directive / Ratification / Ruling N-N citations in AGENTS.md -> draft
  Ruling pages.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.rulings [--agents FILE] [--force]
executor:
  resource: knowledge/ingest/rulings.py
  receipt:
  - found
  - written
  - skipped
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/rulings.py
  title: knowledge/ingest/rulings.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.rulings [--agents FILE] [--force]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/rulings.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.rulings

> Directive / Ratification / Ruling N-N citations in AGENTS.md -> draft Ruling pages.

# Computation

```
python -m knowledge.ingest.rulings [--agents FILE] [--force]
```

## Receipt (the `--json` fields)

- `found`
- `written`
- `skipped`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/rulings.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
