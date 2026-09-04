"""
Unit tests for HL_Monarch Obsidian exporter.
Verifies Markdown generation, TradFi table formatting, funding arbitrage rendering,
and custom Obsidian vault path resolution.
"""

import unittest
from pathlib import Path
import tempfile

from analytics.obsidian_exporter import get_vault_path, export_hyperliquid_to_obsidian
from storage.db import DatabaseManager
from storage.repository import MarketRepository


class TestObsidianExporter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_dir = Path(self.temp_dir.name) / "vault"

        # Isolate from the production database. The exporter reads snapshots,
        # whales, liquidations and the titan table; run against the live DB these
        # assertions would pass or fail depending on what the collector happened
        # to have written, and the export itself would touch production state.
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "export.db")
        self.repo = MarketRepository(self.db)

    def tearDown(self):
        self.db.close()
        DatabaseManager._instance = None
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError):
            pass  # Windows can hold the sqlite file briefly after close

    def test_get_vault_path_resolution(self):
        target = self.vault_dir / "my_vault"
        resolved = get_vault_path(str(target))
        self.assertTrue(resolved.exists())
        self.assertTrue(resolved.is_dir())

    def test_export_hyperliquid_to_obsidian(self):
        master_note = export_hyperliquid_to_obsidian(str(self.vault_dir), repo=self.repo)
        self.assertTrue(master_note.exists())

        content = master_note.read_text(encoding="utf-8")
        self.assertIn("# 👑 HyperLiquid Monarch • Market Intelligence", content)
        self.assertIn("Perpetual DEX Terminal Status", content)
        self.assertIn("HIP-3 TradFi Markets", content)
        self.assertIn("Funding Rate Arbitrage Yield Opportunities", content)
        self.assertIn("> [!INFO]", content)

    def test_single_vault_in_workspace(self):
        dev_root = Path(__file__).resolve().parent.parent.parent.parent
        vaults = [p for p in dev_root.glob("**/obsidian_vault") if p.is_dir() and "venv" not in str(p) and ".gemini" not in str(p)]
        # Assert only one primary shared obsidian_vault exists in the workspace
        self.assertEqual(len(vaults), 1, f"Expected 1 unified vault, found: {vaults}")
        self.assertEqual(vaults[0].resolve(), (dev_root / "obsidian_vault").resolve())


if __name__ == "__main__":
    unittest.main()
