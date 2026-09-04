"""
Funding harvester: the bankroll gate and the after-tax economics of the basis trade.

WHAT THIS IS, AND WHAT IT IS NOT

The delta-neutral engine already exists and works. `execution/basis_harvester.py`
shorts the perp, buys matching spot, accrues at the CURRENT hourly rate rather
than extrapolating the entry quote, and refuses uncosted rows;
`analytics/funding_arbitrage.py` scans the universe and amortises the spread over
a realistic hold. None of that is rebuilt here, and duplicating it would be worse
than useless - a second engine with its own copy of the fee model is a second
thing to keep correct.

What was missing is the layer between that engine and the rest of the desk, and
it was missing in two specific ways.

FIRST: THE HARVESTER NEVER ASKED THE BANKROLL. `BasisHarvester.can_open` gates on
`self.cash` - the paper engine's own float - and imports STRATEGY_BASIS_HARVEST
only to TAG RECEIPTS. `RiskManager` holds a real `MonarchBankrollHook` gate at
`check_order(..., strategy=...)`, but nothing routed the harvester through it, and
`market_collector.py` opens positions with no bucket check at all. Two positions
at the configured $10,000 per leg is $40,000 of capital committed without one
reference to whether the `hl_basis_harvest` bucket allows it. This is the same
defect that let Monarch_Shark run 1.7x over its sports bucket: an engine sizing
against local state instead of the shared one.

SECOND: THE HEADLINE APR IS QUOTED AGAINST ONE LEG AND THE CAPITAL IS TWO.
`capital_required()` returns `notional_per_leg * 2`, correctly, because both legs
tie up money. But every APR in the system - the scanner's `funding_apr`, the
entry quote, `format_report`'s realised APR, which divides accrued funding by
`notional_per_leg` - is a return on ONE leg. So a position reporting 56% realised
is earning 28% on the capital it actually consumes. That is not a rounding
difference; it is a factor of two on the only number that decides whether the
strategy is worth running.

Put the two corrections together with tax and the decision changes shape:

    quoted net APR                                    20.0%
    on capital actually employed (2 legs)             10.0%
    after tax at the NJ composite 32.37%               6.8%
    Treasury bills at 5%, after tax on THEIR terms     3.7%

The strategy still wins, but by three points rather than fifteen, and that margin
is what has to cover basis drift, liquidation risk on the perp leg, and the rate
evaporating mid-hold. Quoting 20% against a 5% Treasury makes it look like a
different trade than it is.

THE TREASURY COMPARISON IS DONE ON EACH INSTRUMENT'S OWN TAX TERMS, which is why
it is not simply `hurdle * (1 - t)`. Treasury interest is exempt from state income
tax under 31 USC 3124(a); funding income is not. For a New Jersey resident that
hands T-bills a 6.37-point advantage in tax rate that a gross-to-gross comparison
never shows.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from execution.risk_manager import STRATEGY_BASIS_HARVEST
from config.settings import (BASIS_DEFAULT_PERP_LEVERAGE,
                             BASIS_LEVERAGE_EXCEPTIONS,
                             BASIS_MAX_PERP_LEVERAGE)

HOURS_PER_YEAR = 24.0 * 365.0

# Spot is bought outright and the perp leg is modelled unlevered, so a 1:1
# cash-and-carry consumes two units of capital per unit of quoted notional.
SPOT_BACKED_CAPITAL_MULTIPLE = 2.0

# Where a comparable riskless dollar earns. Not a constant of nature - override it
# from the live curve - but a harvester with no benchmark at all will happily
# report that 4% annualised is worth the liquidation risk.
DEFAULT_RISK_FREE_APR = 5.0


class GateUnavailable(RuntimeError):
    """The bankroll could not be consulted, so no size can be authorised."""


def max_leverage_for(coin: str) -> float:
    """
    The leverage ceiling for one market, per the Round 31 policy.

    1.0x everywhere, with a 2.0x exception for BTC, ETH and SOL only. The
    exception is a statement about BOOK DEPTH, not about those assets being
    safer: at 2x the perp leg liquidates on a ~48.8% adverse move, and the case
    for tolerating that rests on being able to add margin before it arrives -
    which needs a book that will still be there in a cascade.

    A coin absent from the table gets the default, so a NEW listing is 1x until
    somebody decides otherwise rather than inheriting a ceiling by accident.
    """
    ceiling = BASIS_LEVERAGE_EXCEPTIONS.get(str(coin or "").upper().strip())
    return float(ceiling if ceiling is not None else BASIS_MAX_PERP_LEVERAGE)


def clamp_leverage(coin: str, requested: float) -> float:
    """Requested leverage, clamped to this market's ceiling and never below 1x."""
    return max(1.0, min(float(requested), max_leverage_for(coin)))


