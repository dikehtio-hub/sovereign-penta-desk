"""
Round 29: the funding harvester's bankroll gate and after-tax economics.

TWO BUGS ARE BEING GUARDED, and both are the kind that report success.

THE HARVESTER NEVER ASKED THE BANKROLL. `BasisHarvester.can_open` gates on its
own paper cash and imports STRATEGY_BASIS_HARVEST only to tag receipts, so two
positions at the configured $10,000 per leg commit $40,000 without one reference
to the `hl_basis_harvest` bucket. Same defect as Monarch_Shark running 1.7x over
its sports bucket: an engine sizing against local state instead of the shared one.

THE APR IS QUOTED AGAINST ONE LEG AND THE CAPITAL IS TWO. `capital_required()`
is `notional * 2`; every APR in the system is a return on one leg. A position
reporting 56% realised earns 28% on the money it consumes. A gate that asks the
bucket for one leg's notional inherits that error and authorises half what the
position spends - while reporting that it was approved.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from execution.risk_manager import STRATEGY_BASIS_HARVEST
from strategies.funding_harvester import (
    DEFAULT_RISK_FREE_APR,
    clamp_leverage,
    max_leverage_for,
    BucketGate,
    FundingHarvester,
    HarvestEconomics,
    after_tax_risk_free,
    capital_multiple,
    format_economics,
    harvest_economics,
    liquidation_move_pct,
    resolve_tax_rates,
)

COMPOSITE = 0.24 + 0.0637 + 0.02          # 32.37%, the NJ composite
FEDERAL_ONLY = 0.24 + 0.02                # what a state-exempt T-bill actually pays


class FakeDecision:
    def __init__(self, approved=True, approved_notional=20_000.0, reason="ok",
                 strategy_budget=50_000.0, strategy_remaining=30_000.0):
        self.approved = approved
        self.approved_notional = approved_notional
        self.reason = reason
        self.safe_bankroll = 100_000.0
        self.strategy_budget = strategy_budget
        self.strategy_remaining = strategy_remaining
        self.detail = {}


class FakeHook:
    """Records what it was asked, because the ASK is what these tests are about."""

    config = {"tax_rates": {"short_term_capital_gains": 0.24,
                            "state_tax_rate": 0.0637,
                            "safety_buffer_pct": 0.02}}

    def __init__(self, decision=None, raises=False):
        self._decision = decision or FakeDecision()
        self._raises = raises
        self.calls = []

    def check_order(self, desired_notional, **kwargs):
        if self._raises:
            raise RuntimeError("ledger unreadable")
        self.calls.append({"desired_notional": desired_notional, **kwargs})
        return self._decision


class FakeHarvester:
    """The engine underneath, reduced to what the orchestrator touches."""

    def __init__(self, positions=None):
        self.positions = positions or {}
        self.opened = []

    def open_position(self, opportunity, notional_per_leg=None, **kwargs):
        self.opened.append({"opportunity": opportunity,
                            "notional_per_leg": notional_per_leg, **kwargs})
        return {"coin": opportunity.get("coin"), "notional_per_leg": notional_per_leg}


def _gate(hook):
    return BucketGate(hook=hook, strategy=STRATEGY_BASIS_HARVEST)


# ---------------------------------------------------------------------------
# Capital efficiency
# ---------------------------------------------------------------------------

def test_an_unlevered_cash_and_carry_costs_two_units_of_capital():
    """The existing engine's `notional * 2` is the 1x case of a general rule."""
    assert capital_multiple(1.0) == pytest.approx(2.0)
    assert capital_multiple(2.0) == pytest.approx(1.5)
    assert capital_multiple(5.0) == pytest.approx(1.2)


def test_the_quoted_apr_is_double_the_return_on_capital_at_1x():
    """
    THE FACTOR OF TWO. Every APR in the system is quoted against one leg while
    the position consumes both. 20% quoted is 10% on the money committed.
    """
    economics = harvest_economics(20.0, perp_leverage=1.0)
    assert economics.quoted_apr == pytest.approx(20.0)
    assert economics.capital_apr == pytest.approx(10.0)


