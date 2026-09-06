---
type: Attested Computation
title: knowledge.views
description: Obsidian Bases views (wiki/_views/*.base) and human page templates (wiki/_templates/*.md)
  with OKF-valid frontmatter.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:24Z'
status: draft
runtime: python
computation: python -m knowledge.views [--force] [--dry-run]
executor:
  resource: knowledge/views.py
  receipt:
  - written
  - skipped
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/views.py
  title: knowledge/views.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.views [--force] [--dry-run]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/views.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.views

> Obsidian Bases views (wiki/_views/*.base) and human page templates (wiki/_templates/*.md) with OKF-valid frontmatter.

# Computation

```
python -m knowledge.views [--force] [--dry-run]
```

## Receipt (the `--json` fields)

- `written`
- `skipped`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/views.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
