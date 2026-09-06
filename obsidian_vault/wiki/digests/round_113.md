---
type: Digest
title: Round 113 digest
description: 'Round 113 (2026-09-06): THE FOMC DRILL HAS A PRE-FLIGHT, THE HUB CAN
  NO LONGER LAG A REGISTER, AND `ready` MEANS EVERY GATE'
tags:
- digest
- work-chain
- round-113
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T18:39:16Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-113-complete
  title: AGENTS.md - Round 113 complete
  author: claude-code/fable-5.1
dev:
  round: 113
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 113 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 113 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE FOMC DRILL HAS A PRE-FLIGHT, THE HUB CAN NO LONGER LAG A

REGISTER, AND `ready` MEANS EVERY GATE. D4: `python -m knowledge.drills.fomc_rehearsal` checks the
five things the 2026-09-16 drill needs to agree on (Event page, rules registration + raw JSON, the
drill card, the git-ignored batch file the task runs, the scheduled task itself via one injectable
PowerShell query) - 22 checks on the real setup, read-only by construction (vault hashed before and
after). Real result: 0 FAIL, 2 WARN (battery flags; interactive-only logon), tokens agree three ways,
trigger 13:58:00 local = T-2. The one FAIL on first run was the module's OWN regex reading `set
BOOKS=%2` instead of the default line beneath it - fixed, and now a test. Out of band, Antigravity's
b3c4493 hand-fix showed the registers hub one pass behind whenever an adapter rewrote a register
without a following seed: `registers.write_register` now writes the register AND the hub in one
call, wired into all 12 adapter call sites (seed untouched; it writes the hub last anyway). D2:
`ready` is set only when EVERY sample requirement the registration wrote down passes - for
passive_fade_rebenchmark that is four gates mirrored read-only from cascade_excursions (19,008 vs
500 events; 62 vs 20 coins; top coin ZEC 19.84% vs 20% ceiling; 7.49 vs 7 days) - with each gate
recorded on the page. `ready_since` is the first run that OBSERVED every gate passing, carried over
like measured_at; lint L11 (warning) fires STALL_DAYS after that with no verdict page. Dating
readiness from the day the count crossed 500 (2026-09-01) would have fired L11 today on a sample
the registration itself called inadequate at Round 104 (PONS 22.5%). D1 REVERSED: lint owns
STALL_DAYS - the adapters already import from lint, so lint importing from experiments would be a
circular import; the experiments copy was dead code and is gone. D3: the four Desk 4 collection
errors were THREE different missing packages (hyperliquid-python-sdk x2, uvicorn, fastapi), not one;
each module now skips on the one it lacks, naming the install; fastapi was installed after a clean
dry run (no upgrades) but the webhook module still skips because `main` imports the Hyperliquid
adapter at module level. Desk 4 from its own directory: 151 passed, 10 skipped, 0 errors. Tests:
knowledge 286 (+23), all green offline. Vault 493 pages, lint CLEAN, idempotent across
experiments/digests/seed by hash. NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
