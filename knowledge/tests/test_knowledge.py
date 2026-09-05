"""Master Module 23 tests: frontmatter, pages/ownership, lint L1-L5 + C1/C5, seed.

Everything runs in temporary directories. No network, no real vault, no real
DEV root: the fixture builds its own registry and its own source files so
C1 has something to grep.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from knowledge import EXIT_FINDINGS, EXIT_HALT, EXIT_OK
from knowledge import frontmatter as fm
from knowledge import lint, pages, seed

NOW = datetime(2026, 9, 5, 20, 0, 0, tzinfo=timezone.utc)

FIXTURE_REGISTRY = """\
================================================================================
TIER 1: CORE FOUNDATION & RISK DEFENSE
--------------------------------------------------------------------------------

[x] ITEM 1: SPORTS ODDS INGESTION & FAIR-VALUE (NO-VIG) ENGINE
  - Added:        2026-09-03 21:53 EDT (Round 26L Baseline)
  - What It Does: Pulls multi-bookmaker odds. Strips the vig using Shin's method
    to compute the fair-value probability.
  - Primary Code: Sports_Desk/engine/fair_value.py
                  Sports_Desk/ingestors/odds_fetcher.py
  - Database:     Sports_Desk/data/sports_market.db
  - How to Activate:
      # Ingest sample odds:
      python -m Sports_Desk.ingestors.odds_fetcher --sample
  - Test Command:
      python -m unittest Sports_Desk.tests.test_fair_value

--------------------------------------------------------------------------------
TIER 2: CORE EXECUTION & CROSS-MARKET ALPHA
--------------------------------------------------------------------------------
[ ] ITEM 7: AUTOMATED HEADLESS SPORTS EXECUTION AGENT
  - Added:        Cataloged 2026-09-04 19:43 EDT (Round 50 Milestone)
  - What It Does: Headless browser automation navigating to bookmaker betslips.
  - Status: [ROADMAP] Specification ready; pending live account credentials.

--------------------------------------------------------------------------------
[x] ITEM 12: POLYMARKET BREAKING NEWS & ORACLE LATENCY SNIPER
  - Added:        2026-09-05 (Round 87)
  - What It Does: Pre-registered rules map an event payload to one market.
  - Primary Code: cross_market/latency_sniper.py
  - Test Command:
      python -m unittest cross_market.tests.test_latency_sniper
3. QUICK START
  This top-level line ends the registry block above.
