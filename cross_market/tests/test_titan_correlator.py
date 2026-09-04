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

        self.correlator = TitanCorrelator(
            hl_db_path=self.hl_db,
            pm_db_path=self.pm_db,
            vault_path=self.vault,
            cache_path=self.cache_path,
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


if __name__ == "__main__":
    unittest.main()
