"""
Round 8 tests:
  Task 1 - two-tier exotic liquidation detection
  Task 2 - squeeze rotation hysteresis cooldown
  Task 3 - rotation capacity / interval tuning
  Task 4 - liquidation-fade paper engine on exotic markets

Fully offline: no network, no production database.
"""

import unittest

from analytics.liquidation_engine import LiquidationEngine
from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from config.settings import (
    EXOTIC_SWEEP_MIN_NOTIONAL,
    EXOTIC_SWEEP_MIN_SLIPPAGE_PCT,
    MAJOR_SWEEP_MIN_NOTIONAL,
    MAJOR_SWEEP_MIN_SLIPPAGE_PCT,
    WHALE_ORDER_MIN_NOTIONAL,
    SQUEEZE_ROTATION_COOLDOWN_SECONDS,
    SQUEEZE_ROTATION_INTERVAL,
    SQUEEZE_ROTATION_MAX_COINS,
    FADE_MIN_NOTIONAL_EXOTIC,
    FADE_MIN_NOTIONAL_MAJOR,
)


def sweep(notional, slippage_pct, mark=100.0, side="A", coin="SKR"):
    """Build a trade printing `slippage_pct` away from `mark` for `notional`."""
    px = mark * (1.0 + slippage_pct / 100.0)
    return {"coin": coin, "px": px, "sz": notional / px, "side": side, "time": 1}


# --------------------------------------------------------------------------
# Task 1: exotic liquidation detection
# --------------------------------------------------------------------------

class TestExoticSweepDetection(unittest.TestCase):
    def detect(self, notional, slippage_pct, mark=100.0, **kw):
        return LiquidationEngine.detect_liquidation_trade(
            sweep(notional, slippage_pct, mark, **kw), mark
        )

    def test_exotic_sweep_is_detected(self):
        """$1,500 at 1.2% slippage - the case that was silently dropped."""
        r = self.detect(1_500.0, 1.2)
        self.assertIsNotNone(r)
        self.assertEqual(r["source"], "trade_sweep")
        self.assertAlmostEqual(r["notional"], 1_500.0, places=2)

    def test_dust_is_rejected_even_with_large_slippage(self):
        """$500 at 1.2% is noise in a thin book, not a forced exit."""
        self.assertIsNone(self.detect(500.0, 1.2))

    def test_small_size_with_small_slippage_is_rejected(self):
        """Below the exotic slippage bar: an ordinary fill, not a cascade."""
        self.assertIsNone(self.detect(1_500.0, 0.5))

    def test_exotic_thresholds_are_inclusive_at_the_boundary(self):
        self.assertIsNotNone(self.detect(EXOTIC_SWEEP_MIN_NOTIONAL, EXOTIC_SWEEP_MIN_SLIPPAGE_PCT))

    def test_just_below_either_exotic_bound_is_rejected(self):
        self.assertIsNone(self.detect(EXOTIC_SWEEP_MIN_NOTIONAL - 1, EXOTIC_SWEEP_MIN_SLIPPAGE_PCT))
        self.assertIsNone(self.detect(EXOTIC_SWEEP_MIN_NOTIONAL, EXOTIC_SWEEP_MIN_SLIPPAGE_PCT - 0.1))

    def test_major_tier_still_needs_less_slippage(self):
        """A deep-book market qualifies at 0.4%, where an exotic would not."""
        self.assertIsNotNone(self.detect(MAJOR_SWEEP_MIN_NOTIONAL, MAJOR_SWEEP_MIN_SLIPPAGE_PCT))
        self.assertIsNone(self.detect(MAJOR_SWEEP_MIN_NOTIONAL - 1, MAJOR_SWEEP_MIN_SLIPPAGE_PCT))

    def test_whale_order_qualifies_on_size_alone(self):
        r = self.detect(WHALE_ORDER_MIN_NOTIONAL, 0.0)
        self.assertIsNotNone(r)
        self.assertEqual(r["source"], "trade_flow")

    def test_protocol_backstop_fill_is_always_a_liquidation(self):
        t = sweep(10.0, 0.0)
        t["users"] = ["0x0000000000000000000000000000000000000000"]
        r = LiquidationEngine.detect_liquidation_trade(t, 100.0)
        self.assertIsNotNone(r)
        self.assertEqual(r["source"], "liquidation_fill")

    def test_slippage_is_directionless(self):
        """A cascade prints away from mark in either direction."""
        self.assertIsNotNone(self.detect(1_500.0, 1.2))
        self.assertIsNotNone(self.detect(1_500.0, -1.2))

    def test_missing_mark_falls_back_to_size_only(self):
        self.assertIsNone(LiquidationEngine.detect_liquidation_trade(sweep(1_500.0, 1.2), None))
        self.assertIsNotNone(
            LiquidationEngine.detect_liquidation_trade(sweep(60_000.0, 0.0), None)
        )

    def test_realistic_exotic_stream_now_produces_events(self):
        """
        Regression for the measured failure: 10,443 exotic fills produced 6
        liquidation events because only 2 cleared $25k. With the exotic tier the
        high-slippage subset is captured.
        """
        fills = (
            [sweep(69.0, 0.1) for _ in range(50)]        # median dust
            + [sweep(495.0, 0.8) for _ in range(10)]     # p90, still dust
            + [sweep(2_000.0, 1.5) for _ in range(5)]    # real exotic sweeps
        )
        detected = [
            LiquidationEngine.detect_liquidation_trade(f, 100.0) for f in fills
        ]
        hits = [d for d in detected if d]
        self.assertEqual(len(hits), 5)
        self.assertTrue(all(h["source"] == "trade_sweep" for h in hits))


