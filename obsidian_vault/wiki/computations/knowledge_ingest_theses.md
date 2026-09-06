---
type: Attested Computation
title: knowledge.ingest.theses
description: Titled docstring sections of the desk modules -> Concept pages, each
  heading pinned with dev:asserts (lint C1).
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:24Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.theses [--root DIR ...] [--force]
executor:
  resource: knowledge/ingest/theses.py
  receipt:
  - scanned
  - written
  - skipped
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/theses.py
  title: knowledge/ingest/theses.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.theses [--root DIR ...] [--force]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/theses.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.theses

> Titled docstring sections of the desk modules -> Concept pages, each heading pinned with dev:asserts (lint C1).

# Computation

```
python -m knowledge.ingest.theses [--root DIR ...] [--force]
```

## Receipt (the `--json` fields)

- `scanned`
- `written`
- `skipped`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/theses.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
