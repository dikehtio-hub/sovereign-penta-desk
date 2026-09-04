"""
Odds fetcher: puts a real-shaped odds file into the drop folder, then prices it.

WHAT THIS CLOSES. Sports_Desk had 680 passing tests and no database. Every test
built its own SQLite fixture in a temp directory; `data/odds_drops/` held zero
files; `sports_market.db` did not exist. The Brier and skill-score machinery was
built and had never scored a single forecast, because there were no forecasts.
This module is the collector that makes the desk's first real row exist.

OFFLINE BY DEFAULT, AND THAT IS NOT A SHORTCUT. Every test in this ecosystem runs
without a socket, and the odds watcher it feeds refuses to price a market with no
sharp reference in it. So the default source is a bundled multi-book sample that
exercises exactly the shape `parse_odds_csv` accepts - a sharp book, three retail
books, moneyline / spread / totals, one deliberate retail mispricing per fixture
so an edge lands - and a `--url` path for a live feed that is never touched unless
asked for. A collector that silently fetched would make the desk's output depend
on whether the machine happened to have connectivity, which is not something the
operator can see from the screen.

THE LIVE PATH IS A CONTRACT, NOT A SCRAPER. `--url` expects a JSON list of rows
already in the CSV column shape below. Adapting a specific provider's payload is
a one-function shim the operator writes against the provider's terms; this module
does not ship one and does not guess at one.

    event_id,sport,market_type,line,selection,book,odds,is_sharp,timestamp,start_time,is_closing
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from Sports_Desk.data.db import DEFAULT_DB_PATH
from Sports_Desk.ingestors.odds_watcher import DEFAULT_DROP_FOLDER, OddsWatcher

COLUMNS = ("event_id", "sport", "market_type", "line", "selection", "book", "odds",
           "is_sharp", "timestamp", "start_time", "is_closing")

SHARP_BOOK = "Pinnacle"
RETAIL_BOOKS = ("DraftKings", "FanDuel", "BetMGM")


class FetchError(RuntimeError):
    """A live payload did not have the shape the drop folder accepts."""


# ---------------------------------------------------------------------------
# The bundled sample
# ---------------------------------------------------------------------------

# Two fixtures. Each carries the sharp book on every market and three retail
# quotes, one of which is DELIBERATELY better than the sharp fair price so the
# pipeline produces a genuine edge row rather than an empty table. The numbers
# are plausible, not live - that is the point of a sample.
SAMPLE_FIXTURES = (
    {
        "event_id": "NFL_KC_BAL", "sport": "NFL",
        "home": "Chiefs", "away": "Ravens", "spread": "-3.5", "total": "47.5",
        "moneyline": {SHARP_BOOK: ("-140", "+125"), "DraftKings": ("-135", "+140"),
                      "FanDuel": ("-142", "+122"), "BetMGM": ("-138", "+118")},
        "spread_prices": {SHARP_BOOK: ("-110", "-110"), "DraftKings": ("-108", "-112"),
                          "FanDuel": ("-105", "-115"), "BetMGM": ("-110", "-110")},
        "total_prices": {SHARP_BOOK: ("-108", "-112"), "DraftKings": ("-110", "-110"),
                         "FanDuel": ("+100", "-120"), "BetMGM": ("-112", "-108")},
    },
    {
        "event_id": "NFL_PHI_DAL", "sport": "NFL",
        "home": "Eagles", "away": "Cowboys", "spread": "-6.5", "total": "44.5",
        "moneyline": {SHARP_BOOK: ("-260", "+215"), "DraftKings": ("-255", "+210"),
                      "FanDuel": ("-270", "+230"), "BetMGM": ("-265", "+220")},
        "spread_prices": {SHARP_BOOK: ("-110", "-110"), "DraftKings": ("-115", "-105"),
                          "FanDuel": ("-110", "-110"), "BetMGM": ("-104", "-116")},
        "total_prices": {SHARP_BOOK: ("-110", "-110"), "DraftKings": ("-105", "-115"),
                         "FanDuel": ("-110", "-110"), "BetMGM": ("-115", "-105")},
    },
)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sample_rows(now: Optional[datetime] = None,
                hours_to_start: float = 3.0) -> List[Dict[str, str]]:
    """
    The bundled multi-book snapshot, stamped `now` so it is never stale on arrival.

    Timestamps matter more than prices here. The watcher drops quotes older than
    its per-sport age limit and refuses to price a market whose sharp leg went
    stale, so a sample stamped at write time is the only kind that survives the
    pipeline it is meant to exercise.
    """
    now = now or datetime.now(timezone.utc)
    quoted_at = _iso(now)
    starts = _iso(now + timedelta(hours=hours_to_start))
    rows: List[Dict[str, str]] = []

    def add(fixture, market_type, line, selection, book, odds):
        rows.append({
            "event_id": fixture["event_id"], "sport": fixture["sport"],
            "market_type": market_type, "line": line, "selection": selection,
            "book": book, "odds": odds, "is_sharp": "1" if book == SHARP_BOOK else "0",
            "timestamp": quoted_at, "start_time": starts, "is_closing": "0",
        })

    for fx in SAMPLE_FIXTURES:
        home, away = fx["home"], fx["away"]
        for book, (h, a) in fx["moneyline"].items():
            add(fx, "moneyline", "", home, book, h)
            add(fx, "moneyline", "", away, book, a)
        # ONE LINE KEY FOR BOTH LEGS. The watcher groups a market by
        # (event, sport, market_type, LINE); writing the home leg at -3.5 and the
        # away leg at +3.5 makes them two different one-leg markets, and the
        # watcher refuses each because a market missing a leg devigs cleanly and
        # WRONGLY. Its guard caught exactly that in the first real run. The
        # handicap is the market's identity; the selection says which side.
        line = fx["spread"]
        for book, (h, a) in fx["spread_prices"].items():
            add(fx, "spread", line, home, book, h)
            add(fx, "spread", line, away, book, a)
        for book, (o, u) in fx["total_prices"].items():
            add(fx, "totals", fx["total"], "Over %s" % fx["total"], book, o)
            add(fx, "totals", fx["total"], "Under %s" % fx["total"], book, u)
    return rows


# ---------------------------------------------------------------------------
# Writing and fetching
# ---------------------------------------------------------------------------

def rows_to_csv(rows: Sequence[Dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS), extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in COLUMNS})
    return buffer.getvalue()


def write_drop(rows: Sequence[Dict[str, Any]], drop_folder: Path = DEFAULT_DROP_FOLDER,
               name: Optional[str] = None, now: Optional[datetime] = None) -> Path:
    """Write rows into the drop folder as one CSV. Returns the path."""
    drop_folder = Path(drop_folder)
    drop_folder.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    target = drop_folder / (name or now.strftime("odds_%Y%m%dT%H%M%SZ.csv"))
    target.write_text(rows_to_csv(rows), encoding="utf-8")
    return target


def validate_rows(rows: Any) -> List[Dict[str, Any]]:
    """
    Reject a payload that is not a list of rows carrying the required columns.

    Checked BEFORE anything is written, because a malformed file in the drop
    folder is archived into failed/ by the watcher with a terse reason, and the
    shape error is far more legible here, where the payload came from.
    """
    if not isinstance(rows, list):
        raise FetchError("payload must be a JSON list of row objects, got %s"
                         % type(rows).__name__)
    required = ("event_id", "selection", "book", "odds")
    clean: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise FetchError("row %d is not an object" % index)
        lowered = {str(k).strip().lower(): v for k, v in row.items()}
        missing = [c for c in required if not str(lowered.get(c, "")).strip()]
        if missing:
            raise FetchError("row %d is missing %s" % (index, ", ".join(missing)))
        clean.append(lowered)
    if not clean:
        raise FetchError("payload carried no rows")
    return clean


def fetch_json_rows(url: str, timeout: float = 10.0,
                    getter: Optional[Callable[[str, float], Any]] = None
                    ) -> List[Dict[str, Any]]:
    """
    Pull a JSON list of rows from `url`. Never called unless the operator asks.

    `requests` is imported lazily, inside this function, so the offline path
    never touches a network library at all - and a test can pass `getter` to
    exercise the validation without a socket.
    """
    if getter is None:
        import requests  # noqa: WPS433 - deliberate lazy import

        def getter(target: str, limit: float) -> Any:
            response = requests.get(target, timeout=limit)
            response.raise_for_status()
            return response.json()
    return validate_rows(getter(url, timeout))


# ---------------------------------------------------------------------------
# Running the watcher over what was written
# ---------------------------------------------------------------------------

def run_watcher(drop_folder: Path = DEFAULT_DROP_FOLDER,
                db_path: Path = DEFAULT_DB_PATH,
                hurdle: Optional[Callable[[float], float]] = None,
                archive: bool = True) -> List[Any]:
    """
    Price everything in the drop folder, honouring the two-poll stability rule.

    The watcher will not open a file it has seen only once, so a single pass is
    primed first and the real scan runs a beat later - the same dance
    `odds_watcher.main --once` performs.
    """
    watcher = OddsWatcher(drop_folder=drop_folder, db_path=db_path,
                          after_tax_hurdle=hurdle, archive=archive)
    watcher.scan_once()
    return watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)


def ledger_hurdle() -> Callable[[float], float]:
    """The after-tax hurdle per odds, from the tax ledger's own treatment."""
    from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
    ledger = get_hook()
    return lambda odds: ledger.breakeven_gross_edge(category="sports", decimal_odds=odds)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sports_Desk odds fetcher - drops a real-shaped odds file and prices it")
    parser.add_argument("--sample", action="store_true",
                        help="write the bundled multi-book sample (the default when no --url)")
    parser.add_argument("--url", type=str, default=None,
                        help="fetch a JSON list of rows in the drop-file column shape")
    parser.add_argument("--folder", type=Path, default=None, help="drop folder")
    parser.add_argument("--db", type=Path, default=None, help="sports_market.db path")
    parser.add_argument("--name", type=str, default=None, help="drop file name")
    parser.add_argument("--run-watcher", action="store_true",
                        help="price the drop folder immediately after writing")
    parser.add_argument("--hurdle-from-ledger", action="store_true",
                        help="compute the after-tax hurdle per row from the tax ledger")
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args(argv)

    folder = Path(args.folder or DEFAULT_DROP_FOLDER)
    db_path = Path(args.db or DEFAULT_DB_PATH)

    if args.url:
        rows = fetch_json_rows(args.url)
        source = args.url
    else:
        rows = sample_rows()
        source = "bundled sample"
    target = write_drop(rows, folder, name=args.name)
    print("[DROP] %d row(s) from %s -> %s" % (len(rows), source, target))

    if args.run_watcher:
        hurdle = ledger_hurdle() if args.hurdle_from_ledger else None
        reports = run_watcher(folder, db_path, hurdle=hurdle, archive=not args.no_archive)
        for report in reports:
            print(report.summary())
        print("[DB] %s" % db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
