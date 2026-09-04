"""
Round 17: the native order executor.

The properties under test are ordering and honesty: an unapproved order must not
reach the wallet, and the ledger must be told exactly what filled - never what
was requested.
"""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from execution.order_executor import ExecutionResult, OrderExecutor
from execution.risk_manager import (
    STRATEGY_BASIS_HARVEST,
    RiskBreachException,
    RiskDecision,
    RiskManager,
)
from execution.wallet_manager import WalletManager

SYNTHETIC_KEY = "0x" + "11" * 32
ASSETS = {"BTC": 0, "ETH": 1, "BTC-SPOT": 10, "BTC-PERP": 11}


class _Gate:
    """A risk manager stand-in with a scripted verdict."""

    def __init__(self, approved=True, max_size_usd=1_000_000.0, reason="ok"):
        self._decision = RiskDecision(approved=approved, max_size_usd=max_size_usd,
                                      reason=reason, strategy=STRATEGY_BASIS_HARVEST)
        self.calls = []

    def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
        self.calls.append((strategy, size_usd))
        if size_usd <= 0:
            # Faithful to the real RiskManager: a non-positive notional is not
            # gateable and is refused. A double that approved anything would let
            # the other tests pass against a gate that does not exist.
            return RiskDecision(approved=False, max_size_usd=0.0, strategy=strategy,
                                reason="requested size must be positive")
        return self._decision


class _SpyWallet(WalletManager):
    """Records whether signing was ever reached."""

    def __init__(self, **kwargs):
        super().__init__(private_key=SYNTHETIC_KEY, **kwargs)
        self.signed = []

    def sign_action(self, action, nonce=None, vault_address=None):
        self.signed.append(action)
        return super().sign_action(action, nonce=nonce, vault_address=vault_address)


def _executor(gate=None, wallet=None, submit_fn=None, dry_run=True, **kwargs):
    return OrderExecutor(wallet=wallet if wallet is not None else _SpyWallet(),
                         risk_manager=gate or _Gate(), strategy=STRATEGY_BASIS_HARVEST,
                         submit_fn=submit_fn, asset_index=ASSETS,
                         dry_run=dry_run, **kwargs)


