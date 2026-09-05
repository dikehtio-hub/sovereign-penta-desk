---
type: Attested Computation
title: knowledge.ingest.experiments
description: Pre-registrations and archived controls -> Experiment pages with json_path-guarded
  bars.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.experiments [--dir DIR ...] [--force]
executor:
  resource: knowledge/ingest/experiments.py
  receipt:
  - written
  - skipped
  - ignored
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/experiments.py
  title: knowledge/ingest/experiments.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.experiments [--dir DIR ...] [--force]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/experiments.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.experiments

> Pre-registrations and archived controls -> Experiment pages with json_path-guarded bars.

# Computation

```
python -m knowledge.ingest.experiments [--dir DIR ...] [--force]
```

## Receipt (the `--json` fields)

- `written`
- `skipped`
- `ignored`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/experiments.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
