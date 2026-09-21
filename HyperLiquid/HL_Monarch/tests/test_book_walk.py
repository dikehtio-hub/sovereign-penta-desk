"""
Section 101 WP3, the arithmetic: what a basis round trip costs at a size.

Hand-built books, so every expected number below can be checked with a pencil.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics import book_walk as bw


def book(bids, asks):
    side = lambda lv: [{"px": str(p), "sz": str(s)} for p, s in lv]          # noqa: E731
    return {"levels": [side(bids), side(asks)]}


# mid 100. Each side: $1,000 at the touch, then $4,000 one level out.
DEEP = book(bids=[(99.9, 10.01001), (99.0, 40.40404)], asks=[(100.1, 9.99001), (101.0, 39.60396)])


def test_inside_the_top_level_the_cost_is_exactly_the_touch_spread():
    bids, asks = bw.parse_book(DEEP)
    assert bw.mid_price(bids, asks) == pytest.approx(100.0)
    assert bw.touch_spread_bps(bids, asks) == pytest.approx(20.0)
    assert bw.walk_slippage_bps(asks, 100.0, 500) == pytest.approx(10.0), "half the spread, one way"
    assert bw.leg_round_trip_bps(bids, asks, 500) == pytest.approx(20.0), "in and out = the whole spread"


def test_walking_past_the_touch_costs_the_vwap_not_the_touch():
    _, asks = bw.parse_book(DEEP)
    # $2,000: $1,000 at 100.1 and $1,000 at 101.0 -> qty 9.99001 + 9.90099, vwap 100.5480
    qty = 1000 / 100.1 + 1000 / 101.0
    assert bw.walk_slippage_bps(asks, 100.0, 2000) == pytest.approx((2000 / qty - 100.0) / 100.0 * 1e4)
    assert bw.walk_slippage_bps(asks, 100.0, 2000) > 5 * bw.walk_slippage_bps(asks, 100.0, 500)


def test_a_size_the_visible_book_cannot_absorb_is_none_never_a_number():
    bids, asks = bw.parse_book(DEEP)
    assert bw.visible_depth_usd(asks) == pytest.approx(5000.0, rel=1e-4)
    assert bw.walk_slippage_bps(asks, 100.0, 5001) is None
    assert bw.leg_round_trip_bps(bids, asks, 6000) is None
    assert bw.walk_slippage_bps(asks, 100.0, 0) == 0.0


def test_a_basis_round_trip_is_the_sum_of_both_legs_and_none_if_either_cannot_fill():
    thin = book(bids=[(9.99, 50.0)], asks=[(10.01, 50.0)])                  # ~$500 a side, 20 bps wide
    r = bw.basis_round_trip_bps(DEEP, thin, 400)
    assert r["perp"] == pytest.approx(20.0) and r["spot"] == pytest.approx(20.0, rel=1e-3)
    assert r["total"] == pytest.approx(r["perp"] + r["spot"])
    r = bw.basis_round_trip_bps(DEEP, thin, 2500)
    assert r["perp"] is not None and r["spot"] is None and r["total"] is None, "the thin leg decides"


def test_the_thinner_side_is_what_limits_a_round_trip():
    lopsided = book(bids=[(99.9, 1.0)], asks=[(100.1, 1000.0)])
    assert bw.thinner_side_usd(lopsided) == pytest.approx(99.9)


def test_a_one_sided_or_empty_payload_is_an_error_not_a_zero():
    for bad in ({}, {"levels": []}, {"levels": [[], []]}, book(bids=[], asks=[(1.0, 1.0)])):
        with pytest.raises(ValueError):
            bw.parse_book(bad)


def test_percentile_is_nearest_rank_on_sorted_input():
    xs = sorted(range(1, 101))
    assert bw.percentile(xs, 0.5) == 51 and bw.percentile(xs, 0.95) == 96 and bw.percentile(xs, 1.0) == 100
    assert bw.percentile([], 0.5) != bw.percentile([], 0.5), "NaN for no data"
