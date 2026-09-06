"""AGENTS.md -> one Digest page per round (Round 109, backlog B5).

    python -m knowledge.ingest.digests [--agents AGENTS.md] [--since N] [--at ISO]

WHY THIS EXISTS. AGENTS.md is 210 KB of 63 chronological "Round N complete" entries, and every
round re-greps the whole monolith to answer "what happened in Round 97?". Splitting it into one
addressable page per round turns a linear scan into a lookup, and gives every round a stem that
other pages can link to - which the log itself, being one file, never could.

AGENTS.MD REMAINS THE RECORD. These pages are COMPILED, not moved: nothing is deleted from the log,
and every digest cites the section it came from. If a digest and the log disagree, the log wins and
the digest is stale - which is why each one carries `dev.round` and the source anchor rather than
pretending to be the original.

THE ONE REAL HAZARD IS QUOTATION. The log's prose contains wikilink SYNTAX as subject matter -
`[[Whales/<addr>]]`, `[[page\\|alias]]`, `[[wikilinks]]` - written to describe the format, not to
link anywhere. Copied verbatim into a page these become dangling links (lint L8), and one of them
points at a git-ignored dashboard (lint L9). They are neutralised into code spans, which both checks
correctly skip: the digest is QUOTING a link, and a quoted link is not a link.

Read-only on AGENTS.md. Writes only through pages.write_page.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from ..registers import update_register
from . import add_common_args, at_from, guard, page_changed, rel_to

DEFAULT_AGENTS = Path("AGENTS.md")
REGISTER_STEM = "digests_register"
# THE LOG HAS THREE ENTRY FORMATS, and a regex for only the newest silently covers a third of it.
# Rounds 74+ carry a date:      "Round 104 complete (2026-09-06, corrected in 104b): TWO NEW..."
# Rounds 31-73 carry none:      "Round 73 complete: ITEM 18 MAIDEN RUN AUTOMATED..."
# and one uses a dash:          "Round 50 complete - MILESTONE. Titan correlator gains..."
# Caught by counting `^Round \d+ complete` (63) against what parsed (22) before shipping. An
# undated round records date=None rather than a guessed one.
ROUND_RE = re.compile(r"^Round (\d+) complete(?:\s*\(([^)]*)\))?\s*[:\-]\s*(.*)$", re.M)
WIKILINK_RE = re.compile(r"(?<!`)\[\[([^\]]*)\]\](?!`)")
# Ruling R109-1.C: 250, not 120. The longest entry today (Round 85) is 110 lines - ten from the old
# ceiling - so the next long round would have been clipped without a word. Truncation is now also
# ANNOUNCED on the page and warned about at compile time, because a digest that quietly drops the
# end of a round is worse than one that is obviously incomplete.
MAX_BODY_LINES = 250


def neutralise(text: str) -> str:
    """Wrap bare wikilinks in backticks so a QUOTED link is not a link.

    The log discusses link syntax as subject matter. Left bare, `[[Whales/<addr>]]` becomes a
    dangling link (L8) and `[[Cross_Market_Titans]]` points at a git-ignored file (L9) - the digest
    would trip the very rules the rounds it describes were spent building. A code span is the honest
    rendering: the digest is showing you what the log said, not making the link itself.
    """
    return WIKILINK_RE.sub(lambda m: f"`[[{m.group(1)}]]`", text)


def parse_rounds(text: str) -> list[dict[str, Any]]:
    """Every `Round N complete (date): summary` block, newest first as the log stores them."""
    out: list[dict[str, Any]] = []
    hits = list(ROUND_RE.finditer(text))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = (m.group(3) + "\n" + text[m.end():end]).strip()
        # a following "## ..." heading belongs to the document, not to this round's entry
        body = re.split(r"^## ", body, maxsplit=1, flags=re.M)[0].strip()
        out.append({"round": int(m.group(1)), "date": (m.group(2) or "").strip() or None, "summary": body})
    seen: set[int] = set()
    uniq = []
    for r in out:                      # the log can restate a round; the FIRST (newest) entry wins
        if r["round"] not in seen:
            seen.add(r["round"])
            uniq.append(r)
    return sorted(uniq, key=lambda r: r["round"])


def first_sentence(summary: str, limit: int = 240) -> str:
    flat = " ".join(summary.split())
    cut = flat.split(". ")[0].strip()
    if len(cut) > limit:
        cut = cut[:limit].rsplit(" ", 1)[0] + "…"
    return cut or "(no summary recorded)"


def build_digest(entry: dict[str, Any], vault: Path, dev_root: Path, agents: Path, at: datetime,
                 by: str = GENERATED_BY) -> Page:
    n = entry["round"]
    rel = rel_to(agents, dev_root)
    all_lines = neutralise(entry["summary"]).splitlines()
    lines = all_lines[:MAX_BODY_LINES]
    if len(all_lines) > MAX_BODY_LINES:
        # NOT a wikilink. The directive spelled this `[[AGENTS.md#round-N-complete]]`, but AGENTS.md
        # lives at the REPO ROOT and lint L8 resolves wikilinks against files in the VAULT - so every
        # truncated digest would have failed lint on the very line telling the reader where the rest
        # of the text is. A code span says the same thing and resolves for a human either way.
        lines += ["", "> [!NOTE]",
                  f"> Entry truncated at {MAX_BODY_LINES} of {len(all_lines)} lines. "
                  f"The full text is in `{rel}` under `Round {n} complete`."]
    body = [f"# Round {n} digest", "",
            f"> {entry['date'] or 'date not recorded in the log'} · compiled from `{rel}`. **The log is the record**; this page is an "
            "index into it, and loses to it wherever they disagree.", "",
            "## What the log says", "", *lines, "",
            "## Related", "", f"- [[{REGISTER_STEM}|Digests register]]", ""]
    meta = make_meta("Digest", f"Round {n} digest", f"Round {n}" + (f" ({entry['date']})" if entry['date'] else "") + f": {first_sentence(entry['summary'])}",
                     tags=["digest", "work-chain", f"round-{n}"], generated_by=by, at=at, status="draft",
                     sources=[{"id": "agents-log", "resource": f"{rel}#round-{n}-complete",
                               "title": f"{rel} - Round {n} complete", "author": "claude-code/fable-5.1"}],
                     dev={"round": n, "date": entry["date"], "kind": "round_digest",
                          "truncated": len(all_lines) > MAX_BODY_LINES,
                          # Ruling R109-1.E: pin the heading this page was compiled from. Renaming or
                          # deleting a round entry in the log now trips C1 on the digest that quotes
                          # it, instead of leaving 210 KB of prose pointing at a section that is gone.
                          "asserts": [{"file": rel, "pattern": rf"^Round {n} complete",
                                       "claim": "the round heading this digest was compiled from is still in the log"}]})
    path = page_path(vault, "Digest", f"round_{n}")
    carry_human_fields(load_page_safe(path), meta)
    return Page(path, meta, "\n".join(body))


def load_page_safe(path: Path):
    from ..pages import load_page
    return load_page(path) if path.is_file() else None


def ingest_digests(vault: Path, dev_root: Path, *, agents: Path | None = None, since: int | None = None,
                   at: datetime | None = None, by: str = GENERATED_BY) -> tuple[int, int]:
    at = at or now_utc()
    agents = agents or (dev_root / DEFAULT_AGENTS)
    if not agents.is_file():
        return 0, 0
    entries = parse_rounds(agents.read_text(encoding="utf-8", errors="replace"))
    if since is not None:
        entries = [e for e in entries if e["round"] >= since]
    if not entries:
        return 0, 0
    written = 0
    for e in entries:
        page = build_digest(e, vault, dev_root, agents, at, by)
        if page_changed(page, vault):
            written += 1
        write_page(page, vault, now=at)
    # ONE writer for this page. Ruling R109-1.F made Digest a registers.SPECS type so seed can
    # guarantee the register exists; keeping a bespoke builder here as well meant seed and this
    # adapter produced DIFFERENT content for the same file and silently overwrote each other on
    # every run. The generic register renders round and date from dev, which is what it is for.
    reg = update_register(vault, "Digest", at=at, by=by)
    reg_changed = page_changed(reg, vault)
    write_page(reg, vault, now=at)
    if written or reg_changed:
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"work-chain digests: {len(entries)} round(s) from "
                   f"`{rel_to(agents, dev_root)}`; {written} page(s) written -> [[{REGISTER_STEM}]].", when=at)
    return len(entries), written


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.digests", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--agents", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_AGENTS.as_posix()}")
    ap.add_argument("--since", type=int, default=None, help="only rounds >= N")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    total, written = ingest_digests(args.vault, args.dev_root, agents=args.agents, since=args.since,
                                    at=at_from(args))
    if not total:
        print("[REFUSE] no `Round N complete (date):` entries found in the log (exit 3)", file=out)
        return 3
    print(f"digests: {total} round(s), {written} page(s) written, {total - written} unchanged", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
