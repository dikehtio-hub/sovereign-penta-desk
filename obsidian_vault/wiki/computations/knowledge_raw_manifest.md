---
type: Attested Computation
title: knowledge.raw_manifest
description: 'raw/index.md: every federated raw stream in the OKF index format.'
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.raw_manifest [--dry-run]
executor:
  resource: knowledge/raw_manifest.py
  receipt:
  - streams
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/raw_manifest.py
  title: knowledge/raw_manifest.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.raw_manifest [--dry-run]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/raw_manifest.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.raw_manifest

> raw/index.md: every federated raw stream in the OKF index format.

# Computation

```
python -m knowledge.raw_manifest [--dry-run]
```

## Receipt (the `--json` fields)

- `streams`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/raw_manifest.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
