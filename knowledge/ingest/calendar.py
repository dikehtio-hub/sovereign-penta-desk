"""Committed calendars -> Event pages (Round 98, B7).

    python -m knowledge.ingest.calendar [--dir knowledge/calendars] [--force] [--at ISO]

Two YAML shapes live in knowledge/calendars/:
  fomc_*.yaml   kind fed_rate; meetings[] with id, meeting, statement_utc, sep -> Event pages with
                `dev.window` = statement - window_before .. + window_after (T-2..T+5), `dev.sep`
  tax_*.yaml    kind estimated_tax; deadlines[] with quarter, period, due -> Event pages with
                `stale_after` = the due date, so a passed deadline is a lint L4 finding until deprecated
Pages are `status: draft`. A FOMC Event page written here is later ENRICHED, not replaced, by
knowledge.ingest.clob (it merges window / sep / meeting / calendar into the recorded event).
Windows are enforced twice: write_page refuses to write a page inside its own window, and lint C5
reports one that was. The Events register is rebuilt after every run.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from .. import EXIT_OK, GENERATED_BY
from ..frontmatter import parse_iso8601
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from ..registers import write_register
from . import add_common_args, at_from, guard, rel_to

DEFAULT_DIR = Path("knowledge") / "calendars"
BOOKS_ROOT = "cross_market/data/clob_books"   # where the drill recorder writes (Ruling R108-1.D)
REGISTER_FILE = "events_register"


def _fomc_pages(cal: dict[str, Any], rel: str, vault: Path, at: datetime, by: str) -> list[Page]:
    before = timedelta(minutes=int(cal.get("window_before_minutes", 2)))
    after = timedelta(minutes=int(cal.get("window_after_minutes", 5)))
    pages: list[Page] = []
    for m in cal.get("meetings") or []:
        release = parse_iso8601(m["statement_utc"])
        eid = str(m["id"])
        et_hour = release.astimezone(timezone.utc).hour
        body = [f"# Event: {eid}", "", f"> FOMC statement, meeting {m.get('meeting')} · SEP {'yes' if m.get('sep') else 'no'}", "",
                "## Timing", "", f"- statement (release_utc): `{iso(release)}` (14:00 Eastern = {et_hour:02d}:00Z on this date)",
                f"- press conference: `{m.get('press_conference_utc', '-')}`",
                f"- window: `{iso(release - before)}` .. `{iso(release + after)}` (T-{int(before.total_seconds() // 60)} .. T+{int(after.total_seconds() // 60)}; "
                "this page and any rules file are frozen inside it)", ""]
        if m.get("note"):
            body += ["## Note", "", str(m["note"]), ""]
        body += ["## After the print", "",
                 "1. write ./event.json {kind fed_rate, payload.change_bps <int from the statement>, source, confidence >= 0.99, observed_at}",
                 f"2. `latency_sniper --survival-curve --event ./event.json --books {BOOKS_ROOT}/{eid} --json > curve.json`",
                 f"3. `knowledge.ingest.clob --result curve.json --event {eid}` (enriches this page, adds Reaction Profiles)", "",
                 "## Related", "", f"- [[{REGISTER_FILE}|Events register]]", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
                 "- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]", ""]
        dev: dict[str, Any] = {"desk": 3, "item": 12, "kind": "fed_rate", "meeting": str(m.get("meeting")),
                               "release_utc": iso(release), "sep": bool(m.get("sep", False)), "calendar": rel,
                               # Ruling R108-1.D: the EVENT declares where its recorder writes, so the
                               # drill card reads it instead of guessing. Round 108 found the guess is
                               # wrong twice over - latency_sniper's own default is the clob_books ROOT,
                               # and the directive proposed a clob_drill/ path that does not exist. A
                               # survival curve aimed at an empty directory reports an empty RESULT, not
                               # an error, one minute after the print.
                               "books_dir": f"{BOOKS_ROOT}/{eid}",
                               "window": {"start": iso(release - before), "end": iso(release + after)}}
        meta = make_meta("Event", f"Event: {eid}",
                         f"FOMC statement {iso(release)} ({'SEP meeting' if m.get('sep') else 'no SEP'}); window T-2..T+5 registered.",
                         tags=["event", "fed_rate", "desk-3", "item-12", "scheduled"], generated_by=by, at=at, status="draft",
                         sources=[{"id": "calendar", "resource": rel, "title": Path(rel).name, "author": "human:operator"},
                                  {"id": "fed", "resource": str(cal.get("source", "")), "title": "FOMC meeting calendars"}],
                         dev=dev)
        pages.append(Page(page_path(vault, "Event", eid), meta, "\n".join(body)))
    return pages


def _tax_pages(cal: dict[str, Any], rel: str, vault: Path, at: datetime, by: str, dev_root: Path | None = None) -> list[Page]:
    pages: list[Page] = []
    src = str(cal.get("source", ""))
    if dev_root is not None and src and not (dev_root / src).is_file():
        src = ""  # the module is not on this machine: no assert, no source entry (L5/C1 would fire)
    for d in cal.get("deadlines") or []:
        eid = str(d["id"])
        due = str(d["due"])
        body = [f"# Event: {eid}", "", f"> Federal estimated-tax payment {d.get('quarter')} for tax year {cal.get('tax_year')}, due {due}.", "",
                "## Period", "", f"- covers `{d.get('period_start')}` .. `{d.get('period_end')}` ({d.get('months')} months: the quarters are not quarters)",
                f"- due `{due}`; this page goes stale at the deadline (lint L4) and is then deprecated", "",
                "## What to do", "", "- `python -m Tax_Reserve_Agent.main calendar` for the amount and the escrow release for this deadline", "",
                "## Related", "", f"- [[{REGISTER_FILE}|Events register]]", "- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]", ""]
        dev: dict[str, Any] = {"desk": 5, "kind": "estimated_tax", "quarter": str(d.get("quarter")), "tax_year": cal.get("tax_year"),
                               "period_start": str(d.get("period_start")), "period_end": str(d.get("period_end")), "due": due, "calendar": rel}
        if src:
            dev["asserts"] = [{"file": src, "pattern": r"THE QUARTERS ARE NOT QUARTERS", "claim": "the tax calendar module still documents the odd quarters"}]
        meta = make_meta("Event", f"Event: {eid}", f"Estimated tax {d.get('quarter')} {cal.get('tax_year')} due {due}.",
                         tags=["event", "estimated_tax", "desk-5", "deadline"], generated_by=by, at=at, status="draft",
                         stale_after=f"{due}T23:59:59Z",
                         sources=[{"id": "calendar", "resource": rel, "title": Path(rel).name, "author": "human:operator"}]
                         + ([{"id": "tax-calendar-module", "resource": src, "title": "tax_calendar.py"}] if src else []),
                         dev=dev)
        pages.append(Page(page_path(vault, "Event", eid), meta, "\n".join(body)))
    return pages


def compile_calendar(path: Path, vault: Path, dev_root: Path, at: datetime, by: str = GENERATED_BY) -> list[Page]:
    cal = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(cal, dict):
        return []
    rel = rel_to(path, dev_root)
    if cal.get("kind") == "fed_rate":
        pages = _fomc_pages(cal, rel, vault, at, by)
    elif cal.get("kind") == "estimated_tax":
        pages = _tax_pages(cal, rel, vault, at, by, dev_root)
    else:
        return []
    for p in pages:
        carry_human_fields(load_page(p.path), p.meta)  # Ruling 99-2
    return pages


@dataclass
class CalendarReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def ingest_calendars(cal_dir: Path, vault: Path, dev_root: Path, *, at: datetime | None = None, by: str = GENERATED_BY,
                     force: bool = False) -> CalendarReport:
    at = at or now_utc()
    report = CalendarReport()
    for path in sorted(cal_dir.glob("*.yaml")):
        for page in compile_calendar(path, vault, dev_root, at, by):
            rel = page.path.relative_to(vault).as_posix()
            if page.path.exists() and not force:
                report.skipped.append(rel)
                continue
            write_page(page, vault, now=at)
            report.written.append(rel)
    if report.written:
        write_register(vault, "Event", at=at, by=by)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"calendars from `{rel_to(cal_dir, dev_root)}`: {len(report.written)} Event page(s) written, "
                   f"{len(report.skipped)} kept; [index](index.md) rebuilt.", when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.calendar", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--dir", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_DIR.as_posix()}")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    cal_dir = args.dir or (args.dev_root / DEFAULT_DIR)
    if not cal_dir.is_dir():
        print(f"[REFUSE] calendars folder not found: {cal_dir} (exit 3)", file=out)
        return 3
    report = ingest_calendars(cal_dir, args.vault, args.dev_root, at=at_from(args), force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    for r in report.skipped:
        print("[KEEP]  " + r, file=out)
    print(f"calendar: {len(report.written)} written, {len(report.skipped)} kept", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
