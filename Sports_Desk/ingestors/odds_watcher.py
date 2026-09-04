"""
Odds drop-folder watcher.

Drop a CSV of quotes into `Sports_Desk/data/odds_drops/` and it becomes priced
edges in `sports_market.db` without another command being typed. Same shape as
`Tax_Reserve_Agent/ingestors/csv_watcher.py`, and built around the same three
failure modes, because they corrupt an odds book as quietly as they corrupt a
tax ledger:

  1. HALF-WRITTEN FILES. Copying an export into a watched folder makes it visible
     long before it is complete, and a truncated market looks exactly like a
     market with fewer legs - which devigs happily and WRONGLY. Every file must
     report the same size and mtime on two consecutive polls before it is opened.
  2. GUESSED REFERENCES. Devigging a soft book yields that book's opinion minus
     its margin, not a fair price, so a market with no sharp book in it is
     REJECTED rather than priced off DraftKings. A wrong fair value is invisible
     downstream and wrong forever after.
  3. DOUBLE IMPORTS. The same file dropped twice would double the edge rows.
     Identity is the file's BYTES (SHA-256), not its name or mtime - a name and
     an mtime can both change without the content changing, and vice versa.

WHICH BOOK IS THE TRUTH-TELLER. This is the question the plan left open and this
module answers it in code: the SHARP book is devigged to produce fair
probabilities, and every retail quote is scored against those. Retail books are
never devigged - you bet the price a book offers, not a fair one, so the retail
side is stored raw. `SHARP_BOOKS` names the references; a row may also carry an
`is_sharp` column to override per market.

EXPECTED CSV SHAPE (column order irrelevant, names flexible):

    event_id,sport,market_type,line,selection,book,odds,is_sharp,timestamp,is_closing
    NFL_KC_BAL,NFL,moneyline,,Chiefs,Pinnacle,-140,1,2026-09-03T18:00:00Z,0
    NFL_KC_BAL,NFL,moneyline,,Ravens,Pinnacle,+120,1,2026-09-03T18:00:00Z,0
    NFL_KC_BAL,NFL,moneyline,,Chiefs,DraftKings,-130,0,2026-09-03T18:00:00Z,0
    NFL_KC_BAL,NFL,spread,-3.5,Chiefs,Pinnacle,-110,1,2026-09-03T18:00:00Z,0

Rows group by (event_id, sport, market_type, LINE). The line is part of the
market identity, not an attribute of it: Chiefs -3.5 and Chiefs -2.5 are
different bets with different fair prices, and grouping them devigs one book
against another quoting a different number - the "edge" that falls out is just
the half-point. `line` is blank for a moneyline.

`timestamp` and `is_closing` are optional. Without timestamps the staleness
guard cannot run and says so; without `is_closing` nothing marks a closing line
and CLV has nothing to compare against.

Odds accept anything `parse_odds` reads.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from Sports_Desk.data.db import (DEFAULT_DB_PATH, already_imported, init_market_db,
                                 record_edge_opportunity, record_fair_value_measurement,
                                 record_import)
from Sports_Desk.engine.fair_value import (ArbitrageError, DevigError,
                                           calculate_fair_value, calculate_edge)
from Tax_Reserve_Agent.engine.lot_engine import as_naive_utc, parse_iso_date
from Tax_Reserve_Agent.engine.odds import OddsFormatError, parse_odds
from Tax_Reserve_Agent.ingestors.sports_betting import canonical_book

DEFAULT_DROP_FOLDER = Path(__file__).resolve().parent.parent / "data" / "odds_drops"

# The reference books. Pinnacle and Circa are the standard choices: low margin,
# high limits, and they move on sharp money rather than on public money, which is
# what makes their devigged price worth calling "fair". Everything else is retail
# and is SCORED, never used as a reference.
SHARP_BOOKS = frozenset({"pinnacle", "circa", "bookmaker", "betcris"})

# A file must look identical on two consecutive polls, at least this far apart.
DEFAULT_STABILITY_SECONDS = 1.0

# HOW OLD A QUOTE MAY BE, relative to the newest quote in its own market.
#
# A stale sharp price against a live retail price is not an edge, it is a clock
# difference - and it is the most flattering possible error, because the market
# has already moved to where the "edge" says it should go. The thresholds scale
# with how fast a line actually moves: an NBA number reprices on every
# possession, a golf outright barely moves in an hour.
#
# THESE ARE ENGINEERING ESTIMATES, NOT MEASUREMENTS. Nothing here has line-history
# data to calibrate them against yet; they are deliberately generous so the guard
# catches the egregious case (a quote from last night) without discarding a
# normal scrape.
MAX_QUOTE_AGE_SECONDS = {
    "live": 30, "inplay": 30, "in_play": 30,
    "tennis": 120,
    "nba": 180, "nhl": 180, "ncaab": 180,
    "nfl": 300, "mlb": 300, "ncaaf": 300, "soccer": 300, "epl": 300, "mls": 300,
    "golf": 3600, "futures": 3600, "outright": 3600, "outrights": 3600,
}
DEFAULT_MAX_QUOTE_AGE_SECONDS = 600

# Inside this window before the scheduled start, the threshold is halved. Lines
# move fastest in the last hour - late injury news, lineup confirmation, and the
# steam that follows both - so a quote that was fresh enough at noon is not fresh
# enough at kickoff minus ten minutes.
NEAR_START_WINDOW_SECONDS = 3600
NEAR_START_TIGHTENING = 0.5


class OddsImportError(ValueError):
    """A market that cannot be priced. Never guessed - always raised."""


@dataclass
class MarketQuote:
    """One book's price on one selection."""
    book: str
    selection: str
    decimal_odds: float
    is_sharp: bool
    quoted_at: Optional[datetime] = None
    is_closing: bool = False
    is_live: bool = False
    start_time: Optional[datetime] = None
    # THIS SELECTION'S OWN handicap or total, as the file gave it: Chiefs -3.5,
    # Ravens +3.5 (Round 35, Ruling 5.B). The MARKET is identified by the unsigned
    # number - see market_line_key - so the two legs still land in one basket.
    line: str = ""

    @property
    def key(self) -> str:
        """
        Selection identity, normalised.

        Books spell the same runner differently - `Chiefs`, `chiefs `,
        `KC  Chiefs`. Matching raw strings means a retail quote silently fails to
        find its sharp counterpart and is dropped, which looks like a market with
        fewer retail books rather than like a bug. Case and whitespace only:
        anything more aggressive would merge genuinely distinct selections.
        """
        return " ".join(str(self.selection).split()).upper()


