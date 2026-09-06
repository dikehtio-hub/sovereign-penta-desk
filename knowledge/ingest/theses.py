"""Docstring theses -> Concept pages (Round 101, B12).

    python -m knowledge.ingest.theses [--root DIR ...] [--force] [--at ISO]

The desk modules carry their reasoning as titled ALL-CAPS sections in the module
docstring: "WHY THIS MODULE EXISTS, AND WHAT IT MOSTLY SAYS", "THE THESIS.",
"WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS", "THE FAILURE MODE THIS MODULE EXISTS
TO PREVENT". A refactor deletes them silently. This adapter compiles every module
that has at least one such section into wiki/concepts/thesis_<module>.md, and pins
each heading with a `dev.asserts` entry, so a heading that disappears from the
docstring is a lint C1 finding. The module itself is `dev.requires_files`.

Read-only on the code (ast parses the source; nothing is imported). The Theses
register (wiki/concepts/theses_register.md) is rebuilt after every run.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, default_stale_after, load_page, load_pages, make_meta, now_utc,
                     page_path, write_index, write_page)
from ..registers import update_register
from . import add_common_args, at_from, guard, rel_to

DEFAULT_ROOTS = ("cross_market", "cross_market/ingestors", "cross_market/interfaces",
                 "HyperLiquid/HL_Monarch/execution", "HyperLiquid/HL_Monarch/strategies", "HyperLiquid/HL_Monarch/analytics",
                 "HyperLiquid/HL_Monarch/collectors", "Sports_Desk/engine", "Sports_Desk/ingestors", "Sports_Desk/interfaces",
                 "Tax_Reserve_Agent/engine", "Tax_Reserve_Agent/interfaces", "Tax_Reserve_Agent/ingestors",
                 "Polymarket/Polymarket_Monarch")
REGISTER_FILE = "theses_register"
MIN_SECTION_CHARS = 40

# a line that IS a heading ("THE THESIS." / "WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS"), or starts with one
# followed by prose on the same line ("WHAT THIS CLOSES. `Cross_Market_Arb.md` reported ...").
HEADING_LINE_RE = re.compile(r"^(?P<h>[A-Z][A-Z0-9 ,'\-/()&:]{5,90}?)[.:]?\s*$")
HEADING_INLINE_RE = re.compile(r"^(?P<h>[A-Z][A-Z0-9 ,'\-/()&]{5,90}?)\.\s+(?P<rest>\S.*)$")

DESK_BY_PREFIX = (("HyperLiquid/", 1), ("Sports_Desk/", 2), ("cross_market/", 3), ("Polymarket/", 3),
                  ("quant_trading_lab/", 4), ("Tax_Reserve_Agent/", 5))
DESK_LINKS = {1: "[[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]", 2: "[[Desk_02_Sports_Desk|Desk 2: Sports Desk]]",
              3: "[[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]", 4: "[[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]",
              5: "[[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]"}


@dataclass
class Section:
    heading: str
    text: str


def _is_heading(candidate: str) -> bool:
    words = [w for w in re.split(r"[\s,]+", candidate) if re.search(r"[A-Z]", w)]
    return len(words) >= 2 and candidate == candidate.upper() and not candidate.startswith(("HTTP", "TODO", "NOTE"))


def extract_sections(docstring: str) -> list[Section]:
    sections: list[Section] = []
    cur: Section | None = None
    for raw in docstring.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        m = HEADING_LINE_RE.match(line)
        if m and _is_heading(m.group("h")):
            cur = Section(m.group("h").strip(), "")
            sections.append(cur)
            continue
        m = HEADING_INLINE_RE.match(line)
        if m and _is_heading(m.group("h")):
            cur = Section(m.group("h").strip(), m.group("rest").strip())
            sections.append(cur)
            continue
        if cur is not None:
            cur.text = (cur.text + " " + line).strip() if line else (cur.text + "\n\n" if cur.text and not cur.text.endswith("\n\n") else cur.text)
    out = []
    for s in sections:
        s.text = re.sub(r"[ \t]+", " ", s.text).strip()
        if len(s.text) >= MIN_SECTION_CHARS:
            out.append(s)
    return out


def module_docstring(path: Path) -> str | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None
    return ast.get_docstring(tree)


def desk_for(rel: str) -> int | None:
    for prefix, desk in DESK_BY_PREFIX:
        if rel.startswith(prefix):
            return desk
    return None


def stem_for(rel: str) -> str:
    return "thesis_" + re.sub(r"[^A-Za-z0-9]+", "_", rel[:-3] if rel.endswith(".py") else rel).strip("_")


def compile_thesis(path: Path, vault: Path, dev_root: Path, at: datetime, by: str = GENERATED_BY) -> Page | None:
    doc = module_docstring(path)
    if not doc:
        return None
    sections = extract_sections(doc)
    if not sections:
        return None
    rel = rel_to(path, dev_root)
    desk = desk_for(rel)
    body = [f"# Thesis: {rel}", "", f"> {len(sections)} titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).", ""]
    for s in sections:
        body += [f"## {s.heading.title()}", "", s.text, ""]
    body += ["## Related", ""]
    if desk:
        body.append(f"- {DESK_LINKS[desk]}")
    body += [f"- [[{REGISTER_FILE}|Theses register]]", ""]
    dev: dict[str, Any] = {
        "kind": "thesis", "module": rel, "headings": [s.heading for s in sections],
        "asserts": [{"file": rel, "pattern": re.escape(s.heading), "claim": f"the docstring still carries the section '{s.heading}'"} for s in sections],
        "requires_files": [rel],
    }
    if desk:
        dev["desk"] = desk
    first = sections[0].text
    meta = make_meta("Concept", f"Thesis: {rel}", (first[:280] + "…") if len(first) > 280 else first,
                     tags=["concept", "thesis"] + ([f"desk-{desk}"] if desk else []), generated_by=by, at=at, status="draft",
                     stale_after=default_stale_after("Concept", at),
                     sources=[{"id": "module", "resource": rel, "title": f"{rel} module docstring", "author": "human:operator"}],
                     dev=dev)
    p = page_path(vault, "Concept", stem_for(rel))
    carry_human_fields(load_page(p), meta)
    return Page(p, meta, "\n".join(body))


@dataclass
class ThesesReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    scanned: int = 0


def ingest_theses(roots, vault: Path, dev_root: Path, *, at: datetime | None = None, by: str = GENERATED_BY,
                  force: bool = False) -> ThesesReport:
    at = at or now_utc()
    report = ThesesReport()
    for root in roots:
        folder = dev_root / root
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("__") or path.name.startswith("test_"):
                continue
            report.scanned += 1
            page = compile_thesis(path, vault, dev_root, at, by)
            if page is None:
                continue
            rel = page.path.relative_to(vault).as_posix()
            if page.path.exists() and not force:
                report.skipped.append(rel)
                continue
            write_page(page, vault, now=at)
            report.written.append(rel)
    if report.written:
        write_page(update_register(vault, "Thesis", at=at, by=by), vault, now=at)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"docstring theses: {report.scanned} module(s) scanned, {len(report.written)} Concept page(s) written, "
                   f"{len(report.skipped)} kept; every heading pinned with dev:asserts; [index](index.md) rebuilt.", when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.theses", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--root", action="append", default=None, help="module folder relative to --dev-root (repeatable)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    report = ingest_theses(args.root or DEFAULT_ROOTS, args.vault, args.dev_root, at=at_from(args), force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    print(f"theses: {report.scanned} module(s) scanned; {len(report.written)} written, {len(report.skipped)} kept", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
