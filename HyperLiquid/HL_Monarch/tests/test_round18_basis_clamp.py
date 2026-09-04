"""
Round 18: basis pair leg parity under clamping.

THE BUG THIS GUARDS. Gating each leg independently lets the gate clamp leg 1 to
one size and leg 2 to another. A cash-and-carry whose legs differ in size is not
delta-neutral - it is a naked directional position wearing a hedge's name, and
nobody chose to hold it.
"""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from execution.order_executor import OrderExecutor
from execution.risk_manager import (
    STRATEGY_BASIS_HARVEST,
    RiskBreachException,
    RiskDecision,
)
from execution.wallet_manager import WalletManager

SYNTHETIC_KEY = "0x" + "11" * 32
ASSETS = {"BTC-SPOT": 10, "BTC-PERP": 11, "ETH-SPOT": 12, "ETH-PERP": 13}
SPOT_PX, PERP_PX = "60000.0", "60100.0"
COMBINED = 60000.0 + 60100.0


class _Gate:
    """Approves up to `max_size_usd`, clamping anything larger - like the real one."""

    def __init__(self, max_size_usd=1_000_000.0, approved=True):
        self.max_size_usd = max_size_usd
        self.approved = approved
        self.calls = []

    def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
        self.calls.append((strategy, size_usd))
        if not self.approved or size_usd <= 0:
            return RiskDecision(approved=False, max_size_usd=0.0, strategy=strategy,
                                reason="no capital for this strategy")
        return RiskDecision(approved=True, max_size_usd=min(size_usd, self.max_size_usd),
                            strategy=strategy, reason="ok")


def _executor(gate=None, submit_fn=None, dry_run=True, **kwargs):
    return OrderExecutor(wallet=WalletManager(private_key=SYNTHETIC_KEY),
                         risk_manager=gate or _Gate(), strategy=STRATEGY_BASIS_HARVEST,
                         submit_fn=submit_fn, asset_index=ASSETS, dry_run=dry_run,
                         **kwargs)


def _filler(sz):
    """A submitter that fills whatever size the order asked for."""
    def submit(payload):
        order = payload["action"]["orders"][0]
        return {"filled_sz": float(order["s"]), "oid": 1,
                "avg_price": float(order["p"])}
    return submit


# ------------------------------------------------------------- the pre-gate

def test_the_pair_is_priced_as_one_thing():
    """Total notional is size x (spot + perp) - both legs, one decision."""
    gate = _Gate()
    _executor(gate=gate).execute_basis_pair(coin="BTC", sz="0.1", spot_px=SPOT_PX,
                                            perp_px=PERP_PX)
    assert gate.calls[0][1] == pytest.approx(0.1 * COMBINED)


def test_an_unapproved_pair_places_nothing():
    with pytest.raises(RiskBreachException):
        _executor(gate=_Gate(approved=False)).execute_basis_pair(
            coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)


