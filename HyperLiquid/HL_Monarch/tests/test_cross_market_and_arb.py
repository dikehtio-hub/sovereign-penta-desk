"""
Tests for the Antigravity audit follow-ups:
  Task A - SHA-256 dirty-checking of Obsidian notes
  Task C - Funding arbitrage tradeability gates

All offline: synthetic SQLite databases and temp vaults, no network.
"""

import tempfile
import time
import unittest
from pathlib import Path

from analytics import obsidian_links as links
from analytics.funding_arbitrage import FundingArbitrageEngine


# --------------------------------------------------------------------------
# Task A: content-hash dirty checking
# --------------------------------------------------------------------------

class TestContentHashing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.note = Path(self.tmp.name) / "n.md"

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _note(ts: str, equity: str = "$100") -> str:
        return (
            f'---\nlast_synced: "{ts}"\n---\n\n# Note\n\n'
            f"> - **Last Updated**: `{ts}`\n\nEquity: {equity}\n"
        )

    def test_first_write_creates_file(self):
        path, written = links.write_note_if_changed(self.note, self._note("T1"))
        self.assertTrue(written)
        self.assertTrue(path.exists())

    def test_timestamp_only_change_is_not_written(self):
        """
        The whole point of Task A: notes carry a per-sync timestamp, so hashing
        raw content would mark everything dirty every pass and save nothing.
        """
        links.write_note_if_changed(self.note, self._note("T1"))
        _, written = links.write_note_if_changed(self.note, self._note("T2"))
        self.assertFalse(written)

    def test_mtime_is_untouched_when_skipped(self):
        """Obsidian re-indexes on mtime, so a skip must not touch the file."""
        links.write_note_if_changed(self.note, self._note("T1"))
        before = self.note.stat().st_mtime_ns
        time.sleep(0.01)
        links.write_note_if_changed(self.note, self._note("T2"))
        self.assertEqual(self.note.stat().st_mtime_ns, before)

    def test_substantive_change_is_written(self):
        links.write_note_if_changed(self.note, self._note("T1", "$100"))
        _, written = links.write_note_if_changed(self.note, self._note("T2", "$999"))
        self.assertTrue(written)
        self.assertIn("$999", self.note.read_text(encoding="utf-8"))

    def test_unreadable_note_is_rewritten_not_skipped(self):
        self.note.write_bytes(b"\xff\xfe\x00corrupt")
        _, written = links.write_note_if_changed(self.note, self._note("T1"))
        self.assertTrue(written)

    def test_hash_ignores_only_the_declared_volatile_fields(self):
        a = links.content_hash(self._note("T1"))
        b = links.content_hash(self._note("T2"))
        c = links.content_hash(self._note("T1", "$5"))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_trailing_whitespace_drift_is_not_a_change(self):
        links.write_note_if_changed(self.note, "# A\n\nbody\n")
        _, written = links.write_note_if_changed(self.note, "# A   \n\nbody   \n")
        self.assertFalse(written)


# --------------------------------------------------------------------------
# Task B: cross-market titan scanner
# --------------------------------------------------------------------------

HL_SCHEMA = """
CREATE TABLE whale_wallets (
    address TEXT PRIMARY KEY, account_value REAL, total_position_value REAL,
    first_coin TEXT, first_notional REAL, is_liquidator INT, discovered_at INT
);
"""

PM_SCHEMA = """
CREATE TABLE sharp_traders (
    wallet TEXT PRIMARY KEY, pseudonym TEXT, pnl_7d REAL, volume_7d REAL,
    trades_7d INT, win_rate REAL, is_sharp INT, polymarket_link TEXT,
    last_scanned TEXT, realized_pnl_7d REAL, unrealized_pnl REAL,
    open_positions INT, closed_positions_7d INT, volume_is_partial INT
);
"""
def _snap(coin, funding, oi, vol, px=100.0):
    return {
        "coin": coin, "dex": "main", "mark_px": px, "notional_oi": oi,
        "day_ntl_vlm": vol, "funding_rate": funding,
    }


class FakeSpreadClient:
    """Returns a scripted L2 book so spread filtering can be tested offline."""

    def __init__(self, spreads):
        self.spreads = spreads
        self.calls = []

    def get_l2_book(self, coin):
        self.calls.append(coin)
        if coin not in self.spreads:
            raise RuntimeError("no book")
        bid, ask = self.spreads[coin]
        return {"levels": [[{"px": str(bid), "sz": "10"}], [{"px": str(ask), "sz": "10"}]]}


