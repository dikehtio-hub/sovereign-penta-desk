---
type: Digest
title: Round 54 digest
description: 'Round 54: WATCHDOG CEILING + ABANDONMENT ALERT, USER-LEVEL WEBHOOK FALLBACK,
  LAUNCHER DETACHMENT ROOT CAUSE FIXED'
tags:
- digest
- work-chain
- round-54
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-54-complete
  title: AGENTS.md - Round 54 complete
  author: claude-code/fable-5.1
dev:
  round: 54
  date: null
  kind: round_digest
---
# Round 54 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

WATCHDOG CEILING + ABANDONMENT ALERT, USER-LEVEL WEBHOOK

FALLBACK, LAUNCHER DETACHMENT ROOT CAUSE FIXED. The dashboard watchdog gives
up after SERVICE_WATCHDOG_MAX_RELAUNCHES (3) relaunches that left the service
dead, logs service_abandoned and alerts once (own cooldown key); the service
coming back resets it. WebhookAlerter.user_env reads DISCORD_WEBHOOK_URL /
TELEGRAM_* from os.environ and then from the USER-level registry value, so a
process born before the variable existed still alerts (tests neutralise the
fallback via tests/conftest.py). start_collector.bat launches the supervisor
with PowerShell Start-Process: a caller that captures the launcher's output
returns at once instead of blocking for the service's lifetime. Service and
the multi-tag Polymarket watcher restarted with the variable exported; the
dashboard runs without it and alerts through the registry fallback (proved
from a fresh variable-less process). 2 new tests.

## Related

- [[digests_register|Digests register]]
