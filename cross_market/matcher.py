"""
Match Polymarket sports markets to `sports_market.db` events.

THE FAILURE MODE THIS MODULE EXISTS TO PREVENT

A pricing error in a hedge costs a few basis points. A MATCHING error costs the
whole position, because the two legs stop being a hedge and become the same bet
placed twice. If "Kansas City Chiefs" is matched to a Kansas City ROYALS market,
or a YES on "Chiefs win" is paired with a sportsbook bet ON the Chiefs rather
than against them, the desk ends up with double exposure to one outcome while
the ledger records a riskless arbitrage. Nothing downstream can detect that: the
tax engine, the sizer and the HUD will all faithfully price a position that does
not exist.

So this module refuses far more than it guesses. Three rules follow from that:

  1. NICKNAME IS THE KEY, CITY IS ONLY A DISAMBIGUATOR. Kansas City fields the
     Chiefs and the Royals; New York fields the Giants and the Jets; Los Angeles
     fields the Kings, the Lakers, the Clippers, the Rams, the Chargers and the
     Dodgers. Matching on city is not matching.

  2. AMBIGUITY IS AN ERROR, NOT A TIE-BREAK. "Cardinals" is Arizona in the NFL
     and St. Louis in MLB; "Panthers" is Carolina in the NFL and Florida in the
     NHL; "Kings" is Los Angeles in the NHL and Sacramento in the NBA. Within one
     sport these are unique, so a resolution without a sport that hits more than
     one canonical team returns no match rather than the first one.

  3. THE HEDGE MUST BE PROVED OPPOSITE, NOT ASSUMED. `hedge_leg_for` derives the
     complementary selection from the market type, and returns None when it
     cannot. A moneyline YES on one team hedges the other team; an Over hedges
     the Under AT THE SAME TOTAL; a spread hedges the mirrored handicap AND ONLY
     at the same number. Pairing -3.5 against +7.5 is not a hedge, it is two bets
     with a four-point hole in the middle, and a half-point difference is the
     difference between a hedge and a middle.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_DB_PATH = (Path(__file__).resolve().parent.parent
                   / "Sports_Desk" / "data" / "sports_market.db")

MONEYLINE, SPREAD, TOTALS = "moneyline", "spread", "totals"
SUPPORTED_MARKETS = (MONEYLINE, SPREAD, TOTALS)


class MatchError(ValueError):
    """A market could not be matched, and guessing is not an option."""


# --------------------------------------------------------------------------
# Team identity
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Team:
    canonical: str
    sport: str
    city: str
    nickname: str
    abbreviations: Tuple[str, ...] = ()


def _t(canonical, sport, city, nickname, *abbr):
    return Team(canonical, sport, city, nickname, tuple(abbr))


# Deliberately not exhaustive. Every entry here is one the desk can trade; a team
# that is absent produces NO MATCH, which is the safe outcome. Adding a team is a
# one-line change, and it is better to add teams on demand than to ship a fuzzy
# matcher that covers everything and is right most of the time.
TEAMS: Tuple[Team, ...] = (
    # NFL
    _t("KC_CHIEFS", "NFL", "Kansas City", "Chiefs", "KC", "KAN"),
    _t("BUF_BILLS", "NFL", "Buffalo", "Bills", "BUF"),
    _t("SF_49ERS", "NFL", "San Francisco", "49ers", "SF", "SFO", "NINERS"),
    _t("PHI_EAGLES", "NFL", "Philadelphia", "Eagles", "PHI"),
    _t("DAL_COWBOYS", "NFL", "Dallas", "Cowboys", "DAL"),
    _t("NYG_GIANTS", "NFL", "New York", "Giants", "NYG"),
    _t("NYJ_JETS", "NFL", "New York", "Jets", "NYJ"),
    _t("BAL_RAVENS", "NFL", "Baltimore", "Ravens", "BAL"),
    _t("CIN_BENGALS", "NFL", "Cincinnati", "Bengals", "CIN"),
    _t("DET_LIONS", "NFL", "Detroit", "Lions", "DET"),
    _t("GB_PACKERS", "NFL", "Green Bay", "Packers", "GB", "GNB"),
    _t("MIA_DOLPHINS", "NFL", "Miami", "Dolphins", "MIA"),
    _t("ARI_CARDINALS", "NFL", "Arizona", "Cardinals", "ARI"),
    _t("CAR_PANTHERS", "NFL", "Carolina", "Panthers", "CAR"),
    _t("LAR_RAMS", "NFL", "Los Angeles", "Rams", "LAR"),
    _t("LAC_CHARGERS", "NFL", "Los Angeles", "Chargers", "LAC"),
    # NBA
    _t("BOS_CELTICS", "NBA", "Boston", "Celtics", "BOS"),
    _t("LAL_LAKERS", "NBA", "Los Angeles", "Lakers", "LAL"),
    _t("LAC_CLIPPERS", "NBA", "Los Angeles", "Clippers", "LAC"),
    _t("DEN_NUGGETS", "NBA", "Denver", "Nuggets", "DEN"),
    _t("SAC_KINGS", "NBA", "Sacramento", "Kings", "SAC"),
    _t("NYK_KNICKS", "NBA", "New York", "Knicks", "NYK"),
    # MLB
    _t("KC_ROYALS", "MLB", "Kansas City", "Royals", "KC", "KAN"),
    _t("SF_GIANTS", "MLB", "San Francisco", "Giants", "SF", "SFG"),
    _t("STL_CARDINALS", "MLB", "St. Louis", "Cardinals", "STL"),
    _t("NYY_YANKEES", "MLB", "New York", "Yankees", "NYY"),
    _t("LAD_DODGERS", "MLB", "Los Angeles", "Dodgers", "LAD"),
    # NHL
    _t("LAK_KINGS", "NHL", "Los Angeles", "Kings", "LAK"),
    _t("FLA_PANTHERS", "NHL", "Florida", "Panthers", "FLA"),
    _t("NYR_RANGERS", "NHL", "New York", "Rangers", "NYR"),
)

_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_QUESTION_PUNCT = re.compile(r"[^A-Z0-9 .+-]+")
_SPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """
    Upper-case, strip punctuation, collapse whitespace. For TEAM NAMES only.

    Stripping the dot is what makes "St. Louis" and "St Louis" one string, which
    is the point here and actively wrong for a question - see below.
    """
    return _SPACE.sub(" ", _PUNCT.sub(" ", str(text).upper())).strip()


def normalise_question(text: str) -> str:
    """
    The same, but keeping `.` `+` and `-`, which carry the LINE.

    Using the team normaliser on a question turned "by more than 3.5 points" into
    "BY MORE THAN 3 5 POINTS". The spread pattern then failed to match, the
    question fell through to the moneyline branch, and a 3.5-point spread market
    was silently parsed as a moneyline - which would have been hedged against the
    opponent's MONEYLINE. That is not a hedge at all: the book wins whenever the
    favourite wins by less than the handicap, and both legs lose together. The
    separation of the two normalisers is the fix.
    """
    return _SPACE.sub(" ", _QUESTION_PUNCT.sub(" ", str(text).upper())).strip()


def _alias_index() -> Dict[str, List[Team]]:
    """
    Every string that may denote a team, mapped to the teams it could denote.

    A list rather than a single team, because collisions are the point: "GIANTS"
    legitimately maps to two teams and the resolver must SEE that rather than
    have one of them silently win on insertion order.
    """
    index: Dict[str, List[Team]] = {}

    def add(key: str, team: Team) -> None:
        key = normalise(key)
        if key:
            index.setdefault(key, [])
            if team not in index[key]:
                index[key].append(team)

    for team in TEAMS:
        add(team.canonical.replace("_", " "), team)
        add(team.nickname, team)
        add("%s %s" % (team.city, team.nickname), team)
        for abbr in team.abbreviations:
            add(abbr, team)
            add("%s %s" % (abbr, team.nickname), team)
    return index


ALIASES: Dict[str, List[Team]] = _alias_index()


def resolve_team(text: str, sport: Optional[str] = None) -> Optional[Team]:
    """
    Resolve free text to exactly one team, or return None.

    None means "do not trade this", never "pick the likeliest". The whole reason
    the return is optional is that an unresolved market must drop out of the
    pipeline rather than be resolved on a coin flip.
    """
    if not text:
        return None
    key = normalise(text)
    sport = sport.upper() if sport else None

    candidates = list(ALIASES.get(key, ()))
    if not candidates:
        # Fall back to the longest alias that appears as a WHOLE-WORD phrase.
        # Longest-first matters: "KANSAS CITY CHIEFS" must beat the bare "CHIEFS"
        # so the city half is used, and must never be beaten by a shorter alias
        # belonging to a different team.
        padded = " %s " % key
        hits = [(alias, teams) for alias, teams in ALIASES.items()
                if (" %s " % alias) in padded]
        if hits:
            longest = max(len(alias) for alias, _ in hits)
            candidates = [t for alias, teams in hits if len(alias) == longest
                          for t in teams]

    if sport:
        candidates = [t for t in candidates if t.sport == sport]
    unique = {t.canonical: t for t in candidates}
    # Exactly one, or nothing. Two candidates is an ambiguity - "Cardinals" with
    # no sport, say - and resolving it by preference would be inventing an answer.
    return next(iter(unique.values())) if len(unique) == 1 else None


# --------------------------------------------------------------------------
# Polymarket question parsing
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PolymarketMarket:
    """A Polymarket market reduced to the fields a hedge needs."""

    question: str
    market_type: str
    yes_team: Optional[Team]           # team the YES share is long, if applicable
    opponent: Optional[Team]
    line: str = ""                     # spread handicap or total, as text
    yes_side: str = ""                 # "OVER" / "UNDER" for totals
    token_id: str = ""
    yes_price: Optional[float] = None
    sport: str = ""

    @property
    def event_key(self) -> str:
        teams = sorted(t.canonical for t in (self.yes_team, self.opponent) if t)
        return "|".join(teams)


_WIN_PATTERNS = (
    re.compile(r"^WILL (?:THE )?(?P<a>.+?) (?:BEAT|DEFEAT) (?:THE )?(?P<b>.+?)\??$"),
    re.compile(r"^WILL (?:THE )?(?P<a>.+?) WIN (?:AGAINST|VS|VERSUS) (?:THE )?(?P<b>.+?)\??$"),
)
_VS_WINNER = re.compile(r"^(?P<a>.+?) (?:VS|V|AT|@) (?P<b>.+?)(?: WINNER| MONEYLINE)?\??$")
_SPREAD_PATTERN = re.compile(
    r"^WILL (?:THE )?(?P<a>.+?) (?:BEAT|DEFEAT) (?:THE )?(?P<b>.+?) BY "
    r"(?:MORE THAN |OVER )?(?P<line>[0-9]+(?:\.[0-9]+)?) (?:POINTS?|RUNS?|GOALS?)\??$")
_TOTAL_PATTERN = re.compile(
    r"^WILL (?:THE )?(?P<a>.+?) (?:VS|V|AT|@) (?:THE )?(?P<b>.+?) "
    r"(?:TOTAL |COMBINED SCORE )?(?:GO )?(?P<side>OVER|UNDER) "
    r"(?P<line>[0-9]+(?:\.[0-9]+)?)(?: POINTS?| RUNS?| GOALS?)?\??$")


def parse_polymarket_question(question: str, sport: Optional[str] = None,
                              token_id: str = "",
                              yes_price: Optional[float] = None
                              ) -> Optional[PolymarketMarket]:
    """
    Turn a Polymarket question into a structured market, or return None.

    Only shapes the desk has actually seen are parsed. An unrecognised question
    returns None and drops out, because a market whose MEANING is guessed cannot
    be hedged safely - the direction of the YES share is exactly what a guess
    would get wrong, and getting it backwards doubles the exposure instead of
    cancelling it.
    """
    text = normalise_question(question)
    if not text:
        return None

    match = _TOTAL_PATTERN.match(text)
    if match:
        a = resolve_team(match.group("a"), sport)
        b = resolve_team(match.group("b"), sport)
        if not _valid_fixture(a, b):
            return None
        return PolymarketMarket(question, TOTALS, a, b,
                                line=_tidy_line(match.group("line")),
                                yes_side=match.group("side"), token_id=token_id,
                                yes_price=yes_price, sport=a.sport)

    match = _SPREAD_PATTERN.match(text)
    if match:
        a = resolve_team(match.group("a"), sport)
        b = resolve_team(match.group("b"), sport)
        if not _valid_fixture(a, b):
            return None
        # "Beat B by more than N" is A giving N away: the handicap is negative.
        return PolymarketMarket(question, SPREAD, a, b,
                                line="-" + _tidy_line(match.group("line")),
                                token_id=token_id, yes_price=yes_price,
                                sport=a.sport)

    for pattern in _WIN_PATTERNS:
        match = pattern.match(text)
        if match:
            a = resolve_team(match.group("a"), sport)
            b = resolve_team(match.group("b"), sport)
            if not _valid_fixture(a, b):
                return None
            return PolymarketMarket(question, MONEYLINE, a, b, token_id=token_id,
                                    yes_price=yes_price, sport=a.sport)

    match = _VS_WINNER.match(text)
    if match:
        a = resolve_team(match.group("a"), sport)
        b = resolve_team(match.group("b"), sport)
        if not _valid_fixture(a, b):
            return None
        # A bare "A vs B" names the fixture but NOT which side the YES share is.
        # Without that the hedge direction is unknown, so it is not tradeable.
        return None
    return None


def _valid_fixture(a: Optional[Team], b: Optional[Team]) -> bool:
    """
    Two DIFFERENT teams from the SAME sport, or it is not a fixture.

    The same-sport half was missing and "Will the Chiefs beat the Royals?" parsed
    cleanly into an NFL-versus-MLB market. Each name resolves fine on its own; it
    is only the pair that is nonsense. A fixture that cannot exist must not reach
    the hedger, because every check downstream is about PRICE and would pass it.
    """
    return bool(a and b and a.canonical != b.canonical and a.sport == b.sport)


def _tidy_line(raw: str) -> str:
    """Normalise 3, 3.0 and 3.50 to a single spelling so lines compare equal."""
    return "%.1f" % float(raw)


# --------------------------------------------------------------------------
# The hedge relation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HedgeTarget:
    """The sportsbook side that hedges a given Polymarket YES."""

    sport: str
    market_type: str
    line: str
    selection: str                     # canonical team, or OVER / UNDER
    rationale: str


def hedge_leg_for(market: PolymarketMarket) -> Optional[HedgeTarget]:
    """
    The sportsbook selection that is genuinely OPPOSITE a Polymarket YES.

    Returns None when the complement cannot be derived. That is not a shortfall
    to be patched later: a hedge whose opposite side is uncertain is not a hedge,
    and the only safe response is to decline the pair.
    """
    if market.market_type == MONEYLINE:
        if not market.opponent:
            return None
        return HedgeTarget(
            market.sport, MONEYLINE, "", market.opponent.canonical,
            "YES on this market pays when %s WINS, so the hedge is %s - the "
            "opposite side of the same fixture." % (market.yes_team.canonical,
                                                    market.opponent.canonical))

    if market.market_type == TOTALS:
        if market.yes_side not in ("OVER", "UNDER"):
            return None
        other = "UNDER" if market.yes_side == "OVER" else "OVER"
        return HedgeTarget(
            market.sport, TOTALS, market.line, other,
            "YES on %s %s is hedged by %s at the SAME total; a different total is "
            "not a hedge." % (market.yes_side, market.line, other))

    if market.market_type == SPREAD:
        if not market.opponent or not market.line:
            return None
        mirrored = _mirror_line(market.line)
        if mirrored is None:
            return None
        return HedgeTarget(
            market.sport, SPREAD, mirrored, market.opponent.canonical,
            "YES on %s %s is hedged by %s %s - the mirrored handicap at the same "
            "number. A different number leaves a middle, not a hedge."
            % (market.yes_team.canonical, market.line,
               market.opponent.canonical, mirrored))
    return None


def _mirror_line(line: str) -> Optional[str]:
    try:
        value = float(line)
    except (TypeError, ValueError):
        return None
    return "%+.1f" % (-value) if value else "0.0"


def lines_match(a: str, b: str, tolerance: float = 1e-9) -> bool:
    """
    Do two handicaps or totals refer to the same number?

    Textual comparison is not enough - "-3", "-3.0" and "-3.00" are one line -
    but nor is loose comparison acceptable: -3.5 against -3.0 is a middle, where
    both legs can lose, and treating it as a hedge understates the risk to zero.
    So: exact in value, tolerant only of spelling.
    """
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) <= tolerance
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------
# Matching against the sports market database
# --------------------------------------------------------------------------

@dataclass
class MatchedPair:
    """A Polymarket market and the sportsbook quote that hedges it."""

    market: PolymarketMarket
    target: HedgeTarget
    book: str
    book_selection: str
    book_decimal_odds: float
    event_id: str
    quoted_at: Optional[str] = None

    def as_record(self) -> Dict[str, Any]:
        return {"question": self.market.question,
                "market_type": self.market.market_type,
                "line": self.market.line, "token_id": self.market.token_id,
                "yes_price": self.market.yes_price,
                "hedge_selection": self.target.selection,
                "rationale": self.target.rationale,
                "book": self.book, "book_selection": self.book_selection,
                "book_decimal_odds": self.book_decimal_odds,
                "event_id": self.event_id}


def load_book_quotes(db_path: Path = DEFAULT_DB_PATH,
                     sport: Optional[str] = None) -> List[Dict[str, Any]]:
    """Most recent offered price per (event, market, line, selection, book)."""
    path = Path(db_path)
    if not path.exists():
        return []
    conn = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        sql = ("SELECT event_id, sport, market_type, line, sportsbook, selection, "
               "offered_odds, timestamp FROM fair_odds_measurements")
        params: List[Any] = []
        if sport:
            sql += " WHERE UPPER(sport) = ?"
            params.append(sport.upper())
        sql += " ORDER BY timestamp ASC"
        rows = [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()
    latest: Dict[Tuple, Dict[str, Any]] = {}
    for row in rows:
        key = (row["event_id"], row["market_type"], row["line"],
               row["selection"], row["sportsbook"])
        latest[key] = row
    return list(latest.values())


def match_markets(markets: Sequence[PolymarketMarket],
                  quotes: Sequence[Dict[str, Any]]) -> List[MatchedPair]:
    """
    Pair each Polymarket market with the BEST sportsbook price on the other side.

    Best means highest decimal odds, because the hedge leg is a purchase of a
    payout and more payout per dollar is strictly better. Where several books
    quote the same side, only the best survives - carrying the rest would offer
    the desk a worse execution with no compensating benefit.
    """
    pairs: List[MatchedPair] = []
    for market in markets:
        target = hedge_leg_for(market)
        if target is None:
            continue
        best: Optional[Dict[str, Any]] = None
        for quote in quotes:
            if not _quote_matches(quote, market, target):
                continue
            if best is None or float(quote["offered_odds"]) > float(best["offered_odds"]):
                best = quote
        if best is None:
            continue
        pairs.append(MatchedPair(
            market=market, target=target, book=best["sportsbook"],
            book_selection=best["selection"],
            book_decimal_odds=float(best["offered_odds"]),
            event_id=best["event_id"], quoted_at=best.get("timestamp")))
    return pairs


def _quote_matches(quote: Dict[str, Any], market: PolymarketMarket,
                   target: HedgeTarget) -> bool:
    if str(quote.get("market_type", "")).lower() != market.market_type:
        return False
    if target.market_type in (SPREAD, TOTALS):
        if not lines_match(str(quote.get("line", "")), target.line):
            return False
    if target.market_type == TOTALS:
        return normalise(quote.get("selection", "")).startswith(target.selection)
    resolved = resolve_team(quote.get("selection", ""), market.sport or None)
    if resolved is None:
        return False
    # The quote must be on the OPPOSITE team. This is the check that stops the
    # engine pairing a YES with a bet on the same side - the error that turns a
    # hedge into double exposure while still reporting an arbitrage.
    return resolved.canonical == target.selection
