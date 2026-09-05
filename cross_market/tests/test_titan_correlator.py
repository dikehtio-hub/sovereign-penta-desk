"""
Unit tests for Cross-Market Titan & Macro Correlation Agent.
Tests EOA->Proxy address resolution, logarithmic conviction scoring, macro signals, and Obsidian export.
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cross_market.titan_correlator import (
    TitanCorrelator,
    TitanProfile,
    compute_conviction_score,
    preserve_user_notes,
    write_note_if_changed,
    USER_NOTES_HEADER,
)


class TestTitanCorrelator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.vault = self.root / "obsidian_vault"
        self.hl_db = self.root / "hyperliquid_data.db"
        self.pm_db = self.root / "polymarket_whales.db"
        self.cache_path = self.root / "titan_cache.json"

        # Create Mock HyperLiquid DB (EOA addresses)
        conn_hl = sqlite3.connect(str(self.hl_db))
        conn_hl.execute("""
            CREATE TABLE whale_wallets (
                address TEXT PRIMARY KEY,
                account_value REAL,
                total_position_value REAL,
                total_margin_used REAL,
                total_unrealized_pnl REAL,
                leverage REAL,
                is_liquidator INTEGER,
                danger_zone_level INTEGER,
                discovered_at INTEGER,
                first_coin TEXT,
                first_notional REAL
            )
        """)
        # EOA #1
        conn_hl.execute("""
            INSERT INTO whale_wallets VALUES (
                '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                5000000.0, 10000000.0, 1000000.0, 250000.0, 2.0, 0, 0, 1725000000, 'BTC', 100000.0
            )
        """)
        # EOA #2
        conn_hl.execute("""
            INSERT INTO whale_wallets VALUES (
                '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                100000.0, 200000.0, 20000.0, 5000.0, 2.0, 0, 0, 1725000000, 'ETH', 50000.0
            )
        """)
        conn_hl.commit()
        conn_hl.close()

        # Create Mock Polymarket DB (Proxy addresses + optional eoa_address)
        conn_pm = sqlite3.connect(str(self.pm_db))
        conn_pm.execute("""
            CREATE TABLE sharp_traders (
                wallet TEXT PRIMARY KEY,
                proxy_wallet TEXT,
                eoa_address TEXT,
                pseudonym TEXT,
                realized_pnl_7d REAL,
                volume_7d REAL,
                closed_positions_7d INTEGER,
                win_rate REAL,
                last_scanned INTEGER
            )
        """)
        # Proxy #1 (resolved from EOA #1 via cache)
        conn_pm.execute("""
            INSERT INTO sharp_traders VALUES (
                '0x1111111111111111111111111111111111111111',
                '0x1111111111111111111111111111111111111111',
                NULL,
                'SharpTitan-Alpha',
                45000.0, 750000.0, 18, 75.0, 1725000000
            )
        """)
        # Proxy #2 (has eoa_address matching EOA #2 directly in DB)
        conn_pm.execute("""
            INSERT INTO sharp_traders VALUES (
                '0x2222222222222222222222222222222222222222',
                '0x2222222222222222222222222222222222222222',
                '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                'SharpTitan-Beta',
                12000.0, 150000.0, 8, 62.5, 1725000000
            )
        """)
        conn_pm.commit()
        conn_pm.close()

        # Write cache mapping EOA #1 -> Proxy #1
        cache_data = {
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                "proxy_wallet": "0x1111111111111111111111111111111111111111",
                "pseudonym": "SharpTitan-Alpha",
            }
        }
        self.cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        self.empty_drops = self.root / "empty_drops"
        self.empty_drops.mkdir(exist_ok=True)

        self.correlator = TitanCorrelator(
            hl_db_path=self.hl_db,
            pm_db_path=self.pm_db,
            vault_path=self.vault,
            cache_path=self.cache_path,
            drop_dirs=[self.empty_drops],
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError):
            pass

    def test_compute_conviction_score_bounds(self):
        zero_score = compute_conviction_score(0.0, 0.0, 0.0, 0.0)
        self.assertEqual(zero_score, 0.0)

        mid_score = compute_conviction_score(1_000_000.0, 100_000.0, 10_000.0, 60.0)
        self.assertTrue(0.0 < mid_score < 100.0)

        max_score = compute_conviction_score(10_000_000.0, 1_000_000.0, 100_000.0, 100.0)
        self.assertAlmostEqual(max_score, 100.0, delta=1.0)

    def test_scan_titans_eoa_to_proxy_resolution(self):
        """Test that distinct EOA (HyperLiquid) and Proxy (Polymarket) resolve correctly."""
        titans = self.correlator.scan_titans()
        self.assertEqual(len(titans), 2)

        # Titan #1: Resolved via EOA->Proxy cache mapping
        t1 = next(t for t in titans if t.hl_address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(t1.pm_proxy_address, "0x1111111111111111111111111111111111111111")
        self.assertEqual(t1.pseudonym, "SharpTitan-Alpha")
        self.assertEqual(t1.hl_equity, 5000000.0)
        self.assertEqual(t1.pm_volume_7d, 750000.0)
        self.assertTrue(t1.conviction_score > 70.0)

        # Titan #2: Resolved via DB eoa_address match
        t2 = next(t for t in titans if t.hl_address == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertEqual(t2.pm_proxy_address, "0x2222222222222222222222222222222222222222")
        self.assertEqual(t2.pseudonym, "SharpTitan-Beta")
        self.assertEqual(t2.hl_equity, 100000.0)
        self.assertEqual(t2.pm_volume_7d, 150000.0)

    def test_markdown_generation_and_export(self):
        note_path, written = self.correlator.export_to_obsidian()
        self.assertTrue(note_path.exists())
        self.assertTrue(written)

        content = note_path.read_text(encoding="utf-8")
        self.assertIn("# 👑 Cross-Market Titan & Macro Intelligence Desk", content)
        self.assertIn("SharpTitan-Alpha", content)
        self.assertIn("[[Whales/0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", content)
        self.assertIn("[[Wallets/0x1111111111111111111111111111111111111111", content)
        self.assertIn("Macro Co-Positioning & Cross-Venue Signals", content)

        # Clean dirty-hash check
        _, second_written = self.correlator.export_to_obsidian()
        self.assertFalse(second_written)

    def test_user_notes_preservation_across_export(self):
        note_path, _ = self.correlator.export_to_obsidian()
        custom_note = f"\n# Header\n{USER_NOTES_HEADER}\n- Hand-written investigation: Titan is market making on BTC perps.\n"
        note_path.write_text(custom_note, encoding="utf-8")

        self.correlator.export_to_obsidian()
        updated_content = note_path.read_text(encoding="utf-8")
        self.assertIn("Hand-written investigation: Titan is market making on BTC perps.", updated_content)


    def test_cli_report_and_scan(self):
        """
        Round 50 (Ruling 50-2): `python -m cross_market.titan_correlator --report`
        prints the scan and writes nothing; `--scan` prints it and writes the
        note. The macro block is labelled as the static placeholder it is.
        """
        import contextlib
        import io
        from cross_market.titan_correlator import format_cli_report, main

        common = ["--hl-db", str(self.hl_db), "--pm-db", str(self.pm_db),
                  "--vault", str(self.vault), "--cache", str(self.cache_path),
                  "--drops", str(self.empty_drops)]
        note = self.vault / "Cross_Market_Titans.md"

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--report"] + common), 0)
        text = out.getvalue()
        self.assertIn("SCAN REPORT", text)
        self.assertIn("titans matched across HyperLiquid and Polymarket: 2", text)
        self.assertIn("SharpTitan-Alpha", text)
        self.assertIn("[NO LIVE MARKET FOUND]", text)                    # the fixture has no macro markets
        self.assertIn("0 measured, 3 unmeasured", text)
        self.assertFalse(note.exists())                                   # --report writes nothing

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--scan"] + common), 0)
        self.assertIn("SharpTitan-Alpha", out.getvalue())
        self.assertIn("note written", out.getvalue())
        self.assertTrue(note.exists())                                    # --scan writes it

        # The report itself is a pure function: ranked by conviction, empty case honest.
        titans = self.correlator.scan_titans()
        report = format_cli_report(titans, [])
        first = [l for l in report.splitlines() if "SharpTitan" in l]
        self.assertEqual(len(first), 2)
        self.assertTrue(first[0].strip().startswith("SharpTitan-Alpha"))  # the higher conviction ranks first
        self.assertIn("none: no HyperLiquid whale resolves", format_cli_report([], []))


class TestMacroSignals(unittest.TestCase):
    """
    Round 51 (Directive 51-1). The macro block used to be three hard-coded
    narratives. Now every number is looked up - Polymarket probabilities in
    whale_trades or drop files, HyperLiquid flow in the snapshot tables - and
    a missing input is reported as missing, never as a percentage.
    """

    H = 3_600_000

    def setUp(self):
        from cross_market.titan_correlator import HOURS_PER_YEAR
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.hl_db = self.root / "hl.db"
        self.pm_db = self.root / "pm.db"
        self.drops = self.root / "drops"
        self.drops.mkdir()
        self.now = 1_788_566_716_255
        con = sqlite3.connect(str(self.hl_db))
        con.execute("CREATE TABLE latest_snapshots (coin TEXT PRIMARY KEY, timestamp INTEGER, dex TEXT, mark_px REAL, "
                    "mid_px REAL, oracle_px REAL, open_interest REAL, notional_oi REAL, funding_rate REAL, premium REAL, day_ntl_vlm REAL)")
        con.execute("CREATE TABLE asset_snapshots (id INTEGER PRIMARY KEY, timestamp INTEGER, coin TEXT, dex TEXT, mark_px REAL, "
                    "mid_px REAL, oracle_px REAL, open_interest REAL, notional_oi REAL, funding_rate REAL, premium REAL, day_ntl_vlm REAL)")
        # now: BTC 1e-5/h on $3B, ETH 2e-5/h on $2B, SOL -1e-5/h on $1B; 24h ago the OI was 5% lower for each.
        rows = [("BTC", 3e9, 1e-5), ("ETH", 2e9, 2e-5), ("SOL", 1e9, -1e-5)]
        for coin, oi, rate in rows:
            con.execute("INSERT INTO latest_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (coin, self.now, "main", 100.0, 100.0, 100.0, 1.0, oi, rate, 0.0, 1e6))
            con.execute("INSERT INTO asset_snapshots (timestamp, coin, dex, mark_px, notional_oi, funding_rate) VALUES (?,?,?,?,?,?)",
                        (self.now - 25 * self.H, coin, "main", 95.0, oi / 1.05, rate))
        con.commit()
        con.close()
        self.expected_apr = ((1e-5 * 3e9 + 2e-5 * 2e9 - 1e-5 * 1e9) / 6e9) * HOURS_PER_YEAR * 100.0

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError):
            pass

    def _pm_db(self, rows):
        con = sqlite3.connect(str(self.pm_db))
        con.execute("CREATE TABLE whale_trades (id INTEGER PRIMARY KEY, tx_hash TEXT, timestamp INTEGER, wallet TEXT, "
                    "pseudonym TEXT, market_title TEXT, market_slug TEXT, outcome TEXT, side TEXT, price REAL, size REAL, "
                    "usd_notional REAL, condition_id TEXT, asset TEXT)")
        for ts, title, outcome, price in rows:
            con.execute("INSERT INTO whale_trades (timestamp, market_title, outcome, price) VALUES (?,?,?,?)",
                        (ts, title, outcome, price))
        con.commit()
        con.close()

    def test_perp_flow_is_measured_from_the_snapshot_tables(self):
        from cross_market.titan_correlator import measure_perp_flow, describe_perp_flow
        flow = measure_perp_flow(self.hl_db)
        self.assertTrue(flow["measured"])
        self.assertAlmostEqual(flow["weighted_funding_apr"], self.expected_apr, places=6)
        self.assertAlmostEqual(flow["total_oi"], 6e9)
        self.assertAlmostEqual(flow["oi_change_pct"], 5.0, places=6)
        self.assertEqual(set(flow["coins"]), {"BTC", "ETH", "SOL"})
        text = describe_perp_flow(flow)
        self.assertIn("Longs paying", text)
        self.assertIn("+5.0% / 24h", text)
        # A cold database measures nothing and says why.
        cold = measure_perp_flow(self.root / "missing.db")
        self.assertFalse(cold["measured"])
        self.assertIn("UNMEASURED", describe_perp_flow(cold))

    def test_polymarket_probability_comes_from_trades_or_drops_newest_wins(self):
        from cross_market.titan_correlator import (FED_CUT_KEYWORDS, BTC_MILESTONE_KEYWORDS,
                                                   find_market_probability)
        self._pm_db([(1_788_000_000_000, "Fed rate cut in September?", "Yes", 0.88),
                     (1_787_000_000_000, "Fed rate cut in September?", "No", 0.30)])
        fed = find_market_probability(FED_CUT_KEYWORDS, [self.drops], self.pm_db)
        self.assertAlmostEqual(fed["probability"], 0.88)
        self.assertIn("whale_trades", fed["source"])
        # A NO fill is inverted; the newest trade wins regardless of source order.
        self._newer_drop("Will Bitcoin hit $100k in 2026?", "0.64", "2026-09-04T22:00:00Z")
        btc = find_market_probability(BTC_MILESTONE_KEYWORDS, [self.drops], self.pm_db)
        self.assertAlmostEqual(btc["probability"], 0.64)
        self.assertTrue(btc["source"].startswith("drop "))
        self.assertIsNone(find_market_probability((("nothing", "matches"),), [self.drops], self.pm_db))
        self.assertIsNone(find_market_probability(FED_CUT_KEYWORDS, [self.root / "absent"], self.root / "absent.db"))

    def _newer_drop(self, question, yes_price, fetched_at, name="polymarket_macro.json"):
        (self.drops / name).write_text(json.dumps([{"question": question, "yes_price": yes_price, "yes_bid": "0.6",
                                                    "token_id": "t", "fetched_at": fetched_at}]), encoding="utf-8")

    def test_signals_are_built_from_measured_inputs_and_degrade_honestly(self):
        from cross_market.titan_correlator import (TitanCorrelator, NO_LIVE_MARKET, build_macro_signals,
                                                   co_positioning_state, format_cli_report)
        self._pm_db([(1_788_000_000_000, "Fed rate cut in September?", "Yes", 0.88)])
        self._newer_drop("Will Bitcoin hit $100k in 2026?", "0.30", "2026-09-04T22:00:00Z")
        c = TitanCorrelator(hl_db_path=self.hl_db, pm_db_path=self.pm_db, vault_path=self.root / "vault",
                            cache_path=self.root / "cache.json", drop_dirs=[self.drops])
        signals = c.detect_macro_signals()
        self.assertEqual([sig.topic for sig in signals],
                         ["Federal Reserve Interest Rate Cut", "Bitcoin Milestone ($100k)", "Crypto Majors Perp Flow (BTC/ETH/SOL)"])
        fed, btc, flow = signals
        self.assertTrue(fed.measured and btc.measured and flow.measured)
        self.assertAlmostEqual(fed.polymarket_probability, 0.88)
        self.assertIn("CONVERGENT", fed.co_positioning_state)             # PM yes, longs paying, OI +5%
        self.assertEqual(fed.signal_strength, "HIGH")
        self.assertAlmostEqual(btc.polymarket_probability, 0.30)
        self.assertIn("DIVERGENT", btc.co_positioning_state)              # PM no, perps long
        self.assertIn("EXPANSION", flow.co_positioning_state)
        self.assertIn("Longs paying", flow.hyperliquid_perp_bias)
        self.assertIn("whale_trades", fed.source)
        # The note renders the measured rows, and the CLI report labels each source.
        markdown = c.generate_markdown([], signals)
        self.assertIn("YES 88% implied", markdown)
        self.assertNotIn("SMT DIVERGENCE", markdown)                        # the old hard-coded narrative is gone
        report = format_cli_report([], signals)
        self.assertIn("3 measured, 0 unmeasured", report)
        self.assertIn("[MEASURED]", report)
        # No markets and a cold HL database: every signal degrades with an explicit tag.
        cold = TitanCorrelator(hl_db_path=self.root / "none.db", pm_db_path=self.root / "none2.db",
                               vault_path=self.root / "vault2", cache_path=self.root / "cache2.json", drop_dirs=[])
        degraded = cold.detect_macro_signals()
        self.assertTrue(all(not sig.measured for sig in degraded))
        self.assertEqual(degraded[0].polymarket_sentiment, NO_LIVE_MARKET)
        self.assertIn("UNMEASURED", degraded[0].co_positioning_state)
        self.assertIn("[UNMEASURED", degraded[2].hyperliquid_perp_bias)
        self.assertIn("0 measured, 3 unmeasured", format_cli_report([], degraded))
        self.assertIn(NO_LIVE_MARKET, cold.generate_markdown([], degraded))
        # The state rules themselves.
        live = {"measured": True, "weighted_funding_apr": 10.0, "oi_change_pct": 3.0}
        self.assertEqual(co_positioning_state(0.9, live)[1], "HIGH")
        self.assertIn("DIVERGENT", co_positioning_state(0.7, {"measured": True, "weighted_funding_apr": -5.0, "oi_change_pct": 1.0})[0])
        self.assertIn("CONVERGENT", co_positioning_state(0.2, {"measured": True, "weighted_funding_apr": -5.0, "oi_change_pct": 0.0})[0])
        self.assertIn("NEUTRAL", co_positioning_state(0.5, live)[0])
        self.assertIn("UNMEASURED", co_positioning_state(None, live)[0])
        self.assertIn("UNMEASURED", co_positioning_state(0.9, {"measured": False})[0])
        self.assertEqual(len(build_macro_signals(None, None, {"measured": False, "note": "cold"})), 3)


if __name__ == "__main__":
    unittest.main()
