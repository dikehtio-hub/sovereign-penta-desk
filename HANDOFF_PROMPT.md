# Round 123 Handoff: R123-1.A delivered (hash scoped, telemetry_health module, resume_all decoupled); two silent-death findings

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-07 13:10 EDT
**Subject**: All four R123-1.A directives implemented and verified. Two findings surfaced while building: tax and sports telemetry had died silently (recovered), and a case-sensitivity bug in the liveness matcher (caught and fixed). Run 2 unaffected, still on for ~22:22 EDT tonight. Section 0 is the standing checklist.

## 0. STANDING CHECKLIST (2026-09-07 13:10 EDT)

### Dated - the operator
- [ ] **Tonight through ~22:22 EDT** - laptop awake on AC; run 2 of 3 closes. **Tue 09-08** through ~22:22 for run 3.
- [ ] **Deploy window for the collector hardening** (`feat/collector-hardening`, `70bd232`): Tue 09-08 or Wed 09-09 evening.
- [ ] **Daily** - `python -m knowledge.drills.fomc_rehearsal --online` (33 checks, 1 inherent WARN); now race-free.
- [ ] **2026-09-13/14** live rehearsal; **09-15** Q3 tax; **09-16** drill sequence.
- [x] ~~Scheduler probe~~ PROBE OK. ~~W32Time~~ synced. ~~Desk 4 packages~~ already installed (venv), 180/0 skips.

### Antigravity - open
- [ ] **Cross-check Round 123** (section 3).
- [ ] **R123-1.B?** - direction on whether the telemetry-liveness check should be wired into a scheduled heartbeat (so a silent exporter death is caught without a human running `--check`). Today's build recovers on demand; it does not yet alert on its own.

### Resolved this round
- [x] `hash_vault` scoped to `wiki/` (both drills); the intermittent `card wrote nothing` FAIL is gone (verified across repeats).
- [x] `knowledge.drills.telemetry_health` (process liveness, not mtime; `--check`/`--json`/`--ensure`); kept OUT of the drill pre-flight.
- [x] `resume_all.bat` decoupled: per-component liveness, no watcher-proxy.
- [x] Found tax + sports exporters dead (silent); recovered. Found + fixed the matcher case bug.

### Standing rules / daemons
- Data pipeline: watcher 17688, cross-market exporter 62760, supervisor 24504, collector 60756 (none touched this round).
- Telemetry: 5 exporters live, one per desk (QuantLab = parent+worker). `telemetry_health` is the source of truth for their liveness.

## 1. What was delivered (R123-1.A)

1. **Pre-flight hash race (Directive 1).** `hash_vault()` in `fomc_rehearsal.py` (imported by `fomc_live_rehearsal.py`) now hashes only `vault/wiki`, with a whole-vault fallback when `wiki/` is absent. Your root cause is confirmed: the five exporters rewrite root dashboards every ~15 s, so a whole-vault hash caught an exporter tick between the before/after and failed `card wrote nothing` intermittently, and the 60 s live loop essentially always. The card and every drill artifact live under `wiki/`, which no exporter writes, so the guard stays meaningful. Now PASSES across repeats.
2. **`telemetry_health` module (Directives 2, 3).** Judges the five exporters by PROCESS liveness read from the OS table (psutil, else PowerShell CIM), never by file mtime, because `write_note_if_changed` leaves an idle desk's dashboard stale. `--check` (exit 1 if any down), `--json`, `--ensure` (launch the down ones detached via Start-Process, one each). It is NOT in `fomc_rehearsal --online`: a dead dashboard can never block the FOMC drill.
3. **`resume_all.bat` decoupled (Directive 4).** Collector, watcher and cross-market exporter each gated on their own `--status`; telemetry recovered via `telemetry_health --ensure`. The "watcher up == ecosystem up" proxy is gone. Verified: with everything up it keeps all and launches nothing.

**Telemetry**: 65 drill+telemetry tests pass (HashVaultScopingTests, TelemetryHealthTests added); lint 510 CLEAN; digest round_123 added; full knowledge suite green (count in the commit). Data pipeline untouched.

**Timing**: START 16:55Z; quoted 45 (35-60).

## 2. Findings while building (please note)

- **Tax and sports telemetry had died silently** sometime after this morning's restart, behind a live watcher and a healthy data pipeline. This is the exact failure class R123-1.A names, caught the first time `telemetry_health --check` ran. Both recovered.
- **A case bug in the matcher.** The real cmdlines are mixed-case (`Tax_Reserve_Agent.obsidian_sync`) while the signatures are lowercase; the normalizer did not lower-case, so the two capitalised desks read as always-down and `--ensure` spawned duplicates. Fixed (lower-case both sides); the test duplicates were cleaned to one per desk. A regression test pins this.
- **Detachment.** `subprocess` with `DETACHED_PROCESS` is reaped inside a parent job (an automation harness); `Start-Process` (ShellExecute) breaks away and survives, so the launcher uses that.

## 3. Independent cross-check requested

1. `python -m knowledge.drills.fomc_rehearsal --online` twice -> `[PASS] card wrote nothing` both times; 33 checks, 0 FAIL. (The old `[FAIL]` you saw at 12:48 will not recur.)
2. `python -m knowledge.drills.telemetry_health` -> 5/5 up, exit 0; `--ensure --dry-run` -> all KEPT; `--json` -> five rows with `up:true`.
3. In a scratch: kill one exporter, `--check` shows it DOWN (exit 1), `--ensure` relaunches exactly it, re-check 5/5.
4. `resume_all.bat` with everything up -> every line "kept"/"RUNNING", nothing double-launched.
5. Knowledge suite -> the round's count; lint -> 510 CLEAN; `grep -n "vault / \"wiki\"" knowledge/drills/fomc_rehearsal.py` shows the scoping.

## 4. Round 124 candidates
- Run 2 tonight (R122-1.B), then run 3 tomorrow.
- Deploy the hardening in the operator's window.
- R123-1.B: a scheduled telemetry heartbeat that alerts (not just recovers on demand), if you want silent deaths caught automatically.
