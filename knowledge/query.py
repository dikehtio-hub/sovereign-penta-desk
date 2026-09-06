"""Pre-baked queries over the compiled vault (Round 107; WIKI_SCHEMA.md s.Query).

    python -m knowledge.query --drill-card fomc-2026-09-16
    python -m knowledge.query --regime BTC
    python -m knowledge.query --list

THE DRILL CARD IS READ AT T-2 WITH A CLOCK RUNNING. That single fact decides everything about it:

  * IT NEVER WRITES. Not a log bullet, not a usage counter, not an index rebuild. Inside its own
    window the Event page and the rules registration are FROZEN (pages.in_window refuses the write
    anyway), and a query that mutates the thing it is describing is a query nobody should run at
    T-2. Read-only is a property of this module, not a mode.
  * IT FITS ON A SCREEN. Hard budget of MAX_LINES; a test asserts it. A card that scrolls is a card
    whose last line does not get read, and the last line is usually the one that says what NOT to do.
  * IT COMPUTES THE CLOCK AT RUN TIME rather than restating the release instant. "T-2 minutes" is
    what the operator needs; "18:00:00Z" is what they have to subtract from under pressure.
  * IT ASSEMBLES FROM PAGES, NOT FROM RAW. The Event page, the rules registration and the journal's
    calibration ledger are already compiled and linted; going back to the JSON would reintroduce
    exactly the copied-state risk the wiki exists to remove.

WHAT IT REFUSES. A missing Event page is an error with the list of known events, never an empty
card - an operator holding a blank sheet two minutes before a print has been actively misled.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, VAULT, halted
from .frontmatter import parse_iso8601
from .pages import Page, load_pages, now_utc, page_path

MAX_LINES = 60          # WIKI_SCHEMA.md s.Query: "one page under 60 lines at T-2"


def normalise(name: str) -> str:
    """`fomc-2026-09-16`, `fomc_2026-09-16` and `FOMC 2026-09-16` all name the same page."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def find_event(vault: Path, name: str) -> Page | None:
    want = normalise(name)
    events = [p for p in load_pages(vault) if p.type == "Event"]
    for p in events:
        if normalise(p.path.stem) == want:
            return p
    return next((p for p in events if want and want in normalise(p.path.stem)), None)


def rules_for(vault: Path, event: Page) -> Page | None:
    """The pre-registration bound to this event, by dev.event or by stem."""
    stem = event.path.stem
    for p in load_pages(vault):
        if p.type != "Experiment":
            continue
        dev = p.meta.get("dev") or {}
        if str(dev.get("event") or "") == stem or normalise(stem) in normalise(p.path.stem):
            return p
    return None


def predictions_for(vault: Path, event: Page) -> list[dict[str, Any]]:
    """Standing forecasts on this event, from the journal pages' calibration rows.

    Included because a forecast recorded before the print SCORES ITSELF against the payload the
    operator is about to write. Reading it at T-2 is the last moment it can be checked against what
    the operator actually believes - and a forecast nobody re-read is not a forecast, it is a bet.
    """
    stem, out = event.path.stem, []
    for p in load_pages(vault):
        if p.type != "Journal Entry":
            continue
        for row in (p.meta.get("dev") or {}).get("predictions") or []:
            if isinstance(row, dict) and normalise(str(row.get("event") or "")) == normalise(stem):
                out.append(dict(row, journal=p.path.stem))
    return out