def _rows(directory: Path):
    out = []
    for path in sorted(directory.glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            out.extend(list(csv.DictReader(handle)))
    return out


# ------------------------------------------------------- the hard pre-condition

def test_an_unapproved_order_raises_before_signing():
    """The whole point: a signing key is unreachable from an unchecked path."""
    wallet = _SpyWallet()
    executor = _executor(gate=_Gate(approved=False, max_size_usd=0.0,
                                    reason="no risk capital"), wallet=wallet)
    with pytest.raises(RiskBreachException) as exc:
        executor.execute_order(coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert "no risk capital" in str(exc.value)
    assert wallet.signed == [], "the wallet was reached despite a rejected gate"


def test_a_missing_risk_manager_raises_rather_than_defaulting_open():
    executor = _executor()
    executor.risk_manager = None
    with pytest.raises(RiskBreachException):
        executor.execute_order(coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")


def test_the_gate_is_called_by_the_decorator_not_the_caller():
    """A gate you must remember to invoke is one that eventually is not invoked."""
    gate = _Gate()
    _executor(gate=gate).execute_order(coin="BTC", is_buy=True, sz="0.1",
                                       limit_px="60000.0")
    assert gate.calls, "check_order was never called"
    assert gate.calls[0][0] == STRATEGY_BASIS_HARVEST


def test_the_notional_reaching_the_gate_is_size_times_price():
    gate = _Gate()
    _executor(gate=gate).execute_order(coin="BTC", is_buy=True, sz="0.1",
                                       limit_px="60000.0")
    assert gate.calls[0][1] == pytest.approx(6_000.0)


def test_a_risk_breach_is_not_a_generic_exception():
    """
    A loop that survives a network blip must not survive an unapproved order, so
    the two cannot share an exception class.
    """
    assert issubclass(RiskBreachException, RuntimeError)
    assert RiskBreachException is not RuntimeError


def test_execute_order_is_actually_decorated():
    assert getattr(OrderExecutor.execute_order, "__wrapped_by_tax_gate__", False)


# ------------------------------------------------------------------- clamping

def test_an_oversized_order_is_clamped_not_rejected():
    """The gate's number is authoritative; the order still happens, sized right."""
    executor = _executor(gate=_Gate(max_size_usd=3_000.0))
    result = executor.execute_order(coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.requested_sz == pytest.approx(0.05)
    assert "clamped" in result.reason


def test_a_within_limit_order_is_untouched():
    result = _executor(gate=_Gate(max_size_usd=1_000_000.0)).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.requested_sz == pytest.approx(0.1)
    assert "clamped" not in result.reason


# --------------------------------------------------------------------- safety

def test_an_unknown_coin_is_refused_not_guessed():
    """Defaulting to index 0 would sign a real order on the wrong market."""
    result = _executor().execute_order(coin="NOPE", is_buy=True, sz="0.1",
                                       limit_px="60000.0")
    assert result.status == "REJECTED"
    assert "refusing to guess" in result.reason.lower()


def test_a_missing_wallet_raises_rather_than_no_opping():
    executor = _executor(wallet=None)
    executor.wallet = None
    with pytest.raises(RiskBreachException):
        executor.execute_order(coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")


def test_dry_run_is_the_default_and_submits_nothing():
    calls = []
    executor = _executor(submit_fn=lambda payload: calls.append(payload))
    result = executor.execute_order(coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.status == "DRY_RUN"
    assert calls == []


def test_live_submission_needs_both_switches():
    """Neither a stray default nor a stray injection is enough on its own."""
    executor = _executor(submit_fn=None, dry_run=False)
    assert executor.execute_order(coin="BTC", is_buy=True, sz="0.1",
                                  limit_px="60000.0").status == "DRY_RUN"


def test_non_numeric_input_is_blocked_before_signing():
    """
    An order whose notional cannot be COMPUTED cannot be gated, so it is blocked
    rather than waved through - and the gate must not crash working it out.
    """
    wallet = _SpyWallet()
    with pytest.raises(RiskBreachException):
        _executor(wallet=wallet).execute_order(coin="BTC", is_buy=True,
                                               sz="abc", limit_px="60000.0")
    assert wallet.signed == []


@pytest.mark.parametrize("sz,px", [("0", "60000.0"), ("0.1", "0"), ("-1", "60000.0")])
def test_a_zero_or_negative_notional_is_blocked_by_the_gate(sz, px):
    """
    Anything with a zero or unparseable notional is blocked at the gate, not
    inside the executor - it cannot be measured, so it cannot be approved.
    """
    with pytest.raises(RiskBreachException):
        _executor().execute_order(coin="BTC", is_buy=True, sz=sz, limit_px=px)


# ------------------------------------------------------------- fills and fees

def test_a_full_fill_is_reported_as_filled(tmp_path):
    submit = lambda payload: {"filled_sz": 0.1, "oid": 555, "avg_price": 60_000.0, "fee": 1.5}
    result = _executor(submit_fn=submit, dry_run=False, receipts_enabled=True,
                       receipts_dir=tmp_path).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.status == "FILLED"
    assert result.filled_sz == pytest.approx(0.1)
    assert result.oid == 555


def test_a_partial_fill_books_exactly_what_filled(tmp_path):
    """
    Booking the REQUESTED size would put inventory in the ledger the account does
    not hold, and every downstream number would be wrong the same way.
    """
    submit = lambda payload: {"filled_sz": 0.04, "oid": 7, "avg_price": 60_000.0}
    result = _executor(submit_fn=submit, dry_run=False, receipts_enabled=True,
                       receipts_dir=tmp_path).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.status == "PARTIAL"
    assert result.filled_sz == pytest.approx(0.04)
    assert result.unfilled_sz == pytest.approx(0.06)
    row = _rows(tmp_path)[0]
    assert float(row["quantity"]) == pytest.approx(0.04)
    assert "requested=0.1" in row["notes"] and "filled=0.04" in row["notes"]


def test_a_rejected_order_writes_no_receipt(tmp_path):
    submit = lambda payload: {"status": "rejected", "reason": "post-only would cross"}
    result = _executor(submit_fn=submit, dry_run=False, receipts_enabled=True,
                       receipts_dir=tmp_path).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.status == "REJECTED"
    assert list(tmp_path.glob("*.csv")) == []


def test_receipts_are_off_by_default(tmp_path):
    submit = lambda payload: {"filled_sz": 0.1, "oid": 1, "avg_price": 60_000.0}
    _executor(submit_fn=submit, dry_run=False, receipts_dir=tmp_path).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert list(tmp_path.glob("*.csv")) == []


def test_the_receipt_carries_the_strategy_tag(tmp_path):
    submit = lambda payload: {"filled_sz": 0.1, "oid": 1, "avg_price": 60_000.0}
    _executor(submit_fn=submit, dry_run=False, receipts_enabled=True,
              receipts_dir=tmp_path).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert "strategy:hl_basis_harvest;" in _rows(tmp_path)[0]["notes"]


# ------------------------------------------------------- network and reconciliation

def test_a_transport_failure_reports_unknown_not_rejected(tmp_path):
    """
    The order may be resting. Reporting a rejection would invite a retry that
    duplicates it.
    """
    def boom(payload):
        raise ConnectionError("socket closed")

    result = _executor(submit_fn=boom, dry_run=False, receipts_enabled=True,
                       receipts_dir=tmp_path).execute_order(
        coin="BTC", is_buy=True, sz="0.1", limit_px="60000.0")
    assert result.status == "ERROR"
    assert "UNKNOWN" in result.reason
    assert result.cloid in result.reason, "the reason must name the cloid to reconcile on"
    assert list(tmp_path.glob("*.csv")) == [], "an unknown outcome must not be booked"


def test_every_order_carries_a_unique_cloid():
    executor = _executor()
    cloids = {executor.execute_order(coin="BTC", is_buy=True, sz="0.001",
                                     limit_px="60000.0").cloid for _ in range(25)}
    assert len(cloids) == 25


def test_nonces_do_not_repeat_across_orders():
    executor = _executor()
    nonces = [executor.execute_order(coin="BTC", is_buy=True, sz="0.001",
                                     limit_px="60000.0").nonce for _ in range(20)]
    assert len(set(nonces)) == 20


# ------------------------------------------------------------------ basis pair

def test_a_hedged_pair_reports_no_residual(tmp_path):
    submit = lambda payload: {"filled_sz": 0.1, "oid": 1, "avg_price": 60_000.0}
    pair = _executor(submit_fn=submit, dry_run=False).execute_basis_pair(
        coin="BTC", sz="0.1", spot_px="60000.0", perp_px="60100.0")
    assert pair["hedged"] is True
    assert pair["residual_sz"] == pytest.approx(0.0)


def test_an_unhedged_pair_is_reported_not_smoothed_over(tmp_path):
    """
    A phantom symmetric hedge in the book is worse than a known-unhedged one you
    can see and act on.
    """
    fills = iter([{"filled_sz": 0.1, "oid": 1, "avg_price": 60_000.0},
                  {"filled_sz": 0.04, "oid": 2, "avg_price": 60_100.0}])
    executor = _executor(submit_fn=lambda payload: next(fills), dry_run=False,
                         receipts_enabled=True, receipts_dir=tmp_path)
    pair = executor.execute_basis_pair(coin="BTC", sz="0.1", spot_px="60000.0",
                                       perp_px="60100.0")
    assert pair["hedged"] is False
    assert pair["residual_sz"] == pytest.approx(0.06)
    quantities = sorted(float(r["quantity"]) for r in _rows(tmp_path))
    assert quantities == pytest.approx([0.04, 0.1])


def test_a_failed_leg_leaves_the_filled_one_booked(tmp_path):
    """The filled leg is real exposure and must appear in the ledger regardless."""
    fills = iter([{"filled_sz": 0.1, "oid": 1, "avg_price": 60_000.0},
                  {"status": "rejected", "reason": "no liquidity"}])
    executor = _executor(submit_fn=lambda payload: next(fills), dry_run=False,
                         receipts_enabled=True, receipts_dir=tmp_path)
    pair = executor.execute_basis_pair(coin="BTC", sz="0.1", spot_px="60000.0",
                                       perp_px="60100.0")
    assert pair["spot"].status == "FILLED"
    assert pair["perp"].status == "REJECTED"
    assert pair["residual_sz"] == pytest.approx(0.1)
    assert len(_rows(tmp_path)) == 1


def test_the_pair_is_gated_as_a_whole_before_either_leg():
    """
    SUPERSEDES a version asserting the legs were gated INDEPENDENTLY - that was
    the bug. Independent gating lets the gate clamp one leg and not the other,
    which turns a delta-neutral pair into a naked directional position. The pair
    is now priced once, up front, and both legs take the agreed size.
    """
    gate = _Gate()
    _executor(gate=gate).execute_basis_pair(coin="BTC", sz="0.1", spot_px="60000.0",
                                            perp_px="60100.0")
    # First call is the whole pair: 0.1 * (60000 + 60100).
    assert gate.calls[0][1] == pytest.approx(0.1 * (60000.0 + 60100.0))


# ------------------------------------------------------------------- reporting

def test_status_line_says_dry_run_by_default():
    assert "DRY RUN" in _executor().status_line()


def test_status_line_says_live_when_it_is():
    executor = _executor(submit_fn=lambda payload: {}, dry_run=False)
    assert "LIVE" in executor.status_line()


def test_result_serialises():
    payload = _executor().execute_order(coin="BTC", is_buy=True, sz="0.1",
                                        limit_px="60000.0").to_dict()
    assert {"status", "coin", "filled_sz", "cloid"} <= set(payload)


def test_the_key_never_appears_in_a_result():
    result = _executor().execute_order(coin="BTC", is_buy=True, sz="0.1",
                                       limit_px="60000.0")
    assert SYNTHETIC_KEY not in str(result.to_dict())