# ---------------------------------------------------------------------------
# Capital efficiency
# ---------------------------------------------------------------------------

def capital_multiple(perp_leverage: float = 1.0) -> float:
    """
    Units of capital consumed per unit of quoted (one-leg) notional.

    The spot leg is bought outright and cannot be levered, so it always costs its
    full notional. The perp leg costs its initial margin, which is notional over
    leverage. At 1x this is the 2.0 the existing engine assumes; at 5x on the perp
    it falls to 1.2, which is where the temptation lives.

    LEVERING THE PERP LEG IS NOT FREE CAPITAL EFFICIENCY. It buys a better APR on
    deployed capital by moving the liquidation price closer - see
    `liquidation_move_pct`. A delta-neutral position that gets liquidated on one
    leg is no longer delta-neutral, and it is left directional at the worst
    possible moment.
    """
    leverage = max(float(perp_leverage), 1e-9)
    return 1.0 + 1.0 / leverage


def liquidation_move_pct(perp_leverage: float = 1.0,
                         maintenance_margin_fraction: float = 0.0125) -> float:
    """
    How far price must move against the perp leg before it liquidates, in percent.

    Approximately `100 * (1/L - mmf)`: the initial margin cushion less the
    maintenance requirement. Returned for the PERP leg alone, deliberately. The
    combined position is delta-neutral and its net equity barely moves, but
    HyperLiquid liquidates a perp position on ITS OWN margin - the spot leg
    sitting in another wallet does not rescue it. Anyone reasoning that "the
    position is hedged so it cannot liquidate" has confused net exposure with
    per-position margin.
    """
    leverage = max(float(perp_leverage), 1e-9)
    return max(0.0, (1.0 / leverage - float(maintenance_margin_fraction)) * 100.0)


# ---------------------------------------------------------------------------
# After-tax economics
# ---------------------------------------------------------------------------

def resolve_tax_rates(hook: Any = None) -> Dict[str, float]:
    """Composite, federal-plus-buffer and bare state, from live config."""
    rates = {}
    if hook is not None:
        rates = (getattr(hook, "config", {}) or {}).get("tax_rates", {}) or {}
    federal = float(rates.get("short_term_capital_gains", 0.24))
    state = float(rates.get("state_tax_rate", 0.0637))
    buffer_pct = float(rates.get("safety_buffer_pct", 0.02))
    return {"federal": federal, "state": state, "buffer": buffer_pct,
            "composite": federal + state + buffer_pct,
            "federal_only": federal + buffer_pct}


def after_tax_risk_free(risk_free_apr: float, rates: Dict[str, float]) -> float:
    """
    The benchmark, taxed on its OWN terms.

    Treasury interest is exempt from state income tax under 31 USC 3124(a).
    Funding income is not. Discounting both by the same composite rate would hide
    a 6.37-point advantage the benchmark actually has, and the whole point of the
    comparison is to be honest about the margin.
    """
    return float(risk_free_apr) * (1.0 - rates["federal_only"])


@dataclass(frozen=True)
class HarvestEconomics:
    """What the trade pays, restated on capital employed and after tax."""

    quoted_apr: float              # per one leg, as every scanner reports it
    capital_multiple: float
    capital_apr: float             # on the capital the position actually consumes
    tax_rate: float
    after_tax_apr: float
    risk_free_apr: float
    after_tax_risk_free_apr: float
    excess_apr: float              # after-tax funding less after-tax benchmark
    perp_leverage: float = 1.0
    liquidation_move_pct: float = 0.0

    @property
    def clears_benchmark(self) -> bool:
        return self.excess_apr > 0.0

    def as_record(self) -> Dict[str, Any]:
        return {"quoted_apr": self.quoted_apr,
                "capital_multiple": self.capital_multiple,
                "capital_apr": self.capital_apr,
                "tax_rate": self.tax_rate,
                "after_tax_apr": self.after_tax_apr,
                "risk_free_apr": self.risk_free_apr,
                "after_tax_risk_free_apr": self.after_tax_risk_free_apr,
                "excess_apr": self.excess_apr,
                "perp_leverage": self.perp_leverage,
                "liquidation_move_pct": self.liquidation_move_pct,
                "clears_benchmark": self.clears_benchmark}


