"""
Polymarket Monarch integration hook.

Adapter that lets a trading bot ask one question before it sizes an order:
"how much of this money is actually mine?" Realised gains create a tax liability
the moment they are booked, so the cash sitting in the wallet overstates risk
capital by exactly the escrow. Sizing off the raw balance is how a profitable
year turns into an April that has to be funded by liquidating positions.

    from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

    hook = MonarchBankrollHook(max_position_pct=0.05)
    decision = hook.check_order(desired_notional=750.0, live_cash=8_200.0)
    if not decision.approved:
        print(decision.reason)
    stake = decision.approved_notional      # already clamped - just use it

Design notes:

  * READ-ONLY. Nothing here writes to the ledger. A bot that crashes mid-decision
    cannot corrupt tax records.
  * NEVER RAISES INTO THE CALLER. A missing database or unreadable config makes
    `check_order()` return a REJECTED decision, not an exception. An accounting
    outage must not take down the trading loop, and it must not silently
    fail-open into unlimited sizing either.
  * CACHED. `calculate_tax_summary()` is a handful of SQLite aggregates, but a
    scanner calling it per candidate market in a tight loop would hit it hundreds
    of times a minute for an answer that changes only when a trade settles. The
    snapshot is cached for `cache_ttl_s` and can be forced with `refresh()`.
  * LIVE CASH WINS. `config.yaml` carries a static `default_cash_balance_usdc`
    that goes stale the moment anything trades. Pass `live_cash=` from the bot's
    own balance check and the escrow is applied against that instead.
"""
import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Sequence

from ..config import load_config
from ..database.db import get_connection
from ..engine.tax_calculator import calculate_tax_summary

DEFAULT_MAX_POSITION_PCT = 0.05  # 5% of safe bankroll per order
DEFAULT_MIN_ORDER_USD = 1.0      # Polymarket's practical floor; below this, don't bother
DEFAULT_CACHE_TTL_S = 60.0


# ----------------------------------------------------------------------------
# Empirical per-category sizing
# ----------------------------------------------------------------------------

MIN_SIZING_PCT = 0.01          # defensive floor
MAX_SIZING_PCT = 0.08          # conviction ceiling
KELLY_FRACTION = 0.25          # quarter-Kelly
DEFAULT_ENTRY_PRICE = 0.50     # used only when a category has no priced history
CATEGORY_WINDOW = 40           # most recent completed trades per category
MIN_CATEGORY_TRADES = 5        # below this the empirical sizer does not engage
DEFAULT_PAYOFF_BASIS = "conservative"   # conservative | price | realized
DEFAULT_ASSUMED_ROUND_TRIP_FEE = 0.02   # break-even filter only, never written
MAX_PAYOFF_RATIO = 10.0        # cap on b when a category has no losses yet

# Substring -> category. Checked in order, first match wins, so put the specific
# patterns above the general ones. Override with `bot_integration.categories`.
DEFAULT_CATEGORY_PATTERNS = (
    ("crypto-intraday", ("-UP-OR-DOWN-", "-UPDOWN-", "-5M-", "-15M-", "-1H-")),
    ("crypto", ("BITCOIN", "ETHEREUM", "SOLANA", "DOGE", "BTC", "ETH", "SOL", "XRP", "CRYPTO")),
    ("macro", ("FED", "CPI", "INFLATION", "RATE", "GDP", "RECESSION", "JOBS", "UNEMPLOYMENT")),
    ("politics", ("ELECTION", "PRESIDENT", "SENATE", "CONGRESS", "TRUMP", "BIDEN", "POLL")),
    ("sports", ("NBA", "NFL", "MLB", "UCL", "PREMIER-LEAGUE", "WORLD-CUP", "WIN-THE")),
)


def categorise(symbol: str, patterns=DEFAULT_CATEGORY_PATTERNS) -> str:
    """
    Bucket a market symbol into a category for edge measurement.

    Deliberately crude and substring-based: the point is to group enough closed
    trades together that a win rate means something. Too many categories and every
    bucket is small enough that the uncertainty penalty wipes out the signal - the
    fine-grained split you want for analysis is the wrong split for sizing.
    """
    # Padded so a whole-token needle can be matched as `-TOKEN-` at either end.
    #
    # Raw substring matching is wrong here and quietly so: "ETH" appears inside
    # "SOMETHING", "SOL" inside "ABSOLUTELY", "BTC" inside plenty of hashes. A
    # symbol landing in the wrong category silently sizes it off another market
    # type's win rate. A needle with no hyphen is therefore matched as a whole
    # token; a hyphenated needle ("-UP-OR-DOWN-", "PREMIER-LEAGUE") is a phrase
    # and stays a substring match.
    padded = "-" + str(symbol or "").upper().replace("/", "-") + "-"
    for category, needles in patterns:
        for needle in needles:
            if "-" in needle:
                if needle in padded:
                    return category
            elif f"-{needle}-" in padded:
                return category
    return "uncategorised"


def wilson_lower_bound(wins: int, trials: int, z: float = 1.0) -> float:
    """
    Lower bound of the Wilson score interval - the conservative win rate.

    REPLACES the briefed `p_hat - sqrt(p_hat(1-p_hat)/N)`, which has a failure
    mode exactly where it matters most: that term is ZERO when p_hat is 0 or 1, so
    three wins from three trades returns 1.0 - full certainty from three
    observations - and sizes the position at the maximum. Wilson returns 0.75 for
    the same input, and converges on the naive answer once the sample is real
    (70/100: 0.6524 vs 0.6542), so it costs nothing where the naive form was safe.

    z = 1.0 keeps the brief's one-sigma intent.
    """
    if trials <= 0:
        return 0.0
    p_hat = wins / trials
    denominator = 1.0 + (z * z) / trials
    centre = (p_hat + (z * z) / (2 * trials)) / denominator
    margin = (z * math.sqrt(p_hat * (1.0 - p_hat) / trials
                            + (z * z) / (4.0 * trials * trials))) / denominator
    return max(0.0, centre - margin)


def kelly_from_payoff_ratio(win_probability: float, payoff_ratio: float) -> float:
    """
    Kelly stake from a win probability and a payoff ratio b = R+ / R-.

        f* = max(0, (p(b + 1) - 1) / b)

    which is the standard f* = p - (1 - p)/b, and is <= 0 exactly when expectancy
    p*b - (1 - p) is <= 0. The clamp is therefore not a separate rule: a category
    with negative expectancy sizes to ZERO, it does not scale up on win rate.

    WHY THIS MATTERS MORE THAN WIN RATE. A book that wins 60% of the time at +0.05
    and loses 40% at -0.40 has a 60% win rate and loses money: b = 0.125, so
    expectancy is 0.6*0.125 - 0.4 = -0.325. Sizing on win rate alone would grow
    that position. Sizing on magnitude closes it.
    """
    b = float(payoff_ratio)
    if b <= 0:
        return 0.0
    p = float(win_probability)
    return max(0.0, (p * (b + 1.0) - 1.0) / b)


def kelly_fraction_for(win_probability: float, entry_price: float) -> float:
    """
    Kelly stake for a prediction-market share bought at `entry_price`, paying $1.

    Net odds on a share costing q are b = (1 - q) / q, so the standard
    f* = p - (1 - p)/b reduces to:

        f* = (p - q) / (1 - q)

    which is 0 when the price already equals the win probability - no edge, no
    stake - and negative when the market is against you. Negative is clamped away
    by the caller; this hook sizes long positions only.
    """
    price = min(max(float(entry_price), 1e-6), 1.0 - 1e-6)
    return (float(win_probability) - price) / (1.0 - price)


@dataclass
class CategoryEdge:
    """Measured trading edge for one category, and the position cap it implies."""
    category: str
    trades: int = 0
    wins: int = 0
    win_rate: float = 0.0
    conservative_win_rate: float = 0.0
    avg_entry_price: float = DEFAULT_ENTRY_PRICE
    net_pnl: float = 0.0
    avg_win_return: float = 0.0     # R+ : mean gain per dollar of basis, on wins
    avg_loss_return: float = 0.0    # R- : mean loss per dollar of basis, on losses
    payoff_ratio: float = 0.0       # b = R+ / R-
    expectancy: float = 0.0         # p*b - (1-p), per dollar risked
    kelly_fraction: float = 0.0
    sizing_pct: float = 0.0
    basis: str = "default"          # "empirical" | "default"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        if self.basis == "default":
            return f"{self.category}: no closed trades, using the flat cap ({self.sizing_pct * 100:.1f}%)"
        if self.sizing_pct <= 0:
            return (f"{self.category}: {self.wins}/{self.trades} wins but NEGATIVE expectancy "
                    f"({self.expectancy:+.3f} per $ risked, b={self.payoff_ratio:.2f}) -> size 0")
        return (f"{self.category}: {self.wins}/{self.trades} wins "
                f"(p={self.win_rate:.2f}, conservative {self.conservative_win_rate:.2f}, "
                f"b={self.payoff_ratio:.2f}, E={self.expectancy:+.3f}) "
                f"@ VWAP ${self.avg_entry_price:.2f} -> {self.sizing_pct * 100:.1f}% cap")


