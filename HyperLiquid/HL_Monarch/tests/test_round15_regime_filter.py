"""
Round 15 tests: trend/ATR confluence filter, volatility-scaled geometry, dual pool.

Context for whoever reads this next. The unfiltered baseline lost GROSS money
(-$482.77 over 12 closes, 25% win rate, PF 0.123) - fees were not the problem,
the entries were. Blind fading on liquid majors was catching trend continuation,
not dislocation. Everything here exists to stop that specific failure.

These tests deliberately pin the CONSERVATIVE defaults: unknown regime blocks,
ambiguity blocks, floors bind. A later round that wants to loosen any of them
should have to edit an assertion and say why.

Fully offline - every indicator input is a synthetic series.
"""

import unittest

from analytics.indicators import (
    atr_pct, atr_pct_true_range, compute_regime, ema, resample, resample_ohlc, rsi,
)
from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from config.settings import (
    FADE_ATR_OFFSET_FLOOR_PCT,
    FADE_ATR_OFFSET_MULT,
    FADE_ATR_TARGET_FLOOR_PCT,
    FADE_ATR_TARGET_MULT,
    FADE_ATR_STOP_MULT,
    MAKER_FEE_PCT,
    ROTATION_EXOTIC_MAX_OI,
    ROTATION_EXOTIC_MIN_VOLUME,
    ROTATION_EXOTIC_SLOTS,
    ROTATION_MAJOR_SLOTS,
    ROTATION_MAX_COINS,
    TAKER_FEE_PCT,
)

MIN = 60_000


def regime(price, ema_v, rsi_v, atr=1.0, sufficient=True):
    return {"price": price, "ema": ema_v, "rsi": rsi_v,
            "atr_pct": atr, "sufficient": sufficient}


class TestIndicatorMaths(unittest.TestCase):
    def test_ema_of_a_known_series(self):
        # SMA-seeded on 1..5 (=3.0), then 6..10 smoothed at k=1/3.
        self.assertAlmostEqual(ema(list(range(1, 11)), 5), 8.0, places=6)

    def test_ema_needs_a_full_period(self):
        self.assertIsNone(ema([1.0, 2.0, 3.0], 5))

    def test_rsi_is_100_when_nothing_ever_fell(self):
        self.assertEqual(rsi([float(i) for i in range(30)], 14), 100.0)

    def test_rsi_of_a_flat_market_is_50(self):
        """No gains and no losses is undefined as a ratio; 50 is the neutral read."""
        self.assertEqual(rsi([10.0] * 30, 14), 50.0)

    def test_rsi_is_below_50_in_a_downtrend(self):
        self.assertLess(rsi([float(100 - i) for i in range(30)], 14), 50.0)

    def test_atr_of_a_flat_market_is_zero(self):
        self.assertEqual(atr_pct([10.0] * 30, 14), 0.0)

    def test_atr_is_a_percent_not_a_fraction(self):
        """
        A market oscillating by 1 point around 100 reads ~1.0, not ~0.01. The
        percentage is taken against the LAST price (101 here), not the series
        base - so the exact value is 1/101. Units matter: every other threshold
        in this codebase is a percent, and mixing the two is a 100x error.
        """
        series = [100.0 + (i % 2) for i in range(30)]
        self.assertAlmostEqual(atr_pct(series, 14), 1.0 / 101.0 * 100.0, places=6)


class TestResampling(unittest.TestCase):
    """Irregular point samples must become a fixed grid before period maths."""

    def test_last_value_in_each_bucket_wins(self):
        series = [(0, 1.0), (10_000, 2.0), (61_000, 3.0), (119_000, 4.0)]
        self.assertEqual(resample(series, 1.0), [2.0, 4.0])

    def test_a_dense_burst_collapses_to_one_bucket(self):
        """
        The collector samples ~370x/hour, unevenly. Without this collapse a burst
        of samples would count as many 'periods' and a gap as none.
        """
        series = [(i * 100, float(i)) for i in range(50)]
        self.assertEqual(len(resample(series, 1.0)), 1)

    def test_empty_series_is_empty_not_an_error(self):
        self.assertEqual(resample([], 1.0), [])


