# AGENTS.md - tradingview_mcp (standalone, pre-migration)

Cross-tool handoff log for Antigravity and Claude Code. Terse. This project lives OUTSIDE
`C:\Users\ixis1\Desktop\DEV` on purpose: DEV is frozen at `fabeb97` for the Wednesday
2026-09-16 14:00 EDT FOMC drill. It moves into DEV afterwards; see `MIGRATION_TO_DEV.md`.
Until then this directory carries its own `HANDOFF_PROMPT.md` (Claude Code -> Antigravity,
single rotating prompt; superseded ones in `HANDOFF_ARCHIVE.md`) and expects Antigravity's
reply in `ANTIGRAVITY_PROMPT.md` here, not in DEV.

Upstream: <https://github.com/moondevonyt/Trading-View-MCP-for-AI-by-Moon-Dev> @ `60f12fd`.

## Status

- 2026-09-15 17:50 EDT (Claude Code, round 8): Section 90 (write 15:28:35, claimed 15:40, 40
  lines, 0 control chars) read and verified; it ratifies both round-7 corrections and locks the
  6-item post-drill queue with the TV MCP migration at position 5. **Pre-drill exchange officially
  closed by both sides.** New empirical datum: exporter PID 51256 passed the 16:30 checkpoint and
  was still RUNNING at 17:47 EDT, 319 min uptime, ~64 prune opportunities, still exactly 2
  tracebacks. Survival at 64 prunes is 0.01% under Section 87's 13.3% (falsified ~1 in 10,000)
  and 53-68% under the calibrated 0.6-1.0%. Section 89's 65-75% call for 16:30 was accurate.
  Next checkpoints: 20:00 EDT (~90 prunes, 40-58%) and Wed 13:30 (~300 prunes, 5-16%).
  The round-7 closure countersign crossed in flight with Section 90 and is functionally answered
  by its queue item 5. **Project status: pre-drill scope complete, nothing owed before the print.**
  Standalone tree still uncommitted (5 modified, 6 untracked) on branch `main`, whose `origin` is
  MoonDev's upstream GitHub: commit locally if desired, NEVER push to that remote.
- 2026-09-15 15:35 EDT (Claude Code, round 7): Section 89 (15:23 EDT, 0 control characters)
  verified. Section 87's 13.3% hazard formally superseded by ~0.6-1.0% per prune (35 survivals,
  p < 0.007). Exporter alive 178 min at 15:25 EDT, 2 tracebacks. Commit `9c87974` verified: it is
  the DEFECT-ENG-001 fix itself (09-13), on `bugfix/engine-slippage-signs` only, checked out in
  the `qtl_slipfix` worktree, not in master; Section 89's "after merge 9c87974" is loose wording.
  Arithmetic note: at the 0.6% end of their range, survival to Wed 13:30 is ~16%, not "<10%";
  conclusion unchanged (13:30 step essential). Parity prerequisites and the two-commit
  DEFECT-EXP-001 plan ratified. Stand-down locked until Wed 14:00 EDT. DEV 52 dirty, standalone
  5 + 6, port 9222 idle (measured 15:26 EDT).
- 2026-09-15 14:20 EDT (Claude Code, round 6): Section 88 (13:53 EDT, 0 control characters)
  verified. On disk: DEFECT-EXP-001 at `DEV\HOMEWORK.md:176` with the safe-mtime fix and the
  audit; D2 unified to the DEV-root path; DEV 52 dirty. Loop 48.67 s and 2 deletions per prune
  agree with my numbers. Section 88's survival predictions (38-50% at 16:30, 15-25% at 20:00)
  imply a ~2% per-prune hazard and silently replace Section 87's 13.3% / "98% inevitable";
  recorded as a revision. Exporter alive 104 min at 14:12 EDT (~21 prune opportunities; the
  13.3% model would allow that with ~5% probability). My sort timing under live load: 265 ms
  (glob 13 + stat-sort 252), same as the warm-cache figure, so Hypothesis A (load inflates the
  window) is not visible in steady state; divergence still unexplained, post-drill instrumentation
  stands. Strategy: t0030 Pine/Python parity accepted with prerequisites (slippage merge first or
  the qtl_slipfix worktree, strategy-tester selectors verified, TV tier known); cache refactor as a
  second commit after the fix + regression test. Stand-down acknowledged.
- 2026-09-15 13:35 EDT (Claude Code, round 5): Antigravity's Section 87 (`ANTIGRAVITY_PROMPT.md`
  here, 13:02 EDT) verified read-only. Confirmed on disk: forensics, code audit, WARN identity,
  D8 (PNG gone, DEV 52 dirty), D9 (HOMEWORK 13:30 line names the guarded launcher). NOT on disk:
  D10 (DEFECT-EXP-001 appears in no DEV file). Odds critique accepted in direction (exposure ~74
  min, not 39 h), disputed in mechanism (measured loop ~49.5 s and 266 ms sort give ~1% per prune,
  empirical 2/15); arbiter is PID 51256's survival (alive 55 min at 13:23). Corrections for the
  record: my "every 15 s" was the sleep, the loop is ~49.5 s; 09-14 is MONDAY (my earlier texts
  said Sunday for the crashes and the PNG); the ruling file holds 14 control characters from
  interpreted backslashes. D2 path in Section 87 (interfaces/ or tools/) conflicts with the
  operator's stated DEV-root target; operator's call. Stand-down acknowledged.
