"""
Offline resilience tests for HyperliquidWsClient dispatch and reconnect behaviour.
These use fakes only - no network required.
"""
import asyncio
import json
import unittest

from api import ws_client as ws_mod
from api.ws_client import HyperliquidWsClient


class FakeWs:
    """Minimal stand-in for a websockets connection."""

    def __init__(self, incoming=None, closes_after=0):
        self.sent = []
        self._incoming = list(incoming or [])
        self.closed = False

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def recv(self):
        if self._incoming:
            return self._incoming.pop(0)
        raise ws_mod.websockets.ConnectionClosed(None, None)

    async def close(self):
        self.closed = True


class TestWsDispatch(unittest.TestCase):
    def test_dispatch_routes_channel_payload(self):
        client = HyperliquidWsClient()
        received = []
        client.register_handler("trades", received.append)
        client._dispatch({"channel": "trades", "data": [{"coin": "BTC"}]})
        self.assertEqual(received, [[{"coin": "BTC"}]])

    def test_dispatch_ignores_pong_and_subscription_ack(self):
        client = HyperliquidWsClient()
        received = []
        client.register_handler("pong", received.append)
        client.register_handler("subscriptionResponse", received.append)
        client._dispatch({"channel": "pong"})
        client._dispatch({"channel": "subscriptionResponse", "data": {}})
        self.assertEqual(received, [])

    def test_dispatch_survives_a_raising_handler(self):
        """One bad callback must not take down the receive loop."""
        client = HyperliquidWsClient()
        seen = []

        def boom(_):
            raise ValueError("handler blew up")

        client.register_handler("trades", boom)
        client.register_handler("trades", seen.append)
        client._dispatch({"channel": "trades", "data": {"coin": "ETH"}})
        self.assertEqual(seen, [{"coin": "ETH"}])

    def test_dispatch_survives_raising_explorer_block_handler(self):
        client = HyperliquidWsClient()

        def boom(_):
            raise RuntimeError("nope")

        client.register_handler("explorerBlock", boom)
        client._dispatch([{"block": 1}])  # must not raise

    def test_dispatch_ignores_non_dict_scalar_frames(self):
        client = HyperliquidWsClient()
        client._dispatch("pong")  # must not raise
        client._dispatch(None)


class TestWsSubscriptions(unittest.TestCase):
    def test_resubscribe_replays_every_topic(self):
        async def run():
            client = HyperliquidWsClient()
            await client.subscribe_trades("BTC")
            await client.subscribe_trades("xyz:GOLD")
            await client.subscribe_all_mids()

            fake = FakeWs()
            await client._resubscribe_all(fake)
            return fake.sent

        sent = asyncio.run(run())
        self.assertEqual(len(sent), 3)
        self.assertTrue(all(m["method"] == "subscribe" for m in sent))
        subs = {json.dumps(m["subscription"], sort_keys=True) for m in sent}
        self.assertIn('{"coin": "BTC", "type": "trades"}', subs)
        self.assertIn('{"type": "allMids"}', subs)

    def test_resubscribe_tolerates_concurrent_subscribe(self):
        """Snapshotting under the lock prevents 'set changed size during iteration'."""
        async def run():
            client = HyperliquidWsClient()
            for i in range(200):
                await client.subscribe_trades(f"COIN{i}")

            fake = FakeWs()

            async def churn():
                for i in range(200, 400):
                    await client.subscribe_trades(f"COIN{i}")
                    await asyncio.sleep(0)

            await asyncio.gather(client._resubscribe_all(fake), churn())
            return len(fake.sent)

        self.assertEqual(asyncio.run(run()), 200)

    def test_stop_closes_socket_and_halts_loop(self):
        async def run():
            client = HyperliquidWsClient()
            client._running = True
            fake = FakeWs()
            client.ws = fake
            await client.stop()
            return client._running, fake.closed

        running, closed = asyncio.run(run())
        self.assertFalse(running)
        self.assertTrue(closed)


class TestWsReconnectBackoff(unittest.TestCase):
    def test_repeated_clean_close_backs_off_instead_of_hot_looping(self):
        """
        A server that closes cleanly every time used to produce a zero-delay
        reconnect loop. Every reconnect path must now sleep.
        """
        delays = []
        attempts = {"n": 0}

        class OneShotConnect:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                attempts["n"] += 1
                return FakeWs()

            async def __aexit__(self, *exc):
                return False

        async def fake_sleep(d):
            delays.append(d)
            if len(delays) >= 4:
                raise asyncio.CancelledError()

        async def run():
            client = HyperliquidWsClient()
            orig_connect, orig_sleep = ws_mod.websockets.connect, asyncio.sleep
            ws_mod.websockets.connect = OneShotConnect
            asyncio.sleep = fake_sleep
            try:
                await client.start()
            except asyncio.CancelledError:
                pass
            finally:
                ws_mod.websockets.connect = orig_connect
                asyncio.sleep = orig_sleep

        asyncio.run(run())
        self.assertGreaterEqual(attempts["n"], 2)
        self.assertTrue(all(d > 0 for d in delays), f"zero-delay reconnect: {delays}")
        # Base delay 1s + up to 0.5s jitter on the first retry.
        self.assertGreaterEqual(delays[0], ws_mod.RECONNECT_BASE_DELAY)


if __name__ == "__main__":
    unittest.main()