def harvest_economics(quoted_apr: float, hook: Any = None,
                      perp_leverage: float = 1.0,
                      risk_free_apr: float = DEFAULT_RISK_FREE_APR,
                      maintenance_margin_fraction: float = 0.0125,
                      rates: Optional[Dict[str, float]] = None) -> HarvestEconomics:
    """
    Restate a quoted funding APR as what it pays, on capital, after tax.

    `quoted_apr` is the scanner's number and is a return on ONE leg. Everything
    that follows is a correction of that: divide by the capital multiple to get a
    return on money actually committed, then tax it as the ordinary income it is.
    """
    rates = rates or resolve_tax_rates(hook)
    multiple = capital_multiple(perp_leverage)
    capital_apr = float(quoted_apr) / multiple
    composite = rates["composite"]
    # Funding received is ordinary income. A loss-making funding leg is a
    # different question and is not netted here: this prices an OPPORTUNITY, and
    # an opportunity whose funding is negative is not opened at all.
    after_tax = capital_apr * (1.0 - composite)
    benchmark = after_tax_risk_free(risk_free_apr, rates)
    return HarvestEconomics(
        quoted_apr=float(quoted_apr), capital_multiple=multiple,
        capital_apr=capital_apr, tax_rate=composite, after_tax_apr=after_tax,
        risk_free_apr=float(risk_free_apr), after_tax_risk_free_apr=benchmark,
        excess_apr=after_tax - benchmark, perp_leverage=float(perp_leverage),
        liquidation_move_pct=liquidation_move_pct(perp_leverage,
                                                  maintenance_margin_fraction))


# ---------------------------------------------------------------------------
# The bankroll gate
# ---------------------------------------------------------------------------

@dataclass
class GateDecision:
    """Whether the `hl_basis_harvest` bucket can fund this position."""

    approved: bool
    reason: str
    requested_capital: float
    approved_capital: float
    approved_notional_per_leg: float
    safe_bankroll: float = 0.0
    strategy_budget: float = 0.0
    strategy_remaining: float = 0.0
    already_deployed: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        verdict = "APPROVED" if self.approved else "REJECTED"
        return ("[{}] ${:,.2f} of ${:,.2f} capital | bucket ${:,.2f} remaining | {}"
                .format(verdict, self.approved_capital, self.requested_capital,
                        self.strategy_remaining, self.reason))


