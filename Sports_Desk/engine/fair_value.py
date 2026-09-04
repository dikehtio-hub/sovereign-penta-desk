"""
Pure Fair-Value (No-Vig) Engine for Sports Betting.

A book's prices are not probabilities. `-110 / -110` implies 52.38% on both sides,
which sums to 104.76%: the extra 4.76% is the overround, and it is how the book
gets paid. This module strips that surplus back out and returns a probability
vector summing to one - because only then can an offered price be compared
against it and an edge computed.

HOW THE SURPLUS IS STRIPPED IS THE ENTIRE QUESTION. Dividing each implied
probability by the booksum (MULTIPLICATIVE) assumes margin is spread
proportionally. It is not: books load disproportionately more margin onto
longshots, because that is where the public bets. Multiplicative devigging
therefore leaves a longshot's fair probability too HIGH - manufacturing value
exactly where the favourite-longshot bias says none exists.

SHIN (1992, 1993) IS THE ESTIMATOR, EVERYWHERE. It models the book as pricing
against a proportion `z` of insider traders and solves for the z that makes the
fair probabilities sum to one. Running a different estimator on wide markets than
on narrow ones would be cheaper and is a trap: two markets devigged differently
are not comparable, and everything downstream compares them. Measured on a 4-way
market Shin and Power differ by 0.0078, so routing by market width shifts every
fair value by that much at the boundary.

  n = 2   closed form, PROVEN exact (see `_shin_two_way`) - no iteration at all
  n >= 3  bisection on z in [0, 1)

POWER IS A CROSS-CHECK ORACLE, NOT AN ALTERNATIVE. `p_i = pi_i ** k` solved for
the normalising k is a different functional form of the same bias. The tolerance
is CALIBRATED, not guessed: across well-formed markets from -110/-110 to a
20-runner golf book the two estimators differ by at most 0.0102, while a market
with one leg mistyped by 10x differs by 0.1070. The 0.03 default sits in that
gap. A flag that fires on normal markets teaches the operator to ignore it.

NOTHING IS RENORMALISED AFTER SOLVING. Rescaling the output so it sums to one is
tempting and it is a trap: it makes a FAILED solve indistinguishable from a good
one. Stopping the bisection early on a 1.20/4.75 market gives [0.9058, 0.0942]
against a true [0.8114, 0.1886] - a 9.4 percentage point error - and a rescale
still leaves it summing to exactly 1.0, so nothing about the vector looks wrong.
`converged` is load-bearing; callers must check it, and `trustworthy` bundles it
with the oracle result for exactly that purpose.

A BOOKSUM AT OR BELOW 1.0 IS A SIGNAL, NOT A PRICE. There is no margin to strip,
every devigger would have to ADD some to normalise, and Shin's z goes negative.
Pricing it anyway reports a POSITIVE edge on both sides of the market - the one
result that cannot be true, and the one a scanner most needs to see. Hence
`ArbitrageError`, which carries the booksum and the edge rather than just a
message.

WHAT THIS MODULE WILL NOT DO
  * No I/O. No database, no network, no file reads - pure arithmetic, so the
    maths is testable against analytic answers with nothing mocked. Persistence
    lives in `Sports_Desk/data/db.py`; ingestion is separate again.
  * No opinion on WHICH book to trust. Devigging a soft book yields that book's
    opinion minus its margin, not a fair price. Choosing a sharp reference
    (Pinnacle, Circa) is a data-layer decision.
  * No tax. `kelly_fraction` is GROSS of tax and must not size a real order on
    its own - see the warning on that function.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# The odds seam. Imported HARD, not in a try/except: a silent fallback would let
# this engine and the tax ledger disagree about what `-110` means, and the whole
# point of sharing `OddsQuote` is that they cannot.
from Tax_Reserve_Agent.engine.odds import OddsFormatError, OddsQuote, parse_odds

SHIN = "shin"
POWER = "power"

# Calibrated - see the module docstring. Well-formed markets deviate by at most
# 0.0102; a single 10x-mistyped leg deviates by 0.1070.
DEFAULT_ORACLE_TOLERANCE = 0.03

MAX_ITERATIONS = 200
SOLVER_TOLERANCE = 1e-13

# Below this the booksum is treated as an arbitrage rather than a rounding wobble.
_BOOKSUM_EPSILON = 1e-9


class DevigError(ValueError):
    """Raised when odds cannot be devigged. Never approximated - always raised."""


class ArbitrageError(DevigError):
    """
    The quotes carry no overround, so there is nothing to strip.

    Its own class because this is a SIGNAL, not a failure: a booksum below one is
    a genuine arbitrage, a stale leg, or legs pasted together from two books. All
    three want a human decision and none wants a fair value, so a scanner catches
    this rather than parsing an error string.
    """

    def __init__(self, message: str, booksum: float, implied: Sequence[float]):
        super().__init__(message)
        self.booksum = float(booksum)
        self.implied = tuple(implied)

    @property
    def edge_pct(self) -> float:
        """Guaranteed return per dollar staked across all legs, as a percentage."""
        return (1.0 / self.booksum - 1.0) * 100.0 if self.booksum > 0 else 0.0


@dataclass(frozen=True)
class OutcomeFairValue:
    """Fair-value metrics for an individual outcome."""
    index: int
    offered_odds: float
    implied_prob_raw: float
    fair_prob: float
    fair_odds: float
    expected_value: float  # p * O - 1
    quarter_kelly: float   # quarter-Kelly fraction, GROSS OF TAX


@dataclass(frozen=True)
class FairValueResult:
    """
    Complete devigging result across all market outcomes.

    Carries its inputs as well as its answer on purpose. A fair probability
    stored without the prices it came from is unfalsifiable later - and "later"
    is when someone is working out why a bet that showed a 4% edge lost.
    """
    method: str
    outcomes: List[OutcomeFairValue]
    overround: float
    shin_z: float
    power_k: float
    converged: bool
    iterations: int
    divergent: bool = False
    max_oracle_delta: float = 0.0
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def fair_probabilities(self) -> List[float]:
        return [o.fair_prob for o in self.outcomes]

    @property
    def fair_odds(self) -> List[float]:
        return [o.fair_odds for o in self.outcomes]

    @property
    def booksum(self) -> float:
        return self.overround + 1.0

    @property
    def vig_pct(self) -> float:
        """
        Margin as a percentage of turnover - the hold a bettor actually pays,
        which is NOT the overround. A 4.76% overround is a 4.55% hold, because
        the surplus is spread across a booksum greater than one.
        """
        return self.overround / (self.overround + 1.0) * 100.0

    @property
    def trustworthy(self) -> bool:
        """
        Converged, oracle-agreed, and warning-free. GATE ORDERS ON THIS, not on
        `converged` alone - see the module docstring on renormalisation.
        """
        return self.converged and not self.divergent and not self.warnings

    def as_record(self) -> Dict[str, Any]:
        """Flat provenance dict for logging or persistence."""
        return {
            "method": self.method,
            "offered_odds": [o.offered_odds for o in self.outcomes],
            "implied_raw": [o.implied_prob_raw for o in self.outcomes],
            "fair_probabilities": self.fair_probabilities,
            "booksum": self.booksum,
            "overround": self.overround,
            "vig_pct": self.vig_pct,
            "shin_z": self.shin_z,
            "power_k": self.power_k,
            "converged": self.converged,
            "iterations": self.iterations,
            "divergent": self.divergent,
            "max_oracle_delta": self.max_oracle_delta,
            "trustworthy": self.trustworthy,
            "warnings": list(self.warnings),
        }


def clean_odds(odds: Sequence[Any], odds_format: Optional[str] = None) -> List[float]:
    """
    Validates a market's quotes and returns them as decimal odds.

    A BARE NUMBER IS DECIMAL ODDS, by this module's contract - that is what a
    market feed carries and it makes `100.0` an unambiguous 100.0 rather than the
    American +100 the tax ledger's sniffer would have to worry about. American
    prices come in as STRINGS (`"-110"`, `"+150"`), which are unambiguous because
    of the sign, or with an explicit `odds_format`. Fractional (`"5/2"`) and
    `"EVEN"` work too - the whole `parse_odds` vocabulary is available.
    """
    cleaned: List[float] = []
    for raw in odds:
        if isinstance(raw, OddsQuote):
            value = raw.decimal
        elif isinstance(raw, bool):
            raise DevigError(f"Invalid odds value: {raw!r}")
        elif isinstance(raw, (int, float)):
            value = float(raw)
        else:
            try:
                quote = parse_odds(raw, fmt=odds_format)
            except OddsFormatError as e:
                raise DevigError(f"Invalid odds value: {raw!r} ({e})")
            if quote is None:
                raise DevigError(
                    f"Outcome has no odds ({raw!r}). Every leg of a market must be "
                    f"quoted - devigging a subset is silently wrong for all of them.")
            value = quote.decimal
        if not math.isfinite(value) or value <= 1.0:
            raise DevigError(
                f"Decimal odds must exceed 1.0; got {value}. A price at or below 1.0 "
                f"returns no more than the stake and implies a probability of 1 or more.")
        cleaned.append(value)
    if len(cleaned) < 2:
        raise DevigError(
            f"Market must have at least 2 outcomes; got {len(cleaned)}. A single "
            f"quote carries no information about the book's margin.")
    return cleaned


def calculate_edge(fair_prob: float, offered_odds: float) -> float:
    """
    Gross expected return per dollar staked: p * O - 1. Zero means the offered
    price is exactly fair. Every edge filter starts here and none should end
    here - fees, slippage and tax all come out of it afterwards.
    """
    return (float(fair_prob) * float(offered_odds)) - 1.0


def kelly_fraction(fair_prob: float, offered_odds: float, fraction: float = 0.25) -> float:
    """
    Fractional Kelly sizing. b = O - 1; f* = max(0, EV / b) * fraction.

    GROSS OF TAX, AND THAT IS NOT A DETAIL. Under the default
    `casual_standard_deduction` treatment in the tax ledger, gambling losses do
    not offset winnings AT ALL - every winning wager is taxed and every losing
    one is disallowed - so the after-tax growth rate this f* maximises is not the
    one the bettor actually experiences. Sizing a real order needs the ledger's
    tax treatment and bankroll, which live in `monarch_hook`. Use this for
    comparison and research; do not wire it straight to an order.
    """
    b = float(offered_odds) - 1.0
    if b <= 0.0:
        return 0.0
    ev = calculate_edge(fair_prob, offered_odds)
    if ev <= 0.0:
        return 0.0
    return max(0.0, (ev / b) * fraction)


# ----------------------------------------------------------------------------
# Shin's method - the primary estimator.
# ----------------------------------------------------------------------------

def _shin_probabilities(raw_probs: Sequence[float], beta: float, z: float) -> List[float]:
    """p_i(z) = (sqrt(z^2 + 4(1-z)(pi_i^2 / beta)) - z) / (2(1-z))"""
    if abs(z) < 1e-12:
        return [pi / math.sqrt(beta) for pi in raw_probs]
    one_minus_z = 1.0 - z
    if one_minus_z <= 1e-12:
        # Unreachable for a booksum above one, and NOT papered over with a
        # uniform 1/n vector: on a 20-runner book that would hand back 5% for
        # every runner, which looks entirely plausible and is entirely wrong.
        raise DevigError(
            f"Shin z reached {z:.12f}; the market is degenerate and has no fair value.")
    denom = 2.0 * one_minus_z
    return [(math.sqrt(max(0.0, z * z + 4.0 * one_minus_z * (pi * pi / beta))) - z) / denom
            for pi in raw_probs]


def _shin_two_way(raw_probs: Sequence[float], beta: float) -> List[float]:
    """
    Closed form for two outcomes:  p_i = pi_i - (beta - 1) / 2.

    THE EQUAL ABSOLUTE DEDUCTION IS NOT AN APPROXIMATION - IT IS A THEOREM.
    Not obvious, either: the general Shin correction is larger on longshots, yet
    at n = 2 the two corrections coincide exactly. The proof (Antigravity's):

        Write R_i = sqrt(z^2 + 4(1-z) pi_i^2 / beta), so p_i = (R_i - z)/(2(1-z)).
        Summing to 1 gives           R_1 + R_2 = 2.
        Difference of squares:       R_1^2 - R_2^2 = 4(1-z)(pi_1^2 - pi_2^2)/beta,
        and dividing by R_1 + R_2 = 2 gives
                                     R_1 - R_2 = 2(1-z)(pi_1^2 - pi_2^2)/beta.
        Hence  p_1 - p_2 = (R_1 - R_2)/(2(1-z)) = (pi_1^2 - pi_2^2)/beta,
        and because beta = pi_1 + pi_2 that is just  pi_1 - pi_2.
        With p_1 + p_2 = 1 and p_1 - p_2 = pi_1 - pi_2:
                                     p_i = pi_i - (beta - 1)/2.   QED

    Note where the proof leans on n = 2: the collapse of (pi_1^2 - pi_2^2)/beta
    needs beta to be exactly pi_1 + pi_2, which is true only when those are the
    whole market. It does not generalise, and n >= 3 still solves numerically.

    The result needs no normalising either - the two deductions sum to (beta - 1)
    by construction, so the probabilities sum to exactly 1.
    """
    margin = (beta - 1.0) / 2.0
    return [pi - margin for pi in raw_probs]


def _shin_z_two_way(raw_probs: Sequence[float], beta: float) -> float:
    """
    The insider parameter z for a two-way market, also in closed form.

    Reported for diagnostics only - `_shin_two_way` does not need it. Substituting
    R_1 = 1 + (1-z)(pi_1 - pi_2) back into R_1^2 = z^2 + 4(1-z)pi_1^2/beta and
    writing u = 1 - z reduces to a LINEAR equation in u:

        u * ((pi_1 - pi_2)^2 - 1) = 2 (pi_1^2 + pi_2^2 - beta) / beta

    so no iteration is needed here either. Agrees with the bisection solver to
    6e-16 across the price range.
    """
    p1, p2 = raw_probs[0], raw_probs[1]
    denominator = beta * ((p1 - p2) ** 2 - 1.0)
    if abs(denominator) < 1e-15:
        # |pi_1 - pi_2| = 1 needs one outcome at probability ~0 and the other
        # at ~1. Nothing sane produces it; fall back rather than divide by zero.
        return 0.0
    one_minus_z = 2.0 * (p1 * p1 + p2 * p2 - beta) / denominator
    return min(max(1.0 - one_minus_z, 0.0), 1.0 - 1e-15)


def shin_devig(odds: Sequence[Any], tol: float = SOLVER_TOLERANCE,
               max_iter: int = MAX_ITERATIONS,
               odds_format: Optional[str] = None) -> Tuple[List[float], float, bool, int]:
    """
    Shin (1992/1993). Returns (fair_probabilities, z, converged, iterations).

    THE ROOT IS ALWAYS BRACKETED BY [0, 1) for a booksum above one, which is why
    plain bisection suffices and no starting guess is needed. At z = 0 the
    expression collapses to pi_i / sqrt(beta), so the sum is sqrt(beta) - above
    one whenever the book has margin. As z approaches 1 each p_i tends to
    pi_i^2 / beta, and that sum is bounded above by max(pi_i) < 1. Opposite signs
    at the ends, continuous between. Newton would converge faster and would need
    safeguarding against overshoot; bisection cannot diverge, which is worth more.

    NOT renormalised afterwards - see the module docstring.
    """
    clean = clean_odds(odds, odds_format)
    raw_probs = [1.0 / o for o in clean]
    beta = math.fsum(raw_probs)
    _guard_booksum(beta, raw_probs)

    if abs(beta - 1.0) <= _BOOKSUM_EPSILON:
        # Already margin-free: there is nothing to strip and z is 0 by definition.
        return list(raw_probs), 0.0, True, 0

    if len(clean) == 2:
        # Both the probabilities and z are closed form - see the proofs above.
        # No iteration on this path at all, so `max_iter` cannot starve it and
        # `converged=True` is a statement of fact rather than a solver result.
        return (_shin_two_way(raw_probs, beta),
                _shin_z_two_way(raw_probs, beta), True, 0)

    z, iterations, converged = _solve_shin_z(raw_probs, beta, tol, max_iter)
    return _shin_probabilities(raw_probs, beta, z), z, converged, iterations


def _solve_shin_z(raw_probs: Sequence[float], beta: float,
                  tol: float, max_iter: int) -> Tuple[float, int, bool]:
    low, high = 0.0, 1.0 - 1e-15
    iterations = 0
    for iterations in range(1, max_iter + 1):
        mid = 0.5 * (low + high)
        excess = math.fsum(_shin_probabilities(raw_probs, beta, mid)) - 1.0
        if abs(excess) < tol or (high - low) < tol:
            return mid, iterations, True
        # The sum decreases in z: too much probability means too little z.
        if excess > 0:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high), iterations, False


# ----------------------------------------------------------------------------
# Power method - the cross-check oracle.
# ----------------------------------------------------------------------------

def power_devig(odds: Sequence[Any], tol: float = SOLVER_TOLERANCE,
                max_iter: int = MAX_ITERATIONS,
                odds_format: Optional[str] = None) -> Tuple[List[float], float, bool, int]:
    """
    Power (odds-ratio / Wojcik-Hurley) devig: p_i = pi_i ** k, k solved so the
    probabilities sum to one. Returns (fair_probabilities, k, converged, iters).

    Also monotone and also bracketed: every pi_i is below one, so a higher power
    shrinks each; the sum starts at beta > 1 at k = 1 and decreases without
    bound. Like Shin it corrects longshots harder than favourites, which is what
    makes it a meaningful oracle - the same qualitative model in a different
    functional form, so agreement is evidence and divergence is a flag.

    NOT renormalised afterwards - see the module docstring.
    """
    clean = clean_odds(odds, odds_format)
    raw_probs = [1.0 / o for o in clean]
    beta = math.fsum(raw_probs)
    _guard_booksum(beta, raw_probs)

    if abs(beta - 1.0) <= _BOOKSUM_EPSILON:
        return list(raw_probs), 1.0, True, 0

    low, high = 1.0, 64.0
    iterations = 0
    for iterations in range(1, max_iter + 1):
        mid = 0.5 * (low + high)
        excess = math.fsum(pi ** mid for pi in raw_probs) - 1.0
        if abs(excess) < tol or (high - low) < tol:
            return [pi ** mid for pi in raw_probs], mid, True, iterations
        if excess > 0:
            low = mid
        else:
            high = mid
    k = 0.5 * (low + high)
    return [pi ** k for pi in raw_probs], k, False, iterations


def _guard_booksum(beta: float, raw_probs: Sequence[float]) -> None:
    """A booksum below one is an arbitrage signal, never a market to price."""
    if beta < 1.0 - _BOOKSUM_EPSILON:
        raise ArbitrageError(
            f"Booksum is {beta:.6f} (< 1.0): these quotes carry no overround, so there "
            f"is nothing to strip. That is an arbitrage worth "
            f"{(1.0 / beta - 1.0) * 100.0:.2f}%, a stale leg, or legs mixed from two "
            f"books - all three need a decision, not a fair value. Pricing it anyway "
            f"reports a POSITIVE edge on every side at once, which cannot be true. "
            f"Raw implied: {[round(p, 6) for p in raw_probs]}.",
            booksum=beta, implied=raw_probs)


# ----------------------------------------------------------------------------
# Master fair-value calculator with oracle cross-check.
# ----------------------------------------------------------------------------

def calculate_fair_value(
    odds: Sequence[Any],
    oracle_tolerance: float = DEFAULT_ORACLE_TOLERANCE,
    odds_format: Optional[str] = None,
) -> FairValueResult:
    """
    Fair-value probabilities via Shin, with the Power method run as a built-in
    cross-check oracle. Sets `divergent` when max|p_shin - p_power| exceeds
    `oracle_tolerance`.

    EVERY LEG MUST BE PRESENT. Devigging a subset silently produces the wrong
    answer for all of it, and nothing in the numbers can reveal that - a two-way
    market missing its second leg just looks like a market with less margin.
    """
    clean = clean_odds(odds, odds_format)
    raw_probs = [1.0 / o for o in clean]
    beta = math.fsum(raw_probs)
    _guard_booksum(beta, raw_probs)
    overround = beta - 1.0
    warnings: List[str] = []

    shin_probs, shin_z, shin_conv, shin_iter = shin_devig(clean, odds_format=odds_format)
    power_probs, power_k, power_conv, _ = power_devig(clean, odds_format=odds_format)

    total = math.fsum(shin_probs)
    if abs(total - 1.0) > 1e-9:
        shin_conv = False
        warnings.append(
            f"Shin probabilities sum to {total:.12f}, not 1.0 - the solver did not "
            f"converge. These are NOT renormalised on purpose; do not trade on them.")
    if not power_conv:
        warnings.append("Power oracle did not converge; its cross-check is unreliable.")
    if any(p < 0.0 for p in shin_probs):
        warnings.append(
            f"Shin produced a NEGATIVE probability {[round(p, 6) for p in shin_probs]}. "
            f"Not clipped: this means the estimator is wrong for this market, not "
            f"that one outcome is slightly impossible.")

    deltas = [abs(sp - pp) for sp, pp in zip(shin_probs, power_probs)]
    max_delta = max(deltas) if deltas else 0.0
    divergent = max_delta > oracle_tolerance
    if divergent:
        warnings.append(
            f"Shin and Power disagree by {max_delta:.4f} (tolerance "
            f"{oracle_tolerance:.4f}). Two independent estimators diverging this far "
            f"usually means a stale or mistyped leg - check the quotes before "
            f"trusting any edge computed from them.")

    outcomes = [
        OutcomeFairValue(
            index=idx,
            offered_odds=o,
            implied_prob_raw=pi,
            fair_prob=p,
            fair_odds=1.0 / p if p > 0 else math.inf,
            expected_value=calculate_edge(p, o),
            quarter_kelly=kelly_fraction(p, o, 0.25),
        )
        for idx, (o, pi, p) in enumerate(zip(clean, raw_probs, shin_probs))
    ]

    return FairValueResult(
        method=SHIN,
        outcomes=outcomes,
        overround=overround,
        shin_z=shin_z,
        power_k=power_k,
        converged=shin_conv,
        iterations=shin_iter,
        divergent=divergent,
        max_oracle_delta=max_delta,
        warnings=tuple(warnings),
    )
