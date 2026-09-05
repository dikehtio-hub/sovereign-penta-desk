---
type: Attested Computation
title: knowledge.computations
description: 'This page''s own writer: the Attested Computation catalogue.'
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.computations [--force] [--at ISO]
executor:
  resource: knowledge/computations.py
  receipt:
  - written
  - skipped
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/computations.py
  title: knowledge/computations.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.computations [--force] [--at ISO]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/computations.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.computations

> This page's own writer: the Attested Computation catalogue.

# Computation

```
python -m knowledge.computations [--force] [--at ISO]
```

## Receipt (the `--json` fields)

- `written`
- `skipped`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/computations.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