class TestRegimeSufficiency(unittest.TestCase):
    def test_a_thin_series_is_reported_insufficient(self):
        r = compute_regime("X", series=[(i * MIN, 10.0) for i in range(5)],
                           bucket_minutes=1.0, ema_period=50)
        self.assertFalse(r["sufficient"])
        self.assertIsNone(r["ema"])

    def test_a_full_series_is_sufficient_and_priced(self):
        series = [(i * MIN, 100.0 + i * 0.1) for i in range(120)]
        r = compute_regime("X", series=series, bucket_minutes=1.0, ema_period=50)
        self.assertTrue(r["sufficient"])
        self.assertTrue(r["above_ema"])
        self.assertAlmostEqual(r["price"], series[-1][1], places=9)


class TestRegimeGate(unittest.TestCase):
    """
    BUY  : price >= EMA  OR  RSI <= oversold
    SELL : price <= EMA  OR  RSI >= overbought

    The OR is the whole idea. A dip in an uptrend is a dip; a dip in a downtrend
    is a falling knife, and only a washed-out RSI justifies catching it.
    """

    permits = staticmethod(LiquidationFadeStrategy.regime_permits)

    def test_buying_a_dip_in_an_uptrend_is_allowed(self):
        self.assertTrue(self.permits("BUY", regime(105.0, 100.0, 50.0)))

    def test_buying_into_a_downtrend_is_blocked(self):
        self.assertFalse(self.permits("BUY", regime(95.0, 100.0, 45.0)))

    def test_buying_a_downtrend_is_allowed_once_washed_out(self):
        self.assertTrue(self.permits("BUY", regime(95.0, 100.0, 25.0)))

    def test_selling_a_rip_in_a_downtrend_is_allowed(self):
        self.assertTrue(self.permits("SELL", regime(95.0, 100.0, 50.0)))

    def test_selling_into_an_uptrend_is_blocked(self):
        self.assertFalse(self.permits("SELL", regime(105.0, 100.0, 60.0)))

    def test_selling_an_uptrend_is_allowed_once_overbought(self):
        self.assertTrue(self.permits("SELL", regime(105.0, 100.0, 75.0)))

    def test_price_exactly_at_the_ema_permits_both_sides(self):
        """The boundary is inclusive on both legs; neither trend is established."""
        self.assertTrue(self.permits("BUY", regime(100.0, 100.0, 50.0)))
        self.assertTrue(self.permits("SELL", regime(100.0, 100.0, 50.0)))


class TestUnknownRegimeBlocks(unittest.TestCase):
    """
    'Unknown' is not 'fine'. Permitting on a missing regime would silently
    reinstate the unfiltered strategy we just measured as gross-negative -
    and it would do it precisely on the thin exotic books where the series is
    gappiest, which is the tier Round 15 exists to start testing.
    """

    permits = staticmethod(LiquidationFadeStrategy.regime_permits)

    def test_none_blocks(self):
        self.assertFalse(self.permits("BUY", None))

    def test_insufficient_blocks(self):
        self.assertFalse(self.permits("BUY", regime(105.0, 100.0, 50.0, sufficient=False)))

    def test_missing_indicator_blocks_even_when_marked_sufficient(self):
        self.assertFalse(self.permits("BUY", regime(105.0, None, 50.0)))

    def test_the_default_is_block_not_permit(self):
        """Pinning the default itself, not just the behaviour under an override."""
        self.assertFalse(self.permits("BUY", None))
        self.assertTrue(self.permits("BUY", None, block_when_unknown=False))


