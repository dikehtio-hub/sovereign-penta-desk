"""
Integration tests for HyperliquidRestClient against live API.
"""
import socket
import unittest
from api.rest_client import HyperliquidRestClient


def api_reachable(host: str = "api.hyperliquid.xyz", timeout: float = 3.0) -> bool:
    """
    Whether the live API can be reached.

    These are integration tests by design - they assert against the real
    Hyperliquid response shape, which is exactly what a mock would stop catching.
    Rather than delete that coverage or fail the suite on a plane, they skip when
    the host is unreachable and run normally when it is.
    """
    try:
        socket.getaddrinfo(host, 443)
    except (socket.gaierror, OSError):
        return False
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


NETWORK_AVAILABLE = api_reachable()

@unittest.skipUnless(NETWORK_AVAILABLE, "live Hyperliquid API unreachable (offline)")
class TestHyperliquidRestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = HyperliquidRestClient()

    def test_get_meta_and_asset_ctxs_main(self):
        res = self.client.get_meta_and_asset_ctxs(dex="main")
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        universe = res[0].get("universe", [])
        self.assertGreater(len(universe), 100)
        self.assertIn("BTC", [u["name"] for u in universe])

    def test_get_meta_and_asset_ctxs_xyz_tradfi(self):
        res = self.client.get_meta_and_asset_ctxs(dex="xyz")
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        universe = res[0].get("universe", [])
        self.assertGreater(len(universe), 50)
        
        symbols = [u["name"] for u in universe]
        for expected in ["xyz:TSLA", "xyz:GOLD", "xyz:XYZ100", "xyz:NVDA"]:
            self.assertIn(expected, symbols)

    def test_get_l2_book(self):
        book = self.client.get_l2_book("xyz:TSLA")
        self.assertIn("levels", book)
        self.assertEqual(len(book["levels"]), 2)
        self.assertGreater(len(book["levels"][0]), 0)  # Bids
        self.assertGreater(len(book["levels"][1]), 0)  # Asks

    def test_get_all_mids(self):
        mids = self.client.get_all_mids()
        self.assertIsInstance(mids, dict)
        self.assertIn("BTC", mids)

if __name__ == "__main__":
    unittest.main()