# --------------------------------------------------------------------------
# Task 2 / 3: rotation hysteresis and capacity
# --------------------------------------------------------------------------

class RotationPlanner:
    """
    Mirror of MarketCollector._plan_rotation, exercised without constructing a
    collector (which would open the production database and a REST client).
    """

    def __init__(self, rotated=None, sub_time=None, max_coins=SQUEEZE_ROTATION_MAX_COINS,
                 cooldown=SQUEEZE_ROTATION_COOLDOWN_SECONDS):
        self._rotated_coins = set(rotated or set())
        self._rotation_sub_time = dict(sub_time or {})
        self.max_coins = max_coins
        self.cooldown = cooldown

    def plan(self, wanted, now):
        capacity = max(0, self.max_coins - len(self._rotated_coins))
        stale = self._rotated_coins - wanted
        to_drop = {
            c for c in stale
            if (now - self._rotation_sub_time.get(c, 0.0)) >= self.cooldown
        }
        held = stale - to_drop
        capacity += len(to_drop)
        to_add = set(sorted(wanted - self._rotated_coins)[:capacity])
        return to_add, to_drop, held


class TestRotationCooldown(unittest.TestCase):
    def setUp(self):
        self.p = RotationPlanner(
            rotated={"A", "B", "C"},
            sub_time={"A": 0.0, "B": 0.0, "C": 0.0},
        )

    def test_coin_is_retained_during_cooldown_even_though_score_dropped(self):
        """
        The whole point: a squeeze stops looking crowded exactly when it starts
        unwinding, which is when its liquidations print.
        """
        add, drop, held = self.p.plan({"A"}, now=100.0)
        self.assertEqual(drop, set())
        self.assertEqual(held, {"B", "C"})

    def test_coin_is_dropped_once_the_cooldown_elapses(self):
        add, drop, held = self.p.plan({"A"}, now=SQUEEZE_ROTATION_COOLDOWN_SECONDS + 1)
        self.assertEqual(drop, {"B", "C"})
        self.assertEqual(held, set())

    def test_cooldown_boundary_is_inclusive(self):
        _, drop, _ = self.p.plan({"A"}, now=SQUEEZE_ROTATION_COOLDOWN_SECONDS)
        self.assertEqual(drop, {"B", "C"})

    def test_coin_that_stays_wanted_is_never_dropped(self):
        add, drop, held = self.p.plan({"A", "B", "C"}, now=1e9)
        self.assertEqual(drop, set())
        self.assertEqual(add, set())

    def test_coin_rejoining_the_set_is_not_resubscribed(self):
        """It never left, so there must be no duplicate subscribe frame."""
        self.p.plan({"A"}, now=100.0)          # B, C held
        add, drop, held = self.p.plan({"A", "B", "C"}, now=200.0)
        self.assertEqual(add, set())
        self.assertEqual(drop, set())

    def test_capacity_is_respected(self):
        p = RotationPlanner(max_coins=3)
        add, _, _ = p.plan({f"C{i}" for i in range(10)}, now=0.0)
        self.assertEqual(len(add), 3)

    def test_held_coins_consume_capacity(self):
        """Cooldown-held coins still occupy slots; new ones must wait."""
        p = RotationPlanner(rotated={"A", "B"}, sub_time={"A": 0.0, "B": 0.0}, max_coins=2)
        add, drop, held = p.plan({"X", "Y"}, now=10.0)
        self.assertEqual(held, {"A", "B"})
        self.assertEqual(add, set())

    def test_freed_slots_are_reused_in_the_same_cycle(self):
        p = RotationPlanner(rotated={"A", "B"}, sub_time={"A": 0.0, "B": 0.0}, max_coins=2)
        add, drop, held = p.plan({"X", "Y"}, now=SQUEEZE_ROTATION_COOLDOWN_SECONDS + 1)
        self.assertEqual(drop, {"A", "B"})
        self.assertEqual(add, {"X", "Y"})

    def test_tuned_capacity_and_interval(self):
        self.assertEqual(SQUEEZE_ROTATION_MAX_COINS, 35)
        self.assertEqual(SQUEEZE_ROTATION_INTERVAL, 180.0)
        self.assertEqual(SQUEEZE_ROTATION_COOLDOWN_SECONDS, 1200.0)

    def test_cooldown_outlives_several_rotation_intervals(self):
        """Otherwise the hysteresis would not actually span a cascade."""
        self.assertGreater(SQUEEZE_ROTATION_COOLDOWN_SECONDS, SQUEEZE_ROTATION_INTERVAL * 3)