class TestDynamicGeometry(unittest.TestCase):
    geo = staticmethod(LiquidationFadeStrategy.geometry_for)

    def test_a_volatile_market_gets_a_wider_offset_and_target(self):
        off, tgt, stop = self.geo(regime(1.0, 1.0, 50.0, atr=2.0), 0.5, 0.65)
        self.assertAlmostEqual(off, FADE_ATR_OFFSET_MULT * 2.0, places=9)
        self.assertAlmostEqual(tgt, FADE_ATR_TARGET_MULT * 2.0, places=9)
        self.assertAlmostEqual(stop, FADE_ATR_STOP_MULT * 2.0, places=9)

    def test_target_and_stop_are_symmetric_so_the_trade_stays_one_to_one(self):
        """Separate multipliers exist for future flexibility, but 1:1 is the contract."""
        _off, tgt, stop = self.geo(regime(1.0, 1.0, 50.0, atr=2.0), 0.5, 0.65)
        self.assertEqual(tgt, stop)

    def test_a_quiet_market_is_held_at_the_floors(self):
        """
        BTC's 15m ATR is ~0.146%. Half of that is 0.073% - inside the noise and
        inside the spread. The floor is what stops the order resting on nothing.
        """
        off, tgt, stop = self.geo(regime(1.0, 1.0, 50.0, atr=0.146), 0.5, 0.65)
        self.assertEqual(off, FADE_ATR_OFFSET_FLOOR_PCT)
        self.assertEqual(tgt, FADE_ATR_TARGET_FLOOR_PCT)
        self.assertEqual(stop, FADE_ATR_TARGET_FLOOR_PCT)

    def test_the_target_floor_keeps_fees_a_minority_of_gross(self):
        """
        The reason the target floor exists. A pure 1.0x ATR target on BTC is
        ~0.146%, against a 4.5bp maker+taker round trip - fees would be ~31% of
        gross. At the floor they are ~15%. Still a tax; no longer the trade.
        """
        round_trip_pct = (MAKER_FEE_PCT + TAKER_FEE_PCT) * 100.0
        self.assertLess(round_trip_pct / FADE_ATR_TARGET_FLOOR_PCT, 0.20)
        self.assertGreater(round_trip_pct / 0.146, 0.30)

    def test_missing_atr_falls_back_to_the_static_geometry(self):
        self.assertEqual(self.geo(regime(1.0, 1.0, 50.0, atr=None), 0.5, 0.65),
                         (0.5, 0.65, 0.65))
        self.assertEqual(self.geo(None, 0.5, 0.65), (0.5, 0.65, 0.65))
        # An explicit static stop is honoured rather than mirrored from the target.
        self.assertEqual(self.geo(None, 0.5, 0.65, static_stop_pct=0.9), (0.5, 0.65, 0.9))

    def test_the_dynamic_switch_restores_the_static_geometry(self):
        self.assertEqual(
            self.geo(regime(1.0, 1.0, 50.0, atr=9.0), 0.5, 0.65, dynamic=False),
            (0.5, 0.65, 0.65),
        )

    def test_geometry_stays_one_to_one_at_any_volatility(self):
        """
        Round 12 replaced 1:3 with 1:1 because 1:3 needed a >75% win rate. Scaling
        by ATR must not quietly reintroduce an asymmetry.
        """
        t = PaperTrader(100_000.0)
        s = LiquidationFadeStrategy(t)
        o = s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 5_000.0}, 10.0,
                                   notional_oi=1e6,
                                   regime=regime(10.0, 9.0, 50.0, atr=2.0))
        self.assertIsNotNone(o)
        self.assertAlmostEqual(o["take_profit"] - o["limit_price"],
                               o["limit_price"] - o["stop_loss"], places=9)


class TestGateIsWiredIntoPlacement(unittest.TestCase):
    def setUp(self):
        self.t = PaperTrader(100_000.0)
        self.s = LiquidationFadeStrategy(self.t)
        self.sweep = {"coin": "SKR", "side": "A", "notional": 5_000.0}  # forced sell -> BUY

    def test_a_fade_against_the_trend_is_not_placed(self):
        self.assertIsNone(
            self.s.on_liquidation_sweep(self.sweep, 10.0, notional_oi=1e6,
                                        regime=regime(9.0, 10.0, 45.0))
        )
        self.assertEqual(self.t.open_orders, [])
        self.assertEqual(self.s.blocked_by_regime, 1)

    def test_the_same_fade_with_the_trend_is_placed(self):
        o = self.s.on_liquidation_sweep(self.sweep, 10.0, notional_oi=1e6,
                                        regime=regime(11.0, 10.0, 50.0))
        self.assertIsNotNone(o)
        self.assertEqual(self.s.blocked_by_regime, 0)

    def test_a_missing_regime_blocks_a_live_fade(self):
        self.assertIsNone(self.s.on_liquidation_sweep(self.sweep, 10.0, notional_oi=1e6))
        self.assertEqual(self.s.blocked_by_regime, 1)

    def test_the_gate_can_be_disabled_wholesale(self):
        s = LiquidationFadeStrategy(PaperTrader(100_000.0), regime_enabled=False)
        self.assertIsNotNone(s.on_liquidation_sweep(self.sweep, 10.0, notional_oi=1e6))

    def test_a_regime_block_is_counted_separately_from_other_rejections(self):
        """
        The gate runs LAST so a rejection is attributable to it, not to the size,
        threshold or cooldown filters ahead of it. Otherwise the block counter
        would silently absorb every other reason and the post-run diagnosis
        would be unreadable.
        """
        self.s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 1.0}, 10.0,
                                    notional_oi=1e6, regime=regime(9.0, 10.0, 45.0))
        self.assertEqual(self.s.blocked_by_regime, 0)


