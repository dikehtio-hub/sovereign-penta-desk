"""
Integration test for HyperliquidWsClient.
"""
import unittest
import asyncio
from api.ws_client import HyperliquidWsClient

class TestHyperliquidWsClient(unittest.TestCase):
    def test_ws_connection_and_subscription(self):
        async def run_test():
            client = HyperliquidWsClient()
            received_messages = []

            def on_trade(trade_data):
                received_messages.append(trade_data)

            client.register_handler("trades", on_trade)

            ws_task = asyncio.create_task(client.start())
            await asyncio.sleep(1.0)

            await client.subscribe_trades("xyz:TSLA")
            await client.subscribe_all_mids()

            # Wait up to 3 seconds for connection and ping
            await asyncio.sleep(2.0)
            await client.stop()
            try:
                await asyncio.wait_for(ws_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
