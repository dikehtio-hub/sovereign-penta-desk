"""
Round 19: the live pre-flight harness.

The first real order should be placed by a person reading the payload. These
tests pin what that person is shown, and pin the four independent things that
have to be switched off before anything can actually be sent.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.asset_resolver import AssetResolver
from execution.preflight import (
    LIVE_CONFIRMATION_PHRASE,
    build_preflight,
    confirm_live,
    render_preflight,
)
from execution.risk_manager import RiskDecision
from execution.wallet_manager import WalletManager

SYNTHETIC_KEY = "0x" + "11" * 32
UNIVERSE = [{"name": "BTC", "szDecimals": 5},
            {"name": "ETH", "szDecimals": 4},
            {"name": "SOL", "szDecimals": 2}]


class _Gate:
    def __init__(self, approved=True, max_size_usd=1_000_000.0, reason="ok"):
        self.approved = approved
        self.max_size_usd = max_size_usd
        self.reason = reason
        self.calls = []

    def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
        self.calls.append({"strategy": strategy, "size_usd": size_usd})
        return RiskDecision(approved=self.approved, max_size_usd=self.max_size_usd,
                            strategy=strategy, reason=self.reason)


def _preflight(**kwargs):
    kwargs.setdefault("coin", "ETH")
    kwargs.setdefault("sz", "0.05")
    kwargs.setdefault("px", "3000.0")
    kwargs.setdefault("wallet", WalletManager(private_key=SYNTHETIC_KEY))
    kwargs.setdefault("risk_manager", _Gate())
    kwargs.setdefault("resolver", AssetResolver(universe=UNIVERSE))
    return build_preflight(**kwargs)


# ------------------------------------------------------------ construction

def test_it_builds_a_signed_payload():
    report = _preflight()
    assert report["blocked"] is None
    assert report["result"]["payload"]["action"]["type"] == "order"


def test_the_resolved_index_reaches_the_payload():
    """The index is what the signature names; a wrong one is a silent misfire."""
    assert _preflight(coin="SOL")["result"]["payload"]["action"]["orders"][0]["a"] == 2


def test_the_index_is_reported_separately_so_a_human_can_check_it():
    assert _preflight(coin="ETH")["asset_index"] == 1


def test_the_price_is_signed_exactly_as_typed():
    """
    Not re-formatted. `3000.0` and `3000` hash differently, so a helpful tidy-up
    here would sign an order the operator never read.
    """
    assert _preflight(px="3000.0")["result"]["payload"]["action"]["orders"][0]["p"] == "3000.0"


def test_a_sell_is_marked_as_a_sell():
    report = _preflight(is_buy=False)
    assert report["side"] == "SELL"
    assert report["result"]["payload"]["action"]["orders"][0]["b"] is False


def test_the_connection_id_is_reported():
    """It is what the signature commits to, so it can be re-derived independently."""
    report = _preflight()
    assert report["connection_id"].startswith("0x")
    assert len(report["connection_id"]) == 66


def test_the_connection_id_matches_an_independent_derivation():
    report = _preflight()
    payload = report["result"]["payload"]
    expected = "0x" + WalletManager.action_hash(
        payload["action"], report["result"]["nonce"],
        payload.get("vaultAddress")).hex()
    assert report["connection_id"] == expected


def test_a_cloid_is_attached():
    assert _preflight()["result"]["cloid"].startswith("0x")


# ------------------------------------------------------------ the gate is real

def test_the_order_passes_through_the_risk_gate():
    """A pre-flight that skipped the gate would be testing a different system."""
    gate = _Gate()
    _preflight(risk_manager=gate)
    assert len(gate.calls) == 1


def test_the_gate_clamps_the_size_that_gets_signed():
    """The signed size is the APPROVED one, not the requested one."""
    report = _preflight(sz="1.0", px="3000.0", risk_manager=_Gate(max_size_usd=150.0))
    assert float(report["result"]["payload"]["action"]["orders"][0]["s"]) == pytest.approx(0.05)


def test_a_rejected_order_is_blocked_and_nothing_is_signed():
    report = _preflight(risk_manager=_Gate(approved=False, max_size_usd=0.0,
                                           reason="bucket exhausted"))
    assert report["blocked"] is not None
    assert report["result"] is None


def test_the_notional_reaching_the_gate_is_size_times_price():
    gate = _Gate()
    _preflight(sz="0.05", px="3000.0", risk_manager=gate)
    assert gate.calls[0]["size_usd"] == pytest.approx(150.0)


# ------------------------------------------------------------ safety defaults

def test_dry_run_is_the_default():
    report = _preflight()
    assert report["dry_run"] is True
    assert report["result"]["status"] == "DRY_RUN"


def test_testnet_is_the_default():
    assert _preflight()["network"] == "testnet"


def test_a_dry_run_submits_nothing_even_with_a_submitter_attached():
    calls = []
    report = _preflight(submit_fn=lambda payload: calls.append(payload) or {})
    assert calls == []
    assert report["result"]["status"] == "DRY_RUN"


def test_live_needs_both_the_flag_and_a_submitter():
    """
    Two independent switches: the payload only reaches the submitter when
    dry_run is off AND a submitter exists.

    Note the terminal status of an ORDER is never "SUBMITTED" - `_submit`
    interprets the reply and returns FILLED / PARTIAL / REJECTED. (Only
    `arm_dead_man_switch`, which has no fill to interpret, reports SUBMITTED.)
    So the thing to assert is that the transport was reached.
    """
    calls = []

    def _exchange(payload):
        calls.append(payload)
        return {"status": "ok", "filled_sz": 0.05, "avg_price": 3000.0, "oid": 42}

    report = _preflight(dry_run=False, submit_fn=_exchange)
    assert len(calls) == 1
    assert report["result"]["status"] == "FILLED"
    assert report["result"]["oid"] == 42


def test_a_live_order_that_does_not_fill_is_reported_rejected_not_sent():
    """An empty reply is not a success. No fill means no fill."""
    report = _preflight(dry_run=False, submit_fn=lambda payload: {})
    assert report["result"]["status"] == "REJECTED"


def test_a_transport_failure_reports_the_order_state_as_unknown():
    """
    The order may well be resting. Calling it a rejection would invite a retry
    that duplicates it.
    """
    def _boom(payload):
        raise ConnectionError("socket closed")

    result = _preflight(dry_run=False, submit_fn=_boom)["result"]
    assert result["status"] == "ERROR"
    assert "UNKNOWN" in result["reason"]
    assert result["cloid"] in result["reason"]      # names what to reconcile on


def test_no_submitter_cannot_send_even_when_live():
    """dry_run=False alone is inert: there is no transport for it to use."""
    assert _preflight(dry_run=False)["result"]["status"] == "DRY_RUN"


def test_mainnet_signs_differently_from_testnet():
    """
    The domain differs, so a testnet-signed action is REJECTED on mainnet rather
    than executed. That is what makes the testnet default a real safety net and
    not just a label.
    """
    testnet = _preflight(wallet=WalletManager(SYNTHETIC_KEY, testnet=True))
    mainnet = _preflight(wallet=WalletManager(SYNTHETIC_KEY, testnet=False))
    assert (testnet["result"]["payload"]["signature"]
            != mainnet["result"]["payload"]["signature"])


# --------------------------------------------------- the confirmation phrase

def test_a_dry_run_needs_no_confirmation():
    assert confirm_live(network_is_mainnet=True, dry_run=True) is True


def test_a_live_testnet_order_needs_no_confirmation():
    assert confirm_live(network_is_mainnet=False, dry_run=False) is True


def test_a_live_mainnet_order_without_the_phrase_is_refused():
    assert confirm_live(network_is_mainnet=True, dry_run=False) is False


def test_a_wrong_phrase_is_refused():
    assert confirm_live(True, False, typed="send it live") is False
    assert confirm_live(True, False, typed="yes") is False


def test_the_exact_phrase_is_accepted():
    assert confirm_live(True, False, typed=LIVE_CONFIRMATION_PHRASE) is True


def test_surrounding_whitespace_is_tolerated():
    assert confirm_live(True, False, typed=f"  {LIVE_CONFIRMATION_PHRASE}  ") is True


# --------------------------------------------------------------- refusals

def test_no_key_blocks_before_anything_is_signed():
    report = _preflight(wallet=WalletManager(private_key=None))
    assert "no agent key" in report["blocked"]
    assert report["result"] is None


def test_an_unknown_coin_is_blocked_at_resolution():
    report = _preflight(coin="NOTACOIN")
    assert "asset resolution failed" in report["blocked"]
    assert report["result"] is None


def test_a_stale_universe_blocks_the_pre_flight():
    """A stale index signs a valid order on whatever market now holds that slot."""
    import time as _time
    stale = AssetResolver(universe=UNIVERSE, max_age_seconds=1.0,
                          loaded_at=_time.time() - 3600)
    report = _preflight(resolver=stale)
    assert report["blocked"] is not None
    assert "stale" in report["blocked"].lower()


def test_nothing_is_signed_when_the_pre_flight_is_blocked():
    """Blocked means blocked - not signed-but-unsent."""
    for report in (_preflight(wallet=WalletManager(private_key=None)),
                   _preflight(coin="NOTACOIN")):
        assert report["result"] is None
        assert "connection_id" not in report


# ---------------------------------------------------------------- rendering

def test_the_rendered_page_shows_the_payload():
    text = render_preflight(_preflight())
    assert "SIGNED PAYLOAD" in text
    assert '"type": "order"' in text


def test_the_rendered_page_shows_the_resolved_index():
    assert "ETH -> 1" in render_preflight(_preflight(coin="ETH"))


def test_the_rendered_page_shows_the_connection_id():
    assert "connectionId" in render_preflight(_preflight())


def test_mainnet_is_called_out_in_the_render():
    text = render_preflight(_preflight(testnet=False,
                                       wallet=WalletManager(SYNTHETIC_KEY,
                                                            testnet=False)))
    assert "REAL MONEY" in text


def test_a_dry_run_says_nothing_was_submitted():
    assert "Nothing was submitted" in render_preflight(_preflight())


def test_a_blocked_report_renders_the_reason_and_no_payload():
    text = render_preflight(_preflight(coin="NOTACOIN"))
    assert "BLOCKED" in text
    assert "SIGNED PAYLOAD" not in text


def test_the_render_never_contains_the_private_key():
    """The page is meant to be read aloud, screenshotted and pasted."""
    assert SYNTHETIC_KEY not in render_preflight(_preflight())


def test_the_render_survives_an_empty_report():
    """It is an operator-facing display; it must not throw on a partial report."""
    assert "PRE-FLIGHT" in render_preflight({})
