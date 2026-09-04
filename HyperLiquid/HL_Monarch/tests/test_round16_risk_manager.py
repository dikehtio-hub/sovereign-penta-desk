"""
Round 16: the sovereign risk gate.

Two limits that constrain different things and must both hold - account margin
utilisation (surviving volatility) and safe bankroll / strategy bucket (not
spending money already owed in tax). Every test here drives a fake hook, so the
suite stays offline and does not depend on the tax ledger's contents.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.paper_trader import PaperTrader
from execution.risk_manager import (
    MAX_ACCOUNT_MARGIN_UTILIZATION,
    STRATEGY_BASIS_HARVEST,
    STRATEGY_LIQUIDATION_FADE,
    RiskManager,
)


class _Decision:
    """Stands in for a BankrollDecision."""

    def __init__(self, approved=True, approved_notional=1_000.0, safe_bankroll=10_000.0,
                 strategy_remaining=2_500.0, reason="within limits"):
        self.approved = approved
        self.approved_notional = approved_notional
        self.safe_bankroll = safe_bankroll
        self.strategy_remaining = strategy_remaining
        self.reason = reason


class _Hook:
    """Fake MonarchBankrollHook: no ledger, no network, scripted answers."""

    def __init__(self, available=True, decision=None, buckets=None, raises=False):
        self._available = available
        self._decision = decision or _Decision()
        self._buckets = buckets or {}
        self._raises = raises
        self.calls = []

    def snapshot(self, live_cash=None, force=False):
        return {"available": self._available}

    def get_safe_bankroll(self, live_cash=None):
        return self._decision.safe_bankroll

    def check_order(self, size_usd, strategy=None, price=None, **kwargs):
        self.calls.append((size_usd, strategy))
        if self._raises:
            raise RuntimeError("ledger exploded")
        if strategy in self._buckets:
            cap = self._buckets[strategy]
            return _Decision(approved=cap > 0, approved_notional=min(size_usd, cap),
                             strategy_remaining=cap,
                             reason=f"{strategy} bucket ${cap:,.2f}")
        return self._decision


def _trader(balance=100_000.0):
    return PaperTrader(initial_balance_usd=balance)


# ---------------------------------------------------------------- margin cap

def test_margin_cap_limits_notional():
    """Headroom is expressed in margin; the cap on notional scales by leverage."""
    manager = RiskManager(trader=_trader(100_000.0),
                          hook=_Hook(decision=_Decision(approved_notional=10_000_000.0,
                                                        strategy_remaining=10_000_000.0)))
    # 50% of $100k equity = $50k of margin, at 10x = $500k of notional.
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, size_usd=1_000_000.0,
                                   margin_required_usd=100_000.0)
    assert decision.approved
    assert decision.max_size_usd == pytest.approx(500_000.0)
    assert decision.binding_limit == "margin"


def test_default_utilisation_cap_is_fifty_percent():
    assert MAX_ACCOUNT_MARGIN_UTILIZATION == 0.50


def test_utilisation_cap_is_configurable():
    manager = RiskManager(trader=_trader(100_000.0), max_margin_utilization=0.10,
                          hook=_Hook(decision=_Decision(approved_notional=1e9,
                                                        strategy_remaining=1e9)))
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 1e9, margin_required_usd=1e9)
    assert decision.max_size_usd == pytest.approx(10_000.0)


def test_an_exhausted_margin_budget_rejects():
    trader = _trader(10_000.0)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0, leverage=10)   # $6k margin
    manager = RiskManager(trader=trader, hook=_Hook())
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 1_000.0, 100.0,
                                   current_prices={"BTC": 60_000.0})
    assert not decision.approved
    assert decision.max_size_usd == 0.0
    assert "margin utilisation" in decision.reason


def test_margin_defaults_to_one_times_when_unspecified():
    """The conservative reading: no leverage figure means assume none."""
    manager = RiskManager(trader=_trader(100_000.0),
                          hook=_Hook(decision=_Decision(approved_notional=1e9,
                                                        strategy_remaining=1e9)))
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, size_usd=1_000_000.0)
    assert decision.max_size_usd == pytest.approx(50_000.0)


# ------------------------------------------------------------- bankroll cap

def test_bankroll_binds_before_margin_when_it_is_smaller():
    manager = RiskManager(trader=_trader(100_000.0),
                          hook=_Hook(decision=_Decision(approved_notional=250.0,
                                                        strategy_remaining=2_500.0)))
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 50_000.0, 5_000.0)
    assert decision.approved
    assert decision.max_size_usd == pytest.approx(250.0)
    assert decision.binding_limit == "bankroll"


def test_the_smaller_of_the_two_limits_always_wins():
    for bankroll_cap, expected in [(100.0, 100.0), (10_000_000.0, 500_000.0)]:
        manager = RiskManager(
            trader=_trader(100_000.0),
            hook=_Hook(decision=_Decision(approved_notional=bankroll_cap,
                                          strategy_remaining=bankroll_cap)))
        decision = manager.check_order(STRATEGY_BASIS_HARVEST, 1_000_000.0, 100_000.0)
        assert decision.max_size_usd == pytest.approx(expected)


def test_a_rejected_bankroll_decision_rejects_the_order():
    manager = RiskManager(trader=_trader(),
                          hook=_Hook(decision=_Decision(approved=False, approved_notional=0.0,
                                                        reason="no risk capital")))
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 1_000.0, 100.0)
    assert not decision.approved
    assert "no risk capital" in decision.reason


# --------------------------------------------------------- bucket isolation

def test_strategies_draw_on_separate_buckets():
    hook = _Hook(buckets={STRATEGY_BASIS_HARVEST: 2_500.0,
                          STRATEGY_LIQUIDATION_FADE: 500.0})
    manager = RiskManager(trader=_trader(), hook=hook)
    basis = manager.check_order(STRATEGY_BASIS_HARVEST, 10_000.0, 1_000.0)
    fade = manager.check_order(STRATEGY_LIQUIDATION_FADE, 10_000.0, 1_000.0)
    assert basis.max_size_usd == pytest.approx(2_500.0)
    assert fade.max_size_usd == pytest.approx(500.0)


def test_exhausting_one_bucket_leaves_the_other_alone():
    hook = _Hook(buckets={STRATEGY_LIQUIDATION_FADE: 0.0,
                          STRATEGY_BASIS_HARVEST: 2_500.0})
    manager = RiskManager(trader=_trader(), hook=hook)
    assert not manager.check_order(STRATEGY_LIQUIDATION_FADE, 1_000.0, 100.0).approved
    assert manager.check_order(STRATEGY_BASIS_HARVEST, 1_000.0, 100.0).approved


def test_the_strategy_tag_reaches_the_hook():
    hook = _Hook()
    RiskManager(trader=_trader(), hook=hook).check_order(STRATEGY_BASIS_HARVEST, 100.0, 10.0)
    assert hook.calls[-1][1] == STRATEGY_BASIS_HARVEST


# ------------------------------------------------------- graceful degradation

def test_no_hook_degrades_to_the_paper_balance():
    manager = RiskManager(trader=_trader(100_000.0), hook=None)
    manager.hook = None
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 1_000_000.0, 100_000.0)
    assert decision.approved
    assert decision.max_size_usd == pytest.approx(500_000.0)
    assert not decision.tax_gate_available


def test_degradation_is_stated_on_every_decision_not_just_logged():
    """A caller must be able to see that the bankroll half did not happen."""
    manager = RiskManager(trader=_trader(), hook=None)
    manager.hook = None
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 100.0, 10.0)
    assert "TAX GATE UNAVAILABLE" in decision.reason
    assert not decision.tax_gate_available


def test_an_unavailable_ledger_degrades_rather_than_raising():
    manager = RiskManager(trader=_trader(), hook=_Hook(available=False))
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 100.0, 10.0)
    assert decision.approved
    assert not decision.tax_gate_available


def test_a_raising_hook_does_not_propagate():
    """An accounting outage must not take down the trading loop."""
    manager = RiskManager(trader=_trader(), hook=_Hook(raises=True))
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 100.0, 10.0)
    assert decision.approved
    assert not decision.tax_gate_available
    assert "TAX GATE UNAVAILABLE" in decision.reason


def test_require_tax_gate_turns_degradation_into_refusal():
    """What a live order router should set."""
    manager = RiskManager(trader=_trader(), hook=_Hook(available=False),
                          require_tax_gate=True)
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 100.0, 10.0)
    assert not decision.approved
    assert decision.max_size_usd == 0.0
    assert "required but unavailable" in decision.reason


def test_no_trader_falls_back_to_the_configured_balance():
    manager = RiskManager(trader=None, hook=None, fallback_balance_usd=20_000.0)
    manager.hook = None
    decision = manager.check_order(STRATEGY_BASIS_HARVEST, 1_000_000.0, 1_000_000.0)
    assert decision.max_size_usd == pytest.approx(10_000.0)


# ------------------------------------------------------------------- shape

def test_decision_exposes_the_briefed_dict_shape():
    decision = RiskManager(trader=_trader(), hook=_Hook()).check_order(
        STRATEGY_BASIS_HARVEST, 100.0, 10.0)
    payload = decision.to_dict()
    assert {"approved", "max_size_usd", "reason"} <= set(payload)
    assert isinstance(payload["approved"], bool)
    assert isinstance(payload["max_size_usd"], float)


def test_non_positive_size_is_rejected():
    manager = RiskManager(trader=_trader(), hook=_Hook())
    for size in (0.0, -100.0):
        assert not manager.check_order(STRATEGY_BASIS_HARVEST, size, 10.0).approved


def test_status_line_reports_both_limits():
    line = RiskManager(trader=_trader(50_000.0), hook=_Hook()).status_line()
    assert "equity" in line and "margin" in line and "safe bankroll" in line


def test_status_line_announces_an_unavailable_gate():
    manager = RiskManager(trader=_trader(), hook=None)
    manager.hook = None
    assert "TAX GATE UNAVAILABLE" in manager.status_line()
