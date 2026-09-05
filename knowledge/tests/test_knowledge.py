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
            "KELLY_FRACTION = 0.25\nMIN_CONFIDENCE = 0.99\n\nclass Book:\n    fee_rate: float = 0.0\n\n"
            "def record_loop():\n    pass\n\nNEG = 'neg_risk'\n", encoding="utf-8")
        (self.dev_root / "cross_market" / "amm_rewards.py").write_text(
            "def book_q():\n    'Ruling R5 pending'\n", encoding="utf-8")
        (self.dev_root / "Sports_Desk" / "engine").mkdir(parents=True)
        (self.dev_root / "Sports_Desk" / "engine" / "fair_value.py").write_text(
            "def devig(): pass\n\ndef kelly_fraction(fair_prob: float, offered_odds: float, fraction: float = 0.25) -> float:\n    return 0.0\n",
            encoding="utf-8")
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
                                    "and [ext](https://example.com) and | [[in_table\\|alias]] |")
        self.assertEqual(links, {"Desk_03_Cross_Market_Desk", "R4", "wiki/a.md", "in_table"})


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

    def test_c1_numeric_semantics_and_requires_files(self):
        self.clean_pair()
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n", dev={
            "parameters": [
                {"name": "k", "value": "0.20", "file": "cross_market/latency_sniper.py", "pattern": r"KELLY_FRACTION = ([0-9.]+)"},  # 0.25 != 0.20
                {"name": "k2", "value": 0.250, "file": "cross_market/latency_sniper.py", "pattern": r"KELLY_FRACTION = ([0-9.]+)"},  # equal as floats
                {"name": "txt", "value": "neg_risk", "file": "cross_market/latency_sniper.py", "pattern": r"NEG = '([a-z_]+)'"},  # strings
            ],
            "requires_files": ["cross_market/latency_sniper.py", "cross_market/vanished.py"]}))
        c1 = [x.message for x in self.findings() if x.code == "C1"]
        self.assertEqual(len(c1), 2, c1)
        self.assertTrue(any("k drift: page says '0.20'" in m for m in c1))
        self.assertTrue(any("requires_files[1] missing: cross_market/vanished.py" in m for m in c1))
        self.assertTrue(lint.values_equal("3,500.00", 3500) and lint.values_equal("0.2", "0.20") and not lint.values_equal("a", "b"))

    def test_c1_json_path_disambiguates_repeated_keys(self):
        """The real tier2b file: readiness.min_points is 200, bars.min_points is 60. A regex takes the first."""
        self.clean_pair()
        (self.dev_root / "reg.json").write_text(json.dumps({"series": {"readiness": {"min_points": 200}}, "bars": {"min_points": 60}}), encoding="utf-8")
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n", dev={"parameters": [
            {"name": "by_path", "value": 60, "file": "reg.json", "json_path": "bars.min_points"},
            {"name": "by_regex", "value": 60, "file": "reg.json", "pattern": r'"min_points":\s*([0-9.]+)'},
            {"name": "missing_path", "value": 1, "file": "reg.json", "json_path": "bars.nope"}]}))
        c1 = [x.message for x in self.findings() if x.code == "C1"]
        self.assertEqual(len(c1), 2, c1)
        self.assertTrue(any("by_regex drift: page says 60, reg.json says '200'" in m for m in c1))
        self.assertTrue(any("missing_path: json_path bars.nope not found" in m for m in c1))
        self.assertEqual(fm.validate({"type": "X", "dev": {"parameters": [{"name": "n", "value": 1, "file": "f"}]}}),
                         ["dev.parameters[0] needs `name`, `value`, string `file` and `pattern` or `json_path`"])

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

    def test_c5_generated_at_is_an_error_and_mtime_alone_a_warning(self):
        self.clean_pair()
        start, end = NOW - timedelta(minutes=2), NOW + timedelta(minutes=5)
        window = {"start": pages.iso(start), "end": pages.iso(end)}
        # generated.at = NOW is inside the window -> error regardless of mtime
        p = self.write("wiki/concepts/ev.md", page_text("Event", title="Ev", body="# Ev\n\n[[a]]\n", dev={"window": window}))
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]] [[ev]]\n"))
        pages.write_index(self.vault)
        before = (start - timedelta(hours=1)).timestamp()
        os.utime(p, (before, before))
        c5 = [x for x in self.findings() if x.code == "C5"]
        self.assertEqual([x.severity for x in c5], ["error"])
        self.assertIn("generated.at", c5[0].message)
        # generated.at outside, mtime inside -> warning (a checkout can do that)
        meta = pages.make_meta("Event", "Ev", "d", at=start - timedelta(days=1), dev={"window": window})
        p.write_text(fm.serialize(meta, "# Ev\n\n[[a]]\n"), encoding="utf-8")
        inside = (NOW + timedelta(minutes=1)).timestamp()
        os.utime(p, (inside, inside))
        c5 = [x for x in self.findings() if x.code == "C5"]
        self.assertEqual([x.severity for x in c5], ["warning"])
        self.assertIn("mtime", c5[0].message)
        # both outside -> nothing
        os.utime(p, (before, before))
        self.assertNotIn("C5", self.codes())

    def test_constitution_is_linted_for_l1_but_exempt_from_index_and_orphans(self):
        self.clean_pair()
        self.write("WIKI_SCHEMA.md", "---\ntitle: no type\n---\n# constitution\n")
        f = self.findings()
        self.assertTrue(any(x.code == "L1" and x.path == "WIKI_SCHEMA.md" for x in f))
        self.assertFalse(any(x.code in ("L2", "L3") and x.path == "WIKI_SCHEMA.md" for x in f))
        self.write("WIKI_SCHEMA.md", page_text("Constitution", title="C", body="# C\n"))
        self.assertEqual(self.findings(), [])
        self.assertEqual([p.path.name for p in pages.load_pages(self.vault)], ["a.md", "b.md"])  # not a page

    def test_c2_expired_tokens_against_newest_drops(self):
        self.clean_pair()
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        drops.mkdir(parents=True)
        (drops / "polymarket_macro_20260901T000000_000000Z.json").write_text(json.dumps([{"token_id": "OLD"}]), encoding="utf-8")
        (drops / "polymarket_macro_20260905T000000_000000Z.json").write_text(json.dumps([{"token_id": "LIVE1"}, {"token_id": "LIVE2"}]), encoding="utf-8")
        (drops / "polymarket_sports_20260905T000000_000000Z.json").write_text(json.dumps([{"token_id": "SPORT1"}]), encoding="utf-8")
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n",
                                                   dev={"tokens": ["LIVE1", "SPORT1", "OLD"], "token_id": "GONE"}))
        self.write("wiki/concepts/b.md", page_text(title="B", body="# B\n\nsee [[a]]\n", status="deprecated", dev={"token_id": "GONE2"}))
        c2 = [x for x in self.findings() if x.code == "C2"]
        self.assertEqual(sorted(m.message.split(" not in")[0] for m in c2), ["token GONE...", "token OLD..."])  # deprecated page skipped
        self.assertTrue(all(x.severity == "warning" for x in c2))
        # explicit drops folder that does not exist -> one warning, nothing else
        c2 = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW, drops=self.root / "nope") if x.code == "C2"]
        self.assertEqual(len(c2), 1)
        self.assertIn("drops folder not found", c2[0].message)

    def test_c3_cross_desk_parameter_conflicts(self):
        self.clean_pair()
        f = self.dev_root / "cross_market" / "latency_sniper.py"
        self.write("wiki/concepts/a.md", page_text(title="A", body="# A\n\nsee [[b]]\n", dev={"parameters": [
            {"name": "kelly_fraction", "value": 0.25, "file": "cross_market/latency_sniper.py", "pattern": r"KELLY_FRACTION = ([0-9.]+)"},
            {"name": "fee_rate", "value": 0.0, "file": "cross_market/latency_sniper.py", "pattern": r"KELLY_FRACTION = ([0-9.]+)"}]}))
        self.write("wiki/concepts/b.md", page_text(title="B", body="# B\n\nsee [[a]]\n", dev={"parameters": [
            {"name": "kelly_fraction", "value": "0.250", "file": "cross_market/latency_sniper.py", "pattern": r"KELLY_FRACTION = ([0-9.]+)"},
            {"name": "fee_rate", "value": 0.02, "file": "cross_market/latency_sniper.py", "pattern": r"KELLY_FRACTION = ([0-9.]+)"}]}))
        self.assertTrue(f.exists())
        c3 = [x for x in self.findings() if x.code == "C3"]
        self.assertEqual(len(c3), 1)
        self.assertIn("'fee_rate' conflicts", c3[0].message)  # kelly agrees as floats; fee_rate does not
        self.assertIn("wiki/concepts/a.md says 0.0", c3[0].message)

    def test_l2_validates_nested_index_files(self):
        self.clean_pair()
        (self.vault / "raw").mkdir(exist_ok=True)
        (self.vault / "raw" / "index.md").write_text("# Desk\n* [ok](../wiki/concepts/a.md) - fine\n* [bad](../nowhere/x.md) - gone\nfree text\n", encoding="utf-8")
        l2 = [x for x in self.findings() if x.code == "L2" and x.path == "raw/index.md"]
        self.assertEqual(len(l2), 2)
        self.assertTrue(any("does not exist: ../nowhere/x.md" in x.message for x in l2))

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
        # Round 97 ruling 11: curated overrides for Items 4 and 19
        self.assertEqual(seed.item_filename(seed.ItemSpec(4, "SECTION 1256 FUTURES TAX INGESTION (60/40 RULE)", True)),
                         "Item_04_Section_1256_Futures_Tax_60_40.md")
        self.assertEqual(seed.item_filename(seed.ItemSpec(19, "MULTI-DESK MONTE CARLO RISK-OF-RUIN SIMULATOR", True)),
                         "Item_19_Multi_Desk_Monte_Carlo_Risk_Of_Ruin.md")

    def test_seed_default_at_is_registry_mtime_so_force_is_byte_idempotent(self):
        reg = self.registry()
        fixed = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        os.utime(reg, (fixed, fixed))
        seed.seed(self.vault, self.dev_root, reg)
        first = {p: p.read_bytes() for p in (self.vault / "wiki").rglob("*.md")}
        r4, _ = fm.parse((self.vault / "wiki/rulings/Ruling_R04.md").read_text(encoding="utf-8"))
        self.assertEqual(r4["generated"]["at"], "2026-09-05T12:00:00Z")
        seed.seed(self.vault, self.dev_root, reg, force=True)
        second = {p: p.read_bytes() for p in (self.vault / "wiki").rglob("*.md")}
        self.assertEqual(first, second)

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
        self.assertTrue(log.startswith("## 2026-09-05\n* **Seed**: seed from the Top 20 registry (generated.at 2026-09-05T20:00:00Z)"), log)
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
        self.assertNotIn("verified", r1)
        self.assertIn("NOT ratified", body)
        d4, _ = fm.parse((self.vault / "wiki/desks/Desk_04_Quant_Trading_Lab.md").read_text(encoding="utf-8"))
        names = {p["name"] for p in d4["dev"]["parameters"]}
        self.assertEqual(names, {"daily_drawdown_killswitch_usd", "single_trade_risk_pct"})
        d5, _ = fm.parse((self.vault / "wiki/desks/Desk_05_Tax_Reserve_Agent.md").read_text(encoding="utf-8"))
        self.assertNotIn("parameters", d5["dev"])  # config.yaml absent in the fixture: nothing emitted
        item1, _ = fm.parse((self.vault / "wiki/items" / "Item_01_Sports_Odds_Ingestion_Fair_Value_No.md").read_text(encoding="utf-8"))
        self.assertEqual(item1["dev"], {"desk": 2, "item": 1, "tier": 1, "registry_checked": True,
                                        "requires_files": ["Sports_Desk/engine/fair_value.py"]})
        # Round 97: historical ratification instants, deprecated R1/R3, kelly_fraction on desks 2 and 3 (5 absent here)
        self.assertEqual(r4["verified"][0]["at"], "2026-09-05T17:15:05Z")
        self.assertEqual(r1["status"], "deprecated")
        d2, _ = fm.parse((self.vault / "wiki/desks/Desk_02_Sports_Desk.md").read_text(encoding="utf-8"))
        d3, _ = fm.parse((self.vault / "wiki/desks/Desk_03_Cross_Market_Desk.md").read_text(encoding="utf-8"))
        self.assertEqual([p["value"] for p in d2["dev"]["parameters"] if p["name"] == "kelly_fraction"], [0.25])
        self.assertEqual([p["value"] for p in d3["dev"]["parameters"] if p["name"] == "kelly_fraction"], [0.25])

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


