"""
Round 18: the dead man's switch.

The protection is the DEADLINE, not the call. A process that hangs, crashes or
loses its network cannot send a cancel - which is precisely when its resting
orders are most dangerous. Arming the exchange to do it unilaterally is the only
version that survives the failure it protects against.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.order_executor import OrderExecutor
from execution.risk_manager import STRATEGY_BASIS_HARVEST, RiskDecision
from execution.wallet_manager import WalletManager

SYNTHETIC_KEY = "0x" + "11" * 32


class _Gate:
    def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
        return RiskDecision(approved=True, max_size_usd=1_000_000.0, strategy=strategy,
                            reason="ok")


def _executor(submit_fn=None, dry_run=True, wallet=True):
    return OrderExecutor(
        wallet=WalletManager(private_key=SYNTHETIC_KEY) if wallet else None,
        risk_manager=_Gate(), strategy=STRATEGY_BASIS_HARVEST,
        submit_fn=submit_fn, asset_index={"BTC": 0}, dry_run=dry_run)


# ----------------------------------------------------------- action shape

def test_the_action_matches_the_documented_payload():
    assert WalletManager.schedule_cancel_action(1700000060000) == {
        "type": "scheduleCancel", "time": 1700000060000}


def test_the_time_is_coerced_to_an_int():
    assert WalletManager.schedule_cancel_action(1700000060000.7)["time"] == 1700000060000


def test_zero_disarms():
    assert WalletManager.schedule_cancel_action(0)["time"] == 0


# --------------------------------------------------------- hashing & signing

def test_the_action_hashes_deterministically():
    action = WalletManager.schedule_cancel_action(1700000060000)
    assert WalletManager.action_hash(action, 1) == WalletManager.action_hash(action, 1)


def test_a_different_deadline_hashes_differently():
    """The deadline is the whole payload; it must reach the signature."""
    first = WalletManager.action_hash(WalletManager.schedule_cancel_action(1_000), 1)
    second = WalletManager.action_hash(WalletManager.schedule_cancel_action(2_000), 1)
    assert first != second


def test_it_signs_offline():
    wallet = WalletManager(private_key=SYNTHETIC_KEY)
    signed = wallet.sign_action(WalletManager.schedule_cancel_action(1700000060000),
                                nonce=1)
    assert set(signed.signature) == {"r", "s", "v"}
    assert signed.action["type"] == "scheduleCancel"


def test_a_schedule_cancel_signature_differs_from_an_order():
    """Two different actions must never share a signature at the same nonce."""
    wallet = WalletManager(private_key=SYNTHETIC_KEY)
    cancel = wallet.sign_action(WalletManager.schedule_cancel_action(1_000), nonce=1)
    order = wallet.sign_action(
        WalletManager.order_action(0, True, "1.0", "1.0"), nonce=1)
    assert cancel.signature != order.signature


def test_testnet_and_mainnet_differ_here_too():
    action = WalletManager.schedule_cancel_action(1_000)
    testnet = WalletManager(SYNTHETIC_KEY, testnet=True).sign_action(action, nonce=1)
    mainnet = WalletManager(SYNTHETIC_KEY, testnet=False).sign_action(action, nonce=1)
    assert testnet.signature != mainnet.signature


# ------------------------------------------------------------------ arming

def test_arming_computes_an_absolute_deadline():
    result = _executor().arm_dead_man_switch(ttl_seconds=60, now_ms=1_700_000_000_000)
    assert result.payload["action"]["time"] == 1_700_000_060_000


def test_arming_is_dry_run_by_default():
    calls = []
    result = _executor(submit_fn=lambda p: calls.append(p)).arm_dead_man_switch(60)
    assert result.status == "DRY_RUN"
    assert calls == []


def test_arming_submits_when_live():
    calls = []
    result = _executor(submit_fn=lambda p: calls.append(p) or {},
                       dry_run=False).arm_dead_man_switch(60)
    assert result.status == "SUBMITTED"
    assert len(calls) == 1
    assert calls[0]["action"]["type"] == "scheduleCancel"


def test_an_armed_switch_is_reported_armed():
    executor = _executor(submit_fn=lambda p: {}, dry_run=False)
    executor.arm_dead_man_switch(60)
    assert executor.dead_man_armed is True


def test_a_deadline_in_the_past_is_not_armed():
    """`dead_man_armed` asks whether protection is LIVE, not whether it was set."""
    executor = _executor(submit_fn=lambda p: {}, dry_run=False)
    executor.arm_dead_man_switch(60, now_ms=1_000)     # long expired
    assert executor.dead_man_armed is False


def test_disarming_sends_zero_and_clears_the_flag():
    executor = _executor(submit_fn=lambda p: {}, dry_run=False)
    executor.arm_dead_man_switch(60)
    result = executor.arm_dead_man_switch(0)
    assert result.payload["action"]["time"] == 0
    assert executor.dead_man_armed is False


def test_re_arming_replaces_the_previous_deadline():
    executor = _executor(submit_fn=lambda p: {}, dry_run=False)
    executor.arm_dead_man_switch(60, now_ms=1_700_000_000_000)
    first = executor.dead_man_deadline_ms
    executor.arm_dead_man_switch(120, now_ms=1_700_000_000_000)
    assert executor.dead_man_deadline_ms > first


# ----------------------------------------------------------------- failures

def test_a_failed_submit_does_NOT_record_the_switch_as_armed():
    """
    An unconfirmed arm is not an armed switch. Recording it would leave the
    caller believing it has protection it does not have - which is worse than
    never arming, because it stops them looking.
    """
    def boom(payload):
        raise ConnectionError("socket closed")

    executor = _executor(submit_fn=boom, dry_run=False)
    result = executor.arm_dead_man_switch(60)
    assert result.status == "ERROR"
    assert "NOT ARMED" in result.reason
    assert executor.dead_man_armed is False


def test_no_wallet_reports_an_error_rather_than_pretending():
    executor = _executor(wallet=False)
    result = executor.arm_dead_man_switch(60)
    assert result.status == "ERROR"
    assert executor.dead_man_armed is False


def test_the_signed_payload_carries_no_secret():
    result = _executor().arm_dead_man_switch(60)
    assert SYNTHETIC_KEY not in str(result.payload)


def test_arming_does_not_pass_through_the_order_gate():
    """
    Cancelling is a RISK-REDUCING action. Gating it behind a bankroll check would
    mean an account out of capital could not protect itself - exactly backwards.
    """
    assert not getattr(OrderExecutor.arm_dead_man_switch, "__wrapped_by_tax_gate__", False)