# ----------------------------------------------------------------------------
# Strategy capital buckets
# ----------------------------------------------------------------------------

SANDBOX_STRATEGY = "sandbox"

# How a strategy is recorded in `transactions.notes`. The schema is FROZEN, so
# there is no column for it - the tag rides in free text instead.
#
# The trailing ';' is load-bearing. Matching `%strategy:sandbox%` would also match
# `strategy:sandbox_v2`, silently pooling a new strategy's exposure into the very
# bucket it was meant to be quarantined from. With the terminator the pattern is
# `%strategy:sandbox;%` and cannot straddle a name boundary.
STRATEGY_TAG_PREFIX = "strategy:"
STRATEGY_TAG_SUFFIX = ";"


def strategy_tag(strategy: str) -> str:
    """`sandbox` -> `strategy:sandbox;` - the exact token written into notes."""
    return f"{STRATEGY_TAG_PREFIX}{str(strategy).strip()}{STRATEGY_TAG_SUFFIX}"


def tag_strategy(transaction: Dict[str, Any], strategy: Optional[str]) -> Dict[str, Any]:
    """
    Stamps a transaction dict with its originating strategy, in place.

    Used by the ingestors so attribution is recorded where a trade is created,
    without touching the frozen lot engine or schema.
    """
    if not strategy:
        return transaction
    tag = strategy_tag(strategy)
    notes = str(transaction.get("notes") or "")
    if tag not in notes:
        transaction["notes"] = f"{tag} {notes}".strip()
    return transaction


@dataclass
class StrategyBudget:
    """One strategy's ring-fenced slice of the safe bankroll."""
    strategy: str
    allocation_pct: float = 1.0     # after normalisation
    budget: float = 0.0             # dollars
    deployed: float = 0.0
    remaining: float = 0.0
    enforced: bool = False          # False = no buckets configured, whole bankroll
    quarantined: bool = False       # True = routed here because it was unrecognised

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        if not self.enforced:
            return f"{self.strategy}: unbucketed (whole safe bankroll)"
        tag = " [QUARANTINED]" if self.quarantined else ""
        return (f"{self.strategy}: {self.allocation_pct * 100:.0f}% = ${self.budget:,.2f}, "
                f"${self.deployed:,.2f} deployed, ${self.remaining:,.2f} left{tag}")


class StrategyAllocationError(ValueError):
    """
    A `strategies:` block that cannot be honoured.

    Its own type so callers can tell a MISCONFIGURATION from an outage. They must
    be handled differently: an outage means "we cannot check, degrade
    gracefully", while a bad allocation table means "the operator asked for
    something impossible", and quietly continuing would size every bucket larger
    than they believe.
    """


