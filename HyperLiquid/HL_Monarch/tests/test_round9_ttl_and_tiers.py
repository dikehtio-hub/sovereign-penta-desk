"""
Round 9 tests:
  Task 1 - TTL expiry for resting fade limit orders
  Task 2 - exotic threshold tuning (squeeze OI floor, whale discovery, alerting)

Fully offline: no network, no production database.
"""

import tempfile
import unittest
from pathlib import Path

from analytics.alerter import WebhookAlerter
from analytics.whale_tracker import WhaleTracker
from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from storage.db import DatabaseManager
from config.settings import (
    ALERT_EXOTIC_MIN_NOTIONAL,
    ALERT_EXOTIC_MIN_SLIPPAGE_PCT,
    FADE_ORDER_TTL_SECONDS,
    SQUEEZE_MIN_NOTIONAL_OI,
    WHALE_DISCOVERY_MIN_NOTIONAL_CORE,
    WHALE_DISCOVERY_MIN_NOTIONAL_EXOTIC,
)

SEC = 1000  # ms


# --------------------------------------------------------------------------
# Task 1: fade order TTL
# --------------------------------------------------------------------------

class TestOrderTTL(unittest.TestCase):
    def setUp(self):
        self.t = PaperTrader(100_000.0)

    def _rest(self, coin="SKR", side="BUY", limit=9.5, size=10.0):
        return self.t.place_limit_order(coin, side, size, limit_price=limit)

    def test_ttl_is_three_minutes(self):
        self.assertEqual(FADE_ORDER_TTL_SECONDS, 180.0)

    def test_fresh_order_is_not_expired(self):
        o = self._rest()
        expired = self.t.expire_stale_orders(now_ms=o["placed_at"] + 60 * SEC)
        self.assertEqual(expired, [])
        self.assertEqual(len(self.t.open_orders), 1)

    def test_order_expires_after_the_ttl(self):
        o = self._rest()
        expired = self.t.expire_stale_orders(now_ms=o["placed_at"] + 181 * SEC)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0]["status"], "EXPIRED")
        self.assertEqual(self.t.open_orders, [])

    def test_stale_order_cannot_fill_on_unrelated_price_action(self):
        """
        The bug this closes: a fade placed during a cascade hours ago would still
        fill later on price action that had nothing to do with it, booking a trade
        the strategy never intended and flattering the paper PnL.
        """
        o = self._rest(limit=9.5)
        filled = self.t.check_open_orders({"SKR": 9.0}, now_ms=o["placed_at"] + 3600 * SEC)
        self.assertEqual(filled, [])
        self.assertNotIn("SKR", self.t.positions)

    def test_order_within_ttl_still_fills(self):
        o = self._rest(limit=9.5)
        filled = self.t.check_open_orders({"SKR": 9.0}, now_ms=o["placed_at"] + 60 * SEC)
        self.assertEqual(len(filled), 1)
        self.assertIn("SKR", self.t.positions)

    def test_expiry_runs_before_fills(self):
        """An order that has outlived its thesis must not fill on the tick that retires it."""
        o = self._rest(limit=9.5)
        filled = self.t.check_open_orders({"SKR": 9.0}, now_ms=o["placed_at"] + 181 * SEC)
        self.assertEqual(filled, [])
        self.assertEqual(self.t.open_orders, [])

    def test_ttl_boundary_is_inclusive_of_survival(self):
        o = self._rest()
        self.t.expire_stale_orders(now_ms=o["placed_at"] + int(FADE_ORDER_TTL_SECONDS) * SEC)
        self.assertEqual(len(self.t.open_orders), 1)

    def test_zero_ttl_disables_expiry(self):
        o = self._rest()
        self.assertEqual(self.t.expire_stale_orders(0, now_ms=o["placed_at"] + 10_000 * SEC), [])
        self.assertEqual(len(self.t.open_orders), 1)

    def test_expiry_is_selective(self):
        old = self._rest(coin="OLD")
        old["placed_at"] -= 600 * SEC
        self._rest(coin="NEW")
        expired = self.t.expire_stale_orders()
        self.assertEqual([o["coin"] for o in expired], ["OLD"])
        self.assertEqual([o["coin"] for o in self.t.open_orders], ["NEW"])

    def test_expiry_on_empty_book_is_safe(self):
        self.assertEqual(self.t.expire_stale_orders(), [])

    def test_strategy_fade_expires_when_the_cascade_does_not_revert(self):
        trader = PaperTrader(100_000.0)
        strat = LiquidationFadeStrategy(trader, regime_enabled=False)
        order = strat.on_liquidation_event(
            {"coin": "SKR", "side": "A", "notional": 5_000.0, "notional_oi": 1e6}, 10.0
        )
        self.assertEqual(order["status"], "OPEN")

        # It would fill right now, while the thesis is still live...
        self.assertEqual(len(strat.on_liquidation_batch([], {"SKR": 9.0})["filled"]), 1)

        # ...but an order left resting past its TTL must not.
        trader2 = PaperTrader(100_000.0)
        strat2 = LiquidationFadeStrategy(trader2, regime_enabled=False)
        stale = strat2.on_liquidation_event(
            {"coin": "SKR", "side": "A", "notional": 5_000.0, "notional_oi": 1e6}, 10.0
        )
        stale["placed_at"] -= int((FADE_ORDER_TTL_SECONDS + 60) * 1000)
        out = strat2.on_liquidation_batch([], {"SKR": 9.0})
        self.assertEqual(out["filled"], [])
        self.assertNotIn("SKR", trader2.positions)


