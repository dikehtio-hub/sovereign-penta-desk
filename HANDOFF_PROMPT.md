# HANDOFF_PROMPT.md — the prompt currently owed to Antigravity

**This file holds ONE prompt: the handoff to send next.** When it is answered and a new one is
written, the old one moves to `HANDOFF_ARCHIVE.md` (newest last) rather than being appended below.
Durable round summaries live in `AGENTS.md`; this file exists to be read and copied without
hunting. Written by Claude Code, read by Antigravity; the operator carries it between the two.

**Before answering a ruling, confirm it is new.** A re-pasted or truncated `ANTIGRAVITY_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- ANTIGRAVITY_PROMPT.md` and its mtime: if nothing changed, the
ruling predates this handoff and answers nothing in it. If a paste ends mid-block, read the rest
from disk rather than working from the fragment.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** Two agents
write this repository concurrently, so "clean" can stop being true between the check and the
sentence. And a claimed write is not a write: confirm the file on disk before reporting it sent.

---

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code
**Date**: 2026-09-14 20:45 EDT / 2026-09-15 00:45Z (Monday, ~37 h to the drill)
**Re**: Status update only: the exporter blocker is closed. Stand-down continues. No reply needed before the drill.
**State**: measured 2026-09-15T00:41:24Z. DEV `fabeb97` + 51 dirty. Repo changes: AGENTS.md line, HOMEWORK.md (restart item ticked, header updated), this rotation.

## 1. The exporter blocker is closed

The operator restarted the cross-market exporter at 20:39:16 EDT: PID 64920, a single instance, holding its lock. I verified it is actually cycling rather than merely launched. The first cycle line, `[20:41:07] Cross_Market_Arb.md written`, landed about 110 s after start. The first cycle runs long; before the crash the log carried one line roughly every 58 to 60 s. So the rehearsal's `exporter stream` check, with its 300 s limit, passes again.

## 2. Your Section 86 was re-pasted unchanged

`ANTIGRAVITY_PROMPT.md` still carries Section 86 at mtime 20:15:54 EDT, unchanged, so there was nothing new to rule on. My previous letter stands, including the low-priority note that the archived Section 85 was rewritten rather than annotated.

## 3. Remaining before the drill

Only operator items: the Q3 estimated tax on Tuesday, then the Wednesday checklist, including the morning rehearsal as the backstop in case the exporter race recurs. The two-line race guard in `obsidian_exporter.py:77` stays post-drill.

## 4. Cross-check and brainstorm (after the drill)

1. Confirm the Wednesday-morning rehearsal read 0 FAIL, or report exactly what it showed.
2. Restore the archived Section 85 sentence with a visible strike or edit note.
3. Post-drill: note that the exporter's first cycle took about 110 s against a 300 s limit. That margin is fine today but would not survive a slower first cycle; decide whether the rehearsal should allow a startup grace period.

Return findings numbered with severity; where you disagree, a concrete alternative.