def normalise_allocations(raw: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """
    Validates a `strategies:` block into fractions of the safe bankroll.

    Over-allocation is a HARD FAILURE. Allocations totalling 130% do not mean
    "we have 130%" - they mean every bucket is 30% larger than the operator
    believes, which is the over-sizing the escrow gate exists to prevent. Scaling
    silently would produce buckets nobody asked for and hide the typo that caused
    them, so it raises instead.

    A total BELOW 1.0 is fine and is left alone: the shortfall is unallocated
    reserve. Inflating buckets to consume it would be the same bug in reverse.

    Negative and non-numeric entries are dropped with a warning rather than
    raising - they are unusable, not dangerous.
    """
    if not isinstance(raw, dict) or not raw:
        return {}
    cleaned: Dict[str, float] = {}
    for name, value in raw.items():
        try:
            fraction = float(value)
        except (TypeError, ValueError):
            print(f"[WARN] Strategy allocation for {name!r} is not a number; ignoring.")
            continue
        if fraction <= 0:
            continue
        cleaned[str(name)] = fraction
    if not cleaned:
        return {}

    total = sum(cleaned.values())
    if total > 1.0001:
        breakdown = ", ".join(f"{name} {fraction * 100:g}%"
                              for name, fraction in sorted(cleaned.items()))
        raise StrategyAllocationError(
            f"bot_integration.strategies allocates {total * 100:g}% of the safe bankroll "
            f"({breakdown}). Allocations must total 100% or less - the remainder is held "
            f"as unallocated reserve. Fix config.yaml; nothing is scaled automatically, "
            f"because a silently shrunk bucket hides the typo that caused it.")
    return cleaned


# Categories the wagering rules apply to. IRC 165(d) governs these and nothing
# else in the book: a capital loss nets against a capital gain, a gambling loss
# does not.
WAGERING_CATEGORIES = frozenset({"sports", "sports_bet", "sports_betting"})

# Fraction of full Kelly used when an edge is supplied. Quarter-Kelly matches the
# prediction-market sizer already in this file; full Kelly on an ESTIMATED edge is
# how a good model still goes broke.
DEFAULT_KELLY_FRACTION = 0.25


@dataclass
class BankrollDecision:
    """
    The answer to "can I place this order, and for how much?"

    `approved_notional` is authoritative: it is already clamped to every limit,
    so a caller that ignores `approved` and just uses the number still cannot
    overtrade. It is 0.0 whenever `approved` is False.
    """
    approved: bool
    reason: str
    requested_notional: float
    approved_notional: float
    safe_bankroll: float
    tax_escrow: float
    cash_balance: float
    max_position_size: float
    reserve_ratio_pct: float
    tax_year: int
    stale: bool = False
    category: str = ""
    strategy: str = "default"
    strategy_budget: float = 0.0
    strategy_remaining: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        verdict = "APPROVED" if self.approved else "REJECTED"
        return (f"[{verdict}] ${self.approved_notional:,.2f} of ${self.requested_notional:,.2f} requested "
                f"| safe bankroll ${self.safe_bankroll:,.2f} | escrow ${self.tax_escrow:,.2f} | {self.reason}")


class MonarchBankrollHook:
    """
    Tax-aware position sizing gate for the Polymarket Monarch bot.

    The clamp chain applied to every order, in order:
        requested -> max_position_size (pct of safe bankroll) -> remaining safe bankroll
    with a rejection if what survives is under `min_order_usd`.
    """

    def __init__(self,
                 tax_year: Optional[int] = None,
                 db_path: Optional[Path] = None,
                 config: Optional[Dict[str, Any]] = None,
                 max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
                 min_order_usd: float = DEFAULT_MIN_ORDER_USD,
                 cache_ttl_s: float = DEFAULT_CACHE_TTL_S,
                 allow_empirical_upsize: bool = False,
                 category_window: int = CATEGORY_WINDOW,
                 min_category_trades: int = MIN_CATEGORY_TRADES,
                 payoff_basis: str = DEFAULT_PAYOFF_BASIS):
        self.config = config if config is not None else load_config()
        self.tax_year = tax_year or int(self.config.get("portfolio", {}).get("tax_year", 2026))
        self.db_path = db_path
        self.max_position_pct = float(max_position_pct)
        self.min_order_usd = float(min_order_usd)
        self.cache_ttl_s = float(cache_ttl_s)
        self.allow_empirical_upsize = bool(allow_empirical_upsize)
        self.category_window = max(1, int(category_window))
        self.min_category_trades = max(0, int(min_category_trades))
        basis = str(payoff_basis or DEFAULT_PAYOFF_BASIS).lower()
        self.payoff_basis = "conservative" if basis == "min" else basis
        bot_cfg = self.config.get("bot_integration", {}) or {}
        # `bot_integration.snapshot_cache_seconds` has been in config.yaml since
        # the bucketing work and was read by nothing - the hook used its own
        # hardcoded default, so editing the file changed no behaviour at all.
        # An EXPLICIT constructor argument still wins, so callers that pass one
        # are unaffected.
        if cache_ttl_s == DEFAULT_CACHE_TTL_S and "snapshot_cache_seconds" in bot_cfg:
            try:
                self.cache_ttl_s = max(0.0, float(bot_cfg["snapshot_cache_seconds"]))
            except (TypeError, ValueError):
                print(f"[WARN] bot_integration.snapshot_cache_seconds is not a number "
                      f"({bot_cfg['snapshot_cache_seconds']!r}); using "
                      f"{DEFAULT_CACHE_TTL_S:.0f}s.")
        configured = bot_cfg.get("categories")
        self.category_patterns = (
            tuple((name, tuple(str(n).upper() for n in needles))
                  for name, needles in configured.items())
            if isinstance(configured, dict) and configured else DEFAULT_CATEGORY_PATTERNS)
        self.strategy_allocations = self._load_strategy_allocations(bot_cfg)
        self._category_cache: Optional[Dict[str, CategoryEdge]] = None
        self._fee_source_cache: Any = None
        self._snapshot: Optional[Dict[str, Any]] = None
        self._snapshot_at = 0.0
        self._last_error: str = ""

    # -- snapshot -----------------------------------------------------------

    def snapshot(self, live_cash: Optional[float] = None, force: bool = False) -> Dict[str, Any]:
        """
        Current tax summary, cached for `cache_ttl_s`.

        Passing `live_cash` bypasses the cache: the balance is an input to the
        arithmetic, so a cached answer computed against a different balance would
        be wrong rather than merely stale.
        """
        if live_cash is not None:
            return self._compute(live_cash)
        fresh = self._snapshot is not None and (time.time() - self._snapshot_at) < self.cache_ttl_s
        if force or not fresh:
            self._snapshot = self._compute(None)
            self._snapshot_at = time.time()
        return self._snapshot

    def refresh(self) -> Dict[str, Any]:
        """Forces a re-read. Call this right after the bot books a fill."""
        return self.snapshot(force=True)

    def _compute(self, live_cash: Optional[float]) -> Dict[str, Any]:
        """
        Runs the tax summary, substituting live cash when supplied.

        On any failure returns a zeroed, `available=False` snapshot: the caller
        then rejects orders instead of trading against numbers nobody can vouch
        for. Fail-closed is the only safe direction for a spending limit.
        """
        config = self.config
        if live_cash is not None:
            config = json.loads(json.dumps(self.config))  # deep copy; never mutate the shared config
            config.setdefault("portfolio", {})["default_cash_balance_usdc"] = float(live_cash)
        try:
            summary = calculate_tax_summary(tax_year=self.tax_year, db_path=self.db_path, config=config)
            summary["available"] = True
            self._last_error = ""
            return summary
        except Exception as e:  # sqlite errors, missing db, malformed config
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"[WARN] Tax Reserve Agent unavailable ({self._last_error}); orders will be rejected.")
            return {
                "available": False, "tax_year": self.tax_year,
                "liquid_cash_balance": float(live_cash or 0.0),
                "tax_escrow_reserve": 0.0, "safe_deployable_bankroll": 0.0,
                "reserve_ratio_pct": 0.0, "net_capital_gains": 0.0,
                "breakdown_by_asset": {},
            }

    # -- measured edge per category -----------------------------------------

    def category_stats(self, tax_year: Optional[int] = None,
                       force: bool = False) -> Dict[str, CategoryEdge]:
        """
        Win rate and average entry price per category, from closed trades.

        Reads `realized_pnl` because that is the only table that knows how a
        position ENDED. Open positions are excluded on purpose - counting them
        would let a book full of losers-in-waiting read as a perfect record.

        `tax_year=None` uses every year on file: sizing wants the largest honest
        sample, not this year's slice.
        """
        if self._category_cache is not None and not force and tax_year is None:
            return self._category_cache

        conn = get_connection(self.db_path)
        try:
            # Newest first, so the per-category window keeps the RECENT trades.
            if tax_year is None:
                rows = conn.execute("""
                    SELECT symbol, quantity, cost_basis, net_gain_loss
                    FROM realized_pnl WHERE asset_class = 'prediction_market'
                    ORDER BY closed_at DESC, id DESC
                """).fetchall()
            else:
                rows = conn.execute("""
                    SELECT symbol, quantity, cost_basis, net_gain_loss
                    FROM realized_pnl WHERE asset_class = 'prediction_market' AND tax_year = ?
                    ORDER BY closed_at DESC, id DESC
                """, (tax_year,)).fetchall()
        except Exception as e:
            print(f"[WARN] Could not read category history ({type(e).__name__}: {e}).")
            rows = []
        finally:
            conn.close()

        buckets: Dict[str, Dict[str, float]] = {}
        for row in rows:
            category = categorise(row["symbol"], self.category_patterns)
            bucket = buckets.setdefault(category, {"trades": 0, "wins": 0, "qty": 0.0,
                                                   "basis": 0.0, "pnl": 0.0,
                                                   "win_gain": 0.0, "win_basis": 0.0,
                                                   "loss_amount": 0.0, "loss_basis": 0.0})
            # ROLLING WINDOW. Rows arrive newest-first, so stopping at the cap keeps
            # the most recent `window` trades. Without it a category that worked in
            # a past regime keeps its size forever: 200 old wins drown out 20 recent
            # losses, and the sizer stays loud exactly while the edge decays.
            if bucket["trades"] >= self.category_window:
                continue

            pnl = float(row["net_gain_loss"] or 0.0)
            cost = float(row["cost_basis"] or 0.0)
            bucket["trades"] += 1
            bucket["qty"] += float(row["quantity"] or 0.0)
            bucket["basis"] += cost
            bucket["pnl"] += pnl
            if pnl > 0:
                bucket["wins"] += 1
                bucket["win_gain"] += pnl
                bucket["win_basis"] += cost
            else:
                bucket["loss_amount"] += -pnl
                bucket["loss_basis"] += cost

        stats: Dict[str, CategoryEdge] = {}
        for category, bucket in buckets.items():
            trades, wins = int(bucket["trades"]), int(bucket["wins"])
            # VWAP, not an arithmetic mean: sum of value over sum of quantity, so a
            # single large fill weighs what it actually cost.
            avg_price = (bucket["basis"] / bucket["qty"]) if bucket["qty"] > 0 else DEFAULT_ENTRY_PRICE
            avg_price = min(max(avg_price, 1e-6), 1.0 - 1e-6)
            conservative = wilson_lower_bound(wins, trades)

            # Payoff magnitudes, normalised per dollar of basis actually risked.
            win_return = (bucket["win_gain"] / bucket["win_basis"]) if bucket["win_basis"] > 0 else 0.0
            loss_return = (bucket["loss_amount"] / bucket["loss_basis"]) if bucket["loss_basis"] > 0 else 0.0
            if loss_return > 0:
                payoff_ratio = win_return / loss_return
            elif win_return > 0:
                # No losses yet. b is unbounded, which would size at the ceiling off
                # a lucky streak - capped instead, and the Wilson bound is already
                # doing the heavy lifting on the probability side.
                payoff_ratio = MAX_PAYOFF_RATIO
            else:
                payoff_ratio = 0.0
            payoff_ratio = min(payoff_ratio, MAX_PAYOFF_RATIO)
            expectancy = conservative * payoff_ratio - (1.0 - conservative)

            kelly = kelly_from_payoff_ratio(conservative, payoff_ratio)
            sizing = (min(MAX_SIZING_PCT, max(MIN_SIZING_PCT, KELLY_FRACTION * kelly))
                      if kelly > 0 else 0.0)
            stats[category] = CategoryEdge(
                category=category, trades=trades, wins=wins,
                win_rate=wins / trades if trades else 0.0,
                conservative_win_rate=conservative, avg_entry_price=avg_price,
                net_pnl=bucket["pnl"], avg_win_return=win_return, avg_loss_return=loss_return,
                payoff_ratio=payoff_ratio, expectancy=expectancy,
                kelly_fraction=kelly, sizing_pct=sizing, basis="empirical")

        if tax_year is None:
            self._category_cache = stats
        return stats

    def category_edge(self, category: Optional[str], price: Optional[float] = None) -> CategoryEdge:
        """
        The position cap for one category.

        With NO closed trades the flat `max_position_pct` is returned rather than
        the 1% floor. An unmeasured category is not evidence of a bad edge, and
        dropping every new market to the defensive minimum would make the sizer a
        ratchet that only ever shrinks into what you already traded.

        `price` overrides the category's historical average entry - the Kelly
        stake depends on what THIS order pays, not what past ones did.
        """
        if not category:
            return CategoryEdge(category="", sizing_pct=self.max_position_pct, basis="default")

        stats = self.category_stats().get(category)
        if stats is None or stats.trades < self.min_category_trades:
            # NOT ENOUGH TRADES TO MEAN ANYTHING. The Wilson bound already shrinks a
            # small sample hard, but shrinking is not the same as abstaining: three
            # observations still produce a number, and that number drives real
            # money. Below the gate the flat percentage applies and the category is
            # reported as unmeasured rather than quietly sized off noise.
            observed = stats.trades if stats else 0
            return CategoryEdge(category=category, trades=observed,
                                wins=stats.wins if stats else 0,
                                sizing_pct=self.max_position_pct, basis="default")
        if price is None:
            return stats

        # WHICH PAYOFF RATIO PAIRS WITH THIS PROBABILITY?
        #
        # `p_wilson` is measured as "what fraction of CLOSED trades in this category
        # were profitable" - an exit-behaviour statistic. Pairing it with the
        # hold-to-resolution payoff b = (1-q)/q mixes two different populations:
        # most of the trades that produced p were exited early and never collected
        # the full $1, so the pairing overstates f* for anyone who scalps.
        # The self-consistent pair is (realised p, realised b).
        #
        #   realized      the consistent pair - what this book actually captures
        #   price         b = (1-q)/q, the contract's own payoff held to resolution
        #   conservative  min of the two (default): equals `realized` except when
        #                 an expensive order caps it lower, which is correct - a 90c
        #                 share pays b = 0.11 no matter how good the history is.
        q = min(max(float(price), 1e-6), 1.0 - 1e-6)
        price_ratio = (1.0 - q) / q
        # "min" is accepted as an alias for "conservative" - the backtest reports
        # under that name, and a config that reads the way the evidence was written
        # up is worth one line of aliasing.
        if self.payoff_basis == "price" or stats.payoff_ratio <= 0:
            effective_ratio = price_ratio
        elif self.payoff_basis == "realized":
            effective_ratio = stats.payoff_ratio
        else:
            effective_ratio = min(price_ratio, stats.payoff_ratio)

        kelly = kelly_from_payoff_ratio(stats.conservative_win_rate, effective_ratio)
        return CategoryEdge(
            category=category, trades=stats.trades, wins=stats.wins,
            win_rate=stats.win_rate, conservative_win_rate=stats.conservative_win_rate,
            avg_entry_price=q, net_pnl=stats.net_pnl,
            avg_win_return=stats.avg_win_return, avg_loss_return=stats.avg_loss_return,
            payoff_ratio=effective_ratio,
            expectancy=stats.conservative_win_rate * effective_ratio - (1.0 - stats.conservative_win_rate),
            kelly_fraction=kelly,
            sizing_pct=(min(MAX_SIZING_PCT, max(MIN_SIZING_PCT, KELLY_FRACTION * kelly))
                        if kelly > 0 else 0.0),
            basis="empirical")

    # -- strategy capital buckets -------------------------------------------

    @staticmethod
    def _load_strategy_allocations(bot_cfg: Dict[str, Any]) -> Dict[str, float]:
        """
        Reads and validates `bot_integration.strategies`.

        Missing or empty means bucketing is OFF and every strategy draws on the
        whole safe bankroll - the pre-Phase-3 behaviour, so existing callers are
        untouched. Once defined, unrecognised tags route to `sandbox`.

        Raises `StrategyAllocationError` on over-allocation. That propagates out of
        the constructor on purpose: a bot must not start against a capital plan
        that cannot be honoured.
        """
        return normalise_allocations((bot_cfg or {}).get("strategies"))

    def strategy_budget(self, strategy: str, safe_bankroll: float,
                        deployed: float = 0.0) -> StrategyBudget:
        """
        The slice of the safe bankroll one strategy may draw on.

        With no `strategies:` block configured this is a no-op and every strategy
        sees the whole bankroll - existing callers are unaffected.

        Once buckets ARE configured they are enforced, and an unrecognised
        strategy is QUARANTINED into `sandbox` rather than being handed the
        default allocation. That is the whole point of the phase: a strategy
        nobody has budgeted for is by definition untested, and the failure mode of
        guessing generously is the one that empties the account. If no sandbox
        bucket exists, an unrecognised strategy gets nothing at all.

        `default` is treated as unrecognised too. It is the tag on every order
        that never named a strategy, so under an enforced-bucket regime it is
        precisely the traffic that has not been classified yet.
        """
        name = str(strategy or "default")
        if not self.strategy_allocations:
            return StrategyBudget(strategy=name, allocation_pct=1.0,
                                  budget=max(0.0, safe_bankroll),
                                  deployed=max(0.0, deployed),
                                  remaining=max(0.0, safe_bankroll - max(0.0, deployed)),
                                  enforced=False)

        quarantined = False
        allocation = self.strategy_allocations.get(name)
        if allocation is None:
            quarantined = True
            allocation = self.strategy_allocations.get(SANDBOX_STRATEGY, 0.0)

        budget = max(0.0, safe_bankroll) * allocation
        used = max(0.0, float(deployed))
        return StrategyBudget(strategy=name, allocation_pct=allocation, budget=budget,
                              deployed=used, remaining=max(0.0, budget - used),
                              enforced=True, quarantined=quarantined)

    def get_strategy_open_exposure(self, strategy: str) -> float:
        """
        Cost basis still open on lots this strategy opened, in dollars.

        This is what makes a bucket a real ceiling rather than a per-order cap: it
        is measured from the ledger, so it holds even when a caller passes
        `already_deployed=0` or never tracks exposure at all.

        Matched on the `strategy:<name>;` token in `transactions.notes` - the
        schema is frozen, so there is no column to join on. Lots opened before
        tagging existed carry no tag and count against nothing, so exposure is
        under-stated on a historical ledger.
        """
        name = str(strategy or "").strip()
        if not name:
            return 0.0
        conn = get_connection(self.db_path)
        try:
            row = conn.execute("""
                SELECT COALESCE(SUM(l.remaining_qty * l.unit_cost_basis), 0.0) AS exposure
                FROM tax_lots l
                JOIN transactions t ON l.transaction_id = t.id
                WHERE l.is_closed = 0 AND t.notes LIKE '%' || ? || '%'
            """, (strategy_tag(name),)).fetchone()
            return float(row["exposure"] or 0.0) if row else 0.0
        except Exception as e:
            print(f"[WARN] Could not measure open exposure for {name!r} "
                  f"({type(e).__name__}: {e}); the bucket ceiling falls back to the "
                  f"caller-supplied figure.")
            return 0.0
        finally:
            conn.close()

    def strategy_stats(self) -> Dict[str, Dict[str, Any]]:
        """Per-strategy open exposure, closed lots, realised P&L and win rate."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("""
                SELECT t.notes AS notes, r.net_gain_loss AS pnl
                FROM realized_pnl r JOIN transactions t ON r.close_transaction_id = t.id
            """).fetchall()
        except Exception as e:
            print(f"[WARN] Could not read strategy history ({type(e).__name__}: {e}).")
            rows = []
        finally:
            conn.close()

        stats: Dict[str, Dict[str, Any]] = {}
        known = set(self.strategy_allocations) | {SANDBOX_STRATEGY}
        for row in rows:
            notes = str(row["notes"] or "")
            for name in known:
                if strategy_tag(name) in notes:
                    bucket = stats.setdefault(name, {"closed": 0, "wins": 0, "pnl": 0.0})
                    pnl = float(row["pnl"] or 0.0)
                    bucket["closed"] += 1
                    bucket["pnl"] += pnl
                    bucket["wins"] += 1 if pnl > 0 else 0
        for name in known:
            bucket = stats.setdefault(name, {"closed": 0, "wins": 0, "pnl": 0.0})
            bucket["open_exposure"] = self.get_strategy_open_exposure(name)
            bucket["win_rate"] = (bucket["wins"] / bucket["closed"] * 100.0) if bucket["closed"] else 0.0
            bucket["expectancy"] = wilson_lower_bound(bucket["wins"], bucket["closed"])
        return stats

    def strategy_report(self, live_cash: Optional[float] = None) -> str:
        """Human-readable table of every configured bucket."""
        safe = self.get_safe_bankroll(live_cash)
        if not self.strategy_allocations:
            return ("[BUCKETS] No strategy allocations configured - every strategy draws "
                    f"on the whole ${safe:,.2f} safe bankroll.")
        lines = [f"[BUCKETS] Safe bankroll ${safe:,.2f} split across strategies:"]
        for name in sorted(self.strategy_allocations):
            lines.append(f"          {self.strategy_budget(name, safe)}")
        allocated = sum(self.strategy_allocations.values())
        if allocated < 1.0 - 1e-9:
            lines.append(f"          unallocated reserve: {(1 - allocated) * 100:.0f}% = "
                         f"${safe * (1 - allocated):,.2f}")
        if SANDBOX_STRATEGY not in self.strategy_allocations:
            lines.append("          [!] no `sandbox` bucket - an unrecognised strategy gets $0")
        return "\n".join(lines)

    # -- sizing -------------------------------------------------------------

    def get_safe_bankroll(self, live_cash: Optional[float] = None) -> float:
        """Dollars that are genuinely risk capital: cash minus the tax escrow."""
        return float(self.snapshot(live_cash).get("safe_deployable_bankroll", 0.0))

    def get_tax_escrow(self, live_cash: Optional[float] = None) -> float:
        """Dollars owed to the taxman and therefore not tradeable."""
        return float(self.snapshot(live_cash).get("tax_escrow_reserve", 0.0))

    def max_position_size(self, live_cash: Optional[float] = None) -> float:
        """Per-order ceiling: `max_position_pct` of the safe bankroll."""
        return self.get_safe_bankroll(live_cash) * self.max_position_pct

    def check_order(self, desired_notional: float, live_cash: Optional[float] = None,
                    already_deployed: float = 0.0, category: Optional[str] = None,
                    price: Optional[float] = None,
                    strategy: str = "default",
                    expected_edge: Optional[float] = None,
                    decimal_odds: Optional[float] = None,
                    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
                    arbitrage_edge: Optional[float] = None,
                    arbitrage_odds: Optional[Sequence[float]] = None) -> BankrollDecision:
        """
        Gate and size one order.

        `already_deployed` is capital the bot has committed this session that the
        ledger does not know about yet - open orders, unsettled fills. It is
        subtracted from the safe bankroll so a burst of orders inside one refresh
        window cannot each be approved against the same dollars.

        WAGERING ORDERS ARE GATED ON THE AFTER-TAX EDGE, NOT THE GROSS ONE.
        For a category in `WAGERING_CATEGORIES` the caller must supply
        `expected_edge` (gross, as `p*O - 1`) and `decimal_odds`. The order is
        REJECTED when the gross edge does not clear `breakeven_gross_edge`, and
        otherwise sized by after-tax Kelly, which can only ever shrink the cap.

        FAIL-CLOSED ON A MISSING EDGE. A wager with no edge supplied is rejected
        rather than falling back to the fee-only gate. That matches the doctrine
        already in this ledger - an unreadable ledger rejects orders - and the
        reason is specific here: under a standard deduction the fee-only gate
        passes a 3% edge that carries a 21.21% hurdle, so the fallback is not a
        weaker check, it is the wrong check.

        CROSS-BOOK ARBITRAGE HAS ITS OWN HURDLE. Pass `arbitrage_edge` (the gross
        arb, as `R - 1`) and optionally `arbitrage_odds` for the two legs, and the
        order is gated on `after_tax_arbitrage_hurdle` instead. The number is
        brutal - 26.92% on a standard deduction - because an arb books a taxable
        win against a non-deductible loss every single time. A 2% arb is not a
        thin edge there, it is a reliable 14% loss.

        Every other category is untouched. Capital losses net against capital
        gains, so `fee/(1-t)` remains the whole story there.
        """
        snapshot = self.snapshot(live_cash)
        safe = float(snapshot.get("safe_deployable_bankroll", 0.0))
        escrow = float(snapshot.get("tax_escrow_reserve", 0.0))
        cash = float(snapshot.get("liquid_cash_balance", 0.0))
        # STRATEGY BUCKET. `already_deployed` is interpreted as what THIS strategy
        # has committed, not the book as a whole - the caller owns that state,
        # because this hook is read-only and a second source of truth for live
        # exposure would be worse than none.
        # A caller that passes 0 - or never tracks exposure at all - would otherwise
        # get only the per-order cap, leaving the bucket ceiling advisory.
        # Measuring from the ledger makes it real.
        deployed = float(already_deployed)
        if deployed == 0.0 and self.strategy_allocations:
            deployed = self.get_strategy_open_exposure(strategy)
        budget = self.strategy_budget(strategy, safe, deployed)
        headroom = min(max(0.0, safe - max(0.0, deployed)), budget.remaining)

        # A measured category adjusts the flat cap.
        #
        # By DEFAULT the empirical sizer can only ever TIGHTEN it. `max_position_pct`
        # is a limit a human chose; a win rate estimated from that human's own past
        # trades is survivorship-prone and noisy at small N, and letting it silently
        # raise the ceiling means the sizer bids itself up hardest right after a hot
        # streak - the same over-Kelly failure the escrow gate exists to prevent.
        # `allow_empirical_upsize=True` opts into the brief's full 1%-8% range and
        # lets a well-measured category exceed the flat cap.
        edge = self.category_edge(category, price)
        if edge.basis != "empirical":
            pct = self.max_position_pct
        elif self.allow_empirical_upsize:
            pct = edge.sizing_pct
        else:
            pct = min(self.max_position_pct, edge.sizing_pct)
        # The per-order cap is a fraction of the strategy's own budget, not of the
        # whole bankroll: a sandbox strategy on 20% should risk 5% OF ITS SANDBOX,
        # otherwise "quarantined" means nothing.
        cap = budget.budget * pct if budget.enforced else safe * pct

        # Seeded before `decision` closes over them; filled in by the wagering
        # gate below when the category calls for it.
        hurdle = after_tax_kelly = kelly_size = arb_hurdle = None

        def decision(approved: bool, notional: float, reason: str) -> BankrollDecision:
            return BankrollDecision(
                approved=approved, reason=reason,
                requested_notional=float(desired_notional),
                approved_notional=round(max(0.0, notional), 2),
                safe_bankroll=round(safe, 2), tax_escrow=round(escrow, 2),
                cash_balance=round(cash, 2), max_position_size=round(cap, 2),
                reserve_ratio_pct=round(float(snapshot.get("reserve_ratio_pct", 0.0)), 2),
                tax_year=self.tax_year, stale=not snapshot.get("available", False),
                category=edge.category, strategy=str(strategy or "default"),
                strategy_budget=round(budget.budget, 2),
                strategy_remaining=round(budget.remaining, 2),
                detail={"headroom": round(headroom, 2), "already_deployed": float(already_deployed),
                        "net_capital_gains": round(float(snapshot.get("net_capital_gains", 0.0)), 2),
                        "sizing_pct": round(pct, 4), "sizing_basis": edge.basis,
                        "measured_exposure": round(deployed, 2),
                        "expected_edge": expected_edge,
                        "decimal_odds": decimal_odds,
                        "after_tax_hurdle": hurdle,
                        "after_tax_kelly": after_tax_kelly,
                        "kelly_notional": kelly_size,
                        "arbitrage_edge": arbitrage_edge,
                        "arbitrage_hurdle": arb_hurdle,
                        "category_edge": edge.to_dict() if edge.basis == "empirical" else None,
                        "error": self._last_error},
            )

        if not snapshot.get("available", False):
            return decision(False, 0.0, f"tax ledger unreadable ({self._last_error or 'unknown error'})")
        if desired_notional <= 0:
            return decision(False, 0.0, "requested notional must be positive")
        if safe <= 0:
            return decision(False, 0.0,
                            f"no risk capital: ${escrow:,.2f} of tax escrow against ${cash:,.2f} of cash")
        if budget.enforced and budget.budget <= 0:
            return decision(False, 0.0,
                            f"strategy {budget.strategy!r} has no capital allocation"
                            + (" and there is no `sandbox` bucket to quarantine it into"
                               if budget.quarantined else ""))
        if edge.basis == "empirical" and edge.sizing_pct <= 0:
            return decision(False, 0.0,
                            f"{edge.category} has negative expectancy "
                            f"({edge.expectancy:+.3f} per $ risked, b={edge.payoff_ratio:.2f}) - "
                            f"win rate alone would have sized this up")
        if headroom < self.min_order_usd:
            scope = (f"{budget.strategy} bucket (${budget.budget:,.2f})"
                     if budget.enforced else "safe bankroll")
            return decision(False, 0.0,
                            f"${headroom:,.2f} of headroom left in the {scope} after "
                            f"${deployed:,.2f} already deployed")

        # -- wagering gate ---------------------------------------------------
        wagering = self.is_wagering_category(category)

        # ARBITRAGE FIRST: it is a different bet with a different hurdle, and
        # letting it fall through to the single-wager test would pass a 2% arb
        # that loses 14% after tax.
        if wagering and arbitrage_edge is not None:
            try:
                arb_hurdle = self.after_tax_arbitrage_hurdle(
                    odds=list(arbitrage_odds) if arbitrage_odds else None)
            except ValueError as e:
                return decision(False, 0.0, f"arbitrage has unusable odds: {e}")
            deductible = self.gambling_loss_deductibility()
            if float(arbitrage_edge) < arb_hurdle:
                return decision(False, 0.0,
                                f"arbitrage of {float(arbitrage_edge) * 100:.2f}% is below "
                                f"the {arb_hurdle * 100:.2f}% after-tax arbitrage hurdle "
                                f"(losses {deductible * 100:.0f}% deductible) - an arb "
                                f"books a taxed win against a non-deductible loss every "
                                f"time, so this is a RELIABLE loss, not a thin edge")

        # An arbitrage that CLEARED its own hurdle is fully gated - it does not
        # also need a single-wager edge, and demanding one would fail-closed on
        # the very positions the arb test just approved. Sizing falls through to
        # the ordinary cap and bucket limits below: an arb is riskless in dollars
        # and only its TAX outcome is uncertain, so after-tax Kelly on a single
        # win probability is not the right sizer for it.
        if wagering and arbitrage_edge is not None:
            wagering = False

        if wagering:
            if expected_edge is None or decimal_odds is None:
                return decision(False, 0.0,
                                "wagering order supplied no expected_edge/decimal_odds - "
                                "FAIL-CLOSED. Under IRC 165(d) the fee-only gate would "
                                "pass a 3% edge that carries a 21%+ after-tax hurdle.")
            try:
                hurdle = self.breakeven_gross_edge(category=category,
                                                   decimal_odds=decimal_odds)
                deductible = self.gambling_loss_deductibility()
                win_probability = (1.0 + float(expected_edge)) / float(decimal_odds)
                after_tax_kelly = self.after_tax_kelly_fraction(win_probability,
                                                                decimal_odds)
            except ValueError as e:
                return decision(False, 0.0, f"wagering order has unusable odds: {e}")

            if float(expected_edge) < hurdle:
                return decision(False, 0.0,
                                f"gross edge {float(expected_edge) * 100:.2f}% is below the "
                                f"{hurdle * 100:.2f}% after-tax hurdle at {decimal_odds:.2f} "
                                f"(losses {deductible * 100:.0f}% deductible) - an after-tax "
                                f"LOSS however good the model looks")

            # Sized on the after-tax payoffs, then scaled by the Kelly fraction.
            # Only ever tightens: an edge that merely clears the hurdle sizes near
            # zero, because f* and the hurdle are the same inequality.
            kelly_size = max(0.0, after_tax_kelly) * max(0.0, float(kelly_fraction)) * (
                budget.budget if budget.enforced else safe)
            cap = min(cap, kelly_size)

        allowed = min(float(desired_notional), cap, headroom)
        if wagering and kelly_size is not None and allowed < self.min_order_usd:
            return decision(False, 0.0,
                            f"after-tax Kelly sizes this to ${kelly_size:,.2f}, below the "
                            f"${self.min_order_usd:,.2f} minimum - the edge clears the "
                            f"{hurdle * 100:.2f}% hurdle but not by enough to stake")
        if allowed < self.min_order_usd:
            return decision(False, 0.0,
                            f"clamped size ${allowed:,.2f} is below the ${self.min_order_usd:,.2f} minimum")
        if allowed < float(desired_notional):
            limiter = ("per-order cap" if cap <= headroom
                       else (f"{budget.strategy} bucket" if budget.enforced
                             else "remaining safe bankroll"))
            # Name the pool the percentage is actually taken from: under bucketing
            # the cap is a fraction of the STRATEGY's budget, and quoting the whole
            # bankroll here would make a correct number look like a bug.
            pool = budget.budget if budget.enforced else safe
            pool_label = f"the {budget.strategy} bucket" if budget.enforced else "safe bankroll"
            return decision(True, allowed,
                            f"trimmed to ${allowed:,.2f} by the {limiter} "
                            f"({pct * 100:.1f}% of ${pool:,.2f} in {pool_label})")
        pool = budget.budget if budget.enforced else safe
        pool_label = f"the {budget.strategy} bucket" if budget.enforced else "safe bankroll"
        return decision(True, allowed,
                        f"within limits ({pct * 100:.1f}% cap on ${pool:,.2f} in {pool_label})")

    def size_order(self, desired_notional: float, live_cash: Optional[float] = None,
                   already_deployed: float = 0.0, category: Optional[str] = None,
                   price: Optional[float] = None, strategy: str = "default",
                   expected_edge: Optional[float] = None,
                   decimal_odds: Optional[float] = None) -> float:
        """`check_order(...).approved_notional` for callers that only want the number."""
        return self.check_order(desired_notional, live_cash, already_deployed,
                                category, price, strategy,
                                expected_edge=expected_edge,
                                decimal_odds=decimal_odds).approved_notional

    def fetch_clob_fee_rate(self, token_id: str, price: float = 0.5,
                            holds_to_resolution: bool = False) -> Optional[float]:
        """
        Live ROUND-TRIP fee for one CLOB token at `price`, or None if unknown.

        None is not zero. "We could not read the fee" must fall back to the
        configured assumption; collapsing it to 0 would remove the hurdle exactly
        when the fee data is missing.

        Note this does NOT read `/fee-rate` as its rate. That endpoint answers
        `base_fee: 1000` for essentially every market (23 of 25 live tokens on
        2026-09-03) - a constant, not a rate. Reading it as basis points implies a
        10% fee and a 30% hurdle that rejects everything. The real terms come from
        Gamma's `feeSchedule`, and they are PRICE-DEPENDENT: on a crypto book at
        7% the round trip is 7.00% at a coin flip and 0.28% at 2c.
        """
        source = self._fee_source()
        if source is None:
            return None
        try:
            return source.round_trip_fee(token_id, price, holds_to_resolution)
        except Exception as e:
            print(f"[INFO] Live fee lookup failed for {str(token_id)[:16]}...: {e}")
            return None

    def _fee_source(self):
        """Lazily built so nothing touches the network unless a fee is asked for."""
        if self._fee_source_cache is None:
            try:
                from ..ingestors.polymarket import PolymarketFeeSource
                self._fee_source_cache = PolymarketFeeSource()
            except Exception as e:
                print(f"[INFO] Live fee source unavailable ({type(e).__name__}: {e}).")
                self._fee_source_cache = False
        return self._fee_source_cache or None

    @staticmethod
    def is_wagering_category(category: Optional[str]) -> bool:
        """One definition of "this is a wager", used by the hurdle and the gate."""
        return str(category or "").strip().lower() in WAGERING_CATEGORIES

    def after_tax_kelly_fraction(self, win_probability: float, decimal_odds: float,
                                 delta: Optional[float] = None,
                                 tax_rate: Optional[float] = None) -> float:
        """
        Kelly on the AFTER-TAX payoffs, which is not the same bet as gross Kelly.

        Staking a fraction f, a win multiplies the bankroll by (1 + f*w) and a loss
        by (1 - f*l), where tax makes the two legs asymmetric:

            w = (O - 1)(1 - t)        winnings, taxed
            l = 1 - t*delta           stake lost, relieved only by the deductible part

        Maximising p*log(1 + f*w) + q*log(1 - f*l) gives

            f* = (p*w - q*l) / (w*l)

        whose NUMERATOR IS EXACTLY THE AFTER-TAX EV. That is the property worth
        noticing: f* is zero precisely when the gross edge equals the hurdle, and
        negative below it. The gate and the sizer therefore cannot disagree - they
        are the same inequality read two ways.

        Gross Kelly on the same bet is (p*b - q)/b, which under a standard
        deduction sizes a losing wager as though it were a winning one.
        """
        odds = float(decimal_odds)
        if odds <= 1.0:
            raise ValueError(f"Decimal odds must exceed 1.0; got {decimal_odds!r}.")
        p = min(max(float(win_probability), 0.0), 1.0)
        tax = self._composite_tax_rate() if tax_rate is None else float(tax_rate)
        tax = min(max(tax, 0.0), 0.99)
        deductible = self.gambling_loss_deductibility() if delta is None else float(delta)
        deductible = min(max(deductible, 0.0), 1.0)

        win_leg = (odds - 1.0) * (1.0 - tax)
        loss_leg = 1.0 - tax * deductible
        if win_leg <= 0 or loss_leg <= 0:
            return 0.0
        return (p * win_leg - (1.0 - p) * loss_leg) / (win_leg * loss_leg)

    def gambling_loss_deductibility(self, tax_year: Optional[int] = None) -> float:
        """
        The fraction `delta` of a gambling LOSS that produces a deduction, read
        from the same `gambling:` config the escrow calculator uses.

          0.00  casual_standard_deduction - IRC 165(d) allows nothing
          0.90  casual_itemized under OBBBA 70114 (from tax year 2026)
          1.00  casual_itemized pre-2026, or professional_schedule_c

        This single number is what separates a 0% after-tax hurdle from a 21%
        one. See `after_tax_edge_hurdle`.
        """
        cfg = (self.config.get("gambling", {}) or {})
        treatment = str(cfg.get("tax_treatment", "casual_standard_deduction")).lower()
        if treatment == "casual_standard_deduction":
            return 0.0
        if treatment == "session_netting" and not cfg.get("session_netting_itemizes", False):
            # Netting happens WITHIN a session; a losing SESSION is still a
            # Schedule A deduction, so a standard-deduction filer gets nothing.
            # A session-netter who itemises falls through to the haircut below.
            return 0.0
        year = tax_year or int((self.config.get("portfolio", {}) or {}).get("tax_year", 2026))
        haircut = float(cfg.get("loss_deduction_pct", 0.90))
        effective = int(cfg.get("loss_haircut_effective_year", 2026))
        return min(max(haircut if year >= effective else 1.0, 0.0), 1.0)

    def after_tax_edge_hurdle(self, decimal_odds: float,
                              delta: Optional[float] = None,
                              tax_rate: Optional[float] = None) -> Dict[str, float]:
        """
        The GROSS edge a wager must show before it breaks even after tax, and the
        win probability that corresponds to.

        THIS IS THE NUMBER THAT DECIDES WHETHER SPORTS BETTING IS A BUSINESS OR A
        HOBBY. Stake 1 at decimal odds O. A win pays (O-1) and is taxed at t; a
        loss costs 1 and returns t*delta of tax benefit, where delta is the
        deductible fraction of the loss. So

            EV_after_tax = p (O-1)(1-t) - (1-p)(1 - t*delta)

        Setting that to zero:

            p_breakeven = (1 - t*delta) / [ (O-1)(1-t) + (1 - t*delta) ]
            hurdle      = p_breakeven * O - 1
                        = (O-1) * t * (1-delta) / [ (O-1)(1-t) + (1 - t*delta) ]

        At t = 35% on an even-money line (O = 2.00):

            professional / fully deductible (delta=1)  ->   0.00%
            OBBBA itemized (delta=0.90)                ->   2.62%
            casual standard deduction (delta=0)        ->  21.21%

        THAT LAST NUMBER IS NOT A TYPO. With losses disallowed entirely, a coin
        flip at 2.00 needs a TRUE win rate of 60.6% just to break even after tax.
        Every "3% edge" sports model is an after-tax loser in that regime, and
        nothing else in this ledger would have told you.

        Verified by Monte-Carlo: simulating 400k wagers at `p_breakeven` returns
        an after-tax EV of zero in all three modes.
        """
        odds = float(decimal_odds)
        if odds <= 1.0:
            raise ValueError(f"Decimal odds must exceed 1.0; got {decimal_odds!r}.")
        tax = self._composite_tax_rate() if tax_rate is None else float(tax_rate)
        tax = min(max(tax, 0.0), 0.99)
        deductible = self.gambling_loss_deductibility() if delta is None else float(delta)
        deductible = min(max(deductible, 0.0), 1.0)

        win_leg = (odds - 1.0) * (1.0 - tax)
        loss_leg = 1.0 - tax * deductible
        denominator = win_leg + loss_leg
        if denominator <= 0:
            raise ValueError("Degenerate tax parameters; hurdle is undefined.")
        p_breakeven = loss_leg / denominator
        hurdle = (odds - 1.0) * tax * (1.0 - deductible) / denominator
        return {
            "decimal_odds": odds,
            "tax_rate": tax,
            "loss_deductibility": deductible,
            "breakeven_win_probability": p_breakeven,
            "tax_hurdle": hurdle,
            "fair_win_probability": 1.0 / odds,
        }

    def after_tax_arbitrage_hurdle(self, delta: Optional[float] = None,
                                   tax_rate: Optional[float] = None,
                                   odds_a: Optional[float] = None,
                                   odds_b: Optional[float] = None,
                                   odds: Optional[Sequence[float]] = None) -> float:
        """
        The gross arbitrage a cross-book position must show before it survives tax.

        AN ARBITRAGE IS NOT RISKLESS AFTER TAX, and that is the whole finding.
        Stake the two legs so both return R on a total stake of 1. Exactly one
        leg wins, so exactly one leg is taxed on its proceeds and exactly one is
        a wagering LOSS - deductible only at the fraction `delta`. With stakes
        `a` and `b`:

            A wins:  (R-1) - t(R-a) + t*delta*b
            B wins:  (R-1) - t(R-b) + t*delta*a
            difference = t(a-b)(1-delta)

        The two branches are EQUAL only when the stakes are equal or losses are
        fully deductible. Otherwise a position that is riskless in dollars has two
        different after-tax outcomes - tax manufactures variance out of nothing,
        and the branch where the SMALL stake (the long-odds leg) wins is the bad
        one, because it books the biggest taxable win against the biggest
        non-deductible loss.

        SYMMETRIC CASE (a = b = 0.5), which is what a two-way arb at matched odds
        looks like and what this returns when no odds are supplied:

            hurdle = (1 - t(1+delta)/2) / (1-t) - 1

        At t = 35%:  delta=0 -> 26.92% | delta=0.90 -> 2.69% | delta=1.0 -> 0.00%

        THE 26.92% IS THE HEADLINE. A casual bettor on the standard deduction
        needs a 27% arbitrage before the position stops losing money, and real
        cross-book arbitrage is 1-3%. Every one of them is an after-tax loss of
        roughly 14%, and it looks like free money right up until April.

        GENERAL CASE, ANY NUMBER OF LEGS. Pass `odds=[...]` (or `odds_a`/`odds_b`)
        and the WORST branch is priced instead. Stakes are fixed by the odds -
        s_i = (1/O_i) / booksum, summing to one - and if outcome j wins the
        after-tax profit is

            (R - 1) - t(R - s_j) + t*delta*(1 - s_j)

        which is INCREASING in s_j, so the worst case is always the smallest
        stake: the longest-odds leg. Setting it to zero,

            R = [ 1 - t*s_min - t*delta*(1 - s_min) ] / (1 - t)

        This contains the symmetric formula exactly (two equal legs give
        s_min = 0.5) and is verified to zero the worst branch for 2-, 3- and
        4-way markets at every delta. A 1.05/25.00 arb needs 51.68%, not 26.92%.
        """
        tax = self._composite_tax_rate() if tax_rate is None else float(tax_rate)
        tax = min(max(tax, 0.0), 0.99)
        deductible = self.gambling_loss_deductibility() if delta is None else float(delta)
        deductible = min(max(deductible, 0.0), 1.0)

        legs = list(odds) if odds is not None else (
            [odds_a, odds_b] if odds_a is not None and odds_b is not None else [])
        if not legs:
            return (1.0 - tax * (1.0 + deductible) / 2.0) / (1.0 - tax) - 1.0
        if len(legs) < 2:
            raise ValueError("An arbitrage needs at least two legs.")

        for leg in legs:
            if float(leg) <= 1.0:
                raise ValueError(f"Decimal odds must exceed 1.0; got {leg!r}.")
        booksum = sum(1.0 / float(leg) for leg in legs)
        if booksum <= 0:
            raise ValueError("Degenerate odds.")
        # NORMALISED stake fractions: s_i = (1/O_i)/booksum, summing to one.
        # Dropping the booksum here (using a bare 1/O) understates every stake and
        # so overstates the hurdle - by 1.2pp on a three-way book at 0.91.
        smallest_stake = min((1.0 / float(leg)) / booksum for leg in legs)
        return ((1.0 - tax * smallest_stake
                 - tax * deductible * (1.0 - smallest_stake)) / (1.0 - tax)) - 1.0

    def _composite_tax_rate(self) -> float:
        """
        Federal + state + buffer, state counted ONCE. 0.24 + 0.05 + 0.02 = 0.31.

        Short-term gains are taxed as ordinary income, so
        `short_term_capital_gains` is the ordinary leg and config.yaml sets it
        equal to `federal_ordinary_rate`.
        """
        rates = self.config.get("tax_rates", {}) or {}
        return (rates.get("short_term_capital_gains", 0.24)
                + rates.get("state_tax_rate", 0.05)
                + rates.get("safety_buffer_pct", 0.02))

    def breakeven_gross_edge(self, round_trip_fee_rate: Optional[float] = None,
                             token_id: Optional[str] = None,
                             price: float = 0.5,
                             holds_to_resolution: bool = False,
                             category: Optional[str] = None,
                             decimal_odds: Optional[float] = None) -> float:
        """
        Smallest GROSS edge that still clears fees and tax.

        Under gross-of-fees accounting the tax is assessed on the gross gain while
        the fees come out of your pocket unrecorded, so:

            after_tax = (e - f) - t*e = e(1 - t) - f      ->      e_min = f / (1 - t)

        At a 2% round trip and a 35% composite rate that is 3.08%, against 2.00% if
        the fees were captured in basis. THE 1.08pp GAP IS THE COST OF NOT
        RECORDING FEES - it is not a rounding detail, it is a third of the
        threshold. Anything below `e_min` is an after-tax loss no matter how clean
        the arbitrage looks.
        """
        if round_trip_fee_rate is None and token_id:
            # A live, market-specific fee beats any assumption. Measured across 300
            # open markets: politics 4%, sports 3%, economics 5%, crypto 7% - and
            # the charge scales with min(p, 1-p), so a flat assumption is wrong at
            # both ends. On a 7% crypto book at a coin flip the true hurdle is
            # 10.77%, not 3.08%.
            round_trip_fee_rate = self.fetch_clob_fee_rate(token_id, price,
                                                           holds_to_resolution)

        if round_trip_fee_rate is None:
            # TWO DIFFERENT FEE NUMBERS, ON PURPOSE.
            #
            # `chain.polymarket_fee_rate` writes into the LEDGER, so it defaults to
            # 0 - a guessed number in a tax record is the same mistake as a guessed
            # market price. This threshold is a DECISION AID: nothing it produces is
            # ever written down, so assuming a realistic fee costs nothing, while
            # refusing to assume one leaves the filter inert exactly when it
            # matters. `bot_integration.assumed_round_trip_fee` therefore defaults
            # to a real 2%, and a measured ledger rate overrides it.
            ledger_rate = float((self.config.get("chain", {}) or {})
                                .get("polymarket_fee_rate", 0.0) or 0.0)
            if ledger_rate > 0:
                round_trip_fee_rate = ledger_rate * 2.0
            else:
                round_trip_fee_rate = float((self.config.get("bot_integration", {}) or {})
                                            .get("assumed_round_trip_fee",
                                                 DEFAULT_ASSUMED_ROUND_TRIP_FEE) or 0.0)
        tax = min(max(self._composite_tax_rate(), 0.0), 0.99)
        fee_hurdle = float(round_trip_fee_rate) / (1.0 - tax)

        if not self.is_wagering_category(category):
            return fee_hurdle

        # SPORTS WAGERS ARE NOT CAPITAL GAINS AND THE FEE HURDLE ALONE IS FAR TOO
        # KIND TO THEM. A capital loss nets against a capital gain; under IRC
        # 165(d) a gambling loss may not, so the tax is charged on the wins with
        # no relief on the losses. `after_tax_edge_hurdle` prices that.
        if decimal_odds is None:
            # Without a price, assume even money - the LEAST punitive assumption
            # available here, since the tax hurdle grows with the odds. A caller
            # that passes real odds gets a real number.
            decimal_odds = 2.0
        tax_hurdle = self.after_tax_edge_hurdle(decimal_odds, tax_rate=tax)["tax_hurdle"]

        # ADDITIVE, AND THAT IS AN APPROXIMATION. The two hurdles are not strictly
        # separable: a commission changes the realised payout, which changes the
        # tax leg. Books embed their margin in the price itself - which devigging
        # already removes - so `round_trip_fee_rate` here means an EXCHANGE
        # commission, and modelling that exactly means shrinking (O-1) instead.
        # Adding them overstates the hurdle slightly, which is the safe direction.
        return fee_hurdle + tax_hurdle

    def category_report(self) -> str:
        """Human-readable table of every measured category."""
        stats = self.category_stats()
        if not stats:
            return "[EDGE] No closed prediction-market trades yet - flat cap applies everywhere."
        lines = ["[EDGE] Measured position caps by category (quarter-Kelly on a Wilson lower bound):"]
        for edge in sorted(stats.values(), key=lambda e: -e.sizing_pct):
            lines.append(f"       {edge}")
        return "\n".join(lines)

    # -- reporting ----------------------------------------------------------

    def status_line(self, live_cash: Optional[float] = None) -> str:
        """One-line banner for a bot's startup log or the Monarch TUI footer."""
        snapshot = self.snapshot(live_cash)
        if not snapshot.get("available", False):
            return "[TAX] ledger unavailable - order gating is FAIL-CLOSED"
        return (f"[TAX] safe ${snapshot['safe_deployable_bankroll']:,.2f} "
                f"| escrow ${snapshot['tax_escrow_reserve']:,.2f} "
                f"({snapshot['reserve_ratio_pct']:.1f}% of ${snapshot['liquid_cash_balance']:,.2f}) "
                f"| max order ${self.max_position_size(live_cash):,.2f}")


