"""
Tests for cross-suite Obsidian vault linking.

Covers the shared-vault layout, conditional cross-suite links, whale note
generation with research preservation, and the liquidation/funding rendering
fixes. No network and no live DB - everything runs against fakes or temp dirs.
"""

import re
import tempfile
import unittest
from pathlib import Path

from analytics import obsidian_links as links
from analytics.obsidian_exporter import (
    export_hyperliquid_to_obsidian,
    format_usd,
    generate_whale_note,
    interleave_opportunities,
    liquidation_side_label,
)

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")


def assert_all_links_resolve(testcase, vault: Path):
    """Every [[wikilink]] in the vault must point at a note that exists."""
    notes = {p.relative_to(vault).with_suffix("").as_posix() for p in vault.rglob("*.md")}
    basenames = {p.stem for p in vault.rglob("*.md")}
    # A canvas is linked WITH its extension ([[Canvases/X.canvas]]), unlike a note.
    canvases = {p.relative_to(vault).as_posix() for p in vault.rglob("*.canvas")}
    broken = []
    for md in vault.rglob("*.md"):
        for target in WIKILINK.findall(md.read_text(encoding="utf-8")):
            t = target.strip()
            if t not in notes and t not in basenames and t not in canvases:
                broken.append(f"{md.relative_to(vault).as_posix()} -> [[{t}]]")
    testcase.assertEqual(broken, [], f"unresolved wikilinks: {broken}")


class FakeRepo:
    """Stands in for MarketRepository with deterministic rows."""

    def __init__(self, whales=None, liqs=None, snapshots=None):
        self._whales = whales if whales is not None else []
        self._liqs = liqs if liqs is not None else []
        self._snapshots = snapshots if snapshots is not None else []

    def get_latest_snapshots(self, coins=None):
        return list(self._snapshots)

    def get_whale_wallets(self, limit=50):
        return list(self._whales)[:limit]

    def get_recent_liquidations(self, limit=50):
        return list(self._liqs)[:limit]


def _whale(addr, equity=1_000_000.0, pos=2_000_000.0, liq_flag=0):
    return {
        "address": addr,
        "account_value": equity,
        "total_position_value": pos,
        "first_coin": "BTC",
        "first_notional": 50_000.0,
        "is_liquidator": liq_flag,
        "discovered_at": 1_788_000_000_000,
    }


class TestLiquidationRendering(unittest.TestCase):
    def test_side_maps_fill_aggressor_to_liquidated_position(self):
        # The DB stores 'B'/'A', never 'LONG'/'SHORT'. A forced sell closes a long.
        self.assertIn("LONG LIQ", liquidation_side_label("A"))
        self.assertIn("SHORT LIQ", liquidation_side_label("B"))

    def test_side_is_not_uniformly_short(self):
        """Regression: every row used to render SHORT LIQ regardless of side."""
        labels = {liquidation_side_label(s) for s in ("A", "B")}
        self.assertEqual(len(labels), 2)

    def test_unknown_side_is_marked_not_guessed(self):
        self.assertIn("UNKNOWN", liquidation_side_label(""))
        self.assertIn("UNKNOWN", liquidation_side_label(None))

    def test_format_usd_keeps_sign(self):
        self.assertEqual(format_usd(-2_500_000), "-$2.50M")
        self.assertEqual(format_usd(1_500), "$1.5K")
        self.assertEqual(format_usd("bad"), "$0.00")


class TestFundingArbSelection(unittest.TestCase):
    def test_both_directions_are_represented(self):
        """Regression: concatenating then slicing showed only short-harvest rows."""
        shorts = [{"coin": f"S{i}", "funding_apr": 100.0} for i in range(50)]
        longs = [{"coin": f"L{i}", "funding_apr": -100.0} for i in range(50)]
        picked = interleave_opportunities(shorts, longs, limit=10)
        self.assertEqual(len(picked), 10)
        self.assertTrue(any(o["coin"].startswith("L") for o in picked))
        self.assertTrue(any(o["coin"].startswith("S") for o in picked))

    def test_handles_one_empty_direction(self):
        shorts = [{"coin": f"S{i}"} for i in range(3)]
        picked = interleave_opportunities(shorts, [], limit=10)
        self.assertEqual([o["coin"] for o in picked], ["S0", "S1", "S2"])