# ---------------------------------------------------------------- ingest adapters (Round 97)

from knowledge import raw_manifest  # noqa: E402
from knowledge.ingest import clob as ingest_clob  # noqa: E402
from knowledge.ingest import experiments as ingest_exp  # noqa: E402
from knowledge.ingest import lead_lag as ingest_ll  # noqa: E402

RULES_JSON = {
    "experiment": "latency_sniper_fomc_2026-09-16",
    "registered_utc": "2026-09-05T18:10:19+00:00",
    "release_utc": "2026-09-16T18:00:00+00:00",
    "status": "PRE-REGISTERED (Ruling R2c). NEVER edit inside the event window (T-2 min to T+5 min).",
    "event_schema": {"kind": "fed_rate", "payload": {"change_bps": "int"}, "source": "federalreserve.gov", "confidence": ">= 0.99"},
    "reading": "All markets are neg_risk: Ruling R4.",
    "not_found_in_drop": ["FOMC 2026-09-17: cut 25 bps"],
    "rules": [
        {"label": "FOMC 2026-09-16: no change", "market": "TOK_NOCHANGE", "kind": "fed_rate", "field": "change_bps", "op": "==",
         "value": 0, "outcome_if_true": "YES", "yes_price_at_registration": 0.5, "neg_risk": True,
         "question": "Will there be no change in Fed interest rates after the September 2026 meeting?",
         "market_slug": "will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615"},
        {"label": "FOMC 2026-09-16: hike 25 bps", "market": "TOK_HIKE25", "kind": "fed_rate", "field": "change_bps", "op": "==",
         "value": 25, "outcome_if_true": "YES", "yes_price_at_registration": 0.5, "neg_risk": True,
         "question": "Will the Fed increase interest rates by 25 bps after the September 2026 meeting?",
         "market_slug": "will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649"},
    ],
    "corrections": [{"at_utc": "2026-09-05T18:15:46+00:00", "what": "date corrected", "before_window": True}],
}
META_JSON = {
    "experiment": "lead_lag_tier2_subfamilies",
    "registered_utc": "2026-09-05T10:00:03+00:00",
    "status": "PRE-REGISTERED - runs only AFTER the Tier 1 maiden run has written its verdict.",
    "bars": {"min_abs_corr": 0.2, "min_events": 5, "min_points": 60, "insufficient_rule": "text", "latency_minutes_crypto": 5.0},
    "subfamilies": {"fed-rates": {"role": "exogenous", "reading": "Tier 1"}, "crypto": {"role": "endogenous", "reading": "latency rule"}},
    "commands": ["python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates"],
    "caveats": ["not independent of Tier 1"],
}
VERDICT_JSON = {
    "events": 41, "price_points": 1440, "max_lag": 60, "sufficient": True, "reason": "",
    "best_lag_minutes": 12, "correlation": 0.31, "n": 200,
    "interpretation": "Polymarket leads HyperLiquid by 12 min (corr +0.31, n=200)",
    "curve": [{"lag_minutes": 12, "correlation": 0.31, "n": 200}, {"lag_minutes": -3, "correlation": -0.05, "n": 210},
              {"lag_minutes": 0, "correlation": 0.12, "n": 215}],
    "latency_minutes": 0.0, "family": "macro", "subfamily": None, "subfamily_from": None, "price_error": None,
}
CURVE_JSON = {
    "anchor": "2026-09-16T18:00:00+00:00", "release_utc": "2026-09-16T18:00:00+00:00", "anchor_minus_release_s": 0.0,
    "event": {"kind": "fed_rate", "payload": {"change_bps": 0}, "confidence": 0.995}, "step_seconds": 1.0, "stamps": 12,
    "markets": [
        {"market": "TOK_NOCHANGE", "rule": "FOMC 2026-09-16: no change", "outcome": "YES", "side": "BUY_YES", "stamps": 6,
         "neg_risk": True, "deferred": None,
         "series": [
             {"delta_s": -2.0, "observed_at": "2026-09-16T17:59:58+00:00", "fillable_shares": 1000, "fillable_notional": 500.0, "vwap": 0.5, "clearing_levels": 4, "best_price": 0.5, "expected_profit": 490.0, "changed": False, "stamp": "a"},
             {"delta_s": -1.0, "observed_at": "2026-09-16T17:59:59+00:00", "fillable_shares": 1000, "fillable_notional": 500.0, "vwap": 0.5, "clearing_levels": 4, "best_price": 0.5, "expected_profit": 490.0, "changed": False, "stamp": "b"},
             {"delta_s": 0.0, "observed_at": "2026-09-16T18:00:00+00:00", "fillable_shares": 1000, "fillable_notional": 500.0, "vwap": 0.5, "clearing_levels": 4, "best_price": 0.5, "expected_profit": 490.0, "changed": False, "stamp": "c"},
             {"delta_s": 1.0, "observed_at": "2026-09-16T18:00:01+00:00", "fillable_shares": 400, "fillable_notional": 240.0, "vwap": 0.6, "clearing_levels": 2, "best_price": 0.55, "expected_profit": 150.0, "changed": True, "stamp": "d"},
             {"delta_s": 2.0, "observed_at": "2026-09-16T18:00:02+00:00", "fillable_shares": 50, "fillable_notional": 45.0, "vwap": 0.9, "clearing_levels": 1, "best_price": 0.9, "expected_profit": 4.0, "changed": True, "stamp": "e"},
             {"delta_s": 3.0, "observed_at": "2026-09-16T18:00:03+00:00", "fillable_shares": 0, "fillable_notional": 0.0, "vwap": None, "clearing_levels": 0, "best_price": None, "expected_profit": 0.0, "changed": True, "stamp": "f"},
         ],
         "summary": {"baseline_notional": 500.0, "baseline_delta_s": -1.0, "pre_print_stamps": 2, "post_print_stamps": 4,
                     "first_change_s": 1.0, "half_s": 1.0, "tenth_s": 2.0, "gone_s": 3.0, "max_post_notional": 500.0, "notional_seconds": 785.0}},
        {"market": "TOK_HIKE25", "rule": "FOMC 2026-09-16: hike 25 bps", "outcome": "NO", "side": "BUY_NO", "stamps": 6,
         "neg_risk": True, "deferred": "neg_risk market: NO side deferred to Phase 2 (Ruling R4)", "series": [], "summary": None},
    ],
}