# ----------------------------------------------------------------------------
# Module-level convenience API (for bots that do not want to hold an instance)
# ----------------------------------------------------------------------------

_DEFAULT_HOOK: Optional[MonarchBankrollHook] = None


def get_hook(**kwargs: Any) -> MonarchBankrollHook:
    """Process-wide singleton, so the snapshot cache is shared across a bot's modules."""
    global _DEFAULT_HOOK
    if _DEFAULT_HOOK is None or kwargs:
        _DEFAULT_HOOK = MonarchBankrollHook(**kwargs)
    return _DEFAULT_HOOK


def check_order(desired_notional: float, live_cash: Optional[float] = None,
                already_deployed: float = 0.0, category: Optional[str] = None,
                price: Optional[float] = None, strategy: str = "default",
                expected_edge: Optional[float] = None,
                decimal_odds: Optional[float] = None) -> BankrollDecision:
    return get_hook().check_order(desired_notional, live_cash, already_deployed,
                                  category, price, strategy,
                                  expected_edge=expected_edge,
                                  decimal_odds=decimal_odds)


def safe_bankroll(live_cash: Optional[float] = None) -> float:
    return get_hook().get_safe_bankroll(live_cash)


def bootstrap_path(dev_root: Optional[Path] = None) -> None:
    """
    Puts `DEV/` on `sys.path` so Monarch scripts can import this package.

    Monarch lives at `DEV/Polymarket/Polymarket_Monarch/` and this package at
    `DEV/Tax_Reserve_Agent/`, so neither can see the other by default. Call this
    once at the top of a Monarch module:

        sys.path.insert(0, r"c:/Users/ixis1/Desktop/DEV")
        from Tax_Reserve_Agent.interfaces.monarch_hook import bootstrap_path
    """
    root = Path(dev_root) if dev_root else Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tax-aware bankroll gate for Polymarket Monarch")
    parser.add_argument("--check", type=float, default=None,
                        help="Desired order notional in USD; exits 1 if rejected")
    parser.add_argument("--cash", type=float, default=None, help="Live cash balance override")
    parser.add_argument("--deployed", type=float, default=0.0, help="Capital already committed this session")
    parser.add_argument("--pct", type=float, default=DEFAULT_MAX_POSITION_PCT,
                        help=f"Max fraction of safe bankroll per order (default {DEFAULT_MAX_POSITION_PCT})")
    parser.add_argument("--year", type=int, default=None, help="Tax year")
    parser.add_argument("--db", type=Path, default=None, help="SQLite ledger path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    hook = MonarchBankrollHook(tax_year=args.year, db_path=args.db, max_position_pct=args.pct)

    if args.check is None:
        snapshot = hook.snapshot(args.cash)
        if args.json:
            print(json.dumps({
                "safe_bankroll": snapshot.get("safe_deployable_bankroll", 0.0),
                "tax_escrow": snapshot.get("tax_escrow_reserve", 0.0),
                "cash_balance": snapshot.get("liquid_cash_balance", 0.0),
                "max_position_size": hook.max_position_size(args.cash),
                "available": snapshot.get("available", False),
            }, indent=2))
        else:
            print(hook.status_line(args.cash))
        sys.exit(0 if snapshot.get("available", False) else 1)

    decision = hook.check_order(args.check, live_cash=args.cash, already_deployed=args.deployed)
    print(json.dumps(decision.to_dict(), indent=2) if args.json else str(decision))
    sys.exit(0 if decision.approved else 1)


if __name__ == "__main__":
    main()
