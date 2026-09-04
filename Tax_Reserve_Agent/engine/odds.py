"""
Sports odds normalisation.

One job: turn whatever a sportsbook wrote in its export into a single canonical
representation, so that nothing downstream has to guess. `-110`, `1.909`, `10/11`
and `EVEN` are all the same price, and a ledger that stores the raw string cannot
check a payout against it.

WHY THIS IS IN THE TAX AGENT AT ALL. Odds never enter a tax computation - the IRS
cares about dollars received and dollars wagered, not the price. They earn their
place as a CONSISTENCY CHECK: `wager x decimal_odds` is what the ticket should
have returned, and a settled row whose payout disagrees is a corrupt import. A
mistyped payout is invisible in every other check this ledger runs and is wrong
in the escrow forever after.

FORMAT DETECTION IS AMBIGUOUS, AND WHERE IT IS TRULY AMBIGUOUS THIS REFUSES.

  signed (`+150`, `-110`, `-110.0`)  American. Decimal odds are never signed and
                                     never negative, so a sign settles it.
  bare integer >= 100 (`150`)        American, by industry convention.
  1 < x < 100 (`1.91`, `26.0`)       decimal. Below +9900 nobody quotes decimal
                                     that high, and American cannot live here.
  bare `150.0`                       REFUSED. It is either American +150 written
                                     by a tool that formatted it as a float, or a
                                     genuine decimal 150.0 (+14900). Those differ
                                     by 60x. Guessing either way is silent,
                                     and wrong half the time.
  (0, 1]                             REFUSED. Implied probability, or a typo.

Refusing is cheap here and guessing is not: odds are metadata, so the ingestor
catches the refusal, warns, and still records the wager and its dollars. The tax
figure is never at risk; only the payout cross-check is lost. Set `fmt=`, the
export's own `odds_format` column, or `gambling.default_odds_format` to make the
ambiguous zone readable.

`implied_probability` is deliberately exposed as its own function: it is the seam
the no-vig / fair-value engine (Item 2) attaches to, and it belongs with the
conversions rather than duplicated there.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

AMERICAN = "american"
DECIMAL = "decimal"
FRACTIONAL = "fractional"

# An American price of |x| < 100 does not exist: 100 IS even money on both sides.
MIN_AMERICAN_MAGNITUDE = 100.0

# Words books print instead of a number for even money.
_EVEN_MONEY_WORDS = frozenset({"even", "evens", "ev", "pk", "pick", "pickem"})

_EMPTY_TOKENS = frozenset({"n/a", "na", "none", "null", "-", "--", "?"})


class OddsFormatError(ValueError):
    """The odds string could not be read as a price. Never guessed - always raised."""


@dataclass(frozen=True)
class OddsQuote:
    """A price, canonicalised. `decimal` is the total return per $1 staked."""

    decimal: float
    american: int
    implied_probability: float
    source_format: str
    raw: str

    def payout_for(self, wager: float) -> float:
        """Total returned on a win, INCLUDING the stake back."""
        return float(wager) * self.decimal

    def profit_for(self, wager: float) -> float:
        """Net winnings on a win - the figure a W-2G reports."""
        return float(wager) * (self.decimal - 1.0)

    def __str__(self) -> str:
        sign = "+" if self.american > 0 else ""
        return f"{sign}{self.american} ({self.decimal:.4f})"


def american_to_decimal(american: float) -> float:
    value = float(american)
    if abs(value) < MIN_AMERICAN_MAGNITUDE:
        raise OddsFormatError(
            f"American odds must be >= +100 or <= -100; got {american!r}. "
            f"A value between -100 and +100 is almost always decimal odds."
        )
    if value > 0:
        return 1.0 + value / 100.0
    return 1.0 + 100.0 / abs(value)


def decimal_to_american(decimal_odds: float) -> int:
    value = float(decimal_odds)
    if value <= 1.0:
        raise OddsFormatError(
            f"Decimal odds must exceed 1.0 (1.0 returns only the stake); got {decimal_odds!r}."
        )
    if value >= 2.0:
        return int(round((value - 1.0) * 100.0))
    return int(round(-100.0 / (value - 1.0)))


def fractional_to_decimal(fraction: str) -> float:
    """`5/2` -> 3.5. Also accepts `5-2` and `5:2`, which some feeds emit."""
    text = str(fraction).strip().replace("-", "/").replace(":", "/")
    numerator, _, denominator = text.partition("/")
    try:
        num = float(numerator)
        den = float(denominator)
    except (TypeError, ValueError):
        raise OddsFormatError(f"Not fractional odds: {fraction!r}")
    if den <= 0 or num < 0:
        raise OddsFormatError(f"Fractional odds must be positive: {fraction!r}")
    return 1.0 + num / den


def implied_probability(decimal_odds: float) -> float:
    """
    The book's quoted probability - INCLUSIVE of the vig, so a two-way market
    sums to more than 1.0. Removing that overround is Item 2's job, not this
    module's; nothing here should pretend this number is a fair probability.
    """
    value = float(decimal_odds)
    if value <= 0:
        raise OddsFormatError(f"Decimal odds must be positive; got {decimal_odds!r}.")
    return 1.0 / value


def parse_odds(raw: Any, fmt: Optional[str] = None) -> Optional[OddsQuote]:
    """
    Reads any common odds representation. Returns None for a genuinely empty
    field (a bet log with no price column is still a valid tax record); raises
    `OddsFormatError` for something present but unreadable.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in _EMPTY_TOKENS:
        return None

    original = text
    if text.lower() in _EVEN_MONEY_WORDS:
        return _quote(2.0, DECIMAL, original)

    if fmt == FRACTIONAL or ("/" in text and fmt is None):
        return _quote(fractional_to_decimal(text), FRACTIONAL, original)

    numeric = text.replace(",", "").replace("$", "").strip()
    signed = numeric.startswith(("+", "-"))
    cleaned = numeric.lstrip("+")
    try:
        value = float(cleaned)
    except (TypeError, ValueError):
        raise OddsFormatError(f"Unreadable odds value: {raw!r}")

    if fmt == AMERICAN:
        return _quote(american_to_decimal(value), AMERICAN, original)
    if fmt == DECIMAL:
        return _quote(value, DECIMAL, original)
    if fmt is not None:
        raise OddsFormatError(f"Unknown odds format {fmt!r}; use american/decimal/fractional.")

    # Sniffed. See the module docstring for the full table.
    if signed:
        # A sign is decisive: no book quotes decimal odds with one, and decimal
        # odds cannot be negative at all. `-110.0` and `+150.0` are safe here.
        return _quote(american_to_decimal(value), AMERICAN, original)
    if abs(value) >= MIN_AMERICAN_MAGNITUDE:
        if "." in cleaned:
            # THE 60x TRAP. `150.0` is American +150 (decimal 2.50) if a tool
            # formatted an integer price as a float, and decimal 150.0
            # (American +14900) if the book quotes decimal. Both readings occur
            # in real exports and nothing in the value distinguishes them.
            raise OddsFormatError(
                f"Ambiguous odds {raw!r}: as American this is "
                f"{american_to_decimal(value):.4f} decimal, as decimal it is "
                f"{value:.4f} - a {value / american_to_decimal(value):.0f}x difference. "
                f"Tag it with fmt=, an `odds_format` column, or "
                f"gambling.default_odds_format."
            )
        return _quote(american_to_decimal(value), AMERICAN, original)
    if value > 1.0:
        return _quote(value, DECIMAL, original)
    raise OddsFormatError(
        f"Ambiguous odds {raw!r}: a value in (0, 1] is either an implied probability "
        f"or a typo, and the two need opposite handling. Pass fmt='decimal' or "
        f"fmt='american' to state which."
    )