"""


def page_text(type_="Concept", title="A page", description="Says something.", body="# A page\n", **kw) -> str:
    meta = pages.make_meta(type_, title, description, at=NOW, **kw)
    return fm.serialize(meta, body)


class TempVault(unittest.TestCase):
    """A vault + dev_root pair in a temp dir, torn down after each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.dev_root = self.root / "DEV"
        self.vault = self.dev_root / "obsidian_vault"
        for d in ("wiki/concepts", "wiki/rulings", "crm", "journal", "raw", "Whales"):
            (self.vault / d).mkdir(parents=True)
        (self.dev_root / "MASTER_COMMAND_LIST.txt").write_text(FIXTURE_REGISTRY, encoding="utf-8")
        (self.dev_root / "cross_market").mkdir()
        (self.dev_root / "cross_market" / "latency_sniper.py").write_text(
            "def record_loop():\n    pass\n\nNEG = 'neg_risk'\n", encoding="utf-8")
        (self.dev_root / "cross_market" / "amm_rewards.py").write_text(
            "def book_q():\n    'Ruling R5 pending'\n", encoding="utf-8")
        (self.dev_root / "Sports_Desk" / "engine").mkdir(parents=True)
        (self.dev_root / "Sports_Desk" / "engine" / "fair_value.py").write_text("def devig(): pass\n", encoding="utf-8")
        (self.dev_root / "quant_trading_lab").mkdir()
        (self.dev_root / "quant_trading_lab" / "CLAUDE.md").write_text(
            "- Single Trade Risk Budget: 1.0% ($1,000)\n- Hard Daily Drawdown Killswitch: $3,500.00 (3.5%)\n",
            encoding="utf-8")
        (self.dev_root / "AGENTS.md").write_text("# log\n", encoding="utf-8")
        (self.dev_root / "LLM_WIKI_BLUEPRINT.md").write_text("---\ntype: Blueprint\n---\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel: str, text: str) -> Path:
        p = self.vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def findings(self, now=NOW):
        return lint.lint_vault(self.vault, self.dev_root, now=now)

    def codes(self, now=NOW):
        return sorted(f.code for f in self.findings(now))


# ---------------------------------------------------------------- frontmatter

class FrontmatterTests(unittest.TestCase):
    def test_roundtrip_preserves_key_order_and_body(self):
        meta = {"type": "Concept", "title": "T", "dev": {"desk": 3}}
        text = fm.serialize(meta, "# T\n\nbody")
        self.assertTrue(text.startswith("---\ntype: Concept\ntitle: T\n"))
        back, body = fm.parse(text)
        self.assertEqual(back, meta)
        self.assertEqual(body, "# T\n\nbody\n")

    def test_crlf_input_is_accepted(self):
        meta, body = fm.parse("---\r\ntype: X\r\n---\r\nbody\r\n")
        self.assertEqual(meta, {"type": "X"})
        self.assertEqual(body, "body\n")

    def test_missing_block_raises_and_try_parse_reports(self):
        with self.assertRaises(fm.FrontmatterError):
            fm.parse("# no frontmatter\n")
        meta, _, err = fm.try_parse("# no frontmatter\n")
        self.assertIsNone(meta)
        self.assertIn("no frontmatter", err)

    def test_non_mapping_block_raises(self):
        with self.assertRaises(fm.FrontmatterError):
            fm.parse("---\n- a\n- b\n---\n")

    def test_type_is_the_only_required_field(self):
        self.assertEqual(fm.validate({"type": "Ruling"}), [])
        self.assertTrue(any("`type` is required" in i for i in fm.validate({})))
        self.assertTrue(any("`type` is required" in i for i in fm.validate({"type": ""})))

    def test_actor_convention(self):
        for ok in ("human:operator", "process:cross_market.lead_lag", "claude-code/fable-5.1", "antigravity/architect"):
            self.assertTrue(fm.is_actor(ok), ok)
        for bad in ("antigravity", "claude code", "", 5):
            self.assertFalse(fm.is_actor(bad), repr(bad))
        issues = fm.validate({"type": "X", "generated": {"by": "antigravity"}})
        self.assertTrue(any("not an actor" in i for i in issues))

    def test_generated_requires_by_and_iso_at(self):
        self.assertTrue(any(".by is required" in i for i in fm.validate({"type": "X", "generated": {"at": "2026-09-05T00:00:00Z"}})))
        self.assertTrue(any("not ISO 8601" in i for i in fm.validate({"type": "X", "generated": {"by": "human:a", "at": "yesterday"}})))
        self.assertEqual(fm.validate({"type": "X", "generated": {"by": "human:a", "at": "2026-09-05T00:00:00Z"}}), [])

    def test_verified_accepts_mapping_or_list(self):
        self.assertEqual(fm.validate({"type": "X", "verified": {"by": "antigravity/architect"}}), [])
        self.assertEqual(fm.validate({"type": "X", "verified": [{"by": "human:op"}, {"by": "antigravity/architect"}]}), [])
        self.assertTrue(fm.validate({"type": "X", "verified": [{"at": "2026-01-01T00:00:00Z"}]}))

    def test_status_vocabulary_and_stale_after(self):
        self.assertTrue(any("`status`" in i for i in fm.validate({"type": "X", "status": "final"})))
        self.assertEqual(fm.validate({"type": "X", "status": "deprecated", "stale_after": "2026-12-31T00:00:00Z"}), [])
        self.assertTrue(any("stale_after" in i for i in fm.validate({"type": "X", "stale_after": "soon"})))

    def test_sources_require_resource(self):
        issues = fm.validate({"type": "X", "sources": [{"id": "a"}, "not-a-mapping"]})
        self.assertTrue(any("sources[0].resource is required" in i for i in issues))
        self.assertTrue(any("sources[1] must be a mapping" in i for i in issues))
        self.assertEqual(fm.validate({"type": "X", "sources": [{"resource": "git:abc", "author": "human:x"}]}), [])

    def test_dev_namespace_shapes(self):
        good = {"type": "X", "dev": {"desk": 3, "asserts": [{"file": "a.py", "pattern": "def x"}],
                                     "parameters": [{"name": "n", "value": 1, "file": "a.py", "pattern": "n = (\\d+)"}],
                                     "window": {"start": "2026-09-16T17:58:00Z", "end": "2026-09-16T18:05:00Z"}}}
        self.assertEqual(fm.validate(good), [])
        bad = {"type": "X", "dev": {"desk": "three", "asserts": [{"file": "a.py"}],
                                    "parameters": [{"name": "n", "file": "a.py", "pattern": "("}],
                                    "window": {"start": "2026-09-16T18:05:00Z", "end": "2026-09-16T17:58:00Z"}}}
        issues = fm.validate(bad)
        self.assertTrue(any("dev.desk must be an integer" in i for i in issues))
        self.assertTrue(any("dev.asserts[0]" in i for i in issues))
        self.assertTrue(any("dev.parameters[0]" in i for i in issues))
        self.assertTrue(any("window.end must be after" in i for i in issues))
        self.assertTrue(any("not a valid regex" in i for i in fm.validate(
            {"type": "X", "dev": {"asserts": [{"file": "a", "pattern": "("}]}})))

    def test_parse_iso8601_z_and_offsets(self):
        self.assertEqual(fm.parse_iso8601("2026-09-05T20:00:00Z"), NOW)
        self.assertEqual(fm.parse_iso8601("2026-09-05T16:00:00-04:00"), NOW)
        with self.assertRaises(ValueError):
            fm.parse_iso8601(42)


# ---------------------------------------------------------------- pages / ownership

class OwnershipTests(TempVault):
    def test_owned_paths_accepted(self):
        for rel in ("wiki/concepts/x.md", "crm/whales/0x1.md", "journal/2026-09-05.md", "raw/statements/f.txt",
                    "WIKI_SCHEMA.md", "index.md", "log.md"):
            pages.assert_owned(self.vault / rel, self.vault)

    def test_dashboards_entity_notes_and_outside_paths_refused(self):
        for rel in ("Cross_Market_Titans.md", "Whales/0xabc.md", "Wallets/0xabc.md", "Trading_Taxes/x.md",
                    "Monarch_Hub.md", "../cross_market/data/x.json", "wikis/x.md"):
            with self.assertRaises(pages.WriteRefused, msg=rel):
                pages.assert_owned(self.vault / rel, self.vault)

    def test_write_page_validates_then_writes_lf(self):
        p = pages.Page(self.vault / "wiki/concepts/a.md", pages.make_meta("Concept", "A", "d", at=NOW), "# A\n")
        pages.write_page(p, self.vault, now=NOW)
        raw = p.path.read_bytes()
        self.assertNotIn(b"\r\n", raw)
        self.assertTrue(raw.startswith(b"---\ntype: Concept\n"))

    def test_write_page_refuses_invalid_frontmatter(self):
        p = pages.Page(self.vault / "wiki/concepts/a.md", {"title": "no type"}, "")
        with self.assertRaises(fm.FrontmatterError):
            pages.write_page(p, self.vault, now=NOW)
        self.assertFalse(p.path.exists())

    def test_write_page_refuses_dashboard_and_reserved_names(self):
        p = pages.Page(self.vault / "Risk_Sentinel.md", pages.make_meta("Concept", "A", "d", at=NOW), "")
        with self.assertRaises(pages.WriteRefused):
            pages.write_page(p, self.vault, now=NOW)
        p2 = pages.Page(self.vault / "wiki/index.md", pages.make_meta("Concept", "A", "d", at=NOW), "")
        with self.assertRaises(pages.WriteRefused):
            pages.write_page(p2, self.vault, now=NOW)

    def test_write_page_refuses_inside_registration_window(self):
        meta = pages.make_meta("Event", "FOMC", "d", at=NOW,
                               dev={"window": {"start": "2026-09-05T19:58:00Z", "end": "2026-09-05T20:05:00Z"}})
        p = pages.Page(self.vault / "wiki/events/fomc.md", meta, "")
        with self.assertRaises(pages.WriteRefused):
            pages.write_page(p, self.vault, now=NOW)  # NOW is inside the window
        pages.write_page(p, self.vault, now=NOW + timedelta(hours=1))  # outside: allowed
        self.assertTrue(p.path.exists())

    def test_extract_links(self):
        links = pages.extract_links("see [[Desk_03_Cross_Market_Desk|Desk 3]] and [[R4#sec]] and [x](wiki/a.md#h) "
                                    "and [ext](https://example.com)")
        self.assertEqual(links, {"Desk_03_Cross_Market_Desk", "R4", "wiki/a.md"})


class IndexAndLogTests(TempVault):
    def test_build_and_parse_index_roundtrip(self):
        a = pages.Page(self.vault / "wiki/rulings/R4.md", pages.make_meta("Ruling", "R4", "neg_risk", at=NOW), "")
        b = pages.Page(self.vault / "wiki/concepts/c.md", pages.make_meta("Concept", "C", "a concept", at=NOW), "")
        text = pages.build_index([b, a], self.vault)
        self.assertEqual(text.split("\n")[0], "# Ruling")  # PAGE_TYPES order, not insertion order
        entries, errors = pages.parse_index(text)
        self.assertEqual(errors, [])
        self.assertEqual([(e.section, e.title, e.path) for e in entries],
                         [("Ruling", "R4", "wiki/rulings/R4.md"), ("Concept", "C", "wiki/concepts/c.md")])

    def test_parse_index_rejects_off_format_lines(self):
        _, errors = pages.parse_index("# Ruling\n- [R4](wiki/rulings/R4.md) - x\nfree text\n")
        self.assertEqual(len(errors), 2)
        _, errors = pages.parse_index("---\ntype: X\n---\n")
        self.assertTrue(any("must not carry frontmatter" in e for e in errors))

    def test_append_log_groups_by_day_newest_first(self):
        d1 = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
        d2 = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
        pages.append_log(self.vault, "Seed", "first", when=d1)
        pages.append_log(self.vault, "Lint", "second same day", when=d1)
        pages.append_log(self.vault, "Ingest", "next day", when=d2)
        text = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertEqual(text, "## 2026-09-06\n* **Ingest**: next day\n\n## 2026-09-05\n* **Seed**: first\n* **Lint**: second same day\n")
        entries, errors = pages.parse_log(text)
        self.assertEqual(errors, [])
        self.assertEqual([e.action for e in entries], ["Ingest", "Seed", "Lint"])

    def test_parse_log_flags_order_and_format(self):
        _, errors = pages.parse_log("## 2026-09-05\n* **Seed**: a\n## 2026-09-06\n* **Lint**: b\n- bad bullet\n")
        self.assertTrue(any("newest first" in e for e in errors))
        self.assertTrue(any("not a date heading" in e for e in errors))


# ---------------------------------------------------------------- lint

class LintTests(TempVault):
    def clean_pair(self):
        """Two pages linking each other, listed in index.md: lint-clean."""
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n"))
        self.write("wiki/concepts/b.md", page_text(title="B", body="# B\n\nsee [[a]]\n"))
        pages.write_index(self.vault)

    def test_clean_vault_has_no_findings(self):
        self.clean_pair()
        self.assertEqual(self.findings(), [])

    def test_l1_missing_type_and_missing_block(self):
        self.clean_pair()
        self.write("wiki/concepts/c.md", "---\ntitle: no type\n---\n# c\n\n[[a]]\n")
        self.write("wiki/concepts/d.md", "# no frontmatter at all\n\n[[a]]\n")
        codes = self.codes()
        self.assertGreaterEqual(codes.count("L1"), 2)
        msgs = [f.message for f in self.findings() if f.code == "L1"]
        self.assertTrue(any("`type` is required" in m for m in msgs))
        self.assertTrue(any("no frontmatter" in m for m in msgs))

    def test_l2_index_missing_entry_and_dead_path(self):
        self.clean_pair()
        idx = self.vault / "index.md"
        idx.write_text(idx.read_text(encoding="utf-8").replace("* [B](wiki/concepts/b.md) - Says something.\n", "")
                       + "* [Ghost](wiki/concepts/ghost.md) - gone\n", encoding="utf-8")
        f = self.findings()
        self.assertTrue(any(x.code == "L2" and "not listed" in x.message for x in f))
        self.assertTrue(any(x.code == "L2" and "does not exist" in x.message for x in f))

    def test_l2_log_format(self):
        self.clean_pair()
        (self.vault / "log.md").write_text("## 2026-09-05\n* **Seed**: ok\n## 2026-09-06\n* **X**: later\n", encoding="utf-8")
        self.assertTrue(any(x.code == "L2" and "newest first" in x.message for x in self.findings()))

    def test_l3_orphan(self):
        self.clean_pair()
        self.write("wiki/concepts/lonely.md", page_text(title="Lonely", body="# Lonely\n"))
        pages.write_index(self.vault)
        f = self.findings()
        self.assertEqual([x.path for x in f if x.code == "L3"], ["wiki/concepts/lonely.md"])

    def test_l4_stale_after(self):
        self.clean_pair()
        self.write("wiki/concepts/old.md", page_text(title="Old", body="# Old\n\n[[a]]\n", stale_after="2026-01-01T00:00:00Z"))
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]] [[old]] [[dep]]\n"))
        self.write("wiki/concepts/dep.md", page_text(title="Dep", body="# Dep\n\n[[a]]\n", status="deprecated",
                                                     stale_after="2026-01-01T00:00:00Z"))
        pages.write_index(self.vault)
        l4 = [x.path for x in self.findings() if x.code == "L4"]
        self.assertEqual(l4, ["wiki/concepts/old.md"])  # deprecated page is not reported

    def test_l5_missing_local_resource(self):
        self.clean_pair()
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n", sources=[
            {"id": "ok", "resource": "AGENTS.md"},
            {"id": "gone", "resource": "cross_market/data/clob_books/purged"},
            {"id": "uri", "resource": (self.dev_root / "missing.json").as_uri()},
            {"id": "web", "resource": "https://example.com/x"},
            {"id": "git", "resource": "git:abc123"},
        ]))
        l5 = [x.message for x in self.findings() if x.code == "L5"]
        self.assertEqual(len(l5), 2)
        self.assertTrue(any("purged" in m for m in l5))
        self.assertTrue(any("missing.json" in m for m in l5))

    def test_c1_assert_and_parameter_drift(self):
        self.clean_pair()
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n", dev={
            "asserts": [
                {"file": "cross_market/latency_sniper.py", "pattern": "def record_loop", "claim": "ok"},
                {"file": "cross_market/latency_sniper.py", "pattern": "def teleport", "claim": "drifted"},
                {"file": "cross_market/missing.py", "pattern": ".", "claim": "file gone"},
            ],
            "parameters": [
                {"name": "kill", "value": "3,500.00", "file": "quant_trading_lab/CLAUDE.md",
                 "pattern": r"Killswitch: \$([0-9,\.]+)"},
                {"name": "risk", "value": 2.0, "file": "quant_trading_lab/CLAUDE.md",
                 "pattern": r"Risk Budget: ([0-9.]+)%"},
                {"name": "absent", "value": 1, "file": "quant_trading_lab/CLAUDE.md", "pattern": r"Nope: (\d+)"},
            ]}))
        c1 = [x.message for x in self.findings() if x.code == "C1"]
        self.assertEqual(len(c1), 4, c1)
        self.assertTrue(any("drift" in m and "teleport" in m for m in c1))
        self.assertTrue(any("file missing" in m for m in c1))
        self.assertTrue(any("risk drift: page says 2.0" in m and "'1.0'" in m for m in c1))
        self.assertTrue(any("absent: pattern not found" in m for m in c1))

    def test_c5_edit_inside_window(self):
        self.clean_pair()
        start, end = NOW - timedelta(minutes=2), NOW + timedelta(minutes=5)
        p = self.write("wiki/concepts/ev.md", page_text("Event", title="Ev", body="# Ev\n\n[[a]]\n",
                                                        dev={"window": {"start": pages.iso(start), "end": pages.iso(end)}}))
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]] [[ev]]\n"))
        pages.write_index(self.vault)
        inside = (NOW + timedelta(minutes=1)).timestamp()
        os.utime(p, (inside, inside))
        self.assertIn("C5", self.codes())
        before = (start - timedelta(hours=1)).timestamp()
        os.utime(p, (before, before))
        self.assertNotIn("C5", self.codes())

    def test_cli_exit_codes_and_json(self):
        self.clean_pair()
        out = io.StringIO()
        self.assertEqual(lint.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), EXIT_OK)
        self.assertIn("CLEAN", out.getvalue())
        self.write("wiki/concepts/lonely.md", page_text(title="Lonely", body="# Lonely\n"))
        pages.write_index(self.vault)
        out = io.StringIO()
        self.assertEqual(lint.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--json"], out=out),
                         EXIT_FINDINGS)
        data = json.loads(out.getvalue())
        self.assertEqual(data["summary"]["by_code"], {"L3": 1})
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(lint.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), EXIT_HALT)
        self.assertIn("[HALT]", out.getvalue())

    def test_cli_refuses_missing_vault(self):
        self.assertEqual(lint.main(["--vault", str(self.root / "nope"), "--dev-root", str(self.dev_root)],
                                   out=io.StringIO()), EXIT_HALT)