def test_leverage_buys_capital_efficiency_by_moving_the_liquidation_price():
    """
    The trade-off must be visible in one object, not spread across two modules.

    A delta-neutral position is not liquidation-proof: HyperLiquid liquidates the
    perp on ITS OWN margin, and the spot leg in another wallet does not rescue it.
    At 10x the perp dies on an 8.8% move, which crypto does before lunch.
    """
    low, high = harvest_economics(20.0, perp_leverage=1.0), harvest_economics(20.0, perp_leverage=10.0)
    assert high.capital_apr > low.capital_apr
    assert high.liquidation_move_pct < low.liquidation_move_pct
    assert high.liquidation_move_pct == pytest.approx(8.75, abs=0.1)
    assert liquidation_move_pct(1.0) == pytest.approx(98.75, abs=0.1)


# ---------------------------------------------------------------------------
# After-tax economics
# ---------------------------------------------------------------------------

def test_funding_is_taxed_as_ordinary_income_at_the_composite():
    economics = harvest_economics(20.0, hook=FakeHook())
    assert economics.tax_rate == pytest.approx(COMPOSITE)
    assert economics.after_tax_apr == pytest.approx(10.0 * (1 - COMPOSITE))


def test_the_treasury_benchmark_is_taxed_on_its_own_terms_not_the_composite():
    """
    31 USC 3124(a) exempts Treasury interest from STATE income tax. Funding income
    is not exempt. Discounting both by the same composite would hand the harvester
    a 6.37-point advantage it does not have, and this comparison exists precisely
    to be honest about the margin.
    """
    rates = resolve_tax_rates(FakeHook())
    assert after_tax_risk_free(5.0, rates) == pytest.approx(5.0 * (1 - FEDERAL_ONLY))
    # Discounting the benchmark at the composite would understate it.
    naive = 5.0 * (1 - COMPOSITE)
    assert after_tax_risk_free(5.0, rates) > naive


def test_the_headline_restatement_is_the_one_that_decides_the_trade():
    """20% quoted against a 5% bill is not a fifteen-point edge. It is three."""
    economics = harvest_economics(20.0, hook=FakeHook(), risk_free_apr=5.0)
    assert economics.capital_apr == pytest.approx(10.0)
    assert economics.after_tax_apr == pytest.approx(6.763, abs=0.01)
    assert economics.after_tax_risk_free_apr == pytest.approx(3.70, abs=0.01)
    assert economics.excess_apr == pytest.approx(3.063, abs=0.01)
    assert economics.clears_benchmark


def test_a_rate_that_looks_fine_gross_can_lose_to_a_treasury_bill():
    """
    The case the restatement exists to catch: 11% quoted is 5.5% on capital and
    3.72% after tax, against 3.70% for a bill that carries no liquidation risk,
    no basis drift and no rate that can vanish in an hour.
    """
    economics = harvest_economics(11.0, hook=FakeHook(), risk_free_apr=5.0)
    assert economics.after_tax_apr == pytest.approx(3.72, abs=0.02)
    assert economics.excess_apr < 0.05
    assert harvest_economics(10.0, hook=FakeHook()).excess_apr < 0.0


def test_the_report_states_all_four_numbers():
    text = format_economics(harvest_economics(20.0, hook=FakeHook()))
    for fragment in ("quoted APR", "on capital employed", "after tax",
                     "T-bill", "EXCESS", "liquidates"):
        assert fragment in text


# ---------------------------------------------------------------------------
# The bucket gate
# ---------------------------------------------------------------------------

def test_the_gate_asks_the_bucket_for_capital_not_for_one_legs_notional():
    """
    THE BUG THIS EXISTS TO PREVENT. Asking for $10,000 when the position consumes
    $20,000 gets an approval for half the money actually spent - and the caller is
    told it was approved.
    """
    hook = FakeHook()
    decision = _gate(hook).check(10_000.0, perp_leverage=1.0)
    assert hook.calls[0]["desired_notional"] == pytest.approx(20_000.0)
    assert decision.requested_capital == pytest.approx(20_000.0)


def test_the_gate_routes_to_the_hl_basis_harvest_bucket():
    hook = FakeHook()
    _gate(hook).check(10_000.0)
    assert hook.calls[0]["strategy"] == "hl_basis_harvest"
    assert STRATEGY_BASIS_HARVEST == "hl_basis_harvest"