- 2026-09-15 12:45 EDT (Claude Code, round 4, Tuesday verification, read-only): dedicated Chrome
  closed (port 9222: 0 listeners; D1 done). No `ANTIGRAVITY_PROMPT.md` here yet, rounds 1-3
  unanswered. The round-4 prompt carries a DEV finding made during the freeze (the cross-market
  exporter crashed twice on a glob-then-stat race with the fetcher's 192 h drop prune; details in
  `HANDOFF_PROMPT.md` section 2) because DEV files are under a no-touch rule for Claude.
- 2026-09-15 00:25 EDT (Claude Code, round 3, readiness confirmation): setup, mount
  verification and registration are complete and re-verified. Canonical registration is now
  USER scope (`~/.claude.json`, added by the operator 23:48 EDT, "Connected" from any cwd).
  The project-scope `.mcp.json` from round 2 is a same-name duplicate (decision D7).
- Native tv_* tools are NOT loaded in the Claude Code session that did this work (opened in DEV
  before the registration; MCP servers attach at session start). Any new or restarted session
  gets the 16 tools natively. Meanwhile the tools were driven from that session through a
  stdio client script and re-proven live at 04:05Z and 04:08Z.
- Someone changed the chart at ~23:48 EDT from a DEV working directory: it now shows
  `BATS:AAPL · 15` in the legend's compact mode, and `DEV\moon_dev_chart.png` (80,404 B,
  untracked, not ignored by DEV) was left behind. DEV dirty 51 -> 53 (that PNG plus vault churn).
  On the 00:06 EDT screenshot the bars/OHLC were still those of the 1D view. Not touched by Claude.
- DEV: `fabeb97`, 53 dirty, 0 staged, no `.mcp.json`. Standalone: `60f12fd` + 5 modified
  + 5 untracked, `git diff --stat` 79+/15-, nothing committed (measured 2026-09-15T04:08:32Z).
  Port 9222: 1 listener (Chrome 152.0.7977.84). `~/.tradingview_mcp_chrome` present.

## What changed (vs upstream 60f12fd)

1. `requirements.txt`: `mcp>=1.0.0,<2` (2.x removed `mcp.server.fastmcp`). Venv 1.30.0.
2. `.gitignore`: + `venv/`, + `.claude/settings.local.json`.
3. `mount_pine.py:69`: `read_text(encoding="utf-8")` (cp1252 locale garbled the 🌙 title).
4. `tools/chart.py` `_current_chart_state`: DOM fallbacks (header symbol button; main-series
   legend row in BOTH display modes, full `Apple Inc 1D NASDAQ` and compact `BATS:AAPL · 15`,
   parsed by regex; header interval bar last because it disagreed with the chart). Returns
   `exchange` and `description` too.
5. `tools/indicators.py` `_read_legend`: hashed-class legend (`sources-` > `study-`, `valueValue`),
   old selector as fallback, `args` list added. NOT fixed, same dead selector in post-action checks:
   `tv_add_indicator` L178, `tv_remove_indicator` L220, `tv_remove_all_indicators` L244.
6. New: `.mcp.json` (project scope, duplicate), `.claude/settings.local.json` (ignored), editable
   install (`pip install -e .`), `HANDOFF_ARCHIVE.md`, round-1 files (`venv/`, `.env`,
   `MIGRATION_TO_DEV.md`, `AGENTS.md`, `HANDOFF_PROMPT.md`).

Verified: mount run 23:30 EDT valid=True 422 ms / 121 lines / add 12.3 s / legend Vol + MD RIBBON /
`moon_dev_chart.png` 131,503 B / MOUNTED: True. Stdio health check: 16 tools, none missing/extra,
from project cwd and `%TEMP%`; live reads AAPL / 1D / NASDAQ before the chart change, AAPL / 15 /
BATS after; `tv_read_indicator_value` RIBBON 12 values, RSI clean error; `tv_screenshot` to a
custom path ok. `tests/test_smoke.py` 3 passed.

## Next / open questions

- Operator: restart (or open) a Claude Code session to get the 16 tools natively; decide the fate
  of `DEV\moon_dev_chart.png` (Claude will not touch DEV); look at the Chrome window and say whether
  the chart is really on 15 minutes.
- D1: close the dedicated Chrome before the Wednesday 13:30 EDT stand-down; reopen after.
- D2: tracking model at migration (A vendored default, B nested repo).
- D5: fix the three remaining dead-selector verification sites now or post-drill.
- D7: delete the duplicate project-scope `.mcp.json` + `.claude/settings.local.json`, or keep for
  option (i) in `MIGRATION_TO_DEV.md` 5.1.
- HOMEWORK.md line 174 item (operator's file, DEV, not edited): the Chrome profile is in HOME, not
  the project, so nothing to gitignore for it; there is no `cwd` key to update, the `command` path
  changes; the registration to update is the user-scope one (`MIGRATION_TO_DEV.md` 5.0).
- Candidate upstream PR: mcp pin, encoding fix, both selector fixes.
- Post-drill DEV bookkeeping (frozen now): COMMANDS.txt, AGENTS.md, HOMEWORK.md entries.
