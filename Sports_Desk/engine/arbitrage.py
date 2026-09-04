"""
Cross-book arbitrage detection.

A single book never offers an arbitrage - its overround is the margin it lives
on. An arbitrage appears only when you take the BEST price for each outcome
across several books at once, building a synthetic market whose implied
probabilities sum to less than one. That synthetic market is what this module
finds.

THE PART EVERYONE GETS WRONG IS THE TAX. A cross-book arb wins one leg and loses
the other, every single time. The winning leg is ordinary income; the losing leg
is a wagering loss, and under IRC 165(d) a casual bettor on the standard
deduction may not deduct it at all. So a 2% arbitrage - which is a good one, in
practice - carries roughly a 14% after-tax LOSS. It is not a thin edge, it is a
reliable one, in the wrong direction, and it looks like free money right up to
the moment the return is filed.

Worse, AN ARBITRAGE IS NOT EVEN RISKLESS AFTER TAX. The legs are taxed
asymmetrically, so a position that is riskless in dollars has a different
after-tax outcome depending on which side wins - unless the stakes happen to be
equal or losses are fully deductible. The binding case is always the longest-odds
leg, because that is the smallest stake and therefore the largest non-deductible
loss. `monarch_hook.after_tax_arbitrage_hurdle` prices exactly that branch, and
nothing here reports an opportunity that does not clear it.

WHAT THIS MODULE DOES NOT DO. It does not devig. An arbitrage is a statement
about PRICES, not about probabilities: you are not claiming to know the true
chance of anything, only that two books disagree by more than their combined
margin. Fair value belongs to `fair_value.py` and has no role here.

STALENESS IS THE DOMINANT FALSE POSITIVE. Most apparent cross-book arbs are two
quotes captured minutes apart, and the "edge" is the market having moved in
between. Quotes are filtered through the same per-sport staleness rule the odds
watcher uses before any of them are compared.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from Sports_Desk.data.db import (DEFAULT_DB_PATH, query_edges, query_measurements,
                                 settled_event_ids)
from Sports_Desk.ingestors.odds_watcher import max_quote_age
from Tax_Reserve_Agent.engine.lot_engine import as_naive_utc, parse_iso_date

# Below this the "arbitrage" is inside the noise of rounding and half-point
# differences between books, and acting on it costs more in slippage than it pays.
MIN_REPORTABLE_ARB = 0.001


class ArbitrageError(ValueError):
    """A market that cannot be assessed for arbitrage."""


@dataclass(frozen=True)
class ArbLeg:
    """One side of a synthetic market: the best price found for that outcome."""

    selection: str
    book: str
    decimal_odds: float
    stake_fraction: float          # of the total stake, to equalise the return
    quoted_at: Optional[datetime] = None

    def stake_for(self, bankroll: float) -> float:
        return float(bankroll) * self.stake_fraction


@dataclass
class ArbOpportunity:
    """
    A synthetic market whose best prices sum to less than one.

    Carries the gross arbitrage AND the after-tax verdict, because the two
    disagree violently: a 2% arb is a fine gross number and a 14% after-tax loss
    under a standard deduction.
    """

    event_id: str
    sport: str
    market_type: str
    line: str
    legs: List[ArbLeg]
    booksum: float
    gross_arb: float                       # R - 1, the riskless pre-tax return
    after_tax_hurdle: Optional[float] = None
    clears_hurdle: Optional[bool] = None
    worst_case_after_tax: Optional[float] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def books(self) -> List[str]:
        return sorted({leg.book for leg in self.legs})

    @property
    def is_cross_book(self) -> bool:
        """A single book quoting an arb against itself is a data error."""
        return len(self.books) > 1

    def stakes_for(self, bankroll: float) -> Dict[str, float]:
        return {leg.selection: leg.stake_for(bankroll) for leg in self.legs}

    def as_record(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id, "sport": self.sport,
            "market_type": self.market_type, "line": self.line,
            "books": self.books, "booksum": self.booksum,
            "gross_arb": self.gross_arb,
            "after_tax_hurdle": self.after_tax_hurdle,
            "clears_hurdle": self.clears_hurdle,
            "worst_case_after_tax": self.worst_case_after_tax,
            "legs": [{"selection": leg.selection, "book": leg.book,
                      "decimal_odds": leg.decimal_odds,
                      "stake_fraction": leg.stake_fraction} for leg in self.legs],
            "warnings": list(self.warnings),
        }


def build_synthetic_market(quotes: Sequence[Dict[str, Any]]) -> List[ArbLeg]:
    """
    Best price per outcome across every book, with the stakes that equalise the
    return.

    `quotes` are dicts with `selection`, `book`, `decimal_odds` and optionally
    `quoted_at`. Stake fractions are s_i = (1/O_i) / booksum, which sum to one and
    make every leg return the same amount whatever happens.
    """
    best: Dict[str, Dict[str, Any]] = {}
    for quote in quotes:
        key = " ".join(str(quote["selection"]).split()).upper()
        current = best.get(key)
        if current is None or float(quote["decimal_odds"]) > float(current["decimal_odds"]):
            best[key] = quote
    if len(best) < 2:
        raise ArbitrageError(
            f"A synthetic market needs at least two outcomes; got {len(best)}. "
            f"An arbitrage on one leg is not an arbitrage, it is a missing leg.")

    booksum = math.fsum(1.0 / float(q["decimal_odds"]) for q in best.values())
    if booksum <= 0:
        raise ArbitrageError("Degenerate odds.")
    return [
        ArbLeg(selection=quote["selection"], book=quote["book"],
               decimal_odds=float(quote["decimal_odds"]),
               stake_fraction=(1.0 / float(quote["decimal_odds"])) / booksum,
               quoted_at=quote.get("quoted_at"))
        for quote in best.values()
    ]


def find_arbitrage(quotes: Sequence[Dict[str, Any]], event_id: str = "",
                   sport: str = "", market_type: str = "",
                   line: str = "") -> Optional[ArbOpportunity]:
    """
    Returns the opportunity when the best cross-book prices sum below one, else
    None. Pure - no database, no tax. `assess_after_tax` adds the verdict.
    """
    legs = build_synthetic_market(quotes)
    booksum = math.fsum(1.0 / leg.decimal_odds for leg in legs)
    if booksum >= 1.0 - MIN_REPORTABLE_ARB:
        return None

    opportunity = ArbOpportunity(
        event_id=event_id, sport=sport, market_type=market_type, line=line,
        legs=legs, booksum=booksum, gross_arb=(1.0 / booksum) - 1.0)
    if not opportunity.is_cross_book:
        opportunity.warnings.append(
            f"every leg came from {opportunity.books[0]!r}. A book does not offer "
            f"an arbitrage against itself - this is a stale or mistyped quote, not "
            f"an opportunity.")
    return opportunity


def assess_after_tax(opportunity: ArbOpportunity, hook: Any) -> ArbOpportunity:
    """
    Prices the worst branch and records whether the arb survives it.

    `hook` is a `MonarchBankrollHook`. Passed in rather than constructed so this
    module never owns a ledger connection, and so the caller's tax treatment is
    the one that applies.
    """
    legs = [leg.decimal_odds for leg in opportunity.legs]
    opportunity.after_tax_hurdle = hook.after_tax_arbitrage_hurdle(odds=legs)
    opportunity.clears_hurdle = opportunity.gross_arb > opportunity.after_tax_hurdle

    # The actual after-tax return on the worst branch, in the units the operator
    # cares about: cents per dollar staked.
    tax = min(max(hook._composite_tax_rate(), 0.0), 0.99)
    deductible = hook.gambling_loss_deductibility()
    total_return = 1.0 + opportunity.gross_arb
    opportunity.worst_case_after_tax = min(
        (total_return - 1.0) - tax * (total_return - leg.stake_fraction)
        + tax * deductible * (1.0 - leg.stake_fraction)
        for leg in opportunity.legs)

    if not opportunity.clears_hurdle:
        opportunity.warnings.append(
            f"gross arbitrage {opportunity.gross_arb * 100:.2f}% is below the "
            f"{opportunity.after_tax_hurdle * 100:.2f}% after-tax hurdle - staking it "
            f"loses {abs(opportunity.worst_case_after_tax) * 100:.2f}% on the worst leg. "
            f"An arb books a taxed win against a "
            f"{deductible * 100:.0f}%-deductible loss every time.")
    return opportunity


# ---------------------------------------------------------------------------
# The one impure function: scanning the stored edge table.
# ---------------------------------------------------------------------------

def scan_market_db(hook: Any, db_path: Path = DEFAULT_DB_PATH,
                   now: Optional[datetime] = None,
                   include_rejected: bool = False,
                   skip_settled: bool = True) -> List[ArbOpportunity]:
    """
    Finds every cross-book arbitrage currently visible in `sports_market.db`.

    Reads BOTH tables, and it has to. `edge_opportunities` holds one row per
    RETAIL quote, so a selection that only the sharp book priced has no row there
    at all - and an arbitrage needs every leg. `fair_odds_measurements` carries
    the sharp side of every market. Scanning only the edge table finds nothing on
    exactly the shape that matters: a two-way market where one side is best at
    the sharp book and the other is best at a retail book.

    The sharp book is a counterparty like any other here, because the question is
    PRICES, not fair value. Nothing in this scan devigs anything.

    STALE QUOTES ARE DROPPED FIRST. Most apparent cross-book arbs are two prices
    captured minutes apart, and the edge is the market having moved in between.
    """
    now = now or datetime.utcnow()
    settled = settled_event_ids(db_path=db_path) if skip_settled else set()

    # Newest quote per (market, selection, book) - both tables keep history.
    latest: Dict[Tuple, Dict[str, Any]] = {}

    def offer(market, selection, book, odds, timestamp, quoted_at):
        key = market + (" ".join(str(selection).split()).upper(), book)
        seen = latest.get(key)
        if seen is None or str(timestamp) > str(seen["timestamp"]):
            latest[key] = {"selection": selection, "book": book,
                           "decimal_odds": float(odds), "timestamp": timestamp,
                           "quoted_at": _moment(quoted_at), "market": market}

    for row in query_measurements(db_path=db_path):
        if skip_settled and row["event_id"] in settled:
            continue
        offer((row["event_id"], row["sport"], row["market_type"], row["line"]),
              row["selection"], row["sportsbook"], row["offered_odds"],
              row["timestamp"], row.get("quoted_at"))

    for edge in query_edges(min_edge=-1.0, db_path=db_path):
        if skip_settled and edge["event_id"] in settled:
            continue
        if edge.get("is_live"):
            continue
        market = (edge["event_id"], edge["sport"], edge["market_type"], edge["line"])
        for book, odds in ((edge["retail_book"], edge["retail_offered_odds"]),
                           (edge["sharp_book"], edge["sharp_offered_odds"])):
            offer(market, edge["selection"], book, odds, edge["timestamp"],
                  edge.get("quoted_at"))

    markets: Dict[Tuple, List[Dict[str, Any]]] = {}
    for quote in latest.values():
        markets.setdefault(quote["market"], []).append(quote)

    found: List[ArbOpportunity] = []
    for (event_id, sport, market_type, line), quotes in markets.items():
        fresh = _drop_stale(quotes, sport, market_type, now)
        if len(fresh) < 2:
            continue
        try:
            opportunity = find_arbitrage(fresh, event_id, sport, market_type, line)
        except ArbitrageError:
            continue
        if opportunity is None:
            continue
        assess_after_tax(opportunity, hook)
        if opportunity.clears_hurdle or include_rejected:
            found.append(opportunity)

    found.sort(key=lambda o: (bool(o.clears_hurdle), o.gross_arb), reverse=True)
    return found


def _moment(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return as_naive_utc(parse_iso_date(text))
    except (ValueError, TypeError):
        return None


def _drop_stale(quotes: List[Dict[str, Any]], sport: str, market_type: str,
                now: datetime) -> List[Dict[str, Any]]:
    """Same per-sport rule the odds watcher applies, measured against `now`."""
    timed = [q for q in quotes if q.get("quoted_at")]
    if not timed:
        return quotes
    limit = max_quote_age(sport, market_type)
    return [q for q in quotes
            if not q.get("quoted_at")
            or (now - q["quoted_at"]).total_seconds() <= limit]


def render_arbitrage(opportunities: Sequence[ArbOpportunity],
                     bankroll: float = 1000.0) -> str:
    """ASCII card in the shape of the other desks' output."""
    lines = ["=" * 92,
             "          CROSS-BOOK ARBITRAGE (after-tax)",
             "=" * 92,
             f"  Stake basis: ${bankroll:,.2f}"]
    if not opportunities:
        lines.append("-" * 92)
        lines.append("  None found.")
        lines.append("=" * 92)
        return "\n".join(lines)

    for opportunity in opportunities:
        lines.append("-" * 92)
        verdict = "CLEARS" if opportunity.clears_hurdle else "BELOW HURDLE"
        lines.append(
            f"  {opportunity.event_id}/{opportunity.market_type}"
            f"{'@' + opportunity.line if opportunity.line else ''}  "
            f"gross {opportunity.gross_arb * 100:+.2f}%  "
            f"hurdle {(opportunity.after_tax_hurdle or 0) * 100:.2f}%  [{verdict}]")
        for leg in opportunity.legs:
            lines.append(f"      ${leg.stake_for(bankroll):>9,.2f} on {leg.selection:<22}"
                         f"{leg.book:<14}@ {leg.decimal_odds:.3f}")
        if opportunity.worst_case_after_tax is not None:
            lines.append(f"      worst-branch after tax: "
                         f"{opportunity.worst_case_after_tax * 100:+.2f}% "
                         f"(${opportunity.worst_case_after_tax * bankroll:+,.2f})")
        for warning in opportunity.warnings:
            lines.append(f"      [!] {warning}")
    lines.append("=" * 92)
    lines.append("  An arb wins one leg and loses the other EVERY time. Under a standard")
    lines.append("  deduction the loss deducts nothing, so a 2% arb is a ~14% after-tax loss.")
    lines.append("=" * 92)
    return "\n".join(lines)
