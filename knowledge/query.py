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
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, GENERATED_BY, VAULT, halted
from .frontmatter import parse_iso8601
from .pages import (Page, append_log, default_stale_after, in_window, iso, load_page, load_pages, make_meta,
                    now_utc, page_path, safe_title, write_index, write_page)

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


BOOKS_ROOT = "cross_market/data/clob_books"


def books_dir(event: Page) -> str:
    """Where the drill's recorder actually put the stamps.

    Ruling R108-1.D: the EVENT PAGE declares it (`dev.books_dir`) and this reads that first; the
    constructed path below is the fallback for events compiled before Round 109.

    Originally read off fomc_drill_2026-09-16.bat, which runs `--record-loop ... --books
    cross_market\\data\\clob_books\\fomc_2026-09-16`. Worth stating because the obvious guess is
    wrong twice over: latency_sniper's own default is the clob_books ROOT (no event subdirectory),
    and the Round 108 directive proposed `clob_drill/<event>`, which does not exist. Either would
    send the operator's survival curve at a directory with no stamps in it, one minute after the
    print, and report an empty result rather than an error.
    """
    declared = (event.meta.get("dev") or {}).get("books_dir")
    return str(declared) if declared else f"{BOOKS_ROOT}/{event.path.stem}"


def rule_lines(rules: Page) -> list[str]:
    """The registered rules, from `dev.rules` where it exists (Ruling R107-1.E).

    The markdown table truncates token ids to 12 characters so the page reads well; the card needs
    the WHOLE id, because the operator may have to paste it. Legacy pages compiled before Round 108
    have no `dev.rules`, so the table is still parsed as a fallback rather than showing nothing.
    """
    structured = (rules.meta.get("dev") or {}).get("rules")
    out: list[str] = []
    if isinstance(structured, list) and structured:
        for r in structured[:6]:
            if not isinstance(r, dict):
                continue
            out.append(f"  {str(r.get('label', '-'))[:38]:<38} {str(r.get('condition', '-')):<18} "
                       f"-> {r.get('outcome', '-')}")
            out.append(f"      token {r.get('market', '-')}")
        return out
    for ln in [l for l in rules.body.splitlines() if l.startswith("| ") and "`" in l][:6]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) >= 6:
            out.append(f"  {cells[0]:<34} {cells[1]:<18} tok {cells[5]}  (legacy page: id truncated)")
    return out


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
        out += rule_lines(rules)
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

    reg = (rules.meta.get("dev") or {}).get("registration") if rules is not None else None
    out += ["AFTER THE PRINT, IN ORDER  (from the repo root)", "-" * 64,
            "  1. write ./event.json  (the block above)",
            "  2. python -m cross_market.latency_sniper --survival-curve \\",
            f"       --event ./event.json --rules {reg or '<rules.json>'} \\",
            f"       --books {books_dir(event)} --json > curve.json",
            f"  3. python -m knowledge.ingest.clob --result curve.json --event {event.path.stem}",
            "", f"source: [[{event.path.stem}]] - the CARD is read-only; nothing above was written."]
    return out


def regime_card(vault: Path, name: str, now: datetime) -> list[str]:
    want = normalise(name)
    regimes = [p for p in load_pages(vault) if p.type == "Regime"]
    # Ruling R107-1.B: an exact stem or an unambiguous `<want>_` prefix answers with ONE card.
    # Substring matching is the fallback, not the rule - `--regime BTC` should not also hand back
    # the funding regime just because some other page's text happens to contain the letters.
    exact = [p for p in regimes if normalise(p.path.stem) == want or normalise(p.title) == want]
    prefix = [p for p in regimes if normalise(p.path.stem).startswith(want + "_")]
    hits = exact or prefix or [p for p in regimes
                               if want in normalise(p.path.stem) or want in normalise(p.title)]
    ambiguous = not exact and not prefix and len(hits) > 1
    if not hits:
        return [f"no Regime page matches {name!r}.",
                "known: " + ", ".join(sorted(p.path.stem for p in regimes)) or "(none compiled)"]
    out = [f"REGIME - {name.upper()}    as of {now.strftime('%Y-%m-%dT%H:%M:%SZ')}", "=" * 64]
    if ambiguous:
        out.append(f"** {name!r} matched {len(hits)} pages on substring; showing all. "
                   "Name a stem exactly for one. **")
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
    return out + ["the CARD is read-only; nothing above was written."]


USAGE_WINDOW_DAYS = 90     # OKF usage_window: the span the count is meaningful over


def record_usage(vault: Path, pages: list[Page], now: datetime) -> list[str]:
    """Increment `dev.usage.count` on the pages a query actually opened (backlog B16).

    OPT-IN, NOT AUTOMATIC, and that is a correctness requirement rather than a preference. Ruling
    R110-1.E's directive was to count on every query, but `write_page` REFUSES a page inside its own
    `dev.window` - so a drill card counting usage on the FOMC Event page would raise WriteRefused at
    T-2, in the one window the card exists for, and hand the operator a traceback instead of a
    briefing. Round 107 also guarantees, and tests, that every query mode writes nothing; that
    guarantee is what makes the card safe to run inside a frozen window at all.

    So counting happens only when the caller asks for it, and even then a windowed page is skipped
    rather than attempted: the counter is never worth breaking the thing it is counting.
    """
    touched: list[str] = []
    for page in pages:
        if in_window(page.meta, now):
            continue                     # a registration inside its window is frozen; never amend it
        fresh = load_page(page.path)
        if fresh is None:
            continue
        dev = fresh.meta.setdefault("dev", {})
        usage = dev.get("usage") if isinstance(dev.get("usage"), dict) else {}
        usage = {"count": int(usage.get("count", 0)) + 1, "last": iso(now),
                 "window_days": USAGE_WINDOW_DAYS}
        dev["usage"] = usage
        write_page(fresh, vault, now=now)
        touched.append(fresh.path.stem)
    return touched