# --------------------------------------------------------------------------
# Task 4: fade engine on exotic markets
# --------------------------------------------------------------------------

def liq(coin, side, notional, oi=None, px=10.0):
    e = {"coin": coin, "side": side, "notional": notional, "px": px}
    if oi is not None:
        e["notional_oi"] = oi
    return e


class TestExoticFade(unittest.TestCase):
    def setUp(self):
        self.trader = PaperTrader(100_000.0)
        self.strat = LiquidationFadeStrategy(self.trader, regime_enabled=False)

    def test_exotic_cascade_triggers_a_fade(self):
        """$2k on a thin market - previously ignored by the flat $50k trigger."""
        r = self.strat.on_liquidation_event(liq("SKR", "A", 2_000.0, oi=2_000_000.0), 10.0)
        self.assertIsNotNone(r)
        self.assertEqual(r["status"], "OPEN")
        self.assertEqual(r["side"], "BUY")

    def test_same_size_on_a_deep_market_does_not_trigger(self):
        r = self.strat.on_liquidation_event(liq("BTC", "A", 2_000.0, oi=5e8), 70_000.0)
        self.assertIsNone(r)

    def test_major_cascade_still_triggers(self):
        r = self.strat.on_liquidation_event(liq("BTC", "B", 250_000.0, oi=5e8), 70_000.0)
        self.assertIsNotNone(r)
        self.assertEqual(r["side"], "SELL")

    def test_forced_sell_is_faded_by_buying_below_mark(self):
        r = self.strat.on_liquidation_event(liq("SKR", "A", 5_000.0, oi=1e6), 10.0)
        self.assertEqual(r["side"], "BUY")
        self.assertLess(r["limit_price"], 10.0)

    def test_forced_buy_is_faded_by_selling_above_mark(self):
        r = self.strat.on_liquidation_event(liq("SKR", "B", 5_000.0, oi=1e6), 10.0)
        self.assertEqual(r["side"], "SELL")
        self.assertGreater(r["limit_price"], 10.0)

    def test_limit_rests_and_only_fills_on_overshoot(self):
        self.strat.on_liquidation_event(liq("SKR", "A", 5_000.0, oi=1e6), 10.0)
        self.assertEqual(self.trader.check_open_orders({"SKR": 10.0}), [])
        filled = self.trader.check_open_orders({"SKR": 9.90})
        self.assertEqual(len(filled), 1)
        self.assertIn("SKR", self.trader.positions)

    def test_cascade_does_not_compound_into_an_oversized_position(self):
        for _ in range(5):
            self.strat.on_liquidation_event(liq("SKR", "A", 5_000.0, oi=1e6), 10.0)
        self.assertEqual(len(self.trader.open_orders), 1)

    def test_unknown_side_is_ignored(self):
        self.assertIsNone(self.strat.on_liquidation_event(liq("SKR", "?", 9_999.0, oi=1e6), 10.0))

    def test_zero_mark_is_ignored(self):
        self.assertIsNone(self.strat.on_liquidation_event(liq("SKR", "A", 9_999.0, oi=1e6), 0.0))

    def test_batch_ingestion_places_and_settles(self):
        events = [
            liq("SKR", "A", 5_000.0, oi=1e6),
            liq("BTC", "B", 250_000.0, oi=5e8, px=70_000.0),
        ]
        out = self.strat.on_liquidation_batch(events, {"SKR": 10.0, "BTC": 70_000.0})
        self.assertEqual(len(out["placed"]), 2)
        self.assertEqual(out["filled"], [])

        settled = self.strat.on_liquidation_batch([], {"SKR": 9.9, "BTC": 70_400.0})
        self.assertEqual(len(settled["filled"]), 2)

    def test_batch_skips_events_without_a_mark(self):
        out = self.strat.on_liquidation_batch([liq("NOPRICE", "A", 9_999.0, oi=1e6)], {})
        self.assertEqual(out["placed"], [])

    def test_exotic_classification_falls_back_to_notional(self):
        """Without OI on the event, size alone decides which scale applies."""
        self.assertTrue(LiquidationFadeStrategy.is_exotic({"notional": 2_000.0}))
        self.assertFalse(LiquidationFadeStrategy.is_exotic({"notional": 80_000.0}))

    def test_market_order_mode_still_works(self):
        strat = LiquidationFadeStrategy(PaperTrader(100_000.0), use_limit_orders=False, regime_enabled=False)
        r = strat.on_liquidation_event(liq("SKR", "A", 5_000.0, oi=1e6), 10.0)
        self.assertEqual(r["status"], "FILLED")

    def test_configured_thresholds(self):
        self.assertEqual(FADE_MIN_NOTIONAL_EXOTIC, 1_000.0)
        self.assertEqual(FADE_MIN_NOTIONAL_MAJOR, 50_000.0)