class IngestFixture(TempVault):
    def setUp(self):
        super().setUp()
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW)  # desks/items/rulings to link to
        for name in ("verdict.json", "v2.json", "v3.json", "x.json", "curve.json", "a.json", "b.json"):
            (self.dev_root / name).write_text("{}", encoding="utf-8")  # the raw sources the pages will cite (L5)
        self.exp_dir = self.dev_root / "cross_market" / "experiments"
        self.exp_dir.mkdir()
        (self.exp_dir / "fomc_2026-09-16.rules.json").write_text(json.dumps(RULES_JSON), encoding="utf-8")
        (self.exp_dir / "lead_lag_tier2.meta.json").write_text(json.dumps(META_JSON), encoding="utf-8")
        (self.exp_dir / "sniper_rules.sample.json").write_text(json.dumps({"rules": [], "release_utc": None}), encoding="utf-8")
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        drops.mkdir(parents=True)
        (drops / "polymarket_macro_20260905T000000_000000Z.json").write_text(json.dumps([
            {"token_id": "TOK_NOCHANGE", "sport": "FED-RATES", "question": "Will there be no change in Fed interest rates after the September 2026 meeting?",
             "market_slug": "will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615", "condition_id": "0xabc",
             "event_slug": "fed-decision-in-september-2026", "event_title": "Fed decision in September?", "fetched_at": "2026-09-05T19:25:36Z",
             "yes_price": 0.5, "yes_bid": 0.49},
            {"token_id": "TOK_HIKE25", "sport": "FED-RATES", "question": "Will the Fed increase interest rates by 25 bps after the September 2026 meeting?",
             "market_slug": "will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649", "condition_id": "0xdef",
             "fetched_at": "2026-09-05T19:25:36Z", "yes_price": 0.5},
            {"token_id": "TOK_CUTS2026", "sport": "FED-RATES", "question": "Will no Fed rate cuts happen in 2026?",
             "market_slug": "will-no-fed-rate-cuts-happen-in-2026", "condition_id": "0x123", "fetched_at": "2026-09-05T19:25:36Z", "yes_price": 0.93},
            {"token_id": "TOK_BTC78K", "sport": "CRYPTO", "question": "Will the price of Bitcoin be above $78,000 on September 6?",
             "market_slug": "bitcoin-above-78k-on-september-6-2026", "fetched_at": "2026-09-05T19:25:36Z", "yes_price": 0.98},
        ]), encoding="utf-8")


