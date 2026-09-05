---
type: Attested Computation
title: knowledge.ingest.calendar
description: Committed calendar YAML (FOMC statements, estimated-tax deadlines) ->
  Event pages with windows.
tags:
- computation
- knowledge-cli
- module-23
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:22Z'
status: draft
runtime: python
computation: python -m knowledge.ingest.calendar [--dir DIR] [--force]
executor:
  resource: knowledge/ingest/calendar.py
  receipt:
  - written
  - skipped
attester:
  resource: knowledge/tests/test_knowledge.py
sources:
- id: module
  resource: knowledge/ingest/calendar.py
  title: knowledge/ingest/calendar.py
  author: human:operator
dev:
  kind: knowledge_cli
  command: python -m knowledge.ingest.calendar [--dir DIR] [--force]
  exit_codes:
    '0': ok
    '1': findings
    '3': refused (HALT.flag, missing input)
  requires_files:
  - knowledge/ingest/calendar.py
  - knowledge/tests/test_knowledge.py
---
# knowledge.ingest.calendar

> Committed calendar YAML (FOMC statements, estimated-tax deadlines) -> Event pages with windows.

# Computation

```
python -m knowledge.ingest.calendar [--dir DIR] [--force]
```

## Receipt (the `--json` fields)

- `written`
- `skipped`

## Exit codes

- `0`: ok
- `1`: findings
- `3`: refused (HALT.flag, missing input)

## Attestation

Declarative (R95-C): the module `knowledge/ingest/calendar.py` and the test `knowledge/tests/test_knowledge.py` must exist; nothing is executed by the wiki.

## Related

- [[computations_register|Computations register]]