def countdown(release: datetime | None, now: datetime) -> str:
    if release is None:
        return "release instant not recorded on the page"
    delta = (release - now).total_seconds()
    mins = int(abs(delta) // 60)
    d, rem = divmod(mins, 1440)
    h, m = divmod(rem, 60)
    # Days only past 48h: at T-2 the operator needs minutes, and "T-251h 29m" is a number nobody
    # converts under pressure. The unit the card shows is the unit the decision is made in.
    span = f"{d}d {h}h" if d >= 2 else (f"{h}h {m:02d}m" if h else f"{m}m")
    return f"T-{span}" if delta > 0 else f"T+{span} (the print has happened)"


def _win(dev: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    w = dev.get("window") if isinstance(dev.get("window"), dict) else {}
    def at(k):
        try:
            return parse_iso8601(w[k]) if w.get(k) else None
        except (ValueError, TypeError):
            return None
    return at("start"), at("end")


def drill_card(vault: Path, event: Page, now: datetime) -> list[str]:
    dev = event.meta.get("dev") or {}
    try:
        release = parse_iso8601(dev["release_utc"]) if dev.get("release_utc") else None
    except (ValueError, TypeError):
        release = None
    start, end = _win(dev)
    frozen = bool(start and end and start <= now <= end)
    rules = rules_for(vault, event)
    preds = predictions_for(vault, event)

    out = [f"DRILL CARD - {event.path.stem}    {countdown(release, now)}",
           "=" * 64,
           f"release  {dev.get('release_utc', '-')}     now  {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
           f"window   {(start and start.strftime('%H:%M:%SZ')) or '-'} .. {(end and end.strftime('%H:%M:%SZ')) or '-'}"
           + ("   ** INSIDE THE WINDOW: pages are FROZEN, do not edit **" if frozen else ""),
           ""]

    out += ["THE ONE THING ONLY YOU CAN DO", "-" * 64,
            "Read the actual decision off the statement and write event.json:",
            f'  {{"kind": "{dev.get("kind", "fed_rate")}", "payload": {{"change_bps": <int>}},',
            '   "source": "federalreserve.gov statement", "confidence": 0.995,',
            '   "observed_at": "<ISO>"}',
            "Confidence >= 0.99 ONLY from the statement itself. Nothing automated may",
            "decide what was said. 0 means hold.", ""]

    if rules is not None:
        out += [f"REGISTERED RULES  [[{rules.path.stem}]]", "-" * 64]
        rows = [ln for ln in rules.body.splitlines() if ln.startswith("| ") and "`" in ln]
        for ln in rows[:6]:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) >= 6:
                out.append(f"  {cells[0]:<34} {cells[1]:<18} tok {cells[5]}")
        out += ["  neg_risk: Ruling R4 - only the winning YES is lifted, NO sides deferred.", ""]
    else:
        out += ["REGISTERED RULES", "-" * 64, "  ** NO RULES REGISTRATION FOUND FOR THIS EVENT **", ""]

    if preds:
        out += ["YOUR STANDING FORECAST (scores itself against the payload)", "-" * 64]
        for p in preds[:3]:
            claim = p.get("claim") or " ".join(str(p.get(k, "")) for k in ("field", "op", "value")).strip()
            scored = "" if p.get("outcome") is None else f"  outcome {p['outcome']} brier {p.get('brier')}"
            out.append(f"  p={p.get('p', '-')}  {claim or '-'}{scored}   [[{p.get('journal')}]]")
        out.append("")

    out += ["AFTER THE PRINT, IN ORDER", "-" * 64,
            "  1. write event.json (above)",
            "  2. python -m cross_market.latency_sniper --survival-curve ... --json > curve.json",
            f"  3. python -m knowledge.ingest.clob --result curve.json --event {event.path.stem}",
            "", f"source: [[{event.path.stem}]] - this card is read-only and wrote nothing."]
    return out


def regime_card(vault: Path, name: str, now: datetime) -> list[str]:
    want = normalise(name)
    regimes = [p for p in load_pages(vault) if p.type == "Regime"]
    hits = [p for p in regimes if want in normalise(p.path.stem) or want in normalise(p.title)]
    if not hits:
        return [f"no Regime page matches {name!r}.",
                "known: " + ", ".join(sorted(p.path.stem for p in regimes)) or "(none compiled)"]
    out = [f"REGIME - {name.upper()}    as of {now.strftime('%Y-%m-%dT%H:%M:%SZ')}", "=" * 64]
    for p in hits:
        dev = p.meta.get("dev") or {}
        out += [f"[[{p.path.stem}]]  {p.title}", "-" * 64]
        current = dev.get("current")
        if isinstance(current, dict) and current:
            for key, st in sorted(current.items()):
                out.append(f"  {key:<22} {st.get('latest_verdict', '-'):<18} "
                           f"consensus(3) {st.get('regime_consensus_3', '-')}  runs {st.get('runs', '-')}")
        hist = dev.get("history") or []
        if hist:
            last = hist[-1]
            out.append("  latest row: " + ", ".join(f"{k}={last[k]}" for k in list(last)[:6] if k in last))
        out.append(f"  {len(hist)} history row(s); the page carries the full series.")
        out.append("")
    return out + ["read-only; nothing was written."]


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.query", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--drill-card", metavar="EVENT", default=None)
    ap.add_argument("--regime", metavar="NAME", default=None)
    ap.add_argument("--list", action="store_true", help="the events and regimes a card can be built for")
    ap.add_argument("--now", default=None, help="ISO 8601 instant to compute the countdown from (tests)")
    args = ap.parse_args(argv)

    if halted(args.dev_root):
        # A query writes nothing, but HALT means "the operator has stopped the system"; answering
        # normally would imply the pipeline behind this card is still running. It is not.
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - refusing (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    now = parse_iso8601(args.now) if args.now else now_utc()

    if args.list or not (args.drill_card or args.regime):
        pages = load_pages(args.vault)
        print("events:  " + ", ".join(sorted(p.path.stem for p in pages if p.type == "Event")), file=out)
        print("regimes: " + ", ".join(sorted(p.path.stem for p in pages if p.type == "Regime")), file=out)
        return EXIT_OK if args.list else EXIT_HALT

    if args.drill_card:
        event = find_event(args.vault, args.drill_card)
        if event is None:
            known = sorted(p.path.stem for p in load_pages(args.vault) if p.type == "Event")
            print(f"[REFUSE] no Event page matches {args.drill_card!r}. Known: {', '.join(known) or '(none)'}\n"
                  f"A blank card two minutes before a print is worse than no card (exit {EXIT_HALT})", file=out)
            return EXIT_HALT
        lines = drill_card(args.vault, event, now)
    else:
        lines = regime_card(args.vault, args.regime, now)

    for line in lines:
        print(line, file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