# --------------------------------------------------------------------------
# Task 2: exotic thresholds
# --------------------------------------------------------------------------

class TestSqueezeOiFloor(unittest.TestCase):
    def test_floor_lowered_to_admit_thin_exotics(self):
        self.assertEqual(SQUEEZE_MIN_NOTIONAL_OI, 100_000.0)

    def test_markets_in_the_newly_admitted_band(self):
        """$100k-$200k OI perps are exactly the thinnest books that squeeze hardest."""
        for oi in (100_000.0, 150_000.0, 200_000.0):
            self.assertGreaterEqual(oi, SQUEEZE_MIN_NOTIONAL_OI)

    def test_dust_markets_are_still_excluded(self):
        self.assertLess(50_000.0, SQUEEZE_MIN_NOTIONAL_OI)


class TestWhaleDiscoveryTiers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.tmp.name) / "w.db")
        self.users = Path(self.tmp.name) / "users.txt"
        self.tracker = WhaleTracker(
            users_file_path=str(self.users), auto_scan_portfolio=False
        )

    def tearDown(self):
        self.db.close()
        DatabaseManager._instance = None
        try:
            self.tmp.cleanup()
        except (OSError, PermissionError):
            pass

    def _fill(self, coin, notional, addr):
        return self.tracker.on_trade_fill(
            {"coin": coin, "px": "10", "sz": str(notional / 10.0), "users": [addr]}
        )

    def test_configured_tiers(self):
        self.assertEqual(WHALE_DISCOVERY_MIN_NOTIONAL_CORE, 25_000.0)
        self.assertEqual(WHALE_DISCOVERY_MIN_NOTIONAL_EXOTIC, 7_500.0)

    def test_core_market_keeps_the_high_floor(self):
        self.assertEqual(self.tracker.discovery_floor_for("BTC"), 25_000.0)

    def test_exotic_market_uses_the_low_floor(self):
        self.assertEqual(self.tracker.discovery_floor_for("SKR"), 7_500.0)

    def test_exotic_fill_above_the_exotic_floor_discovers(self):
        """Previously ignored: the counterparties to exotic cascades."""
        found = self._fill("SKR", 8_000.0, "0x" + "a" * 40)
        self.assertEqual(len(found), 1)

    def test_same_fill_on_a_core_market_does_not_discover(self):
        self.assertEqual(self._fill("BTC", 8_000.0, "0x" + "b" * 40), [])

    def test_exotic_dust_is_still_ignored(self):
        self.assertEqual(self._fill("SKR", 5_000.0, "0x" + "c" * 40), [])

    def test_large_core_fill_still_discovers(self):
        self.assertEqual(len(self._fill("BTC", 30_000.0, "0x" + "d" * 40)), 1)

    def test_boundaries_are_inclusive(self):
        self.assertEqual(len(self._fill("SKR", 7_500.0, "0x" + "e" * 40)), 1)
        self.assertEqual(len(self._fill("BTC", 25_000.0, "0x" + "f" * 40)), 1)


class TestExoticAlertTier(unittest.TestCase):
    def test_configured_tier(self):
        self.assertEqual(ALERT_EXOTIC_MIN_NOTIONAL, 2_500.0)
        self.assertEqual(ALERT_EXOTIC_MIN_SLIPPAGE_PCT, 1.5)

    def test_qualifying_exotic_sweep(self):
        self.assertTrue(WebhookAlerter.qualifies_as_exotic_sweep(2_500.0, 1.5))
        self.assertTrue(WebhookAlerter.qualifies_as_exotic_sweep(10_000.0, 3.0))

    def test_below_notional_is_rejected(self):
        self.assertFalse(WebhookAlerter.qualifies_as_exotic_sweep(2_400.0, 1.5))

    def test_below_slippage_is_rejected(self):
        """Size without violence is ordinary flow, not a forced exit."""
        self.assertFalse(WebhookAlerter.qualifies_as_exotic_sweep(2_500.0, 1.4))

    def test_slippage_direction_does_not_matter(self):
        self.assertTrue(WebhookAlerter.qualifies_as_exotic_sweep(2_500.0, -1.6))

    def test_zero_slippage_never_qualifies(self):
        self.assertFalse(WebhookAlerter.qualifies_as_exotic_sweep(1_000_000.0, 0.0))

    def test_alert_dispatch_is_inert_without_webhooks(self):
        """No configured webhook must be a silent no-op, never an exception."""
        alerter = WebhookAlerter(discord_webhook_url=None,
                                 telegram_bot_token=None, telegram_chat_id=None)
        self.assertFalse(alerter.enabled)
        alerter.alert_exotic_sweep("SKR", "A", 9.8, 3_000.0, 1.8, 10.0)

    def test_exotic_alert_builds_without_a_mark(self):
        alerter = WebhookAlerter(discord_webhook_url=None,
                                 telegram_bot_token=None, telegram_chat_id=None)
        alerter.alert_exotic_sweep("SKR", "B", 10.2, 3_000.0, 2.0)


if __name__ == "__main__":
    unittest.main()