# ---------------------------------------------------------------- seed

class SeedTests(TempVault):
    def registry(self) -> Path:
        return self.dev_root / "MASTER_COMMAND_LIST.txt"

    def test_parse_registry_blocks_fields_and_tiers(self):
        items = seed.parse_registry(FIXTURE_REGISTRY)
        self.assertEqual([i.number for i in items], [1, 7, 12])
        one, seven, twelve = items
        self.assertTrue(one.checked and not seven.checked)
        self.assertEqual((one.tier, seven.tier), (1, 2))
        self.assertEqual(one.lines("Primary Code"), ["Sports_Desk/engine/fair_value.py", "Sports_Desk/ingestors/odds_fetcher.py"])
        self.assertIn("Shin's method", one.text("What It Does"))
        self.assertEqual(one.lines("Test Command"), ["python -m unittest Sports_Desk.tests.test_fair_value"])
        self.assertEqual(one.text("Database"), "Sports_Desk/data/sports_market.db")
        self.assertTrue(seven.text("Status").startswith("[ROADMAP]"))
        self.assertNotIn("QUICK START", twelve.text("Test Command"))  # top-level line ended the block

    def test_desk_assignment_and_filenames(self):
        items = seed.parse_registry(FIXTURE_REGISTRY)
        self.assertEqual([seed.desk_for_item(i) for i in items], [2, 2, 3])
        self.assertEqual(seed.item_filename(items[0]), "Item_01_Sports_Odds_Ingestion_Fair_Value_No.md")
        self.assertEqual(seed.slugify("SOVEREIGN MASTER COCKPIT UI (WAR ROOM DASHBOARD & CANVAS)"),
                         "Sovereign_Master_Cockpit_UI_War_Room")
        # Item 18's real title carries `->`, which must never reach a filename.
        self.assertEqual(seed.slugify("CROSS-MARKET TITAN CORRELATOR (MACRO -> CRYPTO -> PREDICTIONS)"),
                         "Cross_Market_Titan_Correlator_Macro_Crypto")
        self.assertEqual(seed.slugify("SECTION 1256 FUTURES TAX INGESTION (60/40 RULE)"),
                         "Section_1256_Futures_Tax_Ingestion_60")
        self.assertEqual(seed.ruling_filename(seed.RULINGS[3]), "Ruling_R04.md")
        self.assertEqual(seed.ruling_filename(seed.RULINGS[-1]), "Ruling_R95.md")

    def test_seed_writes_pages_index_log_and_is_lint_clean(self):
        report = seed.seed(self.vault, self.dev_root, self.registry(), at=NOW)
        self.assertEqual(len(report.written), 5 + 3 + 7)
        self.assertEqual(report.skipped, [])
        self.assertTrue((self.vault / "wiki/desks/Desk_03_Cross_Market_Desk.md").exists())
        self.assertTrue((self.vault / "wiki/rulings/Ruling_R95.md").exists())
        idx = (self.vault / "index.md").read_text(encoding="utf-8")
        self.assertTrue(idx.startswith("# Desk\n"))
        self.assertIn("* [R4 - neg_risk books skip the NO side](wiki/rulings/Ruling_R04.md) - ", idx)
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertTrue(log.startswith("## 2026-09-05\n* **Seed**: Round 96 seed"))
        for d in ("wiki", "crm", "journal", "raw"):
            self.assertTrue((self.vault / d).is_dir())
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_seed_frontmatter_details(self):
        seed.seed(self.vault, self.dev_root, self.registry(), at=NOW)
        r4, _ = fm.parse((self.vault / "wiki/rulings/Ruling_R04.md").read_text(encoding="utf-8"))
        self.assertEqual(r4["type"], "Ruling")
        self.assertEqual(r4["status"], "stable")
        self.assertEqual(r4["verified"][0]["by"], seed.ANTIGRAVITY)
        self.assertEqual(r4["dev"]["asserts"][0]["file"], "cross_market/latency_sniper.py")
        self.assertIn({"id": "commit-da48cf3", "resource": "git:da48cf3", "title": "commit da48cf3"}, r4["sources"])
        r1, body = fm.parse((self.vault / "wiki/rulings/Ruling_R01.md").read_text(encoding="utf-8"))
        self.assertEqual(r1["status"], "draft")
        self.assertNotIn("verified", r1)
        self.assertIn("NOT ratified", body)
        d4, _ = fm.parse((self.vault / "wiki/desks/Desk_04_Quant_Trading_Lab.md").read_text(encoding="utf-8"))
        names = {p["name"] for p in d4["dev"]["parameters"]}
        self.assertEqual(names, {"daily_drawdown_killswitch_usd", "single_trade_risk_pct"})
        d5, _ = fm.parse((self.vault / "wiki/desks/Desk_05_Tax_Reserve_Agent.md").read_text(encoding="utf-8"))
        self.assertNotIn("parameters", d5["dev"])  # config.yaml absent in the fixture: nothing emitted
        item1, _ = fm.parse((self.vault / "wiki/items" / "Item_01_Sports_Odds_Ingestion_Fair_Value_No.md").read_text(encoding="utf-8"))
        self.assertEqual(item1["dev"], {"desk": 2, "item": 1, "tier": 1, "registry_checked": True,
                                        "asserts": [{"file": "Sports_Desk/engine/fair_value.py", "pattern": ".",
                                                     "claim": "primary code present at the registered path"}]})

    def test_seed_is_idempotent_and_force_rewrites(self):
        first = seed.seed(self.vault, self.dev_root, self.registry(), at=NOW)
        target = self.vault / "wiki/rulings/Ruling_R04.md"
        target.write_text(target.read_text(encoding="utf-8") + "\nhuman edit\n", encoding="utf-8")
        second = seed.seed(self.vault, self.dev_root, self.registry(), at=NOW)
        self.assertEqual(second.written, [])
        self.assertEqual(sorted(second.skipped), sorted(first.written))
        self.assertIn("human edit", target.read_text(encoding="utf-8"))
        third = seed.seed(self.vault, self.dev_root, self.registry(), at=NOW, force=True)
        self.assertEqual(len(third.written), 15)
        self.assertNotIn("human edit", target.read_text(encoding="utf-8"))

    def test_seed_dry_run_writes_nothing(self):
        report = seed.seed(self.vault, self.dev_root, self.registry(), at=NOW, dry_run=True)
        self.assertEqual(len(report.written), 15)
        self.assertFalse((self.vault / "index.md").exists())
        self.assertFalse(any((self.vault / "wiki").rglob("*.md")))

    def test_seed_cli_halt_and_missing_registry(self):
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(seed.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)
        (self.dev_root / "HALT.flag").unlink()
        self.assertEqual(seed.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root),
                                    "--registry", str(self.dev_root / "nope.txt")], out=io.StringIO()), EXIT_HALT)
        out = io.StringIO()
        self.assertEqual(seed.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root),
                                    "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("seed: 15 page(s) written, 0 skipped", out.getvalue())
        self.assertIn("[WRITE] wiki/desks/Desk_01_HyperLiquid_Monarch.md", out.getvalue())

    def test_seed_never_writes_outside_owned_folders(self):
        before = {p.relative_to(self.vault).as_posix() for p in self.vault.rglob("*") if p.is_file()}
        seed.seed(self.vault, self.dev_root, self.registry(), at=NOW)
        after = {p.relative_to(self.vault).as_posix() for p in self.vault.rglob("*") if p.is_file()}
        for rel in after - before:
            self.assertTrue(rel.startswith(("wiki/", "crm/", "journal/", "raw/")) or rel in ("index.md", "log.md"), rel)
        self.assertFalse(any((self.vault / "Whales").iterdir()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