@dataclass
class ImportReport:
    """What one file produced. Returned rather than printed so tests can assert."""
    filename: str = ""
    content_hash: str = ""
    rows_read: int = 0
    markets_seen: int = 0
    markets_priced: int = 0
    edges_found: int = 0
    arbitrages: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    stale_dropped: int = 0
    duplicate: bool = False

    def summary(self) -> str:
        if self.duplicate:
            return f"[SKIP] {self.filename}: identical content already imported."
        parts = [f"[OK  ] {self.filename}: {self.rows_read} row(s), "
                 f"{self.markets_priced}/{self.markets_seen} market(s) priced, "
                 f"{self.edges_found} edge(s)"
                 + (f", {self.stale_dropped} stale quote(s) dropped"
                    if self.stale_dropped else "")]
        for arb in self.arbitrages:
            parts.append(f"[ARB ] {arb}")
        for reason in self.skipped:
            parts.append(f"[WARN] {reason}")
        return "\n".join(parts)


def _first(row: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value).strip()
    return ""


def market_line_key(line: str) -> str:
    """
    The number that identifies a market, sign dropped.

    Chiefs -3.5 and Ravens +3.5 are the two legs of ONE market, so the market is
    keyed by 3.5 while each leg keeps its own signed handicap (Ruling 5.B, Round
    35). A file that keys both legs under the home number (-3.5 / -3.5, the
    Round 33 convention) still groups, because abs() is the same either way;
    what it cannot do is tell the matcher the away side's true handicap, so such
    a feed produces no spread hedges. Totals are already unsigned. A non-numeric
    line is used as written.
    """
    text = str(line or "").strip()
    if not text:
        return ""
    try:
        value = abs(float(text))
    except ValueError:
        return text
    return ("%.2f" % value).rstrip("0").rstrip(".")


