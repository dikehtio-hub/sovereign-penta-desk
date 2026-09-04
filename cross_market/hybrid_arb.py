"""
Cross-market arbitrage: a prediction market leg against a sportsbook leg.

WHY THIS MODULE EXISTS, AND WHAT IT MOSTLY SAYS

A Polymarket position and a sportsbook position on opposite sides of the same
event look like the cleanest arbitrage available, because the two venues price
independently and their errors are uncorrelated. In dollars that is true. After
tax it is usually false, and the gap is not small.

The reason is an asymmetry with no analogue in single-venue arbitrage:

    EACH LEG'S LOSS IS DEDUCTIBLE ONLY AGAINST A CLASS OF INCOME THE OTHER LEG
    DOES NOT PRODUCE.

  * When the sportsbook leg loses, the winner is Polymarket. Under the capital
    reading that is a CAPITAL GAIN, not a gambling winning. NJ GITA 54A:5-1(g)
    nets gambling losses against gambling WINNINGS - same category, same year,
    capped at winnings. There are none here. The state relief that makes a
    sportsbook loss bearable is not available in the branch that needs it.

  * When the Polymarket leg loses, the winner is the sportsbook. That is
    ORDINARY income. IRC 1211(b) lets a capital loss offset capital gains without
    limit but ordinary income by only $3,000 a year; the rest carries forward and
    is worth nothing this year. The capital relief that makes a Polymarket loss
    bearable is likewise unavailable in the branch that needs it.

Both reliefs therefore depend on income the position does not generate - on
CAPACITY the taxpayer either has from elsewhere or does not have at all. That is
why this module takes `gambling_win_capacity` and `capital_gain_capacity` as
inputs and defaults both to ZERO. A delta is not a property of a leg; it is a
property of the leg and the rest of the return together.

WHAT THE NUMBERS COME OUT AT (NJ resident, composite 32.37%, state 6.37%):

    required gross arbitrage, both capacities ample      8.83%
    required gross arbitrage, no capacity at all        16.75%
    for reference, single-venue sportsbook arb          23.93%
    what cross-book arbitrage actually pays              1-3%

So cross-market genuinely beats staying inside the sportsbook - the capital leg
is worth roughly seven points of hurdle - and it is still nowhere near riskless.
At 1-3% gross, every opportunity this module finds is an after-tax loss, and its
main job is to say so before the capital is committed.

ONE ASSUMPTION IS LOAD-BEARING AND UNSETTLED: that a Polymarket event contract
is CAPITAL rather than wagering. The IRS has not ruled on retail-held
CFTC-regulated binary event contracts. IRC 1234A supports capital treatment for
gain or loss on the termination of a right with respect to property; a
characterisation as wagering would put the leg under IRC 165(d) and collapse it
to the same trap as the sportsbook. `prediction_as_wagering_tax` prices that
reading, and it is materially worse. Do not present the capital number as settled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# IRC 1211(b): capital losses offset ordinary income up to $3,000 a year for a
# single filer or MFJ ($1,500 MFS). The excess carries forward under 1212(b) and
# is worth nothing in the year the arbitrage is struck, so it is not credited.
CAPITAL_LOSS_ORDINARY_CAP = 3000.0

# Below this the split search is not meaningful and the caller is asking for a
# position too small to bother sizing.
MIN_CAPITAL = 1.0


class HybridArbError(ValueError):
    """The two legs cannot form a hedge."""


@dataclass(frozen=True)
class LegTax:
    """
    How one leg is taxed, on the way up and on the way down.

    `relief_rate` and `relief_capacity` are separate on purpose. A leg can have a
    perfectly good deduction rate and no income to apply it to, which is exactly
    the cross-market situation, and collapsing the two into a single `delta`
    hides the failure - it reports full relief for a taxpayer who will receive
    none.
    """

    label: str
    gain_rate: float                 # tax on this leg's winnings
    relief_rate: float               # marginal rate a relievable loss is relieved at
    relief_capacity: float           # dollars of loss that CAN be relieved this year
    secondary_rate: float = 0.0      # rate on the fallback tranche (1211(b) ordinary)
    secondary_cap: float = 0.0       # size of that tranche

    def relief_on(self, loss: float) -> float:
        """Cash value of losing `loss` on this leg, this year."""
        loss = max(0.0, float(loss))
        primary = min(loss, max(0.0, self.relief_capacity))
        spill = min(max(loss - primary, 0.0), max(0.0, self.secondary_cap))
        return primary * self.relief_rate + spill * self.secondary_rate

    def net_win(self, profit: float) -> float:
        return float(profit) * (1.0 - self.gain_rate)

    @property
    def effective_delta(self) -> float:
        """
        Relief on the FIRST marginal dollar, as a fraction of the gain rate.

        This is the number a `delta` argument is really asking for, and it is
        what makes `delta_state = 1.0` misleading: full state netting on a leg
        with no federal deduction is a delta of 6.37/32.37 = 0.197, not 1.0.
        """
        if self.gain_rate <= 0:
            return 0.0
        rate = self.relief_rate if self.relief_capacity > 0 else self.secondary_rate
        return min(max(rate / self.gain_rate, 0.0), 1.0)


@dataclass(frozen=True)
class HybridLeg:
    """One side of a cross-market hedge, with everything needed to execute it."""

    venue: str                       # "polymarket" | book name
    selection: str
    decimal_odds: float
    tax: LegTax
    token_id: str = ""               # Polymarket only
    limit_price: Optional[float] = None
    raw_price: Optional[float] = None
    fee_rate: float = 0.0

    @property
    def implied_prob(self) -> float:
        return 1.0 / self.decimal_odds


@dataclass
class HybridArbResult:
    """The verdict on one cross-market pair."""

    leg_a: HybridLeg
    leg_b: HybridLeg
    capital: float
    stake_a: float
    stake_b: float
    booksum: float
    gross_arb: float                 # R - 1 on the pre-tax equal-return dutch
    branch_a: float                  # after-tax dollars if leg A wins
    branch_b: float                  # after-tax dollars if leg B wins
    worst_after_tax: float
    breakeven_gross_arb: Optional[float] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def viable(self) -> bool:
        return self.worst_after_tax > 0.0

    @property
    def worst_after_tax_pct(self) -> float:
        return self.worst_after_tax / self.capital if self.capital else 0.0

    @property
    def tax_manufactured_variance(self) -> float:
        """
        After-tax spread left by staking this position the way a PRE-TAX
        arbitrage calculator would tell you to.

        Measured at the pre-tax dutch - stakes proportional to 1/O, which return
        the same dollars whichever leg wins - and NOT at the split this module
        chooses. Measuring it at our own split would always return zero, because
        that split is found by equalising the two after-tax branches: the metric
        would be reporting on its own construction and would show 0.00% forever.

        What it measures instead is the cost of the naive stake: how far apart the
        two outcomes end up once tax lands on a position that was riskless in
        dollars. That is the number a spreadsheet arbitrage calculator hides.
        """
        booksum = self.leg_a.implied_prob + self.leg_b.implied_prob
        if booksum <= 0:
            return 0.0
        naive_a = self.capital * (self.leg_a.implied_prob / booksum)
        one, two = branch_returns(self.leg_a, self.leg_b,
                                  naive_a, self.capital - naive_a)
        return abs(one - two)

    def as_record(self) -> Dict[str, Any]:
        return {
            "venue_a": self.leg_a.venue, "selection_a": self.leg_a.selection,
            "odds_a": self.leg_a.decimal_odds, "token_id": self.leg_a.token_id,
            "limit_price": self.leg_a.limit_price,
            "venue_b": self.leg_b.venue, "selection_b": self.leg_b.selection,
            "odds_b": self.leg_b.decimal_odds,
            "capital": self.capital, "stake_a": self.stake_a, "stake_b": self.stake_b,
            "booksum": self.booksum, "gross_arb": self.gross_arb,
            "branch_a": self.branch_a, "branch_b": self.branch_b,
            "worst_after_tax": self.worst_after_tax,
            "worst_after_tax_pct": self.worst_after_tax_pct,
            "breakeven_gross_arb": self.breakeven_gross_arb,
            "viable": self.viable,
            "tax_manufactured_variance": self.tax_manufactured_variance,
            "warnings": list(self.warnings),
        }


# --------------------------------------------------------------------------
# Venue pricing
# --------------------------------------------------------------------------

def polymarket_odds(price: float, fee_rate: float = 0.0) -> float:
    """
    Decimal odds for a Polymarket YES share bought at `price`.

    A share costs `price` and settles at $1, so the gross decimal odds are 1/p.
    Polymarket charges on PROCEEDS, not on stake, so the fee lands on the profit
    leg only - applying it to the whole payout overstates the charge at short
    odds, where most of the payout is the returned stake.
    """
    price = float(price)
    if not 0.0 < price < 1.0:
        raise HybridArbError(
            "A Polymarket price must sit strictly between 0 and 1; got %r." % price)
    fee = min(max(float(fee_rate), 0.0), 1.0)
    return 1.0 + (1.0 / price - 1.0) * (1.0 - fee)


# --------------------------------------------------------------------------
# Tax profiles
# --------------------------------------------------------------------------

def sportsbook_leg_tax(ordinary_rate: float, state_rate: float,
                       gambling_win_capacity: float = 0.0) -> LegTax:
    """
    A New Jersey sportsbook leg for a casual filer on the standard deduction.

    Federally the loss is worth NOTHING - IRC 165(d) makes it a Schedule A
    deduction and a standard-deduction filer never reaches Schedule A. The state
    is a separate and independent question: NJ nets gambling losses against
    gambling winnings as a CATEGORY, with no itemisation requirement.

    But that netting needs winnings to net against, and `gambling_win_capacity`
    is how many the taxpayer actually has. In a cross-market hedge the winning
    leg is Polymarket, which under the capital reading produces none, so the
    default is zero - the conservative and usually correct answer. Pass the
    desk's year-to-date gambling winnings to credit the relief honestly.

    The relief rate is the BARE state rate, without the safety buffer. The buffer
    exists to over-reserve; adding it to a benefit would over-credit instead,
    which is the wrong direction on both counts.
    """
    return LegTax(label="sportsbook (NJ, standard deduction)",
                  gain_rate=float(ordinary_rate),
                  relief_rate=float(state_rate),
                  relief_capacity=max(0.0, float(gambling_win_capacity)))


def polymarket_leg_tax(capital_rate: float, ordinary_rate: float,
                       capital_gain_capacity: float = 0.0,
                       ordinary_cap: float = CAPITAL_LOSS_ORDINARY_CAP) -> LegTax:
    """
    A Polymarket leg read as a CAPITAL asset - the favourable, unsettled view.

    A capital loss offsets capital gains dollar for dollar without limit, so
    `capital_gain_capacity` is the taxpayer's other realised gains for the year.
    Beyond that IRC 1211(b) allows only $3,000 against ordinary income; the
    remainder carries forward under 1212(b) and is worth nothing in the year the
    position is struck, so it is credited at zero rather than at some discounted
    future rate. Discounting a carryforward requires knowing next year's gains,
    which nobody does at the moment of placing the bet.
    """
    return LegTax(label="polymarket (capital, IRC 1234A reading)",
                  gain_rate=float(capital_rate),
                  relief_rate=float(capital_rate),
                  relief_capacity=max(0.0, float(capital_gain_capacity)),
                  secondary_rate=float(ordinary_rate),
                  secondary_cap=max(0.0, float(ordinary_cap)))


def prediction_as_wagering_tax(ordinary_rate: float, state_rate: float,
                               gambling_win_capacity: float = 0.0) -> LegTax:
    """
    The adverse reading: the event contract is a WAGER under IRC 165(d).

    If a prediction market contract is characterised as wagering rather than
    property, the capital treatment vanishes and the leg becomes the same trap as
    the sportsbook. This exists so the desk can price the downside of the
    assumption instead of assuming it away.
    """
    return sportsbook_leg_tax(ordinary_rate, state_rate, gambling_win_capacity)


def resolve_rates(hook: Any) -> Tuple[float, float, float]:
    """(ordinary composite, capital composite, bare state) from the live config."""
    rates = (getattr(hook, "config", {}) or {}).get("tax_rates", {}) or {}
    state = float(rates.get("state_tax_rate", 0.0637))
    buffer_pct = float(rates.get("safety_buffer_pct", 0.02))
    ordinary = float(rates.get("short_term_capital_gains", 0.24)) + state + buffer_pct
    # Event contracts resolve in days or weeks, so the holding period is short and
    # the capital leg is taxed at ordinary rates anyway. It is named separately
    # because a long-dated market that survives a year is taxed at the long-term
    # rate, and the two must not be silently conflated.
    capital = ordinary
    return ordinary, capital, state


# --------------------------------------------------------------------------
# The branch algebra
# --------------------------------------------------------------------------

def branch_returns(leg_a: HybridLeg, leg_b: HybridLeg,
                   stake_a: float, stake_b: float) -> Tuple[float, float]:
    """
    After-tax dollars in each of the two branches.

    Exactly one leg wins. The winner is taxed on its profit at its own gain rate;
    the loser gives up its stake and recovers whatever relief its own capacity
    allows. Nothing here assumes the two legs are taxed alike, which is the whole
    point of the module.
    """
    stake_a, stake_b = float(stake_a), float(stake_b)
    a_wins = (leg_a.tax.net_win(stake_a * (leg_a.decimal_odds - 1.0))
              - stake_b + leg_b.tax.relief_on(stake_b))
    b_wins = (leg_b.tax.net_win(stake_b * (leg_b.decimal_odds - 1.0))
              - stake_a + leg_a.tax.relief_on(stake_a))
    return a_wins, b_wins


def optimal_split(leg_a: HybridLeg, leg_b: HybridLeg, capital: float,
                  tolerance: float = 1e-10) -> float:
    """
    Fraction of capital on leg A that maximises the WORST branch.

    Bisection rather than a closed form, and deliberately so. The relief terms
    are piecewise linear - they kink where a loss exhausts its capacity, and
    again at the 1211(b) ceiling - so a closed-form dutch derived on the
    uncapped branch is wrong past the first kink, and wrong in the optimistic
    direction.

    The search is sound because branch A rises monotonically in the A stake while
    branch B falls: every relief rate is below 1, so giving up a dollar of stake
    can never be worth more than the dollar. Their difference is therefore
    strictly increasing in the split and crosses zero at most once. When it never
    crosses, the maximum sits at an endpoint and the clamp returns it.
    """
    capital = float(capital)
    if capital < MIN_CAPITAL:
        raise HybridArbError("Capital must be at least %s; got %r."
                             % (MIN_CAPITAL, capital))

    def gap(f: float) -> float:
        a, b = branch_returns(leg_a, leg_b, f * capital, (1.0 - f) * capital)
        return a - b

    lo, hi = 0.0, 1.0
    if gap(lo) >= 0.0:          # A already ahead with nothing staked on it
        return 0.0
    if gap(hi) <= 0.0:
        return 1.0
    while hi - lo > tolerance:
        mid = (lo + hi) / 2.0
        if gap(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _rescaled(leg: HybridLeg, scale: float) -> HybridLeg:
    price = leg.implied_prob * scale
    return HybridLeg(venue=leg.venue, selection=leg.selection,
                     decimal_odds=1.0 / price, tax=leg.tax,
                     token_id=leg.token_id, limit_price=leg.limit_price,
                     raw_price=leg.raw_price, fee_rate=leg.fee_rate)


def breakeven_gross_arb(leg_a: HybridLeg, leg_b: HybridLeg,
                        capital: float = 10000.0) -> Optional[float]:
    """
    Gross arbitrage this pair would need before the worst branch stops losing.

    Both implied probabilities are scaled by a common factor, which fattens the
    arbitrage while holding the SHAPE of the book fixed. That matters: the hurdle
    depends on how lopsided the two legs are, not only on how wide the book is,
    so scaling one leg alone would answer a different question. Returns None when
    no achievable book clears it.

    THE SEARCH MUST BE ALLOWED TO RUN PAST THE CURRENT BOOK. An earlier version
    capped the scale at 1.0 - the book as quoted - and so could only ever look at
    positions FATTER than the live one. When a pair already cleared, that cap made
    the function return the current arbitrage and call it the hurdle, which reads
    as "this barely scrapes through" for a position with room to spare. The range
    now extends to a book sum of 2.0, which also lets the hurdle come back
    NEGATIVE: with generous relief on both legs a position can survive a book that
    is not a gross arbitrage at all, and that is a real and useful answer.
    """
    base = leg_a.implied_prob + leg_b.implied_prob
    if base <= 0:
        return None

    def worst_at(scale: float) -> float:
        a, b = _rescaled(leg_a, scale), _rescaled(leg_b, scale)
        f = optimal_split(a, b, capital)
        return min(branch_returns(a, b, f * capital, (1.0 - f) * capital))

    lo, hi = 1e-6, 2.0 / base
    if worst_at(lo) <= 0.0:
        return None                          # even a near-free position never clears
    if worst_at(hi) > 0.0:
        return 1.0 / (hi * base) - 1.0       # survives even a 2.0 book sum
    for _ in range(120):
        mid = (lo + hi) / 2.0
        if worst_at(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    booksum = lo * base
    return (1.0 / booksum - 1.0) if booksum > 0 else None


# --------------------------------------------------------------------------
# The entry point
# --------------------------------------------------------------------------

def evaluate_hybrid_arb(leg_a: HybridLeg, leg_b: HybridLeg,
                        capital: float = 1000.0,
                        compute_breakeven: bool = True) -> HybridArbResult:
    """Size a cross-market pair and price the worst branch after tax."""
    if leg_a.decimal_odds <= 1.0 or leg_b.decimal_odds <= 1.0:
        raise HybridArbError("Decimal odds must exceed 1.0 on both legs.")
    capital = float(capital)
    if capital < MIN_CAPITAL:
        raise HybridArbError("Capital must be at least %s; got %r."
                             % (MIN_CAPITAL, capital))

    booksum = leg_a.implied_prob + leg_b.implied_prob
    gross_arb = (1.0 / booksum - 1.0) if booksum > 0 else 0.0

    f = optimal_split(leg_a, leg_b, capital)
    stake_a, stake_b = f * capital, (1.0 - f) * capital
    branch_a, branch_b = branch_returns(leg_a, leg_b, stake_a, stake_b)
    worst = min(branch_a, branch_b)

    warnings: List[str] = []
    if booksum >= 1.0:
        warnings.append(
            "NOT AN ARBITRAGE GROSS: the book sums to %.4f. The two legs together "
            "cost more than they can return." % booksum)
    if leg_a.tax.relief_capacity <= 0 and leg_b.tax.relief_capacity <= 0:
        warnings.append(
            "NEITHER LEG HAS RELIEF CAPACITY. The sportsbook loss has no gambling "
            "winnings to net against under NJ 54A:5-1(g), and the capital loss has "
            "no capital gains to offset under IRC 1211(b) - only the $3,000 "
            "ordinary tranche. This is the default because it is usually true, and "
            "it is what makes the hurdle roughly double the single-venue figure.")
    if worst <= 0 < gross_arb:
        warnings.append(
            "AFTER-TAX LOSS ON A GROSS ARBITRAGE. The book shows %+.2f%% and the "
            "worst branch returns %+.2f%%. This is the characteristic cross-market "
            "trap: the position is riskless in dollars and loses money in April."
            % (gross_arb * 100.0, (worst / capital) * 100.0))
    result = HybridArbResult(
        leg_a=leg_a, leg_b=leg_b, capital=capital,
        stake_a=stake_a, stake_b=stake_b,
        booksum=booksum, gross_arb=gross_arb,
        branch_a=branch_a, branch_b=branch_b, worst_after_tax=worst,
        warnings=warnings)
    # Read from the result, because the number that matters is the spread the
    # NAIVE pre-tax stake would leave. The spread on our own split is driven to
    # zero by the solver, so warning on it would mean warning never.
    spread = result.tax_manufactured_variance
    if spread > 0.005 * capital:
        warnings.append(
            "STAKED THE PRE-TAX WAY, THE TWO BRANCHES LAND %.2f%% APART on a "
            "position that is riskless in dollars. One branch books a taxable win "
            "against a non-deductible loss and the other does the reverse. The "
            "stakes below are corrected for that; a spreadsheet arbitrage "
            "calculator's are not." % ((spread / capital) * 100.0))
    if compute_breakeven:
        result.breakeven_gross_arb = breakeven_gross_arb(leg_a, leg_b, capital)
    return result


def build_legs(hook: Any, polymarket_price: float, polymarket_selection: str,
               book: str, book_odds: float, book_selection: str,
               token_id: str = "", polymarket_fee: float = 0.0,
               gambling_win_capacity: float = 0.0,
               capital_gain_capacity: float = 0.0,
               prediction_is_wagering: bool = False) -> Tuple[HybridLeg, HybridLeg]:
    """Assemble both legs from live config, so the rates are never hardcoded."""
    ordinary, capital_rate, state = resolve_rates(hook)
    tax_a = (prediction_as_wagering_tax(ordinary, state, gambling_win_capacity)
             if prediction_is_wagering
             else polymarket_leg_tax(capital_rate, ordinary, capital_gain_capacity))
    leg_a = HybridLeg(venue="polymarket", selection=polymarket_selection,
                      decimal_odds=polymarket_odds(polymarket_price, polymarket_fee),
                      tax=tax_a, token_id=token_id,
                      limit_price=float(polymarket_price),
                      raw_price=float(polymarket_price), fee_rate=polymarket_fee)
    leg_b = HybridLeg(venue=book, selection=book_selection,
                      decimal_odds=float(book_odds),
                      tax=sportsbook_leg_tax(ordinary, state, gambling_win_capacity))
    return leg_a, leg_b