def file_answer(vault: Path, question: str, opened: list[Page], now: datetime,
                by: str = GENERATED_BY) -> Page:
    """Scaffold a Concept page for a question the operator wants kept (backlog B16).

    A SCAFFOLD, not an answer. The constitution's Query section says to file the answer as a Concept
    page "when the operator says keep that" - so this writes the question, the pages that were open
    when it was asked, and an empty section for the human to write in. Inventing an answer here
    would be the one thing a knowledge layer must never do: manufacture a claim with no source.
    """
    # Ruling R111-1.D: two questions identical for their first 60 characters used to file onto ONE
    # page, and the second silently inherited the first's Answer section. A 4-hex-char digest of the
    # WHOLE question keeps the slug readable and makes it deterministic: the same question always
    # files to the same page (so re-filing keeps a written answer), a different one never does.
    digest = hashlib.sha256(question.strip().encode("utf-8")).hexdigest()[:4]
    prefix = re.sub(r"[^a-z0-9]+", "_", question.strip().lower()).strip("_")[:54] or "query"
    stem = f"{prefix}_{digest}"
    path = page_path(vault, "Concept", f"query_{stem}")
    existing = load_page(path)
    body = [f"# {safe_title(question)}", "",
            f"> Filed {iso(now)} from `knowledge.query`. The answer below is the OPERATOR's to write;",
            "> this page records the question and what was open when it was asked, nothing more.", "",
            "## Question", "", question.strip(), "",
            "## Answer", "",
            (existing.body.split("## Answer", 1)[1].split("##", 1)[0].strip()
             if existing and "## Answer" in existing.body else "_(not answered yet)_"), "",
            "## Open when asked", ""]
    body += [f"- [[{p.path.stem}|{safe_title(p.title)}]]" for p in opened] or ["- (nothing)"]
    body += ["", "## Related", "", "- [[WIKI_SCHEMA|Constitution]] s.Query", ""]
    meta = make_meta("Concept", safe_title(question)[:120], f"Filed query: {safe_title(question)[:150]}",
                     tags=["concept", "query", "filed"], generated_by=by, at=now, status="draft",
                     # L7: a Concept page carries a review clock. A filed question especially - it is
                     # a scaffold awaiting a human answer, and one nobody returns to in 90 days is
                     # precisely what the staleness policy exists to surface.
                     stale_after=default_stale_after("Concept", now),
                     sources=[{"id": f"page-{p.path.stem}", "resource": f"obsidian_vault/{p.rel(vault)}",
                               "title": safe_title(p.title), "author": by} for p in opened]
                     or [{"id": "query", "resource": "obsidian_vault/index.md", "title": "the vault index",
                          "author": by}],
                     dev={"kind": "filed_query", "question": question.strip(),
                          "opened": [p.path.stem for p in opened]})
    from .pages import carry_human_fields
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.query", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--drill-card", metavar="EVENT", default=None)
    ap.add_argument("--regime", metavar="NAME", default=None)
    ap.add_argument("--list", action="store_true", help="the events and regimes a card can be built for")
    ap.add_argument("--file", metavar="QUESTION", default=None,
                    help="file this question as a Concept page scaffold (the ANSWER stays the operator's)")
    ap.add_argument("--count-usage", action="store_true",
                    help="also record dev.usage on the pages this query opened. OFF by default: a query "
                         "that writes cannot be run inside a frozen registration window, which is exactly "
                         "when the drill card is needed")
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

    if args.list or not (args.drill_card or args.regime or args.file):
        pages = load_pages(args.vault)
        print("events:  " + ", ".join(sorted(p.path.stem for p in pages if p.type == "Event")), file=out)
        print("regimes: " + ", ".join(sorted(p.path.stem for p in pages if p.type == "Regime")), file=out)
        return EXIT_OK if args.list else EXIT_HALT

    opened: list[Page] = []
    if args.drill_card:
        event = find_event(args.vault, args.drill_card)
        if event is None:
            known = sorted(p.path.stem for p in load_pages(args.vault) if p.type == "Event")
            print(f"[REFUSE] no Event page matches {args.drill_card!r}. Known: {', '.join(known) or '(none)'}\n"
                  f"A blank card two minutes before a print is worse than no card (exit {EXIT_HALT})", file=out)
            return EXIT_HALT
        lines = drill_card(args.vault, event, now)
        opened = [p for p in (event, rules_for(args.vault, event)) if p is not None]
    elif args.regime:
        lines = regime_card(args.vault, args.regime, now)
        want = normalise(args.regime)
        opened = [p for p in load_pages(args.vault) if p.type == "Regime"
                  and (want in normalise(p.path.stem) or want in normalise(p.title))]
    else:
        lines = []

    for line in lines:
        print(line, file=out)

    if args.file:
        page = file_answer(args.vault, args.file, opened, now)
        write_page(page, args.vault, now=now)
        write_index(args.vault, load_pages(args.vault))
        append_log(args.vault, "Query", f"filed **{safe_title(args.file)[:120]}** -> "
                   f"[[{page.path.stem}]]; {len(opened)} page(s) open when asked.", when=now)
        print(f"[FILE] {page.path.relative_to(args.vault).as_posix()} - the Answer section is yours to write",
              file=out)
    if args.count_usage:
        touched = record_usage(args.vault, opened, now)
        skipped = len(opened) - len(touched)
        print(f"[USAGE] recorded on {len(touched)} page(s)"
              + (f"; {skipped} skipped (inside their own registration window)" if skipped else ""), file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
