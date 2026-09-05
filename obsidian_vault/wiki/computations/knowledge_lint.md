---
type: Attested Computation
title: knowledge.lint
description: L1-L5 structural checks and C1/C2/C3/C5; writes nothing unless --fix-safe
  (index, log, deprecate a gone Market).
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.lint [--drops DIR] [--json] [--fix-safe]
executor:
  resource: knowledge/lint.py
  receipt:
  - summary
  - findings
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/lint.py
  title: knowledge/lint.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.lint [--drops DIR] [--json] [--fix-safe]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/lint.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.lint

> L1-L5 structural checks and C1/C2/C3/C5; writes nothing unless --fix-safe (index, log, deprecate a gone Market).

# Computation

```
python -m knowledge.lint [--drops DIR] [--json] [--fix-safe]
```

## Receipt (the `--json` fields)

- `summary`
- `findings`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/lint.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