class TestDualRotationPool(unittest.TestCase):
    """
    The defect this fixes took a whole observation window to surface: volume-only
    ranking selected exclusively >$5M OI books, so every one of the 12 baseline
    fills was the $10k major tier and the exotic tier built in rounds 9-12 never
    fired once. The exotic thesis was never actually tested.
    """

    def setUp(self):
        from collectors.market_collector import MarketCollector
        self.c = MarketCollector.__new__(MarketCollector)
        self.c._notional_oi = {}
        self.c._last_rotation_split = (0, 0)

    def snaps(self, n_major=40, n_exotic=40):
        rows = [{"coin": f"MAJ{i}", "notional_oi": 5e7, "day_ntl_vlm": 1e9 - i}
                for i in range(n_major)]
        rows += [{"coin": f"EXO{i}", "notional_oi": 1e6, "day_ntl_vlm": 5e5 - i}
                 for i in range(n_exotic)]
        return rows

    def run_split(self, rows):
        self.c.repo = type("R", (), {"get_latest_snapshots": lambda _s: rows})()
        return self.c._compute_rotation_candidates(ROTATION_MAX_COINS)

    def test_slots_are_split_between_the_two_pools(self):
        picked = self.run_split(self.snaps())
        self.assertEqual(len(picked), ROTATION_MAX_COINS)
        self.assertEqual(self.c._last_rotation_split, (ROTATION_MAJOR_SLOTS, ROTATION_EXOTIC_SLOTS))
        self.assertEqual(sum(1 for c in picked if c.startswith("EXO")), ROTATION_EXOTIC_SLOTS)

    def test_thin_books_are_selected_despite_losing_on_volume(self):
        """Every exotic here has 2000x less volume than every major. Under the
        old ranking not one of them would appear."""
        picked = self.run_split(self.snaps())
        self.assertIn("EXO0", picked)

    def test_an_illiquid_exotic_is_still_excluded(self):
        rows = self.snaps(n_exotic=0)
        rows.append({"coin": "DEAD", "notional_oi": 1e6,
                     "day_ntl_vlm": ROTATION_EXOTIC_MIN_VOLUME - 1})
        self.assertNotIn("DEAD", self.run_split(rows))

    def test_a_book_at_the_oi_ceiling_is_a_major(self):
        rows = [{"coin": "EDGE", "notional_oi": ROTATION_EXOTIC_MAX_OI, "day_ntl_vlm": 1e9}]
        self.run_split(rows)
        self.assertEqual(self.c._last_rotation_split, (1, 0))

    def test_unused_exotic_slots_spill_back_to_majors(self):
        """An empty exotic band must not cost us major coverage."""
        picked = self.run_split(self.snaps(n_exotic=0))
        self.assertEqual(len(picked), ROTATION_MAX_COINS)
        self.assertEqual(self.c._last_rotation_split, (ROTATION_MAX_COINS, 0))

    def test_oi_is_cached_for_every_snapshot_not_just_the_picks(self):
        """The fade strategy tiers off this cache; a miss would mis-size an order."""
        self.run_split(self.snaps())
        self.assertEqual(self.c._notional_oi["EXO39"], 1e6)

    def test_a_failed_read_yields_no_candidates_rather_than_raising(self):
        def boom(_s):
            raise RuntimeError("db down")
        self.c.repo = type("R", (), {"get_latest_snapshots": boom})()
        self.assertEqual(self.c._compute_rotation_candidates(ROTATION_MAX_COINS), [])


if __name__ == "__main__":
    unittest.main()