def test_a_clamp_sizes_BOTH_legs_identically():
    """The property the whole round exists for."""
    gate = _Gate(max_size_usd=6_005.0)      # about half of 0.1 * 120100
    pair = _executor(gate=gate).execute_basis_pair(coin="BTC", sz="0.1",
                                                   spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["gate"]["clamped"] is True
    assert pair["spot"].requested_sz == pytest.approx(pair["perp"].requested_sz)


def test_the_clamped_size_matches_the_approved_notional():
    gate = _Gate(max_size_usd=6_005.0)
    pair = _executor(gate=gate).execute_basis_pair(coin="BTC", sz="0.1",
                                                   spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["spot"].requested_sz == pytest.approx(6_005.0 / COMBINED)


def test_an_unclamped_pair_uses_the_requested_size():
    pair = _executor(gate=_Gate()).execute_basis_pair(coin="BTC", sz="0.1",
                                                      spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["gate"]["clamped"] is False
    assert pair["spot"].requested_sz == pytest.approx(0.1)
    assert pair["perp"].requested_sz == pytest.approx(0.1)


@pytest.mark.parametrize("cap", [500.0, 1_500.0, 6_005.0, 11_000.0, 12_010.0])
def test_leg_parity_holds_at_every_clamp_level(cap):
    pair = _executor(gate=_Gate(max_size_usd=cap)).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["spot"].requested_sz == pytest.approx(pair["perp"].requested_sz)


def test_a_clamped_pair_that_fills_has_zero_residual():
    pair = _executor(gate=_Gate(max_size_usd=6_005.0), submit_fn=_filler(None),
                     dry_run=False).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["hedged"] is True
    assert pair["residual_sz"] == pytest.approx(0.0)


def test_the_clamped_pair_never_exceeds_the_approved_notional():
    cap = 6_005.0
    pair = _executor(gate=_Gate(max_size_usd=cap), submit_fn=_filler(None),
                     dry_run=False).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    spent = (pair["spot"].filled_sz * float(SPOT_PX)
             + pair["perp"].filled_sz * float(PERP_PX))
    assert spent <= cap + 1e-6


# ------------------------------------------------- the gate moving underneath

def test_a_resized_spot_leg_aborts_before_the_perp_leg():
    """
    If the gate clamps leg 1 below what the pair agreed, leg 2 is NOT placed.
    Holding one known leg beats adding a second at the wrong size.
    """
    class _Shifting(_Gate):
        def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
            self.calls.append((strategy, size_usd))
            # Approves the pair generously, then squeezes the first leg.
            cap = 1_000_000.0 if len(self.calls) == 1 else 100.0
            return RiskDecision(approved=True, max_size_usd=min(size_usd, cap),
                                strategy=strategy, reason="ok")

    pair = _executor(gate=_Shifting()).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["perp"] is None
    assert pair["aborted"] and "NOT placed" in pair["aborted"]


def test_the_abort_reports_the_exposure_it_left_behind():
    class _Shifting(_Gate):
        def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
            self.calls.append((strategy, size_usd))
            cap = 1_000_000.0 if len(self.calls) == 1 else 100.0
            return RiskDecision(approved=True, max_size_usd=min(size_usd, cap),
                                strategy=strategy, reason="ok")

    pair = _executor(gate=_Shifting(), submit_fn=_filler(None),
                     dry_run=False).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["hedged"] is False
    assert pair["residual_sz"] > 0


# ------------------------------------------------- fills are still independent

def test_an_unequal_FILL_is_still_reported_honestly():
    """
    Clamping fixes the SIZING. It cannot fix the fill - the exchange owes us
    nothing - so a half-filled leg must still surface as real exposure.
    """
    fills = iter([{"filled_sz": 0.1, "oid": 1, "avg_price": 60_000.0},
                  {"filled_sz": 0.04, "oid": 2, "avg_price": 60_100.0}])
    pair = _executor(submit_fn=lambda payload: next(fills),
                     dry_run=False).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    assert pair["hedged"] is False
    assert pair["residual_sz"] == pytest.approx(0.06)


def test_receipts_book_the_clamped_sizes(tmp_path):
    pair = _executor(gate=_Gate(max_size_usd=6_005.0), submit_fn=_filler(None),
                     dry_run=False, receipts_enabled=True,
                     receipts_dir=tmp_path).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px=SPOT_PX, perp_px=PERP_PX)
    rows = []
    for path in sorted(tmp_path.glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows.extend(list(csv.DictReader(handle)))
    assert len(rows) == 2
    quantities = [float(r["quantity"]) for r in rows]
    assert quantities[0] == pytest.approx(quantities[1])
    assert quantities[0] == pytest.approx(pair["spot"].requested_sz)


# ------------------------------------------------------------------ validation

@pytest.mark.parametrize("sz,spot,perp", [("0", SPOT_PX, PERP_PX),
                                          ("0.1", "0", PERP_PX),
                                          ("0.1", SPOT_PX, "0")])
def test_a_degenerate_pair_is_refused(sz, spot, perp):
    with pytest.raises(RiskBreachException):
        _executor().execute_basis_pair(coin="BTC", sz=sz, spot_px=spot, perp_px=perp)


def test_the_pair_gate_can_be_inspected_without_trading():
    """`pair_gate()` is pure: it decides a size and places nothing."""
    executor = _executor(gate=_Gate(max_size_usd=6_005.0))
    gate = executor.pair_gate("BTC", "0.1", SPOT_PX, PERP_PX)
    assert gate["approved"] and gate["clamped"]
    assert float(gate["sz"]) == pytest.approx(6_005.0 / COMBINED)