class BucketGate:
    """
    Routes basis positions through `MonarchBankrollHook` on the
    `hl_basis_harvest` bucket.

    IT FAILS CLOSED. When the tax ledger cannot be read the gate REJECTS rather
    than waving the order through. An unreadable ledger is not evidence that
    capital is available; it is the absence of evidence that it is, and the
    failure mode of guessing wrong here is trading against money that is already
    committed or already owed in tax.
    """

    def __init__(self, hook: Any = None, strategy: str = STRATEGY_BASIS_HARVEST,
                 tax_year: Optional[int] = None, db_path: Optional[str] = None):
        self.strategy = strategy
        self.hook_error = ""
        self.hook = hook
        if self.hook is None:
            try:
                from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook
                self.hook = MonarchBankrollHook(tax_year=tax_year, db_path=db_path)
            except Exception as exc:                       # noqa: BLE001
                self.hook_error = "%s: %s" % (type(exc).__name__, exc)
                self.hook = None

    def check(self, notional_per_leg: float, perp_leverage: float = 1.0,
              already_deployed: float = 0.0, price: Optional[float] = None,
              live_cash: Optional[float] = None) -> GateDecision:
        """
        Ask the bucket for the CAPITAL the position consumes, not one leg's notional.

        Requesting one leg's notional would understate the ask by the capital
        multiple - at 1x on the perp, by half. The bucket would authorise $10,000
        and the position would consume $20,000, and it would do so while reporting
        that it had been approved.
        """
        multiple = capital_multiple(perp_leverage)
        requested = float(notional_per_leg) * multiple
        if self.hook is None:
            return GateDecision(
                approved=False,
                reason="bankroll unavailable (%s); refusing to size blind"
                       % (self.hook_error or "no hook"),
                requested_capital=requested, approved_capital=0.0,
                approved_notional_per_leg=0.0, already_deployed=already_deployed)
        try:
            decision = self.hook.check_order(
                requested, strategy=self.strategy, price=price,
                live_cash=live_cash, already_deployed=already_deployed)
        except Exception as exc:                           # noqa: BLE001
            self.hook_error = "%s: %s" % (type(exc).__name__, exc)
            return GateDecision(
                approved=False,
                reason="bankroll check failed (%s); refusing to size blind"
                       % self.hook_error,
                requested_capital=requested, approved_capital=0.0,
                approved_notional_per_leg=0.0, already_deployed=already_deployed)

        approved_capital = float(getattr(decision, "approved_notional", 0.0) or 0.0)
        # BOTH LEGS ARE CLAMPED TOGETHER, from one number. Sizing them separately
        # is how a cash-and-carry stops being delta-neutral: two legs clamped by
        # different amounts leave a naked directional remainder that nobody chose
        # to hold. Round 18 fixed exactly this for the order executor.
        per_leg = approved_capital / multiple if multiple else 0.0
        return GateDecision(
            approved=bool(getattr(decision, "approved", False)) and per_leg > 0.0,
            reason=str(getattr(decision, "reason", "")),
            requested_capital=requested, approved_capital=approved_capital,
            approved_notional_per_leg=per_leg,
            safe_bankroll=float(getattr(decision, "safe_bankroll", 0.0) or 0.0),
            strategy_budget=float(getattr(decision, "strategy_budget", 0.0) or 0.0),
            strategy_remaining=float(getattr(decision, "strategy_remaining", 0.0) or 0.0),
            already_deployed=already_deployed,
            detail=dict(getattr(decision, "detail", {}) or {}))


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------

@dataclass
class HarvestVerdict:
    """Everything needed to decide, and to explain the decision afterwards."""

    coin: str
    economics: HarvestEconomics
    gate: GateDecision
    tradeable: bool
    reasons: List[str] = field(default_factory=list)

    def as_record(self) -> Dict[str, Any]:
        return {"coin": self.coin, "tradeable": self.tradeable,
                "reasons": list(self.reasons),
                "economics": self.economics.as_record(),
                "gate": {"approved": self.gate.approved,
                         "reason": self.gate.reason,
                         "requested_capital": self.gate.requested_capital,
                         "approved_capital": self.gate.approved_capital,
                         "approved_notional_per_leg":
                             self.gate.approved_notional_per_leg,
                         "strategy_remaining": self.gate.strategy_remaining}}


