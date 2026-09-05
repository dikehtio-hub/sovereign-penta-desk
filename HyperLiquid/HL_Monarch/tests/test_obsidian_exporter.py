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


class TestClockInvariantHash(unittest.TestCase):
    """
    Round 69 (Ruling 68-1). The cockpit notes carry clocks INSIDE substantive
    lines: the collector's "Ns ago" beside its PID, a position's Duration and
    Realised APR beside its accrued funding. The hash must ignore the clocks
    and keep the state, so a stationary market syncs "unchanged" while a
    restart, an accrual, a price or a config change still rewrites.
    """

    BOT_CONTROL = ("> - **HyperLiquid Ingestion Collector**: 🟢 **ONLINE (PID: {pid})** • SQLite DB Updated: `{db}s ago`\n"
                   "> - **Polymarket Engine**: ⚪ **IDLE ({poly}s ago)**\n")
    POSITION = ("| **`XPL`** | `UXPL` | $10.0K | `$0.0843` | `$0.0843` | `{entry}` | `{realised}` | **`{accrued}`** | `{hours}h` |\n")

    def note(self, pid=38548, db=0, poly=268150, entry="+31.58%", realised="+19.56%", accrued="+$4.02", hours="46.2"):
        return (self.BOT_CONTROL.format(pid=pid, db=db, poly=poly)
                + self.POSITION.format(entry=entry, realised=realised, accrued=accrued, hours=hours))

    def test_clocks_are_ignored_and_state_is_not(self):
        from analytics.obsidian_links import content_hash, normalize_for_hash
        base = self.note()
        ticked = self.note(db=14, poly=268165, realised="+19.55%", hours="46.3")   # fifteen seconds later
        self.assertNotEqual(base, ticked)
        self.assertEqual(content_hash(base), content_hash(ticked))
        for changed in (self.note(pid=46740), self.note(accrued="+$4.20"), self.note(entry="+32.00%")):
            self.assertNotEqual(content_hash(base), content_hash(changed), changed)
        norm = normalize_for_hash(base)
        self.assertIn("ONLINE (PID: 38548)", norm)
        self.assertIn("DB Updated: `<VOLATILE_TIME>`", norm)
        self.assertIn("IDLE (<VOLATILE_TIME>)", norm)
        self.assertIn("`+31.58%` | `<VOLATILE_APR>` | **`+$4.02`** | `<VOLATILE_TIME>`", norm)
        self.assertNotIn("46.2h", norm)
        # Percentages that are not the Realised APR cell are untouched.
        self.assertIn("`+31.58%`", norm)
        self.assertEqual(normalize_for_hash("> - **Funding Rate Arbitrage Opportunities**: `43` liquid pairs (> 25% APR)"),
                         "> - **Funding Rate Arbitrage Opportunities**: `43` liquid pairs (> 25% APR)")


class TestMarketNoteThrottle(unittest.TestCase):
    """Round 70 (Ruling 69-2): an optional cooldown on HyperLiquid_Monarch.md rewrites, judged on mtime."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_dir = Path(self.temp_dir.name) / "vault"
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "export.db")
        self.repo = MarketRepository(self.db)

    def tearDown(self):
        self.db.close()
        DatabaseManager._instance = None
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError):
            pass

    def test_the_throttle_skips_only_the_market_note_and_only_while_it_is_fresh(self):
        import os
        import time
        from analytics.obsidian_exporter import market_note_throttled

        master = export_hyperliquid_to_obsidian(str(self.vault_dir), repo=self.repo, write_whale_notes=False)
        stats = export_hyperliquid_to_obsidian.last_write_stats
        self.assertTrue(master.exists())
        self.assertEqual((stats["master_throttled"], stats["throttle_seconds"]), (False, 0.0))
        # Fresh note + a 300 s throttle: the market note is not rewritten, the companions still sync.
        os.utime(master, None)
        before = master.stat().st_mtime
        export_hyperliquid_to_obsidian(str(self.vault_dir), repo=self.repo, write_whale_notes=False, throttle_seconds=300)
        stats = export_hyperliquid_to_obsidian.last_write_stats
        self.assertTrue(stats["master_throttled"])
        self.assertFalse(stats["master_written"])
        self.assertEqual(master.stat().st_mtime, before)
        self.assertTrue((self.vault_dir / "Bot_Control.md").exists())
        # Older than the throttle: eligible again (unchanged content is then skipped by the hash, not the throttle).
        old = time.time() - 600
        os.utime(master, (old, old))
        export_hyperliquid_to_obsidian(str(self.vault_dir), repo=self.repo, write_whale_notes=False, throttle_seconds=300)
        self.assertFalse(export_hyperliquid_to_obsidian.last_write_stats["master_throttled"])
        # The predicate itself: 0 never throttles; a missing note never throttles; the boundary is strict.
        self.assertFalse(market_note_throttled(master, 0))
        self.assertFalse(market_note_throttled(self.vault_dir / "missing.md", 300))
        os.utime(master, None)
        self.assertTrue(market_note_throttled(master, 300))
        self.assertFalse(market_note_throttled(master, 300, now=master.stat().st_mtime + 300))


class TestLaunchersCarryTheThrottle(unittest.TestCase):
    """
    Round 71 (Ruling 70-1): the 24/7 launchers run the HL obsidian watcher with a 60 s
    market-dashboard throttle; on-demand CLI calls stay unthrottled (code default 0).
    Pinned here because a launcher line is configuration nobody else tests.
    """

    def test_every_watcher_launcher_passes_throttle_seconds_60(self):
        hl_root = Path(__file__).resolve().parents[1]
        dev_root = hl_root.parents[1]
        launchers = [dev_root / "start_all_ecosystem_sync.bat",
                     hl_root / "scripts" / "launchers" / "start_obsidian_sync.bat"]
        for bat in launchers:
            self.assertTrue(bat.exists(), bat)
            lines = [l for l in bat.read_text(encoding="utf-8", errors="replace").splitlines()
                     if "main.py obsidian" in l and "--watch" in l]
            self.assertTrue(lines, "%s starts no HL obsidian watcher" % bat.name)
            for line in lines:
                self.assertIn("--throttle-seconds 60", line, "%s: %s" % (bat.name, line))
        # The code default stays unthrottled for on-demand calls.
        import inspect
        from analytics.obsidian_exporter import export_hyperliquid_to_obsidian as export_fn
        self.assertEqual(inspect.signature(export_fn).parameters["throttle_seconds"].default, 0.0)
