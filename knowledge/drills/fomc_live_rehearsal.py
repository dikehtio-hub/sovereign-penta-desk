"""Live dress rehearsal for the FOMC drill: real books for N seconds, then the whole post-print path, all into SCRATCH.

    python -m knowledge.drills.fomc_live_rehearsal [--seconds 60] [--interval 1] [--event fomc_2026-09-16]
                                                    [--scratch DIR] [--no-task] [--assume-defaults]

Round 116 (self-directed). The pre-flight (fomc_rehearsal) proves the pieces agree; this proves the
PATH runs end to end on this machine, today, with the real order books:

  1. the pre-flight must show 0 FAIL, or nothing is recorded
  2. latency_sniper.record_loop stamps the three registered tokens for --seconds into <scratch>/books
     (read-only public GETs, the same call the scheduled task will make at T-2)
  3. a SYNTHETIC event - kind fed_rate, change_bps 0, source "REHEARSAL ... NOT a statement" - is written
     to <scratch>/event.json, anchored at the middle of the recording, so the curve has both sides
  4. latency_sniper.survival_curve runs over the stamps exactly as the drill card's step 2 would
  5. knowledge.ingest.clob compiles the Reaction Profile pages, the Event page and the latency-decay
     concept into <scratch>/vault, a COPY of the real vault, which is then linted

Nothing real is written. The real vault and the real books directory are hashed before and after and a
difference is itself a FAIL; the repo-root event.json the drill card asks the operator to write is
checked to be as it was. The synthetic event carries confidence 0.995 because the curve and the pages
gate on it - which is exactly why it must never leave the scratch directory, and why its `source`
says what it is in words. The scratch root (cross_market/data/rehearsals/) is git-ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .. import DEV_ROOT, EXIT_FINDINGS, EXIT_OK, VAULT
from ..ingest import rel_to
from ..ingest.clob import ingest_survival
from ..lint import lint_vault
from ..query import books_dir, find_event, rules_for
from .fomc_rehearsal import BAT, Check, RECORDER, collect_task, hash_vault, run_checks

sys.path.insert(0, str(DEV_ROOT)) if str(DEV_ROOT) not in sys.path else None
from cross_market.latency_sniper import (Event, default_fetch, load_rules, load_stamp_series,  # noqa: E402
                                         record_loop, replay_economics, survival_curve)

SCRATCH_ROOT = Path("cross_market") / "data" / "rehearsals"        # git-ignored
MIN_STAMP_YIELD = 0.8            # stamps / (polls x tokens) below this is a recorder problem, not weather
MAX_GAP_FACTOR = 3.0             # a gap over 3 intervals between a token's stamps is a hole in the record
SYNTHETIC_SOURCE = "REHEARSAL {at} - synthetic event, NOT a Federal Reserve statement; scratch only"


def snapshot_dir(directory: Path) -> str:
    """Names and sizes of everything under a directory, hashed; 'absent' when it does not exist."""
    if not directory.exists():
        return "absent"
    h = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(directory).as_posix().encode())
            h.update(str(p.stat().st_size).encode())
    return h.hexdigest()


def synthetic_event(anchor: datetime) -> dict[str, Any]:
    return {"kind": "fed_rate", "payload": {"change_bps": 0},
            "source": SYNTHETIC_SOURCE.format(at=anchor.strftime("%Y-%m-%dT%H:%M:%SZ")),
            "confidence": 0.995, "observed_at": anchor.isoformat()}


def run_live(vault: Path, dev_root: Path, event_name: str, *, seconds: float, interval: float = 1.0,
             scratch: Path | None = None, fetch: Callable[[str], dict[str, Any]] = default_fetch,
             clock: Callable[[], float] | None = None, sleep: Callable[[float], None] | None = None,
             wall: Callable[[], datetime] | None = None, checks: list[Check] | None = None,
             query_task: bool = True, assume_defaults: bool = False,
             now: datetime | None = None, log: list[str] | None = None) -> tuple[list[Check], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    log = log if log is not None else []
    out: list[Check] = []
    ok = lambda name, cond, detail: out.append(Check(name, "PASS" if cond else "FAIL", detail))  # noqa: E731
    summary: dict[str, Any] = {"scratch": None, "stats": None}

    # what must be untouched at the end
    before_vault = hash_vault(vault)
    event = find_event(vault, event_name)
    if event is None:
        out.append(Check("event page", "FAIL", f"no Event page matches {event_name!r}"))
        return out, summary
    real_books = dev_root / books_dir(event)
    before_books = snapshot_dir(real_books)
    root_event = dev_root / "event.json"
    root_event_before = root_event.exists()
    halt = dev_root / "HALT.flag"
    if halt.exists():
        out.append(Check("HALT flag", "FAIL", f"{halt} present: the recorder would stop at once; the kill switch is honoured"))
        return out, summary
    out.append(Check("HALT flag absent", "PASS", str(halt)))

    # 1. the pre-flight, unless the caller already ran it
    if checks is None:
        bat_path = dev_root / BAT
        checks = run_checks(vault, dev_root, event_name, now,
                            task=collect_task() if query_task else None,
                            bat_text=bat_path.read_text(encoding="utf-8", errors="replace") if bat_path.is_file() else None,
                            bat_path=bat_path)
    fails = [c for c in checks if c.level == "FAIL"]
    if fails:
        out.append(Check("pre-flight", "FAIL", f"{len(fails)} FAIL in the pre-flight; nothing recorded: "
                         + "; ".join(f"{c.name}: {c.detail}" for c in fails)[:400]))
        return out, summary
    out.append(Check("pre-flight", "PASS", f"{len(checks)} check(s), 0 FAIL, {sum(c.level == 'WARN' for c in checks)} WARN"))

    # 2. the registration and its tokens
    rules_page = rules_for(vault, event)
    reg_rel = ((rules_page.meta.get("dev") or {}).get("registration")) if rules_page is not None else None
    rules_path = (dev_root / reg_rel) if reg_rel else None
    if rules_path is None or not rules_path.is_file():
        out.append(Check("rules registration", "FAIL", f"no rules file at dev.registration {reg_rel!r}"))
        return out, summary
    rules = load_rules(rules_path)
    tokens = [r.market for r in rules]
    ok("rules loaded", bool(tokens), f"{len(rules)} rule(s) from {reg_rel}")
    # latency_sniper's stamp filename is clob_<token>_<stamp>Z.json and its parser splits on the first "_"
    # after the token: a token with an underscore records fine and loads back as NOTHING.
    ok("tokens are stamp-safe", all(t.isdigit() for t in tokens),
       "all digits" if all(t.isdigit() for t in tokens) else f"non-numeric token(s): {[t for t in tokens if not t.isdigit()]}")
    if not all(t.isdigit() for t in tokens):
        return out, summary

    # scratch
    scratch = scratch or (dev_root / SCRATCH_ROOT / now.strftime("%Y%m%dT%H%M%SZ"))
    books = scratch / "books"
    svault = scratch / "vault"
    scratch.mkdir(parents=True, exist_ok=True)
    if svault.exists():
        shutil.rmtree(svault)
    shutil.copytree(vault, svault, ignore=shutil.ignore_patterns(".obsidian", ".trash", "*.base"))
    summary["scratch"] = str(scratch)
    ok("scratch vault is a copy", hash_vault(svault) == before_vault, f"{svault} - {len(list(svault.rglob('*.md')))} pages")

    # 3. record
    stats = record_loop(tokens, books, fetch, interval=interval, duration=seconds, clock=clock, sleep=sleep,
                        wall=wall, halt_path=halt, log=log.append)
    summary["stats"] = stats
    ok("recording ran to its duration", stats["stopped"] == "duration",
       f"{stats['polls']} poll(s), {stats['stamps']} stamp(s) in {stats['seconds']}s, stopped by {stats['stopped']}")
    expected = stats["polls"] * len(tokens)
    ok("stamp yield", expected > 0 and stats["stamps"] >= MIN_STAMP_YIELD * expected,
       f"{stats['stamps']}/{expected} = {(stats['stamps'] / expected * 100) if expected else 0:.0f}% (floor {MIN_STAMP_YIELD:.0%})")
    out.append(Check("fetch failures", "PASS" if stats["failures"] == 0 else "WARN", f"{stats['failures']} failed fetch(es)"))
    out.append(Check("rate limiting", "PASS" if stats["rate_limited"] == 0 else "WARN", f"{stats['rate_limited']} HTTP 429 poll(s)"))
    stamps = load_stamp_series(books, tokens=tokens)
    per_token = {t: [s.observed_at for s in stamps if s.token == t] for t in tokens}
    gaps = {t[:8] + "..": max((b - a).total_seconds() for a, b in zip(ts, ts[1:])) if len(ts) > 1 else 0.0 for t, ts in per_token.items()}
    ok("every token stamped", all(per_token[t] for t in tokens), {t[:8] + "..": len(v) for t, v in per_token.items()}.__repr__())
    ok("no hole in any token's record", all(g <= MAX_GAP_FACTOR * interval for g in gaps.values()),
       f"largest gap per token {gaps} against {MAX_GAP_FACTOR * interval:.0f}s")
    if not stamps:
        return out, summary

    # 4. the synthetic event, anchored mid-recording, written to scratch only
    first, last = stamps[0].observed_at, stamps[-1].observed_at
    anchor = first + (last - first) / 2
    ev_dict = synthetic_event(anchor)
    (scratch / "event.json").write_text(json.dumps(ev_dict, indent=2), encoding="utf-8")
    ev = Event.from_dict(ev_dict)
    ok("synthetic event says what it is", "NOT a Federal Reserve statement" in ev.source, ev.source)

    # 5. the survival curve, as the drill card's step 2 runs it
    breakeven, _cap, label = replay_economics(assume_defaults)
    result = survival_curve(stamps, rules, ev, breakeven, step_s=1.0, release_utc=anchor)
    curve_path = scratch / "curve.json"
    curve_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    markets = result.get("markets") or []
    ok("curve resolves every rule", len(markets) == len(rules) and all(m.get("outcome") for m in markets),
       f"{len(markets)} market(s) resolved from change_bps=0: " + ", ".join(f"{m['rule']}->{m['outcome']}" for m in markets))
    live = [m for m in markets if not m.get("deferred")]
    ok("post-anchor series on every live market", bool(live) and all(any(pt["delta_s"] > 0 for pt in m["series"]) for m in live),
       f"{len(live)} live, {len(markets) - len(live)} deferred (Ruling R4); series lengths {[len(m['series']) for m in markets]}")
    out.append(Check("economics", "PASS" if label.startswith("Tax Reserve") else "WARN", label))
    summary.update({"curve": str(curve_path), "economics": label, "markets": len(markets), "live_markets": len(live)})

    # 6. the pages, into the scratch vault, then lint it
    profiles, ev_page, concept = ingest_survival(result, svault, dev_root, event_id=event.path.stem,
                                                 source=rel_to(curve_path, dev_root), at=now)
    ok("reaction profiles compiled", len(profiles) == len(markets), f"{len(profiles)} profile(s), event page, concept -> {svault}")
    # Lint the whole scratch vault (link checks need the whole graph) but JUDGE only the pages this path
    # wrote. The copy sits three directories deeper than the real vault, so raw/index.md's vault-relative
    # entries (../../HyperLiquid/...) stop resolving there - ~1,500 L2 findings that say nothing about the
    # drill. The real vault lints CLEAN in place; that is checked separately every round.
    # L9 asks whether a link would break on a fresh clone; the scratch root is git-ignored by design, so in
    # the copy EVERY page is an "ignored target" and the rule says nothing about the drill either.
    findings = lint_vault(svault, dev_root, now=now)
    ours = {p.path.relative_to(svault).as_posix() for p in (*profiles, ev_page, concept)}
    errs = [f for f in findings if f.severity == "error" and f.path in ours and f.code != "L9"]
    warns = [f for f in findings if f.severity == "warning" and f.path in ours]
    other = sum(1 for f in findings if f.severity == "error" and (f.path not in ours or f.code == "L9"))
    ok("rehearsal pages lint without errors", not errs,
       f"{len(ours)} page(s) judged on every rule but L9: {len(errs)} error(s), {len(warns)} warning(s)"
       + ("; " + "; ".join(f"{f.code} {f.path}: {f.message[:80]}" for f in errs[:3]) if errs else "")
       + (f"; {other} relocation finding(s) not judged (raw/index.md paths are vault-relative; L9 sees the whole "
          "git-ignored copy as ignored)" if other else ""))
    if warns:
        out.append(Check("rehearsal page warnings", "WARN", "; ".join(f"{f.code} {f.path}" for f in warns[:4])))
    summary.update({"profiles": [p.path.name for p in profiles], "lint_errors": len(errs), "lint_warnings": len(warns),
                    "relocation_findings": other})

    # 7. nothing real moved
    ok("real vault untouched", hash_vault(vault) == before_vault, "sha256 identical before and after")
    ok("real books dir untouched", snapshot_dir(real_books) == before_books, f"{real_books} unchanged ({before_books[:12]})")
    ok("repo-root event.json untouched", root_event.exists() == root_event_before,
       f"{root_event} {'exists' if root_event_before else 'absent'} before and after")
    return out, summary


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.drills.fomc_live_rehearsal", description=__doc__.split("\n\n")[0])
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--event", default="fomc_2026-09-16")
    ap.add_argument("--scratch", type=Path, default=None, help=f"default <dev-root>/{SCRATCH_ROOT.as_posix()}/<utc stamp>")
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--no-task", action="store_true", help="pre-flight without the Task Scheduler query")
    ap.add_argument("--assume-defaults", action="store_true", help="fair breakeven instead of the Tax Reserve Agent hook")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    print(f"FOMC LIVE REHEARSAL - {a.event}    {now.strftime('%Y-%m-%dT%H:%M:%SZ')}    {a.seconds:.0f}s at {a.interval:g}s", file=out)
    print("=" * 72, file=out)
    print("Read-only GETs of the public CLOB books; every write goes under the scratch directory.", file=out)
    log: list[str] = []
    checks, summary = run_live(a.vault, a.dev_root, a.event, seconds=a.seconds, interval=a.interval, scratch=a.scratch,
                               query_task=not a.no_task, assume_defaults=a.assume_defaults, now=now, log=log)
    for line in log[-3:]:
        print("  " + line, file=out)
    for c in checks:
        print(f"[{c.level}] {c.name}: {c.detail}", file=out)
    fails = sum(c.level == "FAIL" for c in checks)
    warns = sum(c.level == "WARN" for c in checks)
    print("-" * 72, file=out)
    if summary.get("scratch"):
        print(f"scratch: {summary['scratch']}  (books/, vault/, event.json, curve.json - disposable)", file=out)
    print(f"{len(checks)} check(s): {fails} FAIL, {warns} WARN. The real vault, the real books directory and the "
          f"repo-root event.json were not touched.", file=out)
    return EXIT_OK if fails == 0 else EXIT_FINDINGS


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