class TestFundingTradeability(unittest.TestCase):
    def setUp(self):
        self.engine = FundingArbitrageEngine()

    def test_low_oi_market_is_rejected_not_listed(self):
        snaps = [_snap("DEADCOIN", 0.001, oi=10_000.0, vol=5_000_000.0)]
        res = self.engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=snaps)
        self.assertEqual(res["short_harvest"], [])
        self.assertEqual(len(res["rejected"]), 1)
        self.assertIn("OI", res["rejected"][0]["reject_reason"])

    def test_no_volume_market_is_rejected(self):
        """OI without turnover cannot be exited, whatever the quoted funding."""
        snaps = [_snap("STALE", 0.001, oi=50_000_000.0, vol=1_500.0)]
        res = self.engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=snaps)
        self.assertEqual(res["short_harvest"], [])
        self.assertIn("volume", res["rejected"][0]["reject_reason"])

    def test_liquid_market_passes(self):
        snaps = [_snap("BTC", 0.001, oi=50_000_000.0, vol=20_000_000.0)]
        res = self.engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=snaps)
        self.assertEqual(len(res["short_harvest"]), 1)
        self.assertTrue(res["short_harvest"][0]["tradeable"])
        self.assertEqual(res["rejected"], [])

    def test_negative_funding_routes_to_long_harvest(self):
        snaps = [_snap("ETH", -0.001, oi=50_000_000.0, vol=20_000_000.0)]
        res = self.engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=snaps)
        self.assertEqual(len(res["long_harvest"]), 1)
        self.assertEqual(res["long_harvest"][0]["strategy"], "LONG_HARVEST")

    def test_thresholds_are_overridable(self):
        snaps = [_snap("SMALL", 0.001, oi=60_000.0, vol=200_000.0)]
        strict = self.engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=snaps)
        loose = self.engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=snaps, min_notional_oi=50_000.0
        )
        self.assertEqual(strict["short_harvest"], [])
        self.assertEqual(len(loose["short_harvest"]), 1)

    def test_wide_spread_moves_opportunity_to_rejected(self):
        engine = FundingArbitrageEngine(client=FakeSpreadClient({"WIDE": (100.0, 102.0)}))
        snaps = [_snap("WIDE", 0.001, oi=50_000_000.0, vol=20_000_000.0)]
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=snaps, check_spreads=True
        )
        self.assertEqual(res["short_harvest"], [])
        self.assertIn("spread", res["rejected"][0]["reject_reason"])

    def test_tight_spread_survives_and_is_recorded(self):
        engine = FundingArbitrageEngine(client=FakeSpreadClient({"TIGHT": (100.0, 100.05)}))
        snaps = [_snap("TIGHT", 0.001, oi=50_000_000.0, vol=20_000_000.0)]
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=snaps, check_spreads=True
        )
        self.assertEqual(len(res["short_harvest"]), 1)
        self.assertLess(res["short_harvest"][0]["spread_bps"], 25.0)

    def test_unavailable_book_keeps_row_but_unverified(self):
        """A fetch failure must not silently delete a possibly good opportunity."""
        engine = FundingArbitrageEngine(client=FakeSpreadClient({}))
        snaps = [_snap("NOBOOK", 0.001, oi=50_000_000.0, vol=20_000_000.0)]
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=snaps, check_spreads=True
        )
        self.assertEqual(len(res["short_harvest"]), 1)
        self.assertIsNone(res["short_harvest"][0]["spread_bps"])

    def test_spread_checks_are_capped(self):
        """Each check spends rate-limit budget, so only the ranked head is probed."""
        client = FakeSpreadClient({f"C{i}": (100.0, 100.01) for i in range(30)})
        engine = FundingArbitrageEngine(client=client)
        snaps = [_snap(f"C{i}", 0.001, oi=50_000_000.0, vol=20_000_000.0) for i in range(30)]
        engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=snaps, check_spreads=True, spread_check_limit=5
        )
        self.assertLessEqual(len(client.calls), 5)

    def test_spread_checks_skipped_entirely_by_default(self):
        client = FakeSpreadClient({"BTC": (100.0, 100.01)})
        engine = FundingArbitrageEngine(client=client)
        snaps = [_snap("BTC", 0.001, oi=50_000_000.0, vol=20_000_000.0)]
        engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=snaps)
        self.assertEqual(client.calls, [])

    def test_net_apr_charges_the_spread_against_gross(self):
        gross = {"funding_apr": 300.0, "spread_bps": 10.0}
        net = FundingArbitrageEngine.net_apr_after_spread(gross)
        self.assertLess(net, 300.0)
        # Unknown spread must not fabricate a cost.
        self.assertEqual(
            FundingArbitrageEngine.net_apr_after_spread({"funding_apr": 300.0, "spread_bps": None}),
            300.0,
        )

    def test_net_apr_shrinks_magnitude_for_negative_funding(self):
        net = FundingArbitrageEngine.net_apr_after_spread(
            {"funding_apr": -300.0, "spread_bps": 10.0}
        )
        self.assertGreater(net, -300.0)


if __name__ == "__main__":
    unittest.main()
