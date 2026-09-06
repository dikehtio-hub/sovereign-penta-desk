---
type: Ruling
title: R2 - record the CLOB around a scheduled print
description: One read-only GET per token per interval from T-2 to T+5 around a scheduled
  release, so the seconds a resting book survives after the print can be measured
  before anything is built on it.
tags:
- ruling
- desk-3
- r2
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:42Z'
status: stable
verified:
- by: antigravity/architect
  at: '2026-09-05T18:13:11Z'
stale_after: '2027-03-05T00:28:42Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: DEV handoff log
  author: human:operator
- id: commit-49f85f8
  resource: git:49f85f8
  title: commit 49f85f8
dev:
  desk: 3
  ruling_id: R2
  round: 93
  asserts:
  - file: cross_market/latency_sniper.py
    pattern: def record_loop
    claim: the recording loop exists
---
# Ruling R2 - record the CLOB around a scheduled print

Implemented in Round 93 as `latency_sniper.record_loop()` and the CLI `--record-loop --tokens T[,..] --interval 1 --duration 420 [--books DIR]`: sleeps interval minus fetch time, stops at the duration, on HALT.flag (exit 3) or Ctrl-C; an HTTP 429 is counted and answered with a growing pause (5 s x n, max 30 s). The first drill is the 2026-09-16 FOMC statement (Windows task Monarch_FOMC_Drill, 13:58 EDT). Its stamps are the raw layer for the first Reaction Profile pages.

## Applies to

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]

## Provenance

- Round 93, commit `49f85f8`
- ratified by Antigravity
