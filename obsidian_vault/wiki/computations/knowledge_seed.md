---
type: Attested Computation
title: knowledge.seed
description: Compiles Desk, Item and Ruling pages from the Top 20 registry; skips
  existing pages unless --force.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.seed [--force] [--dry-run] [--at ISO]
executor:
  resource: knowledge/seed.py
  receipt:
  - written
  - skipped
  - index
  - log
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/seed.py
  title: knowledge/seed.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.seed [--force] [--dry-run] [--at ISO]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/seed.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.seed

> Compiles Desk, Item and Ruling pages from the Top 20 registry; skips existing pages unless --force.

# Computation

```
python -m knowledge.seed [--force] [--dry-run] [--at ISO]
```

## Receipt (the `--json` fields)

- `written`
- `skipped`
- `index`
- `log`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/seed.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
