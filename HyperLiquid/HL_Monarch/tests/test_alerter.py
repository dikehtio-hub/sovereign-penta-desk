"""
Unit tests for WebhookAlerter.
"""
import unittest
from analytics.alerter import WebhookAlerter

class TestAlerter(unittest.TestCase):
    def test_alerter_disabled_when_no_urls(self):
        alerter = WebhookAlerter()
        self.assertFalse(alerter.enabled)

    def test_alerter_enabled_with_url(self):
        alerter = WebhookAlerter(discord_webhook_url="https://discord.com/api/webhooks/dummy/123")
        self.assertTrue(alerter.enabled)

    def test_alert_whale_trade_dry_run(self):
        alerter = WebhookAlerter()
        # Should not raise any error even when disabled
        alerter.alert_whale_trade("xyz:GOLD", "BUY", 4468.0, 100_000.0, is_liq=False)
        alerter.alert_danger_position("0x0000000000000000000000000000000000000001", "BTC", 1.5, 500_000.0, 76_000.0)

if __name__ == "__main__":
    unittest.main()