class TestTrueRangeATR(unittest.TestCase):
    """
    Round 15 polish. The close-to-close proxy understates measured true range by
    ~1.6x across the live watchlist (min 1.39 xyz:CRWD, median 1.59, max 1.98 INJ).

    Antigravity proposed reconciling this with a flat 1.25x multiplier. That was
    rejected on measurement: 1.25 understated the real ratio in 35 of 35 markets,
    and no single constant fits a 1.39-1.98 spread. With ~67 samples per 15m
    bucket the intra-bar extremes are directly observable, so the range is
    computed per market instead of assumed.
    """

    def test_ohlc_resampling_recovers_the_intra_bucket_extremes(self):
        series = [(0, 10.0), (10_000, 12.0), (20_000, 8.0), (30_000, 11.0)]
        self.assertEqual(resample_ohlc(series, 1.0), [(12.0, 8.0, 11.0)])

    def test_each_bucket_is_independent(self):
        series = [(0, 10.0), (10_000, 12.0), (61_000, 5.0), (70_000, 7.0)]
        self.assertEqual(resample_ohlc(series, 1.0), [(12.0, 10.0, 12.0), (7.0, 5.0, 7.0)])

    def test_true_range_exceeds_the_close_to_close_proxy(self):
        """The whole reason for the change: identical closes, real intra-bar travel."""
        series = []
        for b in range(30):
            base = b * 60_000
            # every bucket closes at 100 but travels 100 -> 104 -> 96 -> 100
            series += [(base, 100.0), (base + 10_000, 104.0),
                       (base + 20_000, 96.0), (base + 30_000, 100.0)]
        closes = resample(series, 1.0)
        self.assertEqual(atr_pct(closes, 14), 0.0)          # closes never move
        tr = atr_pct_true_range(resample_ohlc(series, 1.0), 14)
        self.assertAlmostEqual(tr, 8.0, places=6)           # 8-point range on a 100 close

    def test_true_range_includes_the_gap_between_buckets(self):
        """
        TR = max(h-l, |h-prev_close|, |l-prev_close|). A market that gaps and then
        sits still has real range; ignoring the gap would report almost none.
        """
        bars = [(100.0, 100.0, 100.0)] * 15 + [(110.0, 110.0, 110.0)]
        tr = atr_pct_true_range(bars, 14)
        self.assertGreater(tr, 0.0)

    def test_it_needs_a_full_period_plus_one(self):
        self.assertIsNone(atr_pct_true_range([(1.0, 1.0, 1.0)] * 5, 14))

    def test_compute_regime_uses_true_range_by_default(self):
        series = []
        for b in range(40):
            base = b * 60_000
            series += [(base, 100.0), (base + 20_000, 103.0), (base + 40_000, 100.0)]
        default = compute_regime("X", series=series, bucket_minutes=1.0, ema_period=20)
        legacy = compute_regime("X", series=series, bucket_minutes=1.0, ema_period=20,
                                use_true_range=False)
        self.assertEqual(default["atr_method"], "true_range")
        self.assertEqual(legacy["atr_method"], "close_to_close")
        self.assertGreater(default["atr_pct"], legacy["atr_pct"])

    def test_trend_and_stretch_still_read_off_closes(self):
        """Only volatility needs intra-bar extremes; EMA/RSI are defined on closes."""
        series = [(i * 60_000, 100.0 + i * 0.1) for i in range(120)]
        a = compute_regime("X", series=series, bucket_minutes=1.0, ema_period=50)
        b = compute_regime("X", series=series, bucket_minutes=1.0, ema_period=50,
                           use_true_range=False)
        self.assertEqual(a["ema"], b["ema"])
        self.assertEqual(a["rsi"], b["rsi"])


class TestHoldingWindowConsistency(unittest.TestCase):
    """
    RESOLVED in the Round 15 polish. Targets used to be sized off a 15m ATR bar
    while positions were force-closed at 600s: median time-to-target was 1,224s
    and the target was hit inside the window in under 50% of cases in 35/35
    markets, so most exits resolved TIME_STOP at the mid rather than at TP or SL.

    The fix was applied on BOTH sides - the target multiplier was halved to 0.50
    and the hold extended to 1800s - so the window now comfortably covers the
    distance. These assertions keep it that way.
    """

    def test_the_hold_window_now_covers_the_atr_bar_it_sizes_against(self):
        from config.settings import FADE_POSITION_MAX_HOLD_SECONDS, REGIME_BUCKET_MINUTES
        self.assertGreaterEqual(FADE_POSITION_MAX_HOLD_SECONDS,
                                REGIME_BUCKET_MINUTES * 60.0)

    def test_the_hold_covers_the_measured_median_time_to_target(self):
        """1,224s was measured against a 1.0x target; the target is now 0.50x."""
        from config.settings import FADE_POSITION_MAX_HOLD_SECONDS
        self.assertGreater(FADE_POSITION_MAX_HOLD_SECONDS, 1224.0)

    def test_the_target_multiplier_was_actually_halved(self):
        self.assertEqual(FADE_ATR_TARGET_MULT, 0.50)
