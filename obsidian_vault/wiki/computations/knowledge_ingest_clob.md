---
type: Attested Computation
title: knowledge.ingest.clob
description: A survival-curve --json -> Reaction Profile pages, the Event page, the
  latency-decay table.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.clob --result curve.json --event EVENT
executor:
  resource: knowledge/ingest/clob.py
  receipt:
  - profiles
  - event
  - rows
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/clob.py
  title: knowledge/ingest/clob.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.clob --result curve.json --event EVENT
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/clob.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.clob

> A survival-curve --json -> Reaction Profile pages, the Event page, the latency-decay table.

# Computation

```
python -m knowledge.ingest.clob --result curve.json --event EVENT
```

## Receipt (the `--json` fields)

- `profiles`
- `event`
- `rows`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/clob.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
