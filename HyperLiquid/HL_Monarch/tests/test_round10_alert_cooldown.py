"""
Round 10 tests: per-coin webhook alert cooldown.

Fully offline - no webhook is ever contacted; the cooldown gate is asserted
directly, and dispatch is verified to be a silent no-op without configuration.
"""

import threading
import unittest

from analytics.alerter import WebhookAlerter
from config.settings import ALERT_COOLDOWN_SECONDS


def alerter(**kw):
    """An alerter that believes it is configured, without a reachable webhook."""
    kw.setdefault("discord_webhook_url", "https://example.invalid/hook")
    return WebhookAlerter(**kw)


class TestAlertCooldown(unittest.TestCase):
    def setUp(self):
        self.a = alerter()

    def test_cooldown_is_sixty_seconds(self):
        self.assertEqual(ALERT_COOLDOWN_SECONDS, 60.0)
        self.assertEqual(self.a.cooldown_seconds, 60.0)

    def test_first_alert_for_a_coin_passes(self):
        self.assertTrue(self.a.should_send("whale", "SKR", now=0.0))

    def test_second_alert_within_the_window_is_suppressed(self):
        self.a.should_send("whale", "SKR", now=0.0)
        self.assertFalse(self.a.should_send("whale", "SKR", now=30.0))

    def test_alert_passes_again_after_the_window(self):
        self.a.should_send("whale", "SKR", now=0.0)
        self.assertTrue(self.a.should_send("whale", "SKR", now=61.0))

    def test_boundary_is_exclusive_at_exactly_the_window(self):
        self.a.should_send("whale", "SKR", now=0.0)
        self.assertTrue(self.a.should_send("whale", "SKR", now=ALERT_COOLDOWN_SECONDS))

    def test_a_cascade_collapses_to_one_alert(self):
        """
        The case this exists for: one liquidation cascade prints many qualifying
        fills within seconds and would otherwise emit a dozen near-identical
        webhooks, training readers to ignore the channel.
        """
        sent = sum(
            1 for i in range(12)
            if self.a.should_send("exotic_sweep", "SKR", now=i * 2.0)
        )
        self.assertEqual(sent, 1)
        self.assertEqual(self.a.suppressed_count, 11)

    def test_other_coins_are_unaffected(self):
        self.a.should_send("exotic_sweep", "SKR", now=0.0)
        self.assertTrue(self.a.should_send("exotic_sweep", "XMR", now=1.0))

    def test_other_categories_are_not_masked(self):
        """A margin call must not be swallowed by a whale alert on the same market."""
        self.a.should_send("whale", "SKR", now=0.0)
        self.assertTrue(self.a.should_send("liquidation", "SKR", now=1.0))
        self.assertTrue(self.a.should_send("funding", "SKR", now=1.0))

    def test_coin_key_is_case_insensitive(self):
        self.a.should_send("whale", "SKR", now=0.0)
        self.assertFalse(self.a.should_send("whale", "skr", now=1.0))

    def test_whitespace_in_coin_is_ignored(self):
        self.a.should_send("whale", "SKR", now=0.0)
        self.assertFalse(self.a.should_send("whale", " SKR ", now=1.0))

    def test_zero_cooldown_disables_suppression(self):
        a = alerter(cooldown_seconds=0.0)
        self.assertTrue(all(a.should_send("whale", "SKR", now=float(i)) for i in range(5)))
        self.assertEqual(a.suppressed_count, 0)

    def test_reset_clears_state(self):
        self.a.should_send("whale", "SKR", now=0.0)
        self.a.should_send("whale", "SKR", now=1.0)
        self.assertEqual(self.a.suppressed_count, 1)
        self.a.reset_cooldowns()
        self.assertTrue(self.a.should_send("whale", "SKR", now=2.0))
        self.assertEqual(self.a.suppressed_count, 0)

    def test_margin_alerts_are_keyed_per_address(self):
        """Two accounts in danger on the same market are two separate events."""
        self.assertTrue(self.a.should_send("margin:0xaaaaaaaaaa", "SKR", now=0.0))
        self.assertTrue(self.a.should_send("margin:0xbbbbbbbbbb", "SKR", now=1.0))
        self.assertFalse(self.a.should_send("margin:0xaaaaaaaaaa", "SKR", now=2.0))

    def test_concurrent_callers_cannot_both_pass(self):
        """
        A cascade dispatches from several threads; the check must consume the
        slot atomically or two webhooks escape for the same event.
        """
        a = alerter()
        results = []
        barrier = threading.Barrier(8)

        def race():
            barrier.wait()
            results.append(a.should_send("exotic_sweep", "SKR"))

        threads = [threading.Thread(target=race) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(1 for r in results if r), 1)


class TestAlertEntryPointsRespectCooldown(unittest.TestCase):
    """
    The gate has to live in the alert methods, not only in the helper - otherwise
    every caller has to remember to check it.
    """

    def setUp(self):
        self.a = alerter()
        self.dispatched = []
        self.a._dispatch_alert = lambda *args, **kw: self.dispatched.append(args)

    def test_whale_alerts_are_rate_limited(self):
        for _ in range(5):
            self.a.alert_whale_trade("SKR", "A", 10.0, 30_000.0, is_liq=False)
        self.assertEqual(len(self.dispatched), 1)

    def test_exotic_sweep_alerts_are_rate_limited(self):
        for _ in range(5):
            self.a.alert_exotic_sweep("SKR", "A", 9.8, 3_000.0, 1.8, 10.0)
        self.assertEqual(len(self.dispatched), 1)

    def test_funding_alerts_are_rate_limited(self):
        for _ in range(5):
            self.a.alert_funding_arb("SKR", 300.0, "SHORT_HARVEST")
        self.assertEqual(len(self.dispatched), 1)

    def test_margin_alerts_are_rate_limited_per_address(self):
        for _ in range(3):
            self.a.alert_danger_position("0x" + "a" * 40, "SKR", 2.0, 50_000.0, 9.0)
        self.a.alert_danger_position("0x" + "b" * 40, "SKR", 2.0, 50_000.0, 9.0)
        self.assertEqual(len(self.dispatched), 2)

    def test_liquidation_and_whale_tiers_are_separate(self):
        self.a.alert_whale_trade("SKR", "A", 10.0, 30_000.0, is_liq=False)
        self.a.alert_whale_trade("SKR", "A", 10.0, 30_000.0, is_liq=True)
        self.assertEqual(len(self.dispatched), 2)

    def test_distinct_coins_each_get_through(self):
        for coin in ("SKR", "XMR", "0G"):
            self.a.alert_exotic_sweep(coin, "A", 9.8, 3_000.0, 1.8, 10.0)
        self.assertEqual(len(self.dispatched), 3)


class TestDisabledAlerterIsInert(unittest.TestCase):
    def test_unconfigured_alerter_never_raises(self):
        a = WebhookAlerter(discord_webhook_url=None, telegram_bot_token=None,
                           telegram_chat_id=None)
        self.assertFalse(a.enabled)
        a.alert_whale_trade("SKR", "A", 10.0, 30_000.0)
        a.alert_exotic_sweep("SKR", "A", 9.8, 3_000.0, 1.8, 10.0)
        a.alert_funding_arb("SKR", 300.0, "SHORT_HARVEST")
        a.alert_danger_position("0x" + "a" * 40, "SKR", 2.0, 50_000.0, 9.0)


if __name__ == "__main__":
    unittest.main()
