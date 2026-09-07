"""Known data gaps -> one Event page each, so an interval in which a stream did not record is a fact with a page.

    python -m knowledge.ingest.data_gaps [--gaps knowledge/data_gaps.json] [--at ISO]

Round 121 (operator-permissioned; Antigravity section 3.1 item 3). A nine-hour hole in asset_snapshots
(Round 119) is exactly the kind of fact every later analysis over that interval must cite, and until
now it lived only in a log and a handoff. Each gap in knowledge/data_gaps.json becomes
wiki/events/data_gap_<id>.md (type Event, dev.kind data_gap, dev.window start/end) so it is in the
events register, linkable, and visible to lint: L12 warns when an Experiment page's measured span
overlaps a gap it does not list under dev.data_gaps. The verdict adapters call overlapping_gaps() and
write that acknowledgement themselves.

Read-only on the JSON. Writes only through pages.write_page.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..frontmatter import parse_iso8601
from ..pages import Page, append_log, carry_human_fields, load_page, load_pages, make_meta, now_utc, page_path, write_index, write_page
from ..registers import write_register
from . import add_common_args, at_from, guard, page_changed, rel_to

DEFAULT_GAPS = Path("knowledge") / "data_gaps.json"
KIND = "data_gap"


def gap_stem(gap_id: str) -> str:
    return "data_gap_" + "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(gap_id))


def overlapping_gaps(vault: Path, start: str | datetime | None, end: str | datetime | None) -> list[str]:
    """Stems of data_gap Event pages whose window overlaps [start, end]. Empty when either bound is missing."""
    if not start or not end:
        return []
    try:
        s = parse_iso8601(str(start)) if not isinstance(start, datetime) else start
        e = parse_iso8601(str(end)) if not isinstance(end, datetime) else end
    except ValueError:
        return []
    out: list[str] = []
    for p in load_pages(vault):
        dev = p.meta.get("dev") or {}
        if p.type != "Event" or dev.get("kind") != KIND:
            continue
        w = dev.get("window") or {}
        try:
            gs, ge = parse_iso8601(str(w.get("start"))), parse_iso8601(str(w.get("end")))
        except ValueError:
            continue
        if gs < e and ge > s:
            out.append(p.path.stem)
    return sorted(out)


def compile_gap(gap: dict[str, Any], src_rel: str, vault: Path, at: datetime, by: str = GENERATED_BY) -> Page:
    start, end = parse_iso8601(str(gap["start_utc"])), parse_iso8601(str(gap["end_utc"]))
    hours = round((end - start).total_seconds() / 3600, 2)
    stem = gap_stem(gap["id"])
    body = [f"# Data gap: {gap['id']}", "",
            f"> **{hours} h with no recording** - {gap['start_utc']} to {gap['end_utc']} (desk {gap.get('desk', '-')}). "
            "Any evaluation whose window overlaps this interval must say so; lint L12 checks.", "",
            "## Cause", "", str(gap.get("cause", "-")), "",
            "## Streams affected", ""] + [f"- {t}" for t in gap.get("tables", [])] + ["",
            "## Evaluations that touch this interval", ""] + [f"- {t}" for t in gap.get("affected_evaluations", [])] + ["",
            "## Detection and resolution", "",
            f"- detected {gap.get('detected_utc', '-')}; resolved {gap.get('resolved_utc', '-')}",
            f"- {gap.get('resolution', '-')}", "",
            "## Related", "", "- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]", "- [[events_register|Events register]]", ""]
    dev = {"kind": KIND, "desk": gap.get("desk"), "window": {"start": gap["start_utc"], "end": gap["end_utc"]},
           "gap_hours": hours, "tables": list(gap.get("tables", [])), "cause": gap.get("cause"),
           "affected_evaluations": list(gap.get("affected_evaluations", [])), "round": gap.get("round"),
           "detected_utc": gap.get("detected_utc"), "resolved_utc": gap.get("resolved_utc")}
    meta = make_meta("Event", f"Data gap: {gap['id']}",
                     f"{hours} h with no recording in {', '.join(t.split(' (')[0] for t in gap.get('tables', [])[:2])}: "
                     f"{gap['start_utc']} to {gap['end_utc']}. Round {gap.get('round', '-')}.",
                     tags=["event", "data-gap", f"desk-{gap.get('desk', 'x')}", "incident"],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "gaps", "resource": src_rel, "title": "data_gaps.json", "author": "human:operator"}],
                     dev=dev)
    path = page_path(vault, "Event", stem)
    carry_human_fields(load_page(path), meta)
    return Page(path, meta, "\n".join(body))


def ingest_gaps(vault: Path, dev_root: Path, *, gaps_file: Path | None = None, at: datetime | None = None,
                by: str = GENERATED_BY) -> list[Page]:
    at = at or now_utc()
    gaps_file = gaps_file or (dev_root / DEFAULT_GAPS)
    if not gaps_file.is_file():
        return []
    data = json.loads(gaps_file.read_text(encoding="utf-8"))
    src_rel = rel_to(gaps_file, dev_root)
    written: list[Page] = []
    changed_any = False
    for gap in data.get("gaps", []):
        page = compile_gap(gap, src_rel, vault, at, by)
        changed_any = page_changed(page, vault) or changed_any
        write_page(page, vault, now=at)
        written.append(page)
    if changed_any:
        write_register(vault, "Event", at=at, by=by)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"data gaps from `{src_rel}`: {len(written)} page(s) -> [[events_register]].", when=at)
    return written


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.data_gaps", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--gaps", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_GAPS.as_posix()}")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    pages = ingest_gaps(args.vault, args.dev_root, gaps_file=args.gaps, at=at_from(args))
    for p in pages:
        print(f"[WRITE] {p.path.relative_to(args.vault).as_posix()}  {p.meta['dev']['gap_hours']} h", file=out)
    if not pages:
        print("[SKIP] no data_gaps.json or no gaps in it", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
