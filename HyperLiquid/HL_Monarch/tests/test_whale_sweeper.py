"""
Round 31: HL_Shark whale cascade sweeper, and the gate that holds it shut.

WHAT THESE TESTS DEFEND IS AN ABSENCE.

The strategy this module describes was already built, traded on paper, measured
against a pre-registered bar and retired: MFE/MAE 0.513 against a random-entry
control of 1.092 (n=466, t=-10.52, MAE > MFE in 72.7% of events). A ratio below
the control means the signal was worse than entering at random. Rounds 9-15 of
execution refinement never moved it, because no geometry fixes a sign error.

So the thing worth testing is not that the sweeper trades well. It is that the
sweeper DOES NOT TRADE, that every route to trading is closed, and that each
refusal states the measurement rather than a bare False. A test suite that
confirmed the zone maths and left the gate untested would be testing the part
that was never broken.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from strategies.whale_sweeper import (
    REOPEN_CONFIDENCE,
    REOPEN_RATIO,
    RETIREMENT_CONTROL,
    RETIREMENT_RATIO,
    STRATEGY_WHALE_SWEEP,
    EvidenceGate,
    SweeperDisabled,
    WhaleSweeper,
    format_status,
    rank_clusters,
    wick_rebound_zone,
)
from strategies.funding_harvester import BucketGate


class FakeDecision:
    def __init__(self, approved=True, approved_notional=1_000.0, reason="ok"):
        self.approved = approved
        self.approved_notional = approved_notional
        self.reason = reason
        self.safe_bankroll = 50_000.0
        self.strategy_budget = 10_000.0
        self.strategy_remaining = 8_000.0
        self.detail = {}


class FakeHook:
    config = {"tax_rates": {"short_term_capital_gains": 0.24,
                            "state_tax_rate": 0.0637, "safety_buffer_pct": 0.02}}

    def __init__(self, decision=None):
        self._decision = decision or FakeDecision()
        self.calls = []

    def check_order(self, desired_notional, **kwargs):
        self.calls.append({"desired_notional": desired_notional, **kwargs})
        return self._decision


def _benchmark(ratio=1.40, n=800, coins=25, share=0.10, confidence=0.95,
               control=1.00):
    """A benchmark result shaped like `wick_benchmark.benchmark()` output."""
    return {"horizons": {"30m": {
        "signal": {"ratio": ratio, "n": n},
        "control": {"ratio": control},
        "coins_measured": coins, "top_coin_share": share,
        "cluster_p_ge_1": confidence}}}


def _sweeper(hook=None, enabled=False, **kwargs):
    hook = hook or FakeHook()
    return WhaleSweeper(gate=BucketGate(hook=hook, strategy=STRATEGY_WHALE_SWEEP),
                        execution_enabled=enabled, **kwargs)


# ---------------------------------------------------------------------------
# The gate is shut, and every route through it is closed
# ---------------------------------------------------------------------------

def test_the_sweeper_does_not_trade_by_default():
    """
    THE HEADLINE. A strategy measured at half of random is OFF, and the default
    construction must not be tradeable no matter how good the cluster looks.
    """
    verdict = _sweeper().evaluate("BTC", 58_000.0, 60_000.0,
                                  cluster_notional=25_000_000.0)
    assert not verdict.tradeable
    assert verdict.zone is not None          # the geometry still computes
    assert any("0.513" in reason for reason in verdict.reasons)


def test_a_perfect_benchmark_still_does_not_trade_while_the_flag_is_off():
    """
    Two independent locks. Clearing the evidence bar is necessary and not
    sufficient - somebody still has to decide to turn the strategy on.
    """
    verdict = _sweeper().evaluate("BTC", 58_000.0, 60_000.0,
                                  benchmark_result=_benchmark())
    assert not verdict.tradeable
    assert any("WHALE_SWEEP_EXECUTION_ENABLED is False" in r for r in verdict.reasons)


def test_the_flag_alone_does_not_open_the_path_without_a_measurement():
    """The mirror of the test above: flipping the flag is also not sufficient."""
    verdict = _sweeper(enabled=True).evaluate("BTC", 58_000.0, 60_000.0)
    assert not verdict.tradeable
    assert any("NO_MEASUREMENT" in r for r in verdict.reasons)
    assert any("retirement stands" in r for r in verdict.reasons)


def test_both_locks_open_together_and_only_together():
    """The path IS wired. It is held shut by evidence, not by being unbuilt."""
    verdict = _sweeper(enabled=True).evaluate("BTC", 58_000.0, 60_000.0,
                                              benchmark_result=_benchmark())
    assert verdict.tradeable, verdict.reasons
    assert verdict.evidence.status == "BAR_CLEARED"


def test_placing_an_untradeable_verdict_raises_rather_than_returning_none():
    """
    A refusal a caller can ignore by not checking a return value is not a
    refusal. Same reason RiskBreachException exists for the order executor.
    """
    sweeper = _sweeper()
    verdict = sweeper.evaluate("BTC", 58_000.0, 60_000.0)
    with pytest.raises(SweeperDisabled):
        sweeper.place(verdict)


def test_a_cleared_verdict_places_at_the_bucket_authorised_size():
    hook = FakeHook(FakeDecision(approved_notional=750.0))
    sweeper = _sweeper(hook=hook, enabled=True)
    order = sweeper.place(sweeper.evaluate("BTC", 58_000.0, 60_000.0,
                                           benchmark_result=_benchmark()))
    assert order["notional_usd"] == pytest.approx(750.0)
    assert order["strategy"] == "hl_whale_sweep"
    assert order["side"] == "BUY"


# ---------------------------------------------------------------------------
# The pre-registered bar
# ---------------------------------------------------------------------------

def test_the_registration_on_disk_is_the_bar_not_a_private_copy():
    """
    Amending the pre-registration must amend the gate. A gate carrying its own
    copy lets the two drift, and the version that matters becomes whichever one
    nobody is reading.
    """
    gate = EvidenceGate()
    assert gate.registration, "the pre-registration file must be readable"
    assert gate.bar["min_events"] == 500
    assert gate.bar["min_coins"] == 20
    assert gate.bar["max_single_coin_share"] == pytest.approx(0.20)
    assert gate.bar["ratio"] == REOPEN_RATIO
    assert gate.bar["confidence"] == REOPEN_CONFIDENCE


def test_an_amended_registration_moves_the_bar(tmp_path):
    path = tmp_path / "reg.json"
    path.write_text(json.dumps({"experiment": "x",
                                "sample_requirements": {"min_events": 9_000,
                                                        "min_coins": 40,
                                                        "max_single_coin_share": 0.05}}),
                    encoding="utf-8")
    gate = EvidenceGate(experiment_path=path)
    assert gate.bar["min_events"] == 9_000
    assert gate.check(_benchmark(n=800, coins=25)).status == "SAMPLE_TOO_NARROW"


def test_the_state_at_registration_would_not_reopen_the_strategy():
    """
    Applying the bar to the sample that produced the retirement must FAIL it -
    492 events, 15 coins, one coin at 43%. That is the point of the bar: the
    retirement itself rested on a sample too narrow to reopen on.
    """
    gate = EvidenceGate()
    state = gate.registration["state_at_registration"]
    decision = gate.check({"horizons": {"30m": {
        "signal": {"ratio": state["ratio_30m"], "n": state["events"]},
        "control": {"ratio": state["control_30m"]},
        "coins_measured": state["coins"],
        "top_coin_share": state["top_coin_share"],
        "cluster_p_ge_1": state["cluster_p_ge_1_by_horizon"]["30m"]}}})
    assert not decision.eligible
    assert decision.status == "SAMPLE_TOO_NARROW"
    assert "492" in decision.detail and "15 coins" in decision.detail


def test_every_way_the_sample_can_be_too_narrow_is_caught():
    gate = EvidenceGate()
    assert gate.check(_benchmark(n=300)).status == "SAMPLE_TOO_NARROW"
    assert gate.check(_benchmark(coins=12)).status == "SAMPLE_TOO_NARROW"
    assert gate.check(_benchmark(share=0.45)).status == "SAMPLE_TOO_NARROW"


def test_a_broad_sample_without_a_cluster_bootstrap_is_still_refused():
    """
    An EVENT-level bootstrap is invalid here: 30-minute forward windows on the
    same coin overlap almost completely, so 466 events are nowhere near 466
    independent observations. It reported 0/20,000 where resampling COINS
    reported 0.024 on identical data. Missing the cluster figure is not a
    formatting gap, it is the absence of the only valid statistic.
    """
    decision = EvidenceGate().check(_benchmark(confidence=None))
    assert not decision.eligible
    assert decision.status == "NO_CLUSTER_BOOTSTRAP"
    assert "overlap" in decision.detail


def test_confidence_below_the_bar_is_refused_and_states_the_shortfall():
    decision = EvidenceGate().check(_benchmark(confidence=0.85))
    assert not decision.eligible
    assert decision.status == "BAR_NOT_CLEARED"
    assert "0.850" in decision.detail and "0.90" in decision.detail


def test_the_bar_is_exclusive_not_inclusive():
    """The registration says P > 0.90, so exactly 0.90 does not clear."""
    assert not EvidenceGate().check(_benchmark(confidence=0.90)).eligible
    assert EvidenceGate().check(_benchmark(confidence=0.901)).eligible


def test_an_unreadable_registration_fails_closed(tmp_path):
    """Unverifiable is not the same as satisfied."""
    gate = EvidenceGate(experiment_path=tmp_path / "missing.json")
    decision = gate.check(_benchmark())
    assert not decision.eligible
    assert decision.status == "NO_REGISTRATION"


def test_an_empty_benchmark_fails_closed():
    assert EvidenceGate().check({"horizons": {}}).status == "NO_DATA"
    assert not EvidenceGate().check(None).eligible


# ---------------------------------------------------------------------------
# Zone geometry - measured, never trusted
# ---------------------------------------------------------------------------

def test_a_cluster_below_the_mark_produces_a_buy_beyond_it():
    """Rest BEYOND the cluster: a cascade that stops at it never fills."""
    zone = wick_rebound_zone("BTC", 58_000.0, 60_000.0)
    assert zone.side == "BUY"
    assert zone.entry_price < 58_000.0
    assert zone.stop_price < zone.entry_price
    assert zone.take_profit > zone.entry_price


def test_a_cluster_above_the_mark_mirrors_the_geometry():
    zone = wick_rebound_zone("BTC", 62_000.0, 60_000.0)
    assert zone.side == "SELL"
    assert zone.entry_price > 62_000.0
    assert zone.stop_price > zone.entry_price
    assert zone.take_profit < zone.entry_price


def test_degenerate_prices_produce_no_zone():
    assert wick_rebound_zone("BTC", 0.0, 60_000.0) is None
    assert wick_rebound_zone("BTC", 58_000.0, 0.0) is None


def test_reward_risk_is_computed_but_proves_nothing():
    """
    The geometry was never the problem. Rounds 9-15 rebuilt exactly this and the
    MFE/MAE result did not move, so a healthy reward:risk here is not evidence
    about whether to trade - and the gate ignores it entirely.
    """
    zone = wick_rebound_zone("BTC", 58_000.0, 60_000.0)
    assert zone.reward_risk > 1.0
    verdict = _sweeper().evaluate("BTC", 58_000.0, 60_000.0)
    assert not verdict.tradeable


def test_clusters_are_ranked_by_size_and_capped_by_distance():
    clusters = [{"price": 59_000.0, "notional": 1_000_000.0},
                {"price": 58_000.0, "notional": 9_000_000.0},
                {"price": 30_000.0, "notional": 99_000_000.0}]   # 50% away
    ranked = rank_clusters(clusters, 60_000.0)
    assert [c["price"] for c in ranked] == [58_000.0, 59_000.0]
    assert all(c["distance_pct"] <= 5.0 for c in ranked)


def test_small_clusters_can_be_filtered_out():
    clusters = [{"price": 59_000.0, "notional": 10.0},
                {"price": 58_500.0, "notional": 5_000_000.0}]
    assert len(rank_clusters(clusters, 60_000.0, min_notional=1_000.0)) == 1


# ---------------------------------------------------------------------------
# Passive accumulation - the only route back to trading
# ---------------------------------------------------------------------------

def test_observing_records_a_zone_without_trading_it():
    """
    The registration's status line is explicit: sweeps accumulate with execution
    disabled, and that sample is the only route back.
    """
    sweeper = _sweeper()
    assert sweeper.observe("BTC", 58_000.0, 60_000.0, timestamp=1.0) is not None
    sweeper.observe("ETH", 2_900.0, 3_000.0, timestamp=2.0)
    assert len(sweeper.observed) == 2
    assert sweeper.observed[0]["coin"] == "BTC"


def test_the_bankroll_is_not_consulted_while_the_evidence_gate_is_shut():
    """
    A bucket approval printed next to a retired strategy invites exactly the
    misreading this module exists to prevent - it reads as partial success.
    """
    hook = FakeHook()
    sweeper = _sweeper(hook=hook)
    verdict = sweeper.evaluate("BTC", 58_000.0, 60_000.0)
    assert verdict.gate is None
    assert hook.calls == []


def test_the_bucket_still_binds_once_the_evidence_clears():
    hook = FakeHook(FakeDecision(approved=False, approved_notional=0.0,
                                 reason="bucket exhausted"))
    verdict = _sweeper(hook=hook, enabled=True).evaluate(
        "BTC", 58_000.0, 60_000.0, benchmark_result=_benchmark())
    assert not verdict.tradeable
    assert any("hl_whale_sweep" in reason for reason in verdict.reasons)


def test_the_sweep_bucket_is_its_own_and_not_the_retired_fade_bucket():
    hook = FakeHook()
    _sweeper(hook=hook, enabled=True).evaluate("BTC", 58_000.0, 60_000.0,
                                               benchmark_result=_benchmark())
    assert hook.calls[0]["strategy"] == "hl_whale_sweep"
    assert hook.calls[0]["strategy"] != "hl_liquidation_fade"


def test_scan_prices_every_ranked_cluster():
    verdicts = _sweeper().scan([{"price": 58_000.0, "notional": 5_000_000.0},
                                {"price": 59_000.0, "notional": 2_000_000.0}],
                               60_000.0, "BTC")
    assert len(verdicts) == 2
    assert not any(v.tradeable for v in verdicts)
    assert verdicts[0].as_record()["zone"]["side"] == "BUY"


def test_the_status_report_states_the_measurement_and_the_bar():
    """
    An operator reading "disabled" must be able to see WHY without going to look
    for it, or the flag becomes something to flip out of curiosity.
    """
    text = format_status(_sweeper())
    assert "%.3f" % RETIREMENT_RATIO in text
    assert "%.3f" % RETIREMENT_CONTROL in text
    assert "MOMENTUM" in text
    assert "CLUSTER bootstrap" in text
    assert "DISABLED" in text