class ExperimentsIngestTests(IngestFixture):
    def test_rules_registration_becomes_experiment_with_window_tokens_and_links(self):
        report = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.assertEqual(sorted(report.written), ["wiki/experiments/fomc_2026-09-16_rules.md", "wiki/experiments/lead_lag_tier2_meta.md"])
        self.assertEqual(report.ignored, ["sniper_rules.sample.json"])
        meta, body = fm.parse((self.vault / "wiki/experiments/fomc_2026-09-16_rules.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["type"], "Experiment")
        self.assertEqual(meta["status"], "draft")
        self.assertEqual(meta["dev"]["window"], {"start": "2026-09-16T17:58:00Z", "end": "2026-09-16T18:05:00Z"})
        self.assertEqual(meta["dev"]["tokens"], ["TOK_NOCHANGE", "TOK_HIKE25"])
        self.assertEqual(meta["dev"]["not_found_in_drop"], ["FOMC 2026-09-17: cut 25 bps"])
        self.assertEqual(meta["sources"][0]["resource"], "cross_market/experiments/fomc_2026-09-16.rules.json")
        self.assertIn("| FOMC 2026-09-16: no change | `change_bps == 0` | YES |", body)
        self.assertIn("[[Ruling_R04|", body)
        reg, reg_body = fm.parse((self.vault / "wiki/concepts/experiments_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["pages"], ["fomc_2026-09-16_rules", "lead_lag_tier2_meta"])
        self.assertIn("[[fomc_2026-09-16_rules\\|", reg_body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_meta_registration_carries_bars_as_parameters(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        meta, body = fm.parse((self.vault / "wiki/experiments/lead_lag_tier2_meta.md").read_text(encoding="utf-8"))
        names = {p["name"]: p["value"] for p in meta["dev"]["parameters"]}
        self.assertEqual(names, {"lead_lag_min_abs_corr": 0.2, "lead_lag_min_events": 5, "lead_lag_min_points": 60,
                                 "lead_lag_latency_minutes_crypto": 5.0})
        self.assertEqual({p["json_path"] for p in meta["dev"]["parameters"]},
                         {"bars.min_abs_corr", "bars.min_events", "bars.min_points", "bars.latency_minutes_crypto"})
        self.assertTrue(all("pattern" not in p for p in meta["dev"]["parameters"]))
        self.assertEqual(meta["dev"]["item"], 18)
        self.assertIn("| `min_abs_corr` | 0.2 |", body)
        # C1 verifies the bars against the JSON: corrupt one and lint must fire
        (self.exp_dir / "lead_lag_tier2.meta.json").write_text(json.dumps(dict(META_JSON, bars=dict(META_JSON["bars"], min_abs_corr=0.3))), encoding="utf-8")
        self.assertTrue(any(x.code == "C1" and "lead_lag_min_abs_corr drift" in x.message
                            for x in lint.lint_vault(self.vault, self.dev_root, now=NOW)))

    def test_experiment_window_refuses_writes_inside_it_and_c2_sees_missing_tokens(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        inside = datetime(2026, 9, 16, 18, 1, 0, tzinfo=timezone.utc)
        with self.assertRaises(pages.WriteRefused):
            ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=inside, force=True)
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        (drops / "polymarket_macro_20260906T000000_000000Z.json").write_text(json.dumps([{"token_id": "TOK_NOCHANGE"}]), encoding="utf-8")
        c2 = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C2"]
        self.assertEqual(len(c2), 1)
        self.assertIn("TOK_HIKE25", c2[0].message)

    def test_experiments_skip_existing_unless_force_and_cli_guards(self):
        first = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        second = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.assertEqual(second.written, [])
        self.assertEqual(sorted(second.skipped), sorted(first.written))
        third = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW, force=True)
        self.assertEqual(len(third.written), 2)
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("**Ingest**"), 2)  # the no-op run appended nothing
        out = io.StringIO()
        self.assertEqual(ingest_exp.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--dir", str(self.exp_dir),
                                          "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("[KEEP]", out.getvalue())
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ingest_exp.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class LeadLagIngestTests(IngestFixture):
    def test_classify_vocabulary(self):
        c = ingest_ll.classify
        self.assertEqual(c({"sufficient": False}), "insufficient")
        self.assertEqual(c({"sufficient": True, "correlation": 0.1, "best_lag_minutes": 7}), "no-lead")
        self.assertEqual(c({"sufficient": True, "correlation": 0.4, "best_lag_minutes": 3, "latency_minutes": 5.0}), "contemporaneous")
        self.assertEqual(c({"sufficient": True, "correlation": 0.4, "best_lag_minutes": 12, "latency_minutes": 5.0}), "polymarket-leads")
        self.assertEqual(c({"sufficient": True, "correlation": -0.3, "best_lag_minutes": -9}), "hyperliquid-leads")
        self.assertEqual(c({"sufficient": True, "correlation": 0.3, "best_lag_minutes": 0}), "coincident")

    def test_verdict_and_regime_pages_then_history_accumulates(self):
        v, r = ingest_ll.ingest_verdict(VERDICT_JSON, self.vault, self.dev_root, tier="1", source="verdict.json", at=NOW)
        self.assertEqual(v.path.name, "lead_lag_tier1_macro_20260905T2000Z.md")
        self.assertEqual(v.meta["dev"]["classification"], "polymarket-leads")
        self.assertEqual(v.meta["dev"]["best_lag_minutes"], 12)
        self.assertEqual(r.path.name, "btc_macro_regime.md")
        self.assertEqual(r.meta["dev"]["current"],
                         {"tier 1 macro": {"latest_verdict": "polymarket-leads", "regime_consensus_3": "insufficient-history", "runs": 1}})
        self.assertEqual(len(r.meta["dev"]["history"]), 1)
        body = r.path.read_text(encoding="utf-8")
        self.assertIn("| 1 | macro | label | **polymarket-leads** | insufficient-history | 12 | +0.310 | 200 |", body)
        self.assertIn("- none", body)  # no disagreements yet
        # Tier 2 crypto subfamily, contemporaneous, later
        later = NOW + timedelta(days=1)
        t2 = dict(VERDICT_JSON, subfamily="crypto", subfamily_from="label", best_lag_minutes=2, correlation=0.35, latency_minutes=5.0)
        v2, r2 = ingest_ll.ingest_verdict(t2, self.vault, self.dev_root, tier="2", source="v2.json", at=later)
        self.assertEqual(v2.meta["dev"]["classification"], "contemporaneous")
        self.assertEqual(len(r2.meta["dev"]["history"]), 2)
        # Tier 2b on the same scope with a different class -> a disagreement line
        t2b = dict(t2, subfamily_from="tags", best_lag_minutes=15)
        _, r3 = ingest_ll.ingest_verdict(t2b, self.vault, self.dev_root, tier="2b", source="v3.json", at=later + timedelta(hours=1))
        body = r3.path.read_text(encoding="utf-8")
        self.assertIn("**macro_crypto**: Tier 2 says contemporaneous, Tier 2b says polymarket-leads", body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=later + timedelta(hours=2)), [])
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertIn("lead-lag Tier 1 verdict (macro): **polymarket-leads**", log)

    def test_insufficient_verdict_is_a_non_verdict(self):
        res = {"sufficient": False, "reason": "3 probability shifts < 5 required", "events": 3, "price_points": 100,
               "family": "macro", "subfamily": "fed-rates", "subfamily_from": "tags", "curve": [], "latency_minutes": 0.0}
        v, r = ingest_ll.ingest_verdict(res, self.vault, self.dev_root, tier="2b", source="x.json", at=NOW)
        self.assertEqual(v.meta["dev"]["classification"], "insufficient")
        self.assertIn("3 probability shifts < 5 required", v.body)
        self.assertEqual(r.meta["dev"]["current"]["tier 2b macro_fed-rates"]["latest_verdict"], "insufficient")

    def test_regime_consensus_3_agrees_or_is_mixed(self):
        base = dict(VERDICT_JSON)
        for i, cls_lag in enumerate((12, 15, 9)):  # three polymarket-leads verdicts
            ingest_ll.ingest_verdict(dict(base, best_lag_minutes=cls_lag), self.vault, self.dev_root, tier="1", source="verdict.json",
                                     at=NOW + timedelta(hours=i))
        _, r = ingest_ll.ingest_verdict(dict(base, best_lag_minutes=-7, correlation=-0.3), self.vault, self.dev_root, tier="1",
                                        source="verdict.json", at=NOW + timedelta(hours=3))
        st = r.meta["dev"]["current"]["tier 1 macro"]
        self.assertEqual(st, {"latest_verdict": "hyperliquid-leads", "regime_consensus_3": "mixed", "runs": 4})
        self.assertEqual(ingest_ll.current_state(r.meta["dev"]["history"][:3])["tier 1 macro"]["regime_consensus_3"], "polymarket-leads")

    def test_cli_reads_file_and_refuses_non_verdicts(self):
        f = self.root / "verdict.json"
        f.write_text(json.dumps(VERDICT_JSON), encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(ingest_ll.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(f),
                                         "--tier", "1", "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("class=polymarket-leads", out.getvalue())
        f.write_text(json.dumps({"ready": False}), encoding="utf-8")  # a --check-data payload, not a verdict
        self.assertEqual(ingest_ll.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(f), "--tier", "1"],
                                        out=io.StringIO()), EXIT_HALT)


class ClobIngestTests(IngestFixture):
    def test_profiles_event_and_concept_from_curve(self):
        profiles, event, concept = ingest_clob.ingest_survival(CURVE_JSON, self.vault, self.dev_root, event_id="fomc_2026-09-16",
                                                                source="curve.json", at=NOW)
        self.assertEqual(sorted(p.path.name for p in profiles),
                         ["fomc_2026-09-16__FOMC_2026_09_16_hike_25_bps.md", "fomc_2026-09-16__FOMC_2026_09_16_no_change.md"])
        nc = next(p for p in profiles if p.meta["dev"]["token_id"] == "TOK_NOCHANGE")
        self.assertEqual(nc.meta["type"], "Reaction Profile")
        self.assertEqual(nc.meta["dev"]["summary"]["half_s"], 1.0)
        self.assertEqual(nc.meta["dev"]["summary"]["notional_seconds"], 785.0)
        self.assertIn("| half of baseline gone by | 1 s |", nc.body)
        self.assertIn("| +1 | $240 | 400 | 0.6 | 2 | yes |", nc.body)   # checkpoint row
        self.assertNotIn("17:59:58", nc.body)                             # the per-second series is not copied
        deferred = next(p for p in profiles if p.meta["dev"]["token_id"] == "TOK_HIKE25")
        self.assertIn("NO side deferred", deferred.body)
        self.assertIsNone(deferred.meta["dev"]["summary"]["half_s"])
        self.assertEqual(event.meta["type"], "Event")
        self.assertEqual(event.meta["dev"]["payload"], {"change_bps": 0})
        self.assertEqual(len(event.meta["dev"]["profiles"]), 2)
        self.assertEqual(concept.meta["type"], "Concept")
        self.assertEqual(len(concept.meta["dev"]["history"]), 2)
        self.assertIn("| fomc_2026-09-16 | FOMC 2026-09-16: no change | YES | $500 | 1 s | 1 s | 2 s | 3 s | $785 |", concept.body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_reingesting_an_event_replaces_its_rows_and_a_second_event_adds(self):
        ingest_clob.ingest_survival(CURVE_JSON, self.vault, self.dev_root, event_id="fomc_2026-09-16", source="a.json", at=NOW)
        _, _, concept = ingest_clob.ingest_survival(CURVE_JSON, self.vault, self.dev_root, event_id="fomc_2026-09-16", source="a.json",
                                                    at=NOW + timedelta(hours=1))
        self.assertEqual(len(concept.meta["dev"]["history"]), 2)
        other = dict(CURVE_JSON, anchor="2026-10-28T18:00:00+00:00", release_utc="2026-10-28T18:00:00+00:00")
        _, _, concept = ingest_clob.ingest_survival(other, self.vault, self.dev_root, event_id="fomc_2026-10-28", source="b.json",
                                                    at=NOW + timedelta(days=53))
        self.assertEqual(len(concept.meta["dev"]["history"]), 4)
        self.assertEqual({r["event"] for r in concept.meta["dev"]["history"]}, {"fomc_2026-09-16", "fomc_2026-10-28"})

    def test_cli_guards(self):
        f = self.root / "curve.json"
        f.write_text(json.dumps(CURVE_JSON), encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(ingest_clob.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(f),
                                           "--event", "fomc_2026-09-16", "--at", "2026-09-16T18:10:00Z"], out=out), EXIT_OK)
        self.assertIn("rows=2", out.getvalue())
        self.assertEqual(ingest_clob.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(f),
                                           "--event", "bad id!"], out=io.StringIO()), EXIT_HALT)
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ingest_clob.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(f),
                                           "--event", "x"], out=io.StringIO()), EXIT_HALT)