class TestPaperLimitOrders(unittest.TestCase):
    def setUp(self):
        self.t = PaperTrader(50_000.0)

    def test_rejects_invalid_limit(self):
        self.assertEqual(self.t.place_limit_order("X", "BUY", 1.0, 0.0)["status"], "REJECTED")
        self.assertEqual(self.t.place_limit_order("X", "BUY", 0.0, 10.0)["status"], "REJECTED")

    def test_buy_fills_at_the_limit_not_the_mark(self):
        """A resting order must not be handed price improvement it never asked for."""
        self.t.place_limit_order("X", "BUY", 10.0, limit_price=9.5)
        self.t.check_open_orders({"X": 9.0})
        self.assertEqual(self.t.positions["X"]["entry_price"], 9.5)

    def test_sell_fills_when_price_rises_through_the_limit(self):
        self.t.place_limit_order("X", "SELL", 10.0, limit_price=10.5)
        self.assertEqual(self.t.check_open_orders({"X": 10.4}), [])
        self.assertEqual(len(self.t.check_open_orders({"X": 10.6})), 1)

    def test_unpriced_coin_leaves_the_order_resting(self):
        self.t.place_limit_order("X", "BUY", 10.0, limit_price=9.5)
        self.t.check_open_orders({"OTHER": 1.0})
        self.assertEqual(len(self.t.open_orders), 1)

    def test_cancel_orders(self):
        self.t.place_limit_order("A", "BUY", 1.0, 1.0)
        self.t.place_limit_order("B", "BUY", 1.0, 1.0)
        self.assertEqual(self.t.cancel_orders("A"), 1)
        self.assertEqual(len(self.t.open_orders), 1)
        self.assertEqual(self.t.cancel_orders(), 1)

    def test_account_summary_counts_resting_orders(self):
        self.t.place_limit_order("A", "BUY", 1.0, 1.0)
        self.assertEqual(self.t.get_account_summary()["open_orders_count"], 1)


if __name__ == "__main__":
    unittest.main()
