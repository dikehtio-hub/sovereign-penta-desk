"""
Stale-quote and latency arbitrage core (Round 64, Directive 64-3 groundwork).

The idea: sharp books (Pinnacle, Circa, Bookmaker) move first on information;
slow retail books re-quote later. In the window between, a retail quote on the
outcome the sharp book just SHORTENED is priced off the old consensus and is
cheap. This module finds those windows from timestamped quotes and nothing
else - no execution, no network, no state.

Definitions (all in implied-probability points, because odds formats differ):

  * sharp move       - two consecutive quotes from one sharp book on one selection
                       whose implied probability differs by >= MIN_SHARP_MOVE_PROB
                       and whose VELOCITY (points per minute between the two
                       quotes) is >= MIN_VELOCITY_PROB_PER_MIN. A big move over
                       three hours is drift; a small move in a minute is vig wobble.
  * stale retail     - the LATEST quote a retail book has on that selection was
                       quoted at least MIN_RETAIL_LAG_SECONDS before the sharp move
                       finished (the book has not re-quoted since), is at most
                       MAX_QUOTE_AGE_SECONDS old (older quotes may be pulled), and
                       the edge sharp_to_prob - retail_implied_prob is at least
                       MIN_EDGE_PROB. A sharp DRIFT (probability down) makes the
                       stale retail quote overpriced, not cheap: counted, not flagged.

Thresholds are named constants with the reasoning beside them; they are the
first thing a live run should re-tune from measured line moves.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SHARP_BOOKS = frozenset({"pinnacle", "circa", "bookmaker", "betcris"})
MIN_SHARP_MOVE_PROB = 0.02             # 2 points: a moneyline going -110 -> -120 is ~1.9 pts; below is wobble
MIN_VELOCITY_PROB_PER_MIN = 0.005      # 0.5 pt/min: 2 pts inside 4 min is information; 2 pts over an hour is drift
MIN_RETAIL_LAG_SECONDS = 60            # retail must be at least a minute behind the move's end to be "stale"
MAX_QUOTE_AGE_SECONDS = 900            # a quote older than 15 min may already be pulled; not actionable
MIN_EDGE_PROB = 0.02                   # 2 pts of edge vs the sharp post-move price, before vig and tax
DEFAULT_LOOKBACK_MINUTES = 180

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "sports_market.db"


def implied(decimal_odds: float) -> float:
    odds = float(decimal_odds)
    if odds <= 1.0:
        raise ValueError("decimal odds must exceed 1.0")
    return 1.0 / odds


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def parse_moment(text: Any) -> Optional[datetime]:
    """ISO text (Z or offset) to an aware UTC datetime; None when unreadable."""
    if isinstance(text, datetime):
        return _utc(text)
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return _utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        return None


@dataclass(frozen=True)
class Quote:
    book: str
    selection: str
    decimal_odds: float
    quoted_at: datetime
    event_id: str = ""
    market_type: str = ""
    line: str = ""

    @property
    def implied_prob(self) -> float:
        return implied(self.decimal_odds)

    @property
    def key(self) -> Tuple[str, str, str, str]:
        return (self.event_id, self.market_type, self.line, self.selection)


def is_sharp(book: str, sharp_books: Iterable[str] = SHARP_BOOKS) -> bool:
    return str(book or "").strip().lower() in {str(b).lower() for b in sharp_books}


@dataclass(frozen=True)
class SharpMove:
    book: str
    event_id: str
    market_type: str
    line: str
    selection: str
    from_odds: float
    to_odds: float
    started_at: datetime
    ended_at: datetime

    @property
    def from_prob(self) -> float:
        return implied(self.from_odds)

    @property
    def to_prob(self) -> float:
        return implied(self.to_odds)

    @property
    def delta_prob(self) -> float:
        return self.to_prob - self.from_prob

    @property
    def minutes(self) -> float:
        return max((self.ended_at - self.started_at).total_seconds() / 60.0, 1e-9)

    @property
    def velocity(self) -> float:
        """Implied-probability points per minute, signed."""
        return self.delta_prob / self.minutes

    @property
    def direction(self) -> str:
        return "shortened" if self.delta_prob > 0 else "drifted"


@dataclass(frozen=True)
class StaleQuote:
    retail_book: str
    retail_odds: float
    retail_quoted_at: datetime
    move: SharpMove
    lag_seconds: float                   # how long the retail quote predates the move's end
    age_seconds: float                   # how old the retail quote is now
    edge_prob: float                     # sharp post-move prob minus retail implied prob

    @property
    def selection(self) -> str:
        return self.move.selection

    @property
    def event_id(self) -> str:
        return self.move.event_id

    @property
    def retail_prob(self) -> float:
        return implied(self.retail_odds)


@dataclass
class StaleScan:
    moves: List[SharpMove] = field(default_factory=list)
    hits: List[StaleQuote] = field(default_factory=list)
    overpriced: int = 0                  # stale retail quotes on a DRIFTED selection (not cheap)
    too_old: int = 0
    not_stale: int = 0                   # retail re-quoted after the move
    thin_edge: int = 0


def detect_sharp_moves(quotes: Sequence[Quote], min_move: float = MIN_SHARP_MOVE_PROB,
                       min_velocity: float = MIN_VELOCITY_PROB_PER_MIN,
                       sharp_books: Iterable[str] = SHARP_BOOKS) -> List[SharpMove]:
    """
    The most recent qualifying move per (sharp book, event, market, line,
    selection): consecutive quotes whose implied probability changed by at least
    `min_move` at a velocity of at least `min_velocity` points per minute.
    """
    series: Dict[Tuple[str, str, str, str, str], List[Quote]] = {}
    for q in quotes:
        if is_sharp(q.book, sharp_books):
            series.setdefault((q.book.lower(),) + q.key, []).append(q)
    moves: List[SharpMove] = []
    for run in series.values():
        run = sorted(run, key=lambda q: q.quoted_at)
        latest: Optional[SharpMove] = None
        for prev, cur in zip(run, run[1:]):
            if cur.quoted_at <= prev.quoted_at:
                continue
            candidate = SharpMove(book=prev.book, event_id=prev.event_id, market_type=prev.market_type,
                                  line=prev.line, selection=prev.selection, from_odds=prev.decimal_odds,
                                  to_odds=cur.decimal_odds, started_at=prev.quoted_at, ended_at=cur.quoted_at)
            if abs(candidate.delta_prob) >= min_move and abs(candidate.velocity) >= min_velocity:
                latest = candidate
        if latest is not None:
            moves.append(latest)
    moves.sort(key=lambda m: m.ended_at)
    return moves


def find_stale_quotes(quotes: Sequence[Quote], now: Optional[datetime] = None,
                      min_move: float = MIN_SHARP_MOVE_PROB, min_velocity: float = MIN_VELOCITY_PROB_PER_MIN,
                      min_lag_seconds: float = MIN_RETAIL_LAG_SECONDS, max_age_seconds: float = MAX_QUOTE_AGE_SECONDS,
                      min_edge: float = MIN_EDGE_PROB, sharp_books: Iterable[str] = SHARP_BOOKS) -> StaleScan:
    """
    For every sharp move, the retail books whose LATEST quote on that selection
    predates the move's end by at least `min_lag_seconds`, is at most
    `max_age_seconds` old, and is cheap by at least `min_edge` against the sharp
    post-move price. Drifted selections are counted as overpriced, not flagged.
    """
    now = _utc(now) if now else datetime.now(timezone.utc)
    scan = StaleScan(moves=detect_sharp_moves(quotes, min_move, min_velocity, sharp_books))
    latest_retail: Dict[Tuple[str, str, str, str], Dict[str, Quote]] = {}
    for q in quotes:
        if is_sharp(q.book, sharp_books):
            continue
        book = q.book.lower()
        current = latest_retail.setdefault(q.key, {}).get(book)
        if current is None or q.quoted_at > current.quoted_at:
            latest_retail[q.key][book] = q
    for move in scan.moves:
        for retail in latest_retail.get((move.event_id, move.market_type, move.line, move.selection), {}).values():
            lag = (move.ended_at - retail.quoted_at).total_seconds()
            age = (now - retail.quoted_at).total_seconds()
            if lag < min_lag_seconds:
                scan.not_stale += 1
                continue
            if age > max_age_seconds:
                scan.too_old += 1
                continue
            edge = move.to_prob - retail.implied_prob
            if move.direction != "shortened" or edge < 0:
                scan.overpriced += 1
                continue
            if edge < min_edge:
                scan.thin_edge += 1
                continue
            scan.hits.append(StaleQuote(retail_book=retail.book, retail_odds=retail.decimal_odds,
                                        retail_quoted_at=retail.quoted_at, move=move, lag_seconds=lag,
                                        age_seconds=age, edge_prob=edge))
    scan.hits.sort(key=lambda h: -h.edge_prob)
    return scan


def load_quotes(db_path: Path = DEFAULT_DB_PATH, now: Optional[datetime] = None,
                lookback_minutes: float = DEFAULT_LOOKBACK_MINUTES) -> List[Quote]:
    """Quotes from fair_odds_measurements within the lookback (quoted_at, else the row timestamp)."""
    now = _utc(now) if now else datetime.now(timezone.utc)
    since = now - timedelta(minutes=lookback_minutes)
    try:
        con = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    except sqlite3.Error:
        return []
    try:
        rows = con.execute("SELECT COALESCE(quoted_at, timestamp), event_id, market_type, line, sportsbook, "
                           "selection, offered_odds FROM fair_odds_measurements WHERE offered_odds > 1.0").fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    quotes: List[Quote] = []
    for stamp, event_id, market_type, line, book, selection, odds in rows:
        moment = parse_moment(stamp)
        if moment is None or moment < since or moment > now + timedelta(minutes=5):
            continue
        quotes.append(Quote(book=str(book), selection=str(selection), decimal_odds=float(odds), quoted_at=moment,
                            event_id=str(event_id), market_type=str(market_type), line=str(line or "")))
    return quotes


def scan_market_db(db_path: Path = DEFAULT_DB_PATH, now: Optional[datetime] = None,
                   lookback_minutes: float = DEFAULT_LOOKBACK_MINUTES, **thresholds: Any) -> StaleScan:
    return find_stale_quotes(load_quotes(db_path, now, lookback_minutes), now=now, **thresholds)


def render_stale_quotes(scan: StaleScan, now: Optional[datetime] = None) -> str:
    lines = ["[STALE] sharp moves: %d (>= %.1f pts at >= %.2f pts/min); stale retail quotes flagged: %d "
             "(lag >= %ds, age <= %ds, edge >= %.1f pts); overpriced %d, re-quoted %d, too old %d, thin edge %d"
             % (len(scan.moves), MIN_SHARP_MOVE_PROB * 100, MIN_VELOCITY_PROB_PER_MIN * 100, len(scan.hits),
                MIN_RETAIL_LAG_SECONDS, MAX_QUOTE_AGE_SECONDS, MIN_EDGE_PROB * 100, scan.overpriced, scan.not_stale,
                scan.too_old, scan.thin_edge)]
    for move in scan.moves:
        lines.append("[STALE]   %s %s %s %s: %s %.3f -> %.3f (%+.1f pts in %.1f min, %.2f pts/min)"
                     % (move.book, move.event_id, move.market_type, move.selection, move.direction, move.from_odds,
                        move.to_odds, move.delta_prob * 100, move.minutes, abs(move.velocity) * 100))
    for hit in scan.hits:
        lines.append("[STALE]     %s still %.3f on %s (quoted %ds before the move ended, %ds old): edge %+.1f pts vs sharp %.3f"
                     % (hit.retail_book, hit.retail_odds, hit.selection, int(hit.lag_seconds), int(hit.age_seconds),
                        hit.edge_prob * 100, hit.move.to_odds))
    if not scan.moves:
        lines.append("[STALE]   no sharp move in the window - nothing can be stale relative to it")
    return "\n".join(lines)