class RawManifestTests(IngestFixture):
    def test_manifest_lists_present_streams_in_okf_format_and_lints_clean(self):
        text = raw_manifest.build_manifest(self.dev_root, self.vault)
        entries, errors = pages.parse_index(text)
        self.assertEqual(errors, [])
        titles = {e.title for e in entries}
        self.assertIn("Pre-registrations", titles)          # cross_market/experiments exists in the fixture
        self.assertIn("Polymarket drops", titles)
        self.assertNotIn("Tax ledger", titles)              # not in the fixture -> "Not present" section, no link
        self.assertIn("# Not present on this machine", text)
        self.assertIn("> not present: Tax ledger (`Tax_Reserve_Agent/data/tax_ledger.db`)", text)
        target = raw_manifest.write_manifest(self.dev_root, self.vault)
        self.assertEqual(target, self.vault / "raw" / "index.md")
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        out = io.StringIO()
        self.assertEqual(raw_manifest.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), EXIT_OK)
        self.assertIn("raw manifest:", out.getvalue())
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(raw_manifest.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


# ---------------------------------------------------------------- Round 98: compile what exists

import knowledge as knowledge_pkg  # noqa: E402
from knowledge import computations, registers  # noqa: E402
from knowledge.ingest import calendar as ingest_cal  # noqa: E402
from knowledge.ingest import markets as ingest_mk  # noqa: E402
from knowledge.ingest import rulings as ingest_rl  # noqa: E402

HL_REGIME = {
    "experiment": "regime_filtered_v1", "registered_utc": "2026-09-01T04:40:14+00:00",
    "control": "data/experiments/baseline_unfiltered_N12_2026-09-01.json",
    "changes_vs_control": ["EMA-50/RSI-14 trend gate", "ATR-scaled geometry"],
    "acceptance_bar": {"min_closed_trades": 50, "PASS": "win rate >= 54.0% AND profit factor >= 1.25", "RETUNE": "48-54%", "FAIL": "< 48%"},
    "commitments": ["No mid-flight parameter changes before N=50."],
    "amendments": [{"utc": "2026-09-01T05:00:10+00:00", "closed_trades_at_amendment": 0, "change": "ATR from sampled true range", "why": "measurement"}],
    "known_defect_not_fixed": {"issue": "targets sized off 15m ATR but force-closed at 600s", "measured": "median 1,224s"},
}
HL_BASELINE_META = {
    "experiment": "baseline_unfiltered", "archived_utc": "2026-09-01T04:39:40+00:00",
    "status": "TERMINATED EARLY at N=12 of a pre-registered N=50", "why_archived": "Round 15 resets the paper account.",
    "closed_trades": 12, "wins": 3, "losses": 9, "win_rate_pct": 25.0, "profit_factor": 0.123, "net_pnl": -536.74,
    "key_finding": "Loss was GROSS.", "caveat": "N=12 is far below N>=30.",
}
AGENTS_FIXTURE = """# DEV log

## Status

Round 75 complete (2026-09-05): the protocol runs Directive 75-1 (lock, READY, last run, the log line) and,
only once Tier 1 has written its verdict, Directive 75-2 (both subfamilies under the registered bars). Ruling 39-1
applied to the spread convention.

## Round 39 findings

- Ruling 39-1: spread lines are stored as the selection's OWN handicap. Ratification 77-3 applied: odds_fetcher
  no longer binds print at import.
- Ruling R4 is enforced in code (the R-series is seeded elsewhere and must not be extracted here).
"""


class HLExperimentsTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.hl = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "experiments"
        self.hl.mkdir(parents=True)
        (self.hl / "regime_filtered_v1.meta.json").write_text(json.dumps(HL_REGIME), encoding="utf-8")
        (self.hl / "baseline_unfiltered_N12_2026-09-01.meta.json").write_text(json.dumps(HL_BASELINE_META), encoding="utf-8")
        (self.hl / "baseline_unfiltered_N12_2026-09-01.json").write_text(json.dumps({"closed_trades": 12, "positions": []}), encoding="utf-8")

    def test_hl_registration_and_archived_control_pages(self):
        report = ingest_exp.ingest_experiments([self.exp_dir, self.hl], self.vault, self.dev_root, at=NOW)
        self.assertIn("wiki/experiments/regime_filtered_v1_meta.md", report.written)
        self.assertIn("wiki/experiments/baseline_unfiltered_N12_2026-09-01_meta.md", report.written)
        self.assertIn("baseline_unfiltered_N12_2026-09-01.json", report.ignored)  # the data file is not a registration
        reg, body = fm.parse((self.vault / "wiki/experiments/regime_filtered_v1_meta.md").read_text(encoding="utf-8"))
        self.assertEqual((reg["dev"]["desk"], reg["dev"]["kind"]), (1, "registration"))
        self.assertEqual(reg["dev"]["requires_files"], ["HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.json"])
        self.assertEqual(reg["dev"]["parameters"], [{"name": "regime_filtered_v1_acceptance_bar_min_closed_trades", "value": 50,
                                                     "file": "HyperLiquid/HL_Monarch/data/experiments/regime_filtered_v1.meta.json",
                                                     "json_path": "acceptance_bar.min_closed_trades"}])
        self.assertIn("## Acceptance bar", body)
        self.assertIn("| `PASS` | win rate >= 54.0% AND profit factor >= 1.25 |", body)
        self.assertIn("[[Desk_01_HyperLiquid_Monarch|", body)
        base, _ = fm.parse((self.vault / "wiki/experiments/baseline_unfiltered_N12_2026-09-01_meta.md").read_text(encoding="utf-8"))
        self.assertEqual(base["dev"]["kind"], "archived_control")
        names = {p["name"]: p["value"] for p in base["dev"]["parameters"]}
        self.assertEqual(names["baseline_unfiltered_closed_trades"], 12)
        self.assertEqual(names["baseline_unfiltered_net_pnl"], -536.74)
        self.assertEqual(base["dev"]["requires_files"], ["HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.json"])
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_overwriting_the_control_is_a_c1_finding(self):
        ingest_exp.ingest_experiments([self.exp_dir, self.hl], self.vault, self.dev_root, at=NOW)
        (self.hl / "baseline_unfiltered_N12_2026-09-01.meta.json").write_text(json.dumps(dict(HL_BASELINE_META, closed_trades=13)), encoding="utf-8")
        c1 = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C1"]
        self.assertTrue(any("baseline_unfiltered_closed_trades drift" in x.message for x in c1))
        (self.hl / "baseline_unfiltered_N12_2026-09-01.json").unlink()
        c1 = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C1"]
        self.assertTrue(any("requires_files[0] missing" in x.message for x in c1))

    def test_cli_default_dirs_and_repeatable_dir(self):
        out = io.StringIO()
        code = ingest_exp.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--dir", str(self.exp_dir), "--dir", str(self.hl),
                                "--at", "2026-09-05T20:00:00Z"], out=out)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("regime_filtered_v1_meta", out.getvalue())
        self.assertEqual(ingest_exp.main(["--vault", str(self.vault), "--dev-root", str(self.root / "empty")], out=io.StringIO()), EXIT_HALT)