class TestWhaleNotes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_whale_note_is_created_and_linkable(self):
        addr = "0x" + "a" * 40
        note, written = generate_whale_note(_whale(addr), self.vault, "2026-01-01 00:00:00 UTC")
        self.assertTrue(written)
        self.assertTrue(note.exists())
        self.assertEqual(note.parent.name, links.HL_WHALES_DIR)
        body = note.read_text(encoding="utf-8")
        self.assertIn(addr, body)
        self.assertIn(links.HL_DASHBOARD_NOTE, body)

    def test_unchanged_whale_note_reports_not_written(self):
        """Task A: regenerating identical content must skip the write."""
        addr = "0x" + "e" * 40
        _, first = generate_whale_note(_whale(addr), self.vault, "t1")
        _, second = generate_whale_note(_whale(addr), self.vault, "t2")
        self.assertTrue(first)
        self.assertFalse(second)

    def test_research_notes_survive_regeneration(self):
        addr = "0x" + "b" * 40
        note, _ = generate_whale_note(_whale(addr), self.vault, "t1")
        original = note.read_text(encoding="utf-8")
        note.write_text(original + "\n- **Thesis**: my private edge\n", encoding="utf-8")

        generate_whale_note(_whale(addr, equity=9_999.0), self.vault, "t2")
        refreshed = note.read_text(encoding="utf-8")
        self.assertIn("my private edge", refreshed)
        self.assertIn("t2", refreshed)  # metrics still refreshed

    def test_heuristic_flag_does_not_claim_system_liquidator(self):
        """
        whale_tracker's is_liquidator means "no liquidationPx", not "backstop
        liquidator". Only the curated address set may earn that title.
        """
        addr = "0x" + "c" * 40
        note, _ = generate_whale_note(_whale(addr, liq_flag=1), self.vault, "t1")
        body = note.read_text(encoding="utf-8")
        self.assertNotIn("System Liquidator", body)
        self.assertIn("well collateralised", body)

    def test_known_system_liquidator_is_labelled(self):
        from config.settings import HL_SYSTEM_LIQUIDATOR_ADDRESSES
        addr = sorted(HL_SYSTEM_LIQUIDATOR_ADDRESSES)[0]
        note, _ = generate_whale_note(_whale(addr), self.vault, "t1")
        self.assertIn("System Liquidator", note.read_text(encoding="utf-8"))


class TestCrossSuiteLinking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir(parents=True)
        self.repo = FakeRepo(
            whales=[_whale("0x" + "d" * 40)],
            liqs=[{"coin": "BTC", "side": "A", "px": 70000.0, "notional": 125_000.0, "time": 1_788_000_000_000}],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_counterpart_link_omitted_when_suite_absent(self):
        self.assertIsNone(links.counterpart_link(self.vault, links.PM_DASHBOARD_NOTE, "PM"))

    def test_counterpart_link_emitted_when_suite_present(self):
        (self.vault / f"{links.PM_DASHBOARD_NOTE}.md").write_text("# pm", encoding="utf-8")
        link = links.counterpart_link(self.vault, links.PM_DASHBOARD_NOTE, "PM")
        self.assertEqual(link, f"[[{links.PM_DASHBOARD_NOTE}|PM]]")

    def test_standalone_export_has_no_dangling_links(self):
        export_hyperliquid_to_obsidian(str(self.vault), repo=self.repo)
        body = (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").read_text(encoding="utf-8")
        self.assertNotIn(links.PM_DASHBOARD_NOTE, body)
        assert_all_links_resolve(self, self.vault)

    def test_shared_vault_cross_links_both_ways(self):
        (self.vault / f"{links.PM_DASHBOARD_NOTE}.md").write_text("# pm", encoding="utf-8")
        export_hyperliquid_to_obsidian(str(self.vault), repo=self.repo)

        hl = (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").read_text(encoding="utf-8")
        self.assertIn(f"[[{links.PM_DASHBOARD_NOTE}|", hl)

        hub = (self.vault / f"{links.HUB_NOTE}.md").read_text(encoding="utf-8")
        self.assertIn(links.HL_DASHBOARD_NOTE, hub)
        self.assertIn(links.PM_DASHBOARD_NOTE, hub)
        assert_all_links_resolve(self, self.vault)

    def test_dashboard_links_to_each_whale_note(self):
        export_hyperliquid_to_obsidian(str(self.vault), repo=self.repo)
        body = (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").read_text(encoding="utf-8")
        self.assertIn(f"[[{links.HL_WHALES_DIR}/0x{'d' * 40}|", body)

    def test_liquidation_notional_is_rendered_not_zero(self):
        """Regression: the exporter read a non-existent sz_usd column."""
        export_hyperliquid_to_obsidian(str(self.vault), repo=self.repo)
        body = (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").read_text(encoding="utf-8")
        self.assertIn("$125.0K", body)
        self.assertIn("LONG LIQ", body)  # side 'A' == a long being closed


class TestHubNote(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hub_lists_only_present_suites(self):
        (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").write_text("# hl", encoding="utf-8")
        hub = links.write_hub_note(self.vault, "t1")
        body = hub.read_text(encoding="utf-8")
        self.assertIn(links.HL_DASHBOARD_NOTE, body)
        self.assertNotIn(f"[[{links.PM_DASHBOARD_NOTE}", body)
        assert_all_links_resolve(self, self.vault)

    def test_hub_reports_both_when_shared(self):
        (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").write_text("# hl", encoding="utf-8")
        (self.vault / f"{links.PM_DASHBOARD_NOTE}.md").write_text("# pm", encoding="utf-8")
        body = links.write_hub_note(self.vault, "t1").read_text(encoding="utf-8")
        self.assertIn("Both suites share this vault", body)
        self.assertIn("`2` of 2", body)
        assert_all_links_resolve(self, self.vault)

    def test_hub_warns_when_only_one_suite(self):
        (self.vault / f"{links.HL_DASHBOARD_NOTE}.md").write_text("# hl", encoding="utf-8")
        body = links.write_hub_note(self.vault, "t1").read_text(encoding="utf-8")
        self.assertIn("Only one suite", body)
        self.assertIn("OBSIDIAN_VAULT_PATH", body)


if __name__ == "__main__":
    unittest.main()