def test_an_approval_is_converted_back_to_a_per_leg_size():
    """The engine below is sized per leg; the bucket authorises capital."""
    hook = FakeHook(FakeDecision(approved_notional=15_000.0))
    decision = _gate(hook).check(10_000.0, perp_leverage=1.0)
    assert decision.approved_capital == pytest.approx(15_000.0)
    assert decision.approved_notional_per_leg == pytest.approx(7_500.0)


def test_both_legs_are_clamped_from_one_number():
    """
    Round 18 fixed this for the order executor and the same rule holds here. Two
    legs clamped independently leave a naked directional remainder that nobody
    chose to hold - a cash-and-carry whose legs differ in size is not a hedge.
    """
    hook = FakeHook(FakeDecision(approved_notional=9_000.0))
    decision = _gate(hook).check(10_000.0, perp_leverage=1.0)
    # One authorised capital number, divided once. Both legs get 4,500.
    assert decision.approved_notional_per_leg * capital_multiple(1.0) == pytest.approx(
        decision.approved_capital)


def test_the_gate_fails_closed_when_the_bankroll_cannot_be_read():
    """
    An unreadable ledger is not evidence that capital is available. It is the
    absence of evidence that it is, and waving the order through would trade
    against money that may already be committed or already owed in tax.
    """
    gate = _gate(FakeHook())
    gate.hook = None
    gate.hook_error = "ledger missing"
    decision = gate.check(10_000.0)
    assert not decision.approved
    assert decision.approved_capital == 0.0
    assert decision.approved_notional_per_leg == 0.0
    assert "refusing to size blind" in decision.reason


def test_an_exception_from_the_hook_also_fails_closed():
    decision = _gate(FakeHook(raises=True)).check(10_000.0)
    assert not decision.approved
    assert decision.approved_notional_per_leg == 0.0
    assert "refusing to size blind" in decision.reason


def test_a_rejection_carries_no_size():
    hook = FakeHook(FakeDecision(approved=False, approved_notional=0.0,
                                 reason="bucket exhausted"))
    decision = _gate(hook).check(10_000.0)
    assert not decision.approved
    assert decision.approved_notional_per_leg == 0.0
    assert "bucket exhausted" in decision.reason


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------

def _opportunity(coin="BTC", apr=40.0):
    return {"coin": coin, "net_funding_apr": apr, "spread_bps": 3.0,
            "holding_days": 7.0, "mark_price": 60_000.0}


def test_open_positions_are_declared_to_the_hook_as_already_deployed():
    """
    Without this, every position opened inside one snapshot window is approved
    against the same dollars. The hook documents the hazard; a scanner that opens
    two or three names in a single pass walks straight into it.
    """
    hook = FakeHook()
    harvester = FakeHarvester(positions={"ETH": {"capital": 20_000.0},
                                         "SOL": {"capital": 12_000.0}})
    orchestrator = FundingHarvester(harvester=harvester, gate=_gate(hook), hook=hook)
    assert orchestrator.deployed_capital() == pytest.approx(32_000.0)
    orchestrator.evaluate(_opportunity())
    assert hook.calls[0]["already_deployed"] == pytest.approx(32_000.0)


def test_a_tradeable_opportunity_clears_both_the_economics_and_the_bucket():
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook)
    verdict = orchestrator.evaluate(_opportunity(apr=40.0))
    assert verdict.tradeable
    assert verdict.reasons == []
    assert verdict.economics.capital_apr == pytest.approx(20.0)


def test_negative_funding_is_refused_because_it_is_not_a_trade():
    """
    Running the basis in reverse needs a SPOT BORROW, which HyperLiquid does not
    offer. A negative-funding market is not a worse trade than a positive one; it
    is not available at all, and "or vice versa" describes a venue we do not have.
    """
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook)
    verdict = orchestrator.evaluate(_opportunity(apr=-30.0))
    assert not verdict.tradeable
    assert any("borrow" in reason.lower() for reason in verdict.reasons)


def test_an_opportunity_that_loses_to_a_treasury_bill_is_refused():
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook, risk_free_apr=5.0)
    verdict = orchestrator.evaluate(_opportunity(apr=10.0))
    assert not verdict.tradeable
    assert any("Treasury" in reason for reason in verdict.reasons)