def _quote(decimal_odds: float, source_format: str, raw: str) -> OddsQuote:
    if decimal_odds <= 1.0:
        raise OddsFormatError(
            f"Decimal odds must exceed 1.0; {raw!r} resolved to {decimal_odds}."
        )
    return OddsQuote(
        decimal=decimal_odds,
        american=decimal_to_american(decimal_odds),
        implied_probability=implied_probability(decimal_odds),
        source_format=source_format,
        raw=raw,
    )


def payout_discrepancy(wager: float, payout: float, quote: Optional[OddsQuote],
                       tolerance_pct: float = 0.02) -> Optional[float]:
    """
    Returns the RELATIVE gap between the payout a row claims and the payout its
    odds imply, or None when the row is inside tolerance or the check cannot be
    made at all.

    Not an error on its own: a partial cashout, a dead heat and a parlay with a
    voided leg all legitimately settle away from the opening price. It is a flag
    to record in the row notes so that a $1,910 payout typed as $191 is visible
    later, when the only other evidence is an escrow that looks slightly low.
    """
    if quote is None or wager <= 0 or payout <= 0:
        return None
    expected = quote.payout_for(wager)
    if expected <= 0:
        return None
    discrepancy = abs(payout - expected) / expected
    return discrepancy if discrepancy > tolerance_pct else None
