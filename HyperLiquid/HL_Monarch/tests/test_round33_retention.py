"""
Round 33 Target 1: retention must outlast the holding period it evaluates.

THE DEFECT. SNAPSHOT_RETENTION_HOURS was 72 while BASIS_MIN_HOLD_DAYS was 7 -
the strategy's holding period was 2.3x the data retained to evaluate it, so
`net_apr_after_spread`, which amortises execution cost over 7 days and is what
turns a 3bp spread into ~6% annualised instead of ~44%, rested on a window no
data in the repo could test. The same 72 hours made the fade re-benchmark's
7-day pre-registration unreachable by construction: events older than three
days had no price series to measure against, so the sample could grow forever
and never qualify.

These tests pin the relationship rather than the number, so a future change to
the hold cannot silently reopen the gap.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analytics.wick_benchmark import (REOPEN_CONFIDENCE, REOPEN_RATIO, reopening_gate,
                                      retention_covers_window)
from config.settings import (BASIS_MIN_HOLD_DAYS, SNAPSHOT_RETENTION_HOURS,
                             TRADE_RETENTION_HOURS)
from strategies.whale_sweeper import EvidenceGate

META = Path(__file__).resolve().parents[1] / "data" / "experiments" / "passive_fade_rebenchmark.meta.json"


def _benchmark(n=800, coins=25, share=0.10, confidence=0.95):
    return {"horizons": {"30m": {
        "signal": {"ratio": 1.40, "n": n}, "control": {"ratio": 1.00},
        "coins_measured": coins, "top_coin_share": share, "cluster_p_ge_1": confidence}}}


def test_snapshot_retention_outlasts_the_basis_hold():
    """The relationship, not the number: at least a clear day beyond the hold."""
    assert SNAPSHOT_RETENTION_HOURS >= BASIS_MIN_HOLD_DAYS * 24.0 + 24.0


def test_trade_retention_matches_snapshot_retention():
    """Events and the price series that scores them must age out together."""
    assert TRADE_RETENTION_HOURS >= SNAPSHOT_RETENTION_HOURS


def test_retention_now_covers_the_seven_day_registration_window():
    check = retention_covers_window(7.0)
    assert check["covers"], check["detail"]
    assert check["retention_hours"] == pytest.approx(SNAPSHOT_RETENTION_HOURS)
    assert check["needed_hours"] == pytest.approx(168.5)


def test_a_window_longer_than_retention_is_reported_as_uncoverable():
    check = retention_covers_window(30.0)
    assert not check["covers"]
    assert "age out" in check["detail"]


def test_the_reopening_gate_checks_retention_before_the_sample():
    """
    A SAMPLE_ADEQUATE verdict on a window the database cannot hold would be the
    most misleading status the gate could return, so retention is asked first
    and overrides.
    """
    out = reopening_gate(_benchmark(), window_days=7.0)
    assert out["retention"]["covers"]
    assert out["status"] == "SAMPLE_ADEQUATE"
    blocked = reopening_gate(_benchmark(), window_days=30.0)
    assert blocked["status"] == "RETENTION_TOO_SHORT"
    assert not blocked["eligible"]


def test_the_sample_gate_still_narrows_on_a_narrow_sample():
    out = reopening_gate(_benchmark(n=300), window_days=7.0)
    assert out["status"] == "SAMPLE_TOO_NARROW"
    assert out["retention"]["covers"]


def test_the_pre_registered_bar_is_untouched():
    """
    The registration file gained a `data_retention` record and NOTHING else.
    Amending the bar would be amending the experiment; recording a precondition
    is not.
    """
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta["sample_requirements"]["min_events"] == 500
    assert meta["sample_requirements"]["min_coins"] == 20
    assert meta["sample_requirements"]["max_single_coin_share"] == pytest.approx(0.20)
    assert "P(ratio >= 1.25) > 0.90" in meta["reopening_bar"]["rule"]
    assert meta["data_retention"]["required_snapshot_hours"] == pytest.approx(168.5)
    assert "192" in meta["data_retention"]["fix"]
    bar = EvidenceGate().bar
    assert bar["min_events"] == 500 and bar["min_coins"] == 20
    assert bar["ratio"] == REOPEN_RATIO and bar["confidence"] == REOPEN_CONFIDENCE


def test_raising_retention_does_not_claim_to_recreate_history():
    """The registration says so in words; a reader must not be told 'today'."""
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert "does not recreate" in meta["data_retention"]["note"]
