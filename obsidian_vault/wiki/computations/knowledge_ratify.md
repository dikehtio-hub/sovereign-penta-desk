---
type: Attested Computation
title: knowledge.ratify
description: 'Records an Antigravity ratification: appends `verified` and sets status
  on the selected pages; idempotent.'
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:49Z'
status: draft
runtime: python
computation: python -m knowledge.ratify --type T [--tag TAG] --ruling N-N [--by ACTOR]
  [--dry-run]
executor:
  resource: knowledge/ratify.py
  receipt:
  - selected
  - ratified
  - already
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ratify.py
  title: knowledge/ratify.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ratify --type T [--tag TAG] --ruling N-N [--by ACTOR]
    [--dry-run]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ratify.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ratify

> Records an Antigravity ratification: appends `verified` and sets status on the selected pages; idempotent.

# Computation

```
python -m knowledge.ratify --type T [--tag TAG] --ruling N-N [--by ACTOR] [--dry-run]
```

## Receipt (the `--json` fields)

- `selected`
- `ratified`
- `already`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ratify.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