def test_a_bucket_rejection_blocks_an_otherwise_excellent_rate():
    """A 200% APR that the bucket cannot fund is still not tradeable."""
    hook = FakeHook(FakeDecision(approved=False, approved_notional=0.0,
                                 reason="bucket exhausted"))
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook)
    verdict = orchestrator.evaluate(_opportunity(apr=200.0))
    assert not verdict.tradeable
    assert verdict.economics.clears_benchmark
    assert any("hl_basis_harvest" in reason for reason in verdict.reasons)


def test_open_uses_the_size_the_bucket_authorised_not_the_size_requested():
    """
    `approved_notional` is already clamped to every limit. Honouring it is what
    stops a partial approval being rounded back up to the full ask.
    """
    hook = FakeHook(FakeDecision(approved_notional=11_000.0))
    harvester = FakeHarvester()
    orchestrator = FundingHarvester(harvester=harvester, gate=_gate(hook), hook=hook)
    orchestrator.open(_opportunity(apr=40.0), notional_per_leg=10_000.0)
    assert harvester.opened[0]["notional_per_leg"] == pytest.approx(5_500.0)


def test_open_returns_nothing_and_touches_nothing_when_the_gate_refuses():
    hook = FakeHook(FakeDecision(approved=False, approved_notional=0.0,
                                 reason="bucket exhausted"))
    harvester = FakeHarvester()
    orchestrator = FundingHarvester(harvester=harvester, gate=_gate(hook), hook=hook)
    assert orchestrator.open(_opportunity(apr=40.0)) is None
    assert harvester.opened == []


def test_scan_prices_every_row_and_records_why_each_was_refused():
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook)
    verdicts = orchestrator.scan([_opportunity("BTC", 40.0),
                                  _opportunity("ETH", 8.0),
                                  _opportunity("SOL", -20.0)])
    assert [v.tradeable for v in verdicts] == [True, False, False]
    assert all(v.reasons for v in verdicts[1:])
    assert verdicts[0].as_record()["economics"]["capital_apr"] == pytest.approx(20.0)


def test_the_gross_funding_apr_is_used_when_no_net_rate_was_measured():
    """`net_funding_apr` is preferred; a row that never had a spread still prices."""
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook)
    verdict = orchestrator.evaluate({"coin": "BTC", "funding_apr": 40.0})
    assert verdict.economics.quoted_apr == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Round 31 Target E: the leverage policy
# ---------------------------------------------------------------------------

def test_the_leverage_ceiling_is_one_except_for_the_three_deepest_books():
    for coin in ("BTC", "ETH", "SOL", "btc", " eth "):
        assert max_leverage_for(coin) == pytest.approx(2.0), coin
    for coin in ("DOGE", "CASHCAT", "PONS", "ARB", ""):
        assert max_leverage_for(coin) == pytest.approx(1.0), coin


def test_an_unlisted_coin_gets_the_default_rather_than_inheriting_a_ceiling():
    """
    A NEW listing is 1x until somebody decides otherwise. Defaulting the other
    way would hand a fresh microcap the ceiling reserved for the deepest books,
    by accident and silently.
    """
    assert max_leverage_for("SOMECOIN-LISTED-TODAY") == pytest.approx(1.0)


def test_a_leverage_request_is_clamped_per_coin_and_never_below_one():
    assert clamp_leverage("BTC", 5.0) == pytest.approx(2.0)
    assert clamp_leverage("DOGE", 5.0) == pytest.approx(1.0)
    assert clamp_leverage("BTC", 0.2) == pytest.approx(1.0)


def test_the_orchestrator_clamps_per_coin_not_once_per_constructor():
    """
    THE ACCIDENT THIS PREVENTS. A constructor-wide leverage applies a BTC ceiling
    to a microcap the moment the two are scanned in the same pass - which is the
    normal case, since the scanner returns a mixed universe.
    """
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook, perp_leverage=2.0)
    btc = orchestrator.evaluate({"coin": "BTC", "net_funding_apr": 40.0})
    doge = orchestrator.evaluate({"coin": "DOGE", "net_funding_apr": 40.0})
    assert btc.economics.perp_leverage == pytest.approx(2.0)
    assert doge.economics.perp_leverage == pytest.approx(1.0)
    # And the bucket is asked for the correspondingly different capital.
    assert hook.calls[0]["desired_notional"] < hook.calls[1]["desired_notional"]