def _truthy(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "yes", "y", "sharp", "t")


def content_hash(path: Path) -> str:
    """SHA-256 of the file's bytes - the only identity a CSV really has."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_odds_csv(path: Path,
                   odds_format: Optional[str] = None) -> Tuple[Dict[Tuple[str, str, str], List[MarketQuote]], int, List[str]]:
    """
    Reads a drop file into markets keyed by (event_id, sport, market_type).

    Unreadable ROWS are skipped with a reason rather than aborting the file - one
    mistyped price should not cost the other forty markets - but an unreadable
    row is never silently dropped, because a missing leg makes the whole market
    devig wrongly and nothing downstream could tell.
    """
    markets: Dict[Tuple[str, str, str], List[MarketQuote]] = {}
    skipped: List[str] = []
    rows_read = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for line_no, raw in enumerate(csv.DictReader(handle), start=2):
            row = {str(k).strip().lower(): (v or "").strip()
                   for k, v in raw.items() if k}
            rows_read += 1
            event_id = _first(row, "event_id", "event", "game_id", "match_id")
            sport = _first(row, "sport", "league") or "SPORTS"
            market_type = _first(row, "market_type", "market", "bet_type") or "moneyline"
            selection = _first(row, "selection", "outcome", "runner", "team", "pick")
            book = _first(row, "book", "sportsbook", "bookmaker", "site")
            # NOT `line` any more - see the market key below. A spread export uses
            # `line` for the handicap, and reading it as the PRICE turned -3.5
            # into odds.
            price = _first(row, "odds", "price", "decimal_odds", "american_odds")
            # THE LINE IS PART OF THE MARKET, NOT AN ATTRIBUTE OF IT. Chiefs -3.5
            # and Chiefs -2.5 are different bets with different fair prices;
            # grouping them together devigs one book against another book quoting
            # a different number, and the "edge" that falls out is the half-point.
            line = _first(row, "line", "handicap", "spread", "total", "points",
                          "target")
            quoted_at = _parse_timestamp(
                _first(row, "timestamp", "quoted_at", "captured_at", "observed_at",
                       "time", "datetime"))
            start_time = _parse_timestamp(
                _first(row, "start_time", "commence_time", "kickoff", "starts_at",
                       "event_time", "scheduled_start"))
            is_closing = _truthy(_first(row, "is_closing", "closing", "is_close"))
            # A live price is not a pre-game price and the two must never be
            # compared - see the CLV guardrail in `db.measure_clv`.
            is_live = (_truthy(_first(row, "is_live", "live", "in_play", "inplay"))
                       or str(market_type).strip().lower() in ("live", "inplay", "in_play"))

            if not (event_id and selection and book and price):
                skipped.append(f"{path.name}:{line_no} missing event/selection/book/odds")
                continue
            try:
                quote = parse_odds(price, fmt=odds_format
                                   or (_first(row, "odds_format") or None))
            except OddsFormatError as e:
                skipped.append(f"{path.name}:{line_no} unreadable odds {price!r} - {e}")
                continue
            if quote is None or quote.decimal <= 1.0:
                skipped.append(f"{path.name}:{line_no} odds {price!r} are not a valid price")
                continue

            book_key = canonical_book(book)
            sharp = (_truthy(row["is_sharp"]) if row.get("is_sharp")
                     else book_key in SHARP_BOOKS)
            # Keyed by the UNSIGNED number so both legs of a spread share one
            # market; the quote keeps the signed handicap it was quoted at.
            markets.setdefault((event_id, sport, market_type, market_line_key(line)), []).append(
                MarketQuote(book=book_key, selection=selection,
                            decimal_odds=quote.decimal, is_sharp=sharp,
                            quoted_at=quoted_at, is_closing=is_closing,
                            is_live=is_live, start_time=start_time, line=line))
    return markets, rows_read, skipped


def _parse_timestamp(text: str) -> Optional[datetime]:
    """Quote capture time, or None when the export carries none."""
    if not text:
        return None
    try:
        return as_naive_utc(parse_iso_date(text))
    except (ValueError, TypeError):
        return None


def max_quote_age(sport: str, market_type: str,
                  seconds_to_start: Optional[float] = None) -> float:
    """
    Strictest applicable staleness threshold, in seconds.

    Both the sport and the market type are consulted and the SMALLER wins, so an
    in-play market on a slow sport still gets the in-play limit.

    `seconds_to_start` halves the threshold inside the last hour before kickoff.
    That is where the line moves fastest - late injury news, lineup confirmation,
    and the steam that follows - so a quote that was fresh enough at noon is not
    fresh enough at kickoff minus ten minutes. A negative value (the event has
    started) keeps the tightening rather than reverting: a pre-game price quoted
    after the ball is in the air is the stalest thing in the file.
    """
    candidates = [MAX_QUOTE_AGE_SECONDS[key]
                  for key in (str(sport or "").strip().lower(),
                              str(market_type or "").strip().lower())
                  if key in MAX_QUOTE_AGE_SECONDS]
    limit = float(min(candidates)) if candidates else float(DEFAULT_MAX_QUOTE_AGE_SECONDS)
    if seconds_to_start is not None and seconds_to_start <= NEAR_START_WINDOW_SECONDS:
        limit *= NEAR_START_TIGHTENING
    return limit


def drop_stale_quotes(quotes: List[MarketQuote], sport: str,
                      market_type: str) -> Tuple[List[MarketQuote], List[str]]:
    """
    Removes quotes older than the sport threshold, measured against the NEWEST
    quote in the same market rather than against the wall clock.

    Relative, not absolute, on purpose: a file imported the morning after a scrape
    is entirely valid as long as its quotes are contemporaneous with each other.
    What is never valid is comparing prices captured far apart, because the market
    moved in between and the gap reads as edge.

    An export with no timestamps at all cannot be checked. It is passed through
    with a note rather than refused - the ledger has always preferred a warned
    import to a silent gap - but nothing about it is verified.
    """
    timed = [q for q in quotes if q.quoted_at is not None]
    if not timed:
        return quotes, ["no quote timestamps present - staleness unchecked"]
    if len(timed) < len(quotes):
        return quotes, [f"{len(quotes) - len(timed)} quote(s) carry no timestamp - "
                        f"staleness unchecked for the market"]

    newest = max(q.quoted_at for q in timed)
    starts = [q.start_time for q in quotes if q.start_time is not None]
    seconds_to_start = ((min(starts) - newest).total_seconds() if starts else None)
    limit = max_quote_age(sport, market_type, seconds_to_start)
    fresh, notes = [], []
    for quote in quotes:
        age = (newest - quote.quoted_at).total_seconds()
        if age > limit:
            notes.append(f"{quote.book}/{quote.selection} is {age:.0f}s old against a "
                         f"{limit:.0f}s limit - dropped as stale")
        else:
            fresh.append(quote)
    return fresh, notes


def price_market(quotes: List[MarketQuote],
                 oracle_tolerance: Optional[float] = None):
    """
    Devigs the sharp book and returns (fair_value_result, sharp_book, sharp_legs).

    Raises `OddsImportError` when there is no sharp reference, or when the sharp
    book quotes fewer than two legs. Both are refusals rather than fallbacks: a
    fair price derived from a retail book is not a fair price, and a partial
    market devigs cleanly and wrongly.
    """
    sharp_books = sorted({q.book for q in quotes if q.is_sharp})
    if not sharp_books:
        raise OddsImportError(
            "no sharp book in this market. Devigging a retail book yields that "
            f"book's opinion minus its margin, not a fair price - add a quote from "
            f"one of {sorted(SHARP_BOOKS)} or mark one with an `is_sharp` column.")
    if len(sharp_books) > 1:
        # Two references disagree by construction; picking one silently would
        # make the edge depend on row order.
        raise OddsImportError(
            f"more than one sharp book quoted ({sharp_books}). Pick a single "
            f"reference per market - otherwise the fair value depends on which "
            f"row happened to come first.")

    sharp_book = sharp_books[0]
    sharp_legs = [q for q in quotes if q.book == sharp_book]
    if len(sharp_legs) < 2:
        raise OddsImportError(
            f"sharp book {sharp_book!r} quotes only {len(sharp_legs)} leg(s). A market "
            f"missing a leg devigs cleanly and WRONGLY - there is no way to detect it "
            f"from the numbers, so it is refused here instead.")

    kwargs = {} if oracle_tolerance is None else {"oracle_tolerance": oracle_tolerance}
    result = calculate_fair_value([q.decimal_odds for q in sharp_legs], **kwargs)
    return result, sharp_book, sharp_legs


class OddsWatcher:
    """
    Polls a drop folder and prices whatever lands in it.

    `scan_once()` is the whole engine; `watch()` calls it on a timer. Both are
    safe to run repeatedly: a file is processed once because its content hash is
    recorded, and then MOVED out of the folder.
    """

    def __init__(self, drop_folder: Optional[Path] = None,
                 db_path: Optional[Path] = None,
                 stability_seconds: float = DEFAULT_STABILITY_SECONDS,
                 after_tax_hurdle: Optional[Union[float, Callable[[float], float]]] = None,
                 oracle_tolerance: Optional[float] = None,
                 min_edge: Optional[float] = None,
                 archive: bool = True):
        self.drop_folder = Path(drop_folder or DEFAULT_DROP_FOLDER)
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.stability_seconds = float(stability_seconds)
        # THE HURDLE IS A FUNCTION OF THE ODDS, NOT A CONSTANT. It rises from
        # 16.3% at 1.50 to 49.7% at +1000 under a standard deduction, because the
        # tax is charged on a bigger win while the loss still relieves nothing.
        # Passing one number computed at even money therefore marks longshots as
        # tradeable when they are after-tax losses - a false positive concentrated
        # exactly where the damage is worst, and one that made this table disagree
        # with the order gate, which has always computed it per-odds.
        #
        # So a CALLABLE is the real interface: `f(decimal_odds) -> hurdle`, which
        # `monarch_hook.breakeven_gross_edge` already satisfies. A bare float is
        # still accepted for a caller that genuinely wants a flat threshold, and
        # is reported as flat so nobody mistakes it for the tax computation.
        self.after_tax_hurdle = after_tax_hurdle
        self._hurdle_is_flat = isinstance(after_tax_hurdle, (int, float))
        self.oracle_tolerance = oracle_tolerance
        # None = record EVERY quote, including negative edges. That is the right
        # default for a provenance store: a losing price today is the closing-line
        # comparison tomorrow, and a table that only ever kept the winners cannot
        # answer whether the model was beating the close. Filter on read instead,
        # via `query_edges(min_edge=...)`.
        self.min_edge = None if min_edge is None else float(min_edge)
        self.archive = archive
        self._seen: Dict[Path, Tuple[int, float, float]] = {}
        self.drop_folder.mkdir(parents=True, exist_ok=True)
        init_market_db(self.db_path)

    def hurdle_for(self, decimal_odds: float) -> Optional[float]:
        """The after-tax hurdle at THIS price, or None when none was supplied."""
        if self.after_tax_hurdle is None:
            return None
        if callable(self.after_tax_hurdle):
            try:
                return float(self.after_tax_hurdle(float(decimal_odds)))
            except Exception as e:                       # noqa: BLE001
                print(f"[WARN] hurdle callable failed at odds {decimal_odds}: {e}. "
                      f"Recording no hurdle for that row rather than a wrong one.")
                return None
        return float(self.after_tax_hurdle)

    # -- stability ----------------------------------------------------------

    def _is_stable(self, path: Path, now: Optional[float] = None) -> bool:
        """
        True once the file has reported identical size and mtime on two polls at
        least `stability_seconds` apart. A large export is visible long before it
        is complete, and a truncated market is indistinguishable from a market
        with fewer legs.
        """
        now = time.time() if now is None else now
        try:
            stat = path.stat()
        except OSError:
            return False
        current = (stat.st_size, stat.st_mtime)
        previous = self._seen.get(path)
        if previous is None or previous[:2] != current:
            self._seen[path] = (current[0], current[1], now)
            return False
        return (now - previous[2]) >= self.stability_seconds

    # -- import -------------------------------------------------------------

    def process_file(self, path: Path,
                     odds_format: Optional[str] = None) -> ImportReport:
        """Prices one file. Does not move it - `scan_once` owns that."""
        report = ImportReport(filename=path.name)
        report.content_hash = content_hash(path)
        if already_imported(report.content_hash, db_path=self.db_path):
            report.duplicate = True
            return report

        markets, rows_read, skipped = parse_odds_csv(path, odds_format)
        report.rows_read = rows_read
        report.skipped.extend(skipped)
        report.markets_seen = len(markets)
        now_ts = datetime.now(timezone.utc).isoformat()

        for (event_id, sport, market_type, line), quotes in markets.items():
            label = f"{event_id}/{market_type}" + (f"@{line}" if line else "")

            # STALENESS FIRST: a stale quote must never reach the devigger, and a
            # market that loses a sharp leg to staleness is unpriceable, not
            # priceable-with-fewer-legs.
            before = len(quotes)
            quotes, stale_notes = drop_stale_quotes(quotes, sport, market_type)
            report.stale_dropped += before - len(quotes)
            for note in stale_notes:
                report.skipped.append(f"{label}: {note}")

            try:
                result, sharp_book, sharp_legs = price_market(quotes, self.oracle_tolerance)
            except ArbitrageError as e:
                # The one result a scanner most wants. Not an import failure.
                report.arbitrages.append(
                    f"{label}: {sharp_or_unknown(quotes)} booksum "
                    f"{e.booksum:.4f} -> {e.edge_pct:.2f}% arbitrage")
                continue
            except (OddsImportError, DevigError) as e:
                report.skipped.append(f"{label} not priced - {e}")
                continue

            report.markets_priced += 1
            sharp_selections = [q.selection for q in sharp_legs]
            sharp_quotes = {q.selection: q.decimal_odds for q in sharp_legs}
            market_is_closing = any(q.is_closing for q in sharp_legs)
            market_is_live = any(q.is_live for q in sharp_legs)
            quoted_at = next((q.quoted_at for q in sharp_legs if q.quoted_at), None)
            start_time = next((q.start_time for q in sharp_legs if q.start_time), None)
            record_fair_value_measurement(
                event_id=event_id, sport=sport, selections=sharp_selections,
                market_type=market_type, sportsbook=sharp_book, result=result,
                timestamp=now_ts, line=line,
                # Each leg is stored under ITS OWN signed handicap (Ruling 5.B).
                lines=[q.line or line for q in sharp_legs],
                is_closing=market_is_closing,
                is_live=market_is_live,
                quoted_at=quoted_at.isoformat() if quoted_at else None,
                start_time=start_time.isoformat() if start_time else None,
                db_path=self.db_path)

            # MEMBERSHIP IS ENFORCED ON THE NORMALISED KEY. A retail selection
            # that is not in the devigged sharp set has no fair price, so there is
            # no edge to compute and pretending otherwise would score it against
            # some other runner. Matching on the normalised key rather than the
            # raw string stops `Chiefs` and `chiefs ` from counting as different
            # runners, which would drop every retail quote in the market and look
            # like a market nobody else quoted.
            fair_by_key = {q.key: fair for q, fair in zip(sharp_legs,
                                                          result.fair_probabilities)}
            sharp_odds_by_key = {q.key: q.decimal_odds for q in sharp_legs}

            for quote in quotes:
                if quote.book == sharp_book:
                    continue
                fair = fair_by_key.get(quote.key)
                if fair is None:
                    report.skipped.append(
                        f"{label}: {quote.book} quotes {quote.selection!r}, which is not "
                        f"in the devigged sharp set {sorted(fair_by_key)} - no fair price "
                        f"exists for it, so no edge can be computed")
                    continue
                edge = calculate_edge(fair, quote.decimal_odds)
                if self.min_edge is not None and edge < self.min_edge:
                    continue
                record_edge_opportunity(
                    event_id=event_id, sport=sport, market_type=market_type,
                    selection=quote.selection, sharp_book=sharp_book,
                    sharp_offered_odds=sharp_odds_by_key[quote.key],
                    sharp_fair_prob=fair, sharp_overround=result.overround,
                    sharp_quotes=sharp_quotes, sharp_divergent=result.divergent,
                    sharp_trustworthy=result.trustworthy,
                    retail_book=quote.book, retail_offered_odds=quote.decimal_odds,
                    gross_edge=edge, after_tax_hurdle=self.hurdle_for(quote.decimal_odds),
                    source_file=path.name, content_hash=report.content_hash,
                    timestamp=now_ts, line=quote.line or line,
                    is_closing=quote.is_closing or market_is_closing,
                    is_live=quote.is_live or market_is_live,
                    quoted_at=quote.quoted_at.isoformat() if quote.quoted_at else None,
                    start_time=(quote.start_time or start_time).isoformat()
                    if (quote.start_time or start_time) else None,
                    db_path=self.db_path)
                report.edges_found += 1

        record_import(report.content_hash, path.name, report.rows_read,
                      report.markets_priced, report.edges_found,
                      timestamp=now_ts, db_path=self.db_path)
        return report

    # -- folder -------------------------------------------------------------

    def scan_once(self, now: Optional[float] = None,
                  odds_format: Optional[str] = None) -> List[ImportReport]:
        """One pass over the drop folder. Returns a report per file processed."""
        reports: List[ImportReport] = []
        for path in sorted(self.drop_folder.glob("*.csv")):
            if not path.is_file() or not self._is_stable(path, now):
                continue
            try:
                report = self.process_file(path, odds_format)
                destination = "processed"
            except Exception as e:                      # noqa: BLE001 - a bad file
                report = ImportReport(filename=path.name)   # must not stop the folder
                report.skipped.append(f"{path.name} failed to import - {e}")
                destination = "failed"
            reports.append(report)
            self._seen.pop(path, None)
            if self.archive:
                self._move(path, destination)
        return reports

    def _move(self, path: Path, destination: str) -> None:
        target_dir = self.drop_folder / destination
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            target = target_dir / f"{path.stem}_{stamp}{path.suffix}"
        shutil.move(str(path), str(target))

    def watch(self, poll_interval: float = 5.0) -> None:
        """Blocking poll loop. Ctrl-C to stop."""
        print(f"[WATCH] {self.drop_folder} every {poll_interval:.0f}s "
              f"(sharp references: {sorted(SHARP_BOOKS)})")
        while True:
            for report in self.scan_once():
                print(report.summary())
            time.sleep(poll_interval)


def sharp_or_unknown(quotes: List[MarketQuote]) -> str:
    sharp = sorted({q.book for q in quotes if q.is_sharp})
    return sharp[0] if sharp else "unknown book"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sports_Desk odds drop-folder watcher")
    parser.add_argument("--folder", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--once", action="store_true", help="single pass, then exit")
    parser.add_argument("--poll", type=float, default=5.0)
    parser.add_argument("--min-edge", type=float, default=None,
                        help="only record edges at or above this (0.03 = 3%%). "
                             "Omit to record every quote, which is what CLV needs.")
    parser.add_argument("--hurdle", type=float, default=None,
                        help="FLAT after-tax hurdle, stored per row. The real hurdle "
                             "varies with the odds - prefer --hurdle-from-ledger.")
    parser.add_argument("--hurdle-from-ledger", action="store_true",
                        help="compute the after-tax hurdle per row from the tax "
                             "ledger's own gambling treatment (the correct option)")
    parser.add_argument("--odds-format", choices=("american", "decimal", "fractional"),
                        default=None)
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args(argv)

    hurdle: Optional[Union[float, Callable[[float], float]]] = args.hurdle
    if args.hurdle_from_ledger:
        # Sports_Desk already depends on Tax_Reserve_Agent, so this direction is
        # fine. The reverse - the ledger reading sports_market.db - would be a
        # dependency cycle and is deliberately never done.
        from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
        ledger = get_hook()
        hurdle = lambda odds: ledger.breakeven_gross_edge(   # noqa: E731
            category="sports", decimal_odds=odds)

    watcher = OddsWatcher(drop_folder=args.folder, db_path=args.db,
                          after_tax_hurdle=hurdle, min_edge=args.min_edge,
                          archive=not args.no_archive)
    if args.once:
        # A single pass still honours the two-poll rule, so prime it first.
        watcher.scan_once(odds_format=args.odds_format)
        for report in watcher.scan_once(now=time.time() + watcher.stability_seconds,
                                        odds_format=args.odds_format):
            print(report.summary())
        return 0
    watcher.watch(args.poll)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
