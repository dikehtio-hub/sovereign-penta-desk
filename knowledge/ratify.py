"""Ratification: append Antigravity's `verified` block to a set of pages (Round 99, Ruling 98-1).

    python -m knowledge.ratify --type Ruling --tag extracted --ruling 98-1 [--by antigravity/architect]
                               [--status stable] [--at ISO] [--dry-run]

The constitution (s.2) says an agent never verifies a page it generated; this
command exists so the RECORD of Antigravity's ratification is written the same
way every other page is written: through `pages.write_page`, with the actor
string, the instant and the ruling that authorised it. It selects pages by
`type` and, optionally, by a tag, appends `{by, at}` to `verified` unless that
actor is already there, sets `status`, records `dev.ratified_by`, rebuilds the
type's register and appends one `**Ratify**` bullet to log.md. Idempotent: a
second run with the same actor changes nothing.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, VAULT, halted
from .frontmatter import is_actor, parse_iso8601
from .pages import append_log, iso, load_pages, now_utc, write_index, write_page
from .registers import SPECS, update_register

DEFAULT_ACTOR = "antigravity/architect"


@dataclass
class RatifyReport:
    ratified: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    selected: int = 0


def ratify(vault: Path, *, type_: str, ruling: str, tag: str | None = None, by: str = DEFAULT_ACTOR,
           status: str = "stable", at: datetime | None = None, dry_run: bool = False) -> RatifyReport:
    at = at or now_utc()
    if not is_actor(by):
        raise ValueError(f"{by!r} is not an OKF actor string")
    report = RatifyReport()
    for page in load_pages(vault):
        if page.type != type_:
            continue
        if tag and tag not in (page.meta.get("tags") or []):
            continue
        report.selected += 1
        rel = page.path.relative_to(vault).as_posix()
        v = page.meta.get("verified")
        entries = v if isinstance(v, list) else ([v] if isinstance(v, dict) else [])
        if any(isinstance(e, dict) and e.get("by") == by for e in entries):
            report.already.append(rel)
            continue
        entries.append({"by": by, "at": iso(at)})
        page.meta["verified"] = entries
        page.meta["status"] = status
        dev = page.meta.setdefault("dev", {})
        dev["ratified_by"] = ruling
        if not dry_run:
            write_page(page, vault, now=at)
        report.ratified.append(rel)
    if report.ratified and not dry_run:
        if type_ in SPECS:
            write_page(update_register(vault, type_, at=at), vault, now=at)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ratify", f"Ruling {ruling}: {len(report.ratified)} {type_} page(s)" + (f" tagged `{tag}`" if tag else "")
                   + f" verified by `{by}` and set `{status}`; {len(report.already)} already carried that verification.", when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ratify", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--type", required=True, help="page type to ratify, e.g. Ruling")
    ap.add_argument("--tag", default=None, help="only pages carrying this tag, e.g. extracted")
    ap.add_argument("--ruling", required=True, help="the ruling that authorises this, e.g. 98-1")
    ap.add_argument("--by", default=DEFAULT_ACTOR)
    ap.add_argument("--status", default="stable", choices=["draft", "stable", "deprecated"])
    ap.add_argument("--at", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - ratify refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    try:
        report = ratify(args.vault, type_=args.type, ruling=args.ruling, tag=args.tag, by=args.by, status=args.status,
                        at=parse_iso8601(args.at) if args.at else None, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"[REFUSE] {exc} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    for r in report.ratified:
        print(("[DRY]   " if args.dry_run else "[VERIFY] ") + r, file=out)
    print(f"ratify: {report.selected} selected, {len(report.ratified)} verified, {len(report.already)} already", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