class RulingsIngestTests(IngestFixture):
    def setUp(self):
        super().setUp()
        (self.dev_root / "AGENTS.md").write_text(AGENTS_FIXTURE, encoding="utf-8")

    def test_extraction_pages_register_and_lint(self):
        cits = ingest_rl.extract_citations(AGENTS_FIXTURE)
        self.assertEqual(sorted(cits), ["Directive 75-1", "Directive 75-2", "Ratification 77-3", "Ruling 39-1"])
        self.assertEqual(len(cits["Ruling 39-1"].occurrences), 2)
        self.assertEqual(cits["Ruling 39-1"].occurrences[1].section, "Round 39 findings")
        report = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        self.assertEqual(report.found, 4)
        self.assertEqual(sorted(report.written), ["wiki/rulings/Directive_75-1.md", "wiki/rulings/Directive_75-2.md",
                                                  "wiki/rulings/Ratification_77-3.md", "wiki/rulings/Ruling_39-1.md"])
        d, body = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertEqual(d["type"], "Ruling")
        self.assertEqual(d["status"], "draft")
        self.assertNotIn("verified", d)
        self.assertEqual((d["dev"]["round"], d["dev"]["ruling_id"], d["dev"]["kind"]), (75, "D75-1", "directive"))
        self.assertTrue(d["title"].startswith("Directive 75-1: lock, READY, last run"))
        self.assertEqual(d["dev"]["asserts"][0]["pattern"], r"Directive\s+75-1\b")
        # a citation wrapped across a line break must still be found by extraction AND by the pinned assert
        wrapped = AGENTS_FIXTURE + "\n## Round 76 findings\n\nThe watcher restart followed Directive\n76-2 exactly.\n"
        self.assertIn("Directive 76-2", ingest_rl.extract_citations(wrapped))
        self.assertIsNotNone(__import__("re").search(r"Directive\s+76-2\b", wrapped, __import__("re").M))
        self.assertIn("**Status** (line 5)", body)
        reg, _ = fm.parse((self.vault / "wiki/concepts/rulings_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], 7 + 4)  # R-series seeds + extracted
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        # rewriting the log so a citation disappears is a C1 finding
        (self.dev_root / "AGENTS.md").write_text(AGENTS_FIXTURE.replace("Ratification 77-3", "Ratification 77-4"), encoding="utf-8")
        self.assertTrue(any(x.code == "C1" and "Ratification" in x.message for x in lint.lint_vault(self.vault, self.dev_root, now=NOW)))

    def test_skip_force_and_cli(self):
        first = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        second = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        self.assertEqual((second.written, sorted(second.skipped)), ([], sorted(first.written)))
        third = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW, force=True)
        self.assertEqual(len(third.written), 4)
        out = io.StringIO()
        self.assertEqual(ingest_rl.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), EXIT_OK)
        self.assertIn("4 distinct citation(s)", out.getvalue())
        self.assertEqual(ingest_rl.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--agents", str(self.root / "nope.md")],
                                        out=io.StringIO()), EXIT_HALT)