def test_the_default_leverage_is_one():
    hook = FakeHook()
    orchestrator = FundingHarvester(harvester=FakeHarvester(), gate=_gate(hook),
                                    hook=hook)
    assert orchestrator.evaluate(_opportunity()).economics.perp_leverage == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Round 31 Target D: exit hysteresis
# ---------------------------------------------------------------------------

def _harvester_with(coin="BTC", hours_held=0.0):
    from execution.basis_harvester import BasisHarvester
    harvester = BasisHarvester()
    harvester.positions = {coin: {"coin": coin, "hours_held": hours_held,
                                  "capital": 20_000.0}}
    return harvester


def test_a_dip_below_the_entry_bar_does_not_close_the_position():
    """
    HYSTERESIS. Entry is 20%; exiting the moment funding dips under it makes the
    strategy thrash - a rate oscillating around 20% reopens the same position
    repeatedly and pays the full round trip each time to buy back what it just
    sold.
    """
    harvester = _harvester_with(hours_held=24.0)
    for apr in (19.0, 15.0, 11.0, 0.5):
        assert harvester.should_exit("BTC", apr) is None, apr


def test_funding_turning_negative_closes_immediately_at_any_age():
    """A reversal is an exit at one hour old; we are now PAYING to hold."""
    assert _harvester_with(hours_held=1.0).should_exit("BTC", -0.1) is not None
    assert "adverse" in _harvester_with(hours_held=1.0).should_exit("BTC", -5.0)


def test_a_stale_position_closes_only_after_seven_days_and_under_ten_percent():
    """
    Both conditions, not either. Without the stale leg a position earning 2% APR
    is held indefinitely - never a loss, so nothing ever fires, and the capital
    sits there at unbounded opportunity cost.
    """
    assert _harvester_with(hours_held=7 * 24.0).should_exit("BTC", 5.0) is not None
    # Under 10% but too young: hold.
    assert _harvester_with(hours_held=6 * 24.0).should_exit("BTC", 5.0) is None
    # Old enough but still paying well: hold.
    assert _harvester_with(hours_held=30 * 24.0).should_exit("BTC", 15.0) is None


def test_the_stale_exit_states_the_age_and_the_rate():
    reason = _harvester_with(hours_held=10 * 24.0).should_exit("BTC", 4.0)
    assert "stale" in reason and "10.0d" in reason and "4.0%" in reason


def test_a_data_gap_is_never_an_exit_signal():
    """An unknown rate is not a reversal, at any age."""
    assert _harvester_with(hours_held=90 * 24.0).should_exit("BTC", None) is None


def test_sweep_exits_applies_both_rules_across_the_book():
    from execution.basis_harvester import BasisHarvester
    harvester = BasisHarvester()
    harvester.positions = {
        "REVERSED": {"coin": "REVERSED", "hours_held": 2.0, "capital": 1.0,
                     "notional_per_leg": 1.0, "funding_accrued": 0.0, "entry_fee": 0.0, "size": 1.0,
                     "entry_funding_apr": 40.0, "spot_symbol": None},
        "STALE": {"coin": "STALE", "hours_held": 8 * 24.0, "capital": 1.0,
                  "notional_per_leg": 1.0, "funding_accrued": 0.0, "entry_fee": 0.0, "size": 1.0,
                  "entry_funding_apr": 40.0, "spot_symbol": None},
        "HEALTHY": {"coin": "HEALTHY", "hours_held": 8 * 24.0, "capital": 1.0,
                    "notional_per_leg": 1.0, "funding_accrued": 0.0, "entry_fee": 0.0, "size": 1.0,
                    "entry_funding_apr": 40.0, "spot_symbol": None},
        "DIPPED": {"coin": "DIPPED", "hours_held": 2.0, "capital": 1.0,
                   "notional_per_leg": 1.0, "funding_accrued": 0.0, "entry_fee": 0.0, "size": 1.0,
                   "entry_funding_apr": 40.0, "spot_symbol": None},
    }
    closed = harvester.sweep_exits({"REVERSED": -3.0, "STALE": 4.0,
                                    "HEALTHY": 25.0, "DIPPED": 12.0})
    assert {c["coin"] for c in closed} == {"REVERSED", "STALE"}
    assert set(harvester.positions) == {"HEALTHY", "DIPPED"}