class FundingHarvester:
    """
    Scan, price after tax, gate on the bucket, and only then open.

    The engine underneath is `execution.basis_harvester.BasisHarvester`, which is
    left entirely alone. This class adds the two checks it never had: does the
    trade beat a Treasury bill once tax and the second leg are accounted for, and
    does the `hl_basis_harvest` bucket have room to fund it.
    """

    def __init__(self, harvester: Any = None, gate: Optional[BucketGate] = None,
                 hook: Any = None, risk_free_apr: float = DEFAULT_RISK_FREE_APR,
                 perp_leverage: float = BASIS_DEFAULT_PERP_LEVERAGE,
                 min_excess_apr: float = 0.0):
        self.gate = gate if gate is not None else BucketGate(hook=hook)
        self.hook = hook if hook is not None else self.gate.hook
        self.harvester = harvester
        self.risk_free_apr = float(risk_free_apr)
        self.perp_leverage = float(perp_leverage)
        self.min_excess_apr = float(min_excess_apr)
        self._rates = resolve_tax_rates(self.hook)

    # -- the capital this desk has already committed --------------------------

    def deployed_capital(self) -> float:
        """
        Capital the harvester holds open but the tax ledger has not seen.

        Passed to the hook as `already_deployed`. Without it, every position
        opened inside one snapshot window is approved against the same dollars -
        the hook documents this hazard explicitly, and a scanner that opens two
        or three names in a single pass walks straight into it.
        """
        if self.harvester is None:
            return 0.0
        positions = getattr(self.harvester, "positions", {}) or {}
        return float(sum(float(p.get("capital", 0.0) or 0.0)
                         for p in positions.values()))

    # -- the decision ---------------------------------------------------------

    def evaluate(self, opportunity: Dict[str, Any],
                 notional_per_leg: Optional[float] = None) -> HarvestVerdict:
        """Price one scanner row and ask the bucket to fund it."""
        coin = str(opportunity.get("coin") or "")
        quoted = opportunity.get("net_funding_apr")
        if quoted is None:
            quoted = opportunity.get("funding_apr")
        quoted = float(quoted or 0.0)

        # CLAMPED PER COIN. A constructor-wide leverage would apply a BTC ceiling
        # to a microcap the moment the two were scanned in the same pass, which is
        # exactly the accident the exception list exists to prevent.
        leverage = clamp_leverage(coin, self.perp_leverage)
        economics = harvest_economics(
            quoted, hook=self.hook, perp_leverage=leverage,
            risk_free_apr=self.risk_free_apr, rates=self._rates)

        if notional_per_leg is None:
            notional_per_leg = self._default_notional()
        gate = self.gate.check(notional_per_leg, perp_leverage=leverage,
                               already_deployed=self.deployed_capital(),
                               price=opportunity.get("mark_price"))

        reasons: List[str] = []
        if quoted <= 0:
            reasons.append(
                "Funding is not positive (%.2f%% quoted). Running this in reverse "
                "needs a spot BORROW, which HyperLiquid does not offer, so a "
                "negative-funding market is not harvestable at all - it is not a "
                "worse trade, it is not a trade." % quoted)
        if economics.excess_apr <= self.min_excess_apr:
            reasons.append(
                "%.2f%% quoted is %.2f%% on capital employed and %.2f%% after tax, "
                "against %.2f%% for a Treasury bill after ITS tax (state-exempt "
                "under 31 USC 3124(a)). Excess %.2f%% does not clear %.2f%%."
                % (economics.quoted_apr, economics.capital_apr,
                   economics.after_tax_apr, economics.after_tax_risk_free_apr,
                   economics.excess_apr, self.min_excess_apr))
        if not gate.approved:
            reasons.append("Bucket %s: %s" % (self.gate.strategy, gate.reason))

        return HarvestVerdict(coin=coin, economics=economics, gate=gate,
                              tradeable=not reasons, reasons=reasons)

    def _default_notional(self) -> float:
        try:
            from config.dynamic_config import get_dynamic_config
            return float(get_dynamic_config().basis_notional_usd)
        except Exception:                                   # noqa: BLE001
            from config.settings import BASIS_NOTIONAL_USD
            return float(BASIS_NOTIONAL_USD)

    def open(self, opportunity: Dict[str, Any],
             notional_per_leg: Optional[float] = None,
             **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Open through the underlying engine, at the size the BUCKET authorised.

        The size passed down is `gate.approved_notional_per_leg`, not the
        requested one. The hook's `approved_notional` is already clamped to every
        limit, so honouring it is what keeps a partial approval from being
        rounded back up to the full ask.
        """
        verdict = self.evaluate(opportunity, notional_per_leg)
        if not verdict.tradeable or self.harvester is None:
            return None
        return self.harvester.open_position(
            opportunity, notional_per_leg=verdict.gate.approved_notional_per_leg,
            **kwargs)

    def scan(self, opportunities: List[Dict[str, Any]],
             notional_per_leg: Optional[float] = None) -> List[HarvestVerdict]:
        return [self.evaluate(o, notional_per_leg) for o in opportunities]


def format_economics(economics: HarvestEconomics) -> str:
    """The four-line restatement, which is the whole point of the module."""
    return "\n".join([
        "  quoted APR (one leg)              %7.2f%%" % economics.quoted_apr,
        "  on capital employed (%.2f legs)   %7.2f%%"
        % (economics.capital_multiple, economics.capital_apr),
        "  after tax at %.2f%% composite      %7.2f%%"
        % (economics.tax_rate * 100.0, economics.after_tax_apr),
        "  T-bill %.2f%% after ITS tax        %7.2f%%   (state-exempt)"
        % (economics.risk_free_apr, economics.after_tax_risk_free_apr),
        "  EXCESS                            %+7.2f%%" % economics.excess_apr,
        "  perp leg liquidates on a %.1f%% move at %.1fx"
        % (economics.liquidation_move_pct, economics.perp_leverage),
    ])