class ComputationsTests(IngestFixture):
    def test_pages_are_declarative_okf_attested_computations(self):
        report = computations.write_computations(self.vault, self.dev_root, at=NOW)
        self.assertEqual(len(report.written), len(computations.COMPUTATIONS))
        self.assertEqual(sum(1 for c in computations.COMPUTATIONS if c.kind == "shell_twin"), 2)
        p, body = fm.parse((self.vault / "wiki/computations/lead_lag_check_data.md").read_text(encoding="utf-8"))
        self.assertEqual(p["type"], "Attested Computation")
        self.assertEqual(p["runtime"], "python")
        self.assertEqual(p["computation"], "python -m cross_market.lead_lag --check-data [--json]")
        self.assertEqual(p["executor"]["resource"], "cross_market/lead_lag.py")
        self.assertIn("ready", p["executor"]["receipt"])
        self.assertEqual(p["attester"]["resource"], "cross_market/tests/test_lead_lag.py")
        self.assertEqual(p["dev"]["dashboard"], "Cross_Market_Titans.md")
        self.assertNotIn("requires_files", p["dev"])  # module not present in the fixture -> nothing to guard
        self.assertIn("# Computation", body)
        self.assertIn("Declarative (R95-C)", body)
        reg, _ = fm.parse((self.vault / "wiki/concepts/computations_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], len(computations.COMPUTATIONS))
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        again = computations.write_computations(self.vault, self.dev_root, at=NOW)
        self.assertEqual(again.written, [])
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(computations.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class CalendarTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.cal_dir = Path(knowledge_pkg.__file__).parent / "calendars"  # the committed YAML is the fixture

    def test_fomc_events_carry_windows_and_the_december_utc_shift(self):
        report = ingest_cal.ingest_calendars(self.cal_dir, self.vault, self.dev_root, at=NOW)
        self.assertEqual(sorted(report.written), ["wiki/events/fomc_2026-09-16.md", "wiki/events/fomc_2026-10-28.md",
                                                  "wiki/events/fomc_2026-12-09.md", "wiki/events/tax_estimated_2026_q3.md",
                                                  "wiki/events/tax_estimated_2026_q4.md"])
        dec, body = fm.parse((self.vault / "wiki/events/fomc_2026-12-09.md").read_text(encoding="utf-8"))
        self.assertEqual(dec["dev"]["release_utc"], "2026-12-09T19:00:00Z")
        self.assertEqual(dec["dev"]["window"], {"start": "2026-12-09T18:58:00Z", "end": "2026-12-09T19:05:00Z"})
        self.assertTrue(dec["dev"]["sep"])
        self.assertIn("19:00Z on this date", body)
        octo, _ = fm.parse((self.vault / "wiki/events/fomc_2026-10-28.md").read_text(encoding="utf-8"))
        self.assertEqual((octo["dev"]["release_utc"], octo["dev"]["sep"]), ("2026-10-28T18:00:00Z", False))
        q3, _ = fm.parse((self.vault / "wiki/events/tax_estimated_2026_q3.md").read_text(encoding="utf-8"))
        self.assertEqual(q3["stale_after"], "2026-09-15T23:59:59Z")
        self.assertEqual((q3["dev"]["kind"], q3["dev"]["desk"], q3["dev"]["due"]), ("estimated_tax", 5, "2026-09-15"))
        self.assertNotIn("asserts", q3["dev"])  # tax_calendar.py is not in the fixture
        reg, _ = fm.parse((self.vault / "wiki/concepts/events_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], 5)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        # a passed deadline is L4 until deprecated
        self.assertTrue(any(x.code == "L4" for x in lint.lint_vault(self.vault, self.dev_root, now=datetime(2026, 9, 16, tzinfo=timezone.utc))))

    def test_window_refuses_writes_and_clob_enriches_instead_of_replacing(self):
        ingest_cal.ingest_calendars(self.cal_dir, self.vault, self.dev_root, at=NOW)
        with self.assertRaises(pages.WriteRefused):
            ingest_cal.ingest_calendars(self.cal_dir, self.vault, self.dev_root, at=datetime(2026, 9, 16, 18, 0, 30, tzinfo=timezone.utc), force=True)
        _, event, _ = ingest_clob.ingest_survival(CURVE_JSON, self.vault, self.dev_root, event_id="fomc_2026-09-16", source="curve.json",
                                                  at=datetime(2026, 9, 16, 18, 10, tzinfo=timezone.utc))
        self.assertEqual(event.meta["dev"]["window"], {"start": "2026-09-16T17:58:00Z", "end": "2026-09-16T18:05:00Z"})
        self.assertTrue(event.meta["dev"]["sep"])
        self.assertEqual(len(event.meta["dev"]["profiles"]), 2)
        self.assertEqual(event.meta["dev"]["release_utc"], "2026-09-16T18:00:00+00:00")  # the recording's value wins when present


class MarketsTests(IngestFixture):
    def test_market_pages_from_rules_experiments_and_family(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        report = ingest_mk.ingest_markets(self.vault, self.dev_root, at=NOW)
        self.assertEqual(report.tokens, 3)  # two rule tokens + TOK_CUTS2026 (FED-RATES); the CRYPTO record is not in the family
        names = sorted(Path(r).name for r in report.written)
        self.assertEqual(names, ["will-no-fed-rate-cuts-happen-in-2026.md",
                                 "will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649.md",
                                 "will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615.md"])
        m, body = fm.parse((self.vault / "wiki/markets/will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615.md")
                           .read_text(encoding="utf-8"))
        self.assertEqual(m["type"], "Market")
        self.assertEqual(m["resource"], "polymarket:token:TOK_NOCHANGE")
        self.assertEqual((m["dev"]["token_id"], m["dev"]["family"], m["dev"]["neg_risk"], m["dev"]["rule_label"]),
                         ("TOK_NOCHANGE", "FED-RATES", True, "FOMC 2026-09-16: no change"))
        self.assertEqual(m["dev"]["first_seen"], "2026-09-05T19:25:36Z")
        self.assertNotIn("yes_price", json.dumps(m))  # no copied prices
        self.assertNotIn("0.5", body.split("## Identity")[1].split("## Bound by")[0])
        reg, _ = fm.parse((self.vault / "wiki/concepts/markets_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], 3)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        again = ingest_mk.ingest_markets(self.vault, self.dev_root, at=NOW)
        self.assertEqual(again.written, [])

    def test_c2_then_fix_safe_deprecates_a_vanished_market(self):
        ingest_mk.ingest_markets(self.vault, self.dev_root, at=NOW)
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        (drops / "polymarket_macro_20260906T000000_000000Z.json").write_text(json.dumps([
            {"token_id": "TOK_NOCHANGE", "sport": "FED-RATES"}, {"token_id": "TOK_HIKE25", "sport": "FED-RATES"}]), encoding="utf-8")
        before = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C2"]
        self.assertEqual(len(before), 1)
        self.assertIn("TOK_CUTS2026", before[0].message)
        out = io.StringIO()
        code = lint.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--fix-safe"], out=out)
        self.assertEqual(code, EXIT_OK)  # after the fix the vault is clean again
        self.assertIn("[FIX-SAFE] deprecated 1 Market page(s)", out.getvalue())
        m, _ = fm.parse((self.vault / "wiki/markets/will-no-fed-rate-cuts-happen-in-2026.md").read_text(encoding="utf-8"))
        self.assertEqual(m["status"], "deprecated")
        self.assertIn("not in the newest drops", m["dev"]["deprecated"]["reason"])
        self.assertIn("* **Lint**: --fix-safe deprecated 1 Market page(s)", (self.vault / "log.md").read_text(encoding="utf-8"))
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_cli_guards(self):
        out = io.StringIO()
        self.assertEqual(ingest_mk.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--family", "CRYPTO",
                                         "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("bitcoin-above-78k-on-september-6-2026", out.getvalue())
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ingest_mk.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class RegistersAndSeedLinksTests(IngestFixture):
    def test_every_desk_links_every_register(self):
        body = (self.vault / "wiki/desks/Desk_04_Quant_Trading_Lab.md").read_text(encoding="utf-8")
        for stem in registers.REGISTER_STEMS:
            self.assertIn(f"[[{stem}|", body)
        self.assertEqual(len(registers.REGISTER_STEMS), 5)

    def test_register_columns_and_cells(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        reg = registers.update_register(self.vault, "Experiment", at=NOW)
        self.assertIn("| [[fomc_2026-09-16_rules\\|Experiment: latency_sniper_fomc_2026-09-16]] | sniper_rules | draft |", reg.body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
