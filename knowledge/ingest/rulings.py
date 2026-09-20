"""Directives, Ratifications and numbered Rulings -> Ruling pages (Round 98, B4).

    python -m knowledge.ingest.rulings [--agents AGENTS.md] [--archive AGENTS_ARCHIVE.md] [--force] [--at ISO]

The handoff log cites `Directive N-N`, `Ratification N-N` and `Ruling N-N` by
number across rounds and never defines them anywhere else. This adapter finds
every distinct citation, keeps the sentence window around each occurrence with
the section it sits in, and writes one page per id:

  wiki/rulings/Directive_75-1.md · Ratification_77-3.md · Ruling_39-1.md

Pages are `status: draft` (extracted, not ratified); Antigravity's batch
ratification appends `verified` (R95-D). `dev.round` is the leading number,
`dev.citations` holds every occurrence, and a `dev.asserts` entry keeps the
citation string pinned to AGENTS.md so a rewritten log is a lint C1 finding.
The R-series (Ruling R1..R6) is seeded elsewhere and is skipped here. The
Rulings register is rebuilt after every run.

THE LOG IS A PAIR (2026-09-20). AGENTS.md was rotated and every citation this
adapter had found moved verbatim into AGENTS_ARCHIVE.md beside it, so all 29
pinned asserts became C1 errors in one step. The adapter now reads the live log
and then its archive; every occurrence records the file it was found in, and the
page's source and assert name the file of the FIRST occurrence (live before
archive, which is the newest-first order the single file had). After a future
rotation C1 fires again by design; `--force` re-points the pages.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, default_stale_after, load_page, load_pages, make_meta, now_utc,
                     page_path, write_index, write_page)
from ..registers import write_register
from . import add_common_args, at_from, guard, page_changed, rel_to

CITATION_RE = re.compile(r"\b(Directive|Ratification|Ruling)\s+(\d{1,3})-(\d{1,2})\b")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
REGISTER_FILE = "rulings_register"
ARCHIVE_NAME = "AGENTS_ARCHIVE.md"      # sits beside the live log, wherever that is


@dataclass
class Occurrence:
    section: str
    line: int
    excerpt: str
    file: str | None = None     # dev-root-relative log the occurrence was found in; None = the primary log


@dataclass
class Citation:
    kind: str
    major: int
    minor: int
    occurrences: list[Occurrence] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.kind} {self.major}-{self.minor}"

    @property
    def short(self) -> str:
        return f"{self.kind[0]}{self.major}-{self.minor}"

    @property
    def stem(self) -> str:
        return f"{self.kind}_{self.major}-{self.minor}"


def _paragraphs(text: str):
    """Yield (section heading, first line number, flattened paragraph text)."""
    section = "(top)"
    buf: list[str] = []
    start = 0
    for n, raw in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        h = HEADING_RE.match(raw)
        if h:
            if buf:
                yield section, start, " ".join(s.strip() for s in buf)
                buf = []
            section = h.group(2).strip()
            continue
        if not raw.strip():
            if buf:
                yield section, start, " ".join(s.strip() for s in buf)
                buf = []
            continue
        if not buf:
            start = n
        buf.append(raw)
    if buf:
        yield section, start, " ".join(s.strip() for s in buf)


def _window(flat: str, start: int, end: int, before: int = 220, after: int = 320) -> str:
    lo = max(0, start - before)
    cut = flat.rfind(". ", lo, start)
    lo = cut + 2 if cut != -1 else lo
    hi = min(len(flat), end + after)
    cut = flat.find(". ", end, hi)
    hi = cut + 1 if cut != -1 else hi
    excerpt = flat[lo:hi].strip()
    return ("…" if lo > 0 else "") + excerpt + ("" if hi >= len(flat) else "…")


def extract_citations(text: str, file: str | None = None,
                      into: dict[str, Citation] | None = None) -> dict[str, Citation]:
    """Every citation in one log. Pass `into` to accumulate across the live log and its archive."""
    found: dict[str, Citation] = {} if into is None else into
    for section, line, flat in _paragraphs(text):
        for m in CITATION_RE.finditer(flat):
            kind, major, minor = m.group(1), int(m.group(2)), int(m.group(3))
            key = f"{kind} {major}-{minor}"
            cit = found.setdefault(key, Citation(kind, major, minor))
            cit.occurrences.append(Occurrence(section, line, _window(flat, m.start(), m.end()), file))
    return found


def log_files(agents: Path, archive: Path | None = None) -> list[Path]:
    """The live log, then its archive - only the files that exist, live first."""
    archive = archive if archive is not None else agents.parent / ARCHIVE_NAME
    out = [p for p in (agents, archive) if p.is_file()]
    return out if len({p.resolve() for p in out}) == len(out) else out[:1]


_TITLE_STRIP = " .:;,-–—*)('\"…`"


def _first_clause(cit: Citation, limit: int = 110) -> str:
    """The sentence the citation sits in, minus the citation itself and any parenthesis around it.

    Round 99 (Ruling 98-1): the earlier "text after the citation" rule produced titles like
    `Ratification 74-2: ).…` when the citation closed a parenthetical. A whole sentence,
    cleaned, never does.
    """
    occ = cit.occurrences[0].excerpt.strip("…").strip()
    idx = occ.find(cit.id)
    if idx == -1:
        return ""
    start = occ.rfind(". ", 0, idx)
    start = start + 2 if start != -1 else 0
    end = occ.find(". ", idx)
    end = end + 1 if end != -1 else len(occ)
    sentence = occ[start:end]
    sentence = re.sub(r"\(\s*" + re.escape(cit.id) + r"[^)]*\)", " ", sentence)   # (Ruling 74-2) or (Ruling 74-2, ...)
    sentence = sentence.replace(cit.id, " ")
    sentence = re.sub(r"(^|\s)'s(\s|$)", " ", sentence)                             # the possessive left behind: "Directive 79-2's steps"
    sentence = re.sub(r"\*\*|`", "", sentence)
    sentence = re.sub(r"^\s*(?:-|\d+\.)\s+", "", sentence)                         # a leading bullet or number
    sentence = re.sub(r"[\[\]|]", " ", sentence)                                    # brackets and pipes break index lines and table links
    sentence = re.sub(r"\s+", " ", sentence).strip(_TITLE_STRIP)
    if len(sentence) < 8:
        return ""
    return (sentence[: limit - 1].rstrip(_TITLE_STRIP) + "…") if len(sentence) > limit else sentence


def compile_ruling(cit: Citation, agents_rel: str, vault: Path, at, by: str = GENERATED_BY,
                   ratified_pages: list[str] | None = None) -> Page:
    clause = _first_clause(cit)
    title = f"{cit.id}" + (f": {clause}" if clause else "")
    ratified_pages = ratified_pages or []
    body = [f"# {cit.id}", "",
            "> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).", "",
            "## Citations", ""]
    # the file of the FIRST occurrence is the one the page cites and pins; an occurrence in the
    # primary log keeps the short `(line N)` form, one found in the archive names its file
    pinned = cit.occurrences[0].file or agents_rel
    for o in cit.occurrences:
        where = o.file or agents_rel
        body += [f"- **{o.section}** ({'' if where == agents_rel else f'`{where}` '}line {o.line}): {o.excerpt}"]
    if ratified_pages:  # Ruling 100-f: a ruling that ratified pages says so, and lists them
        body += ["", f"## Effect in this wiki", "",
                 f"This ruling ratified {len(ratified_pages)} page(s) (`dev.ratified_by: {cit.major}-{cit.minor}`), each carrying "
                 f"`verified: antigravity/architect` and `status: stable`:", ""]
        body += [f"- [[{stem}]]" for stem in ratified_pages]
    body += ["", "## Related", "", f"- [[{REGISTER_FILE}|Rulings register]]", ""]
    dev: dict[str, Any] = {
        "round": cit.major, "ruling_id": cit.short, "kind": cit.kind.lower(),
        "citations": [{"file": o.file or agents_rel, "section": o.section, "line": o.line, "excerpt": o.excerpt}
                      for o in cit.occurrences],
        # \s+ not a literal space: three of the real citations wrap across a line break in AGENTS.md
        "asserts": [{"file": pinned, "pattern": rf"{cit.kind}\s+{cit.major}-{cit.minor}\b",
                     "claim": "the citation still exists in the handoff log"}],
    }
    description = (f"Ratification of {len(ratified_pages)} wiki page(s): " if ratified_pages else "") + cit.occurrences[0].excerpt.lstrip("…")
    meta = make_meta("Ruling", title, description[:300],
                     tags=["ruling", cit.kind.lower(), f"round-{cit.major}", "extracted"],
                     generated_by=by, at=at, status="draft", stale_after=default_stale_after("Ruling", at),
                     sources=[{"id": "agents-md", "resource": pinned,
                               "title": f"{Path(pinned).name} · {cit.occurrences[0].section}", "author": "human:operator"}],
                     dev=dev)
    path = page_path(vault, "Ruling", cit.stem)
    carry_human_fields(load_page(path), meta)  # a --force re-extraction never drops a ratification
    return Page(path, meta, "\n".join(body))


@dataclass
class RulingsReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    found: int = 0
    changed: int = 0


def ingest_rulings(agents_path: Path, vault: Path, dev_root: Path, *, archive: Path | None = None, at=None,
                   by: str = GENERATED_BY, force: bool = False) -> RulingsReport:
    at = at or now_utc()
    rel = rel_to(agents_path, dev_root)
    logs = log_files(agents_path, archive)
    cits: dict[str, Citation] = {}
    for log in logs:                     # live first: occurrences stay in the newest-first order of the old single file
        extract_citations(log.read_text(encoding="utf-8"), rel_to(log, dev_root), into=cits)
    report = RulingsReport(found=len(cits))
    ratified_by: dict[str, list[str]] = {}
    for p in load_pages(vault):
        rb = (p.meta.get("dev") or {}).get("ratified_by")
        if isinstance(rb, str):
            ratified_by.setdefault(rb, []).append(p.path.stem)
    for key in sorted(cits, key=lambda k: (cits[k].major, cits[k].minor, cits[k].kind)):
        cit = cits[key]
        page = compile_ruling(cit, rel, vault, at, by, ratified_pages=sorted(ratified_by.get(f"{cit.major}-{cit.minor}", [])))
        prel = page.path.relative_to(vault).as_posix()
        if page.path.exists() and not force:
            report.skipped.append(prel)
            continue
        report.changed += page_changed(page, vault)      # BEFORE the write, which is what makes it true
        write_page(page, vault, now=at)
        report.written.append(prel)
    # `written` is what --force re-extracted; `changed` is what actually moved. Register, index and
    # log follow `changed`: a forced pass over an unchanged log pair is now the routine cure after a
    # rotation, and it must not announce a compilation that produced nothing (Ruling R104-3).
    if report.changed:
        write_register(vault, "Ruling", at=at, by=by)
        write_index(vault, load_pages(vault))
        named = " + ".join(f"`{rel_to(log, dev_root)}`" for log in logs)
        append_log(vault, "Ingest", f"directives, ratifications and numbered rulings from {named}: {report.found} distinct citation(s), "
                   f"{report.changed} page(s) changed of {len(report.written)} extracted, {len(report.skipped)} kept; "
                   f"[index](index.md) rebuilt.", when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.rulings", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--agents", type=Path, default=None, help="default <dev-root>/AGENTS.md")
    ap.add_argument("--archive", type=Path, default=None, help=f"rotated history; default {ARCHIVE_NAME} beside --agents")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    agents = args.agents or (args.dev_root / "AGENTS.md")
    if not agents.is_file():
        print(f"[REFUSE] handoff log not found: {agents} (exit 3)", file=out)
        return 3
    report = ingest_rulings(agents, args.vault, args.dev_root, archive=args.archive, at=at_from(args), force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    for r in report.skipped:
        print("[KEEP]  " + r, file=out)
    print(f"rulings: {report.found} distinct citation(s); {len(report.written)} written ({report.changed} changed), "
          f"{len(report.skipped)} kept", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
