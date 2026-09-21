"""
Section 99 WP2: the basis policy replay.

Every test drives a SYNTHETIC funding path. The replay was frozen and hashed against
these alone, before it was pointed at the real 180-day store, so that nothing about the
history could leak into how the simulator was written.

The exit rule is the project's real BasisHarvester.should_exit, reached through the
replay's shim - so these tests also fail loudly if that rule ever changes underneath it.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("replay_basis_policy", ROOT / "scripts" / "replay_basis_policy.py")
rp = importlib.util.module_from_spec(_spec)
sys.modules["replay_basis_policy"] = rp          # dataclasses resolves annotations through sys.modules
_spec.loader.exec_module(rp)


def rate(apr_pct: float) -> float:
    return apr_pct / 100.0 / rp.HOURS_PER_YEAR


def path(*segments):
    """path((hours, apr), (hours, apr), ...) -> {hour: hourly rate}, starting at hour 0."""
    out, t = {}, 0
    for hours, a in segments:
        for _ in range(hours):
            out[t] = rate(a)
            t += 1
    return out


FRICTION = rp.ROUND_TRIP_FEE_PCT / 100.0 + 20.0 / 10_000.0


def test_the_exit_rule_is_the_projects_own():
    assert "adverse" in rp.real_should_exit("X", -1.0, 1)
    assert rp.real_should_exit("X", 50.0, 1) is None
    assert rp.real_should_exit("X", None, 500) is None, "an unknown rate is not a reversal"
    assert "stale" in rp.real_should_exit("X", 5.0, 7 * 24)
    assert rp.real_should_exit("X", 5.0, 7 * 24 - 1) is None
    assert rp.real_should_exit("X", 10.95, 10_000) is None, "a position on the venue floor is never stale"


def test_no_look_ahead_the_qualifying_spike_is_never_collected():
    rates = {"X": path((10, 10.0), (1, 1000.0), (20, 10.0))}
    res = rp.simulate(rates, "P0", slots=1)
    (trade,) = res.trades
    assert trade.opened == 10, "decided at the close of the spike hour"
    assert trade.funding == pytest.approx(20 * rate(10.0)), "earns from t+1 only"
    assert res.gross < rate(1000.0), "the spike itself was not earned"


def test_the_slot_cap_holds_and_the_top_ranked_win():
    rates = {"LOW": path((30, 30.0)), "MID": path((30, 60.0)), "TOP": path((30, 90.0))}
    res = rp.simulate(rates, "P0", slots=2)
    assert {t.coin for t in res.trades} == {"MID", "TOP"}
    assert res.occupied <= 2 * res.span


def test_friction_is_charged_once_per_round_trip_including_the_mark_out():
    rates = {"X": path((50, 40.0))}
    res = rp.simulate(rates, "P0", slots=1)
    (trade,) = res.trades
    assert "marked out" in trade.reason
    assert res.costs == pytest.approx(FRICTION)
    assert res.curve[-1] == pytest.approx(49 * rate(40.0) - FRICTION), "hours 1..49 earned, one round trip paid"


def test_adverse_funding_closes_through_the_real_rule():
    rates = {"X": path((5, 40.0), (5, -10.0))}
    res = rp.simulate(rates, "P0", slots=1)
    first = res.trades[0]
    assert first.closed == 5 and "adverse" in first.reason
    assert first.funding == pytest.approx(4 * rate(40.0) + rate(-10.0)), "it pays the negative hour that closed it"


def test_a_position_on_the_floor_is_held_forever_but_a_stale_one_is_cut():
    floor = rp.simulate({"X": path((2, 40.0), (400, 10.95))}, "P0", slots=1)
    assert [("marked out" in t.reason) for t in floor.trades] == [True]
    stale = rp.simulate({"X": path((2, 40.0), (400, 5.0))}, "P0", slots=1)
    assert "stale" in stale.trades[0].reason
    assert stale.trades[0].hours == 7 * 24


def test_candidate_a_refuses_a_moderate_flash_spike_and_a_collapse_that_p0_would_buy():
    flash = {"X": path((30, 10.0), (1, 200.0), (30, 10.0))}
    assert len(rp.simulate(flash, "P0", slots=1).trades) == 1
    assert rp.simulate(flash, "A", slots=1).trades == [], "(23 x 10 + 200) / 24 = 17.9 %: under the gate"
    collapse = {"X": path((24, 100.0), (30, 5.0))}
    a = rp.simulate(collapse, "A", slots=1)
    assert all(t.opened < 24 for t in a.trades), "trailing mean still high, current rate collapsed: no entry"


def test_candidate_a_as_ruled_still_admits_a_large_enough_one_hour_flash():
    """
    PINS A HOLE IN THE RULED GATE, it does not endorse it. The trailing mean INCLUDES the
    current hour, so a single print above ~370 % APR lifts a 10 % base over the 25 % gate
    by itself: (23 x 10 + 900) / 24 = 47.1 %. "The 24 h average is high" is not "this has
    been high for 24 h". Found while freezing the replay; reported to Antigravity rather
    than patched here, because changing the gate is re-specifying Candidate A.
    """
    flash = {"X": path((30, 10.0), (1, 900.0), (30, 10.0))}
    (trade,) = rp.simulate(flash, "A", slots=1).trades
    assert trade.opened == 30 and trade.episode_hours == 1
    assert trade.entry_metric == pytest.approx((23 * 10.0 + 900.0) / 24)


def test_candidate_a_enters_once_persistence_is_proven():
    rates = {"X": path((60, 50.0))}
    (trade,) = rp.simulate(rates, "A", slots=1).trades
    assert trade.opened == rp.TRAIL_MIN_PRESENT - 1, "the first hour with enough trailing history"


def test_d_rotates_only_into_a_much_better_name_and_only_out_of_an_old_position():
    rates = {
        "OLD1": path((30, 60.0), (170, 11.0)),
        "OLD2": path((30, 60.0), (170, 11.0)),
        "NEW": path((60, 11.0), (140, 80.0)),
    }
    a = rp.simulate(rates, "A", slots=2)
    assert "NEW" not in {t.coin for t in a.trades}, "without rotation the slots stay full of decayed names"
    d = rp.simulate(rates, "D", slots=2)
    rotated = [t for t in d.trades if "rotated" in t.reason]
    assert len(rotated) == 1, "one slot rotates; then the gain over the other no longer needs proving twice an hour"
    assert rotated[0].hours >= rp.ROTATE_MIN_AGE_HOURS
    assert "NEW" in {t.coin for t in d.trades}


def test_d_does_not_rotate_a_young_position():
    rates = {"A1": path((100, 30.0)), "A2": path((100, 30.0)), "NEW": path((20, 11.0), (80, 90.0))}
    d = rp.simulate(rates, "D", slots=2, hours=list(range(0, 60)))
    assert not [t for t in d.trades if "rotated" in t.reason and t.hours < rp.ROTATE_MIN_AGE_HOURS]


def test_passive_btc_never_exits_and_pays_exactly_one_round_trip():
    rates = {"BTC": path((10, 11.0), (10, -20.0), (10, 11.0)), "X": path((30, 90.0))}
    res = rp.simulate(rates, "PASSIVE")
    (trade,) = res.trades
    assert trade.coin == "BTC" and "marked out" in trade.reason
    assert res.costs == pytest.approx(FRICTION)
    assert trade.funding == pytest.approx(9 * rate(11.0) + 10 * rate(-20.0) + 10 * rate(11.0))


def test_a_hole_in_a_held_coins_history_neither_pays_nor_closes():
    x = path((40, 40.0))
    for gap in (10, 11, 12):
        del x[gap]
    res = rp.simulate({"X": x}, "P0", slots=1, hours=list(range(0, 40)))
    (trade,) = res.trades
    assert "marked out" in trade.reason
    assert trade.funding == pytest.approx((39 - 3) * rate(40.0))


def test_net_apr_is_on_all_slot_capital_idle_included():
    rates = {"X": path((101, 40.0))}
    one = rp.simulate(rates, "P0", slots=1)
    two = rp.simulate(rates, "P0", slots=2)
    assert two.net_apr() == pytest.approx(one.net_apr() / 2), "a second, empty slot halves the yield on capital"


# --- Section 100: per-coin spreads and the spot-history entry mask -----------------------

def test_per_coin_spread_charges_each_name_its_own_round_trip():
    fee = rp.ROUND_TRIP_FEE_PCT / 100.0
    for coin, bps in (("PURR", 38.0), ("XMR", 31.0), ("FARTCOIN", 10.0), ("BTC", 2.0), ("ZEC", rp.PER_COIN_DEFAULT_BPS)):
        res = rp.simulate({coin: path((50, 40.0))}, "P0", slots=1, spread_model="per-coin")
        assert res.costs == pytest.approx(fee + bps / 10_000.0), coin


def test_the_flat_model_is_unchanged_by_the_per_coin_table():
    rates = {"PURR": path((50, 40.0))}
    assert rp.simulate(rates, "P0", slots=1).costs == pytest.approx(FRICTION), "20 bps, whatever the coin"


def test_spread_scale_multiplies_the_spread_and_never_the_fee():
    fee = rp.ROUND_TRIP_FEE_PCT / 100.0
    half = rp.simulate({"PURR": path((50, 40.0))}, "P0", slots=1, spread_model="per-coin", spread_scale=0.5)
    assert half.costs == pytest.approx(fee + 19.0 / 10_000.0)


def test_per_coin_spreads_reprice_the_policy_without_changing_one_decision():
    rates = {"PURR": path((5, 40.0), (5, -10.0), (30, 60.0)), "XMR": path((40, 35.0))}
    flat, per = rp.simulate(rates, "P0", slots=2), rp.simulate(rates, "P0", slots=2, spread_model="per-coin")
    sig = lambda r: [(t.coin, t.opened, t.closed, t.reason) for t in r.trades]
    assert sig(flat) == sig(per), "the gates read funding only"
    assert flat.gross == pytest.approx(per.gross) and flat.costs != pytest.approx(per.costs)


def test_the_eligibility_mask_blocks_an_entry_and_never_closes_a_position():
    rates = {"X": path((100, 40.0))}
    late = rp.simulate(rates, "P0", slots=1, eligible=lambda coin, t: t >= 50)
    (trade,) = late.trades
    assert trade.opened == 50, "hot from hour 0, but the spot hedge did not exist until hour 50"
    early = rp.simulate(rates, "P0", slots=1, eligible=lambda coin, t: t < 10)
    (trade,) = early.trades
    assert trade.opened == 0 and "marked out" in trade.reason, "entered while eligible; the mask never evicts"


def test_the_mask_also_applies_to_the_name_d_would_rotate_into():
    rates = {
        "OLD1": path((30, 60.0), (170, 11.0)),
        "OLD2": path((30, 60.0), (170, 11.0)),
        "NEW": path((60, 11.0), (140, 80.0)),
    }
    d = rp.simulate(rates, "D", slots=2, eligible=lambda coin, t: coin != "NEW")
    assert "NEW" not in {t.coin for t in d.trades}


def test_passive_btc_is_a_benchmark_and_is_never_masked():
    res = rp.simulate({"BTC": path((30, 11.0))}, "PASSIVE", eligible=lambda coin, t: False)
    assert [t.coin for t in res.trades] == ["BTC"]


# --- Section 101: the PURR ablation and the $2,500-a-leg cost table -----------------------

def test_the_2500_table_refuses_to_price_a_coin_that_could_not_be_filled():
    with pytest.raises(ValueError, match="UNFILLABLE"):
        rp.simulate({"PURR": path((50, 40.0)), "XMR": path((50, 40.0))}, "P0", slots=2, spread_model="s2500")


def test_the_2500_table_charges_the_walked_cost_once_purr_is_out():
    fee = rp.ROUND_TRIP_FEE_PCT / 100.0
    for coin, bps in (("XMR", 53.5), ("FARTCOIN", 35.0), ("ZEC", rp.S2500_DEFAULT_BPS), ("BTC", rp.S2500_DEFAULT_BPS)):
        res = rp.simulate({coin: path((50, 40.0))}, "P0", slots=1, spread_model="s2500")
        assert res.costs == pytest.approx(fee + bps / 10_000.0), coin


def test_excluding_a_coin_hands_its_slot_to_the_next_ranked_name():
    """The ablation is not a subtraction: PURR's slot does not sit empty."""
    rates = {"PURR": path((60, 90.0)), "XMR": path((60, 60.0)), "ZEC": path((60, 30.0))}
    assert {t.coin for t in rp.simulate(rates, "P0", slots=2).trades} == {"PURR", "XMR"}
    without = {c: v for c, v in rates.items() if c != "PURR"}
    res = rp.simulate(without, "P0", slots=2)
    assert {t.coin for t in res.trades} == {"XMR", "ZEC"}
    assert res.gross > 0 and res.occupied == 2 * (res.span - 1), "both slots full from the first decision on"


def test_the_ablation_hurdle_is_the_ruled_number_not_a_recomputation():
    assert rp.ABLATION_HURDLE_APR == 9.36
    assert "PURR" in rp.S2500_UNFILLABLE and "PURR" not in rp.S2500_SPREAD_BPS
