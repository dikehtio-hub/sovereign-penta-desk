"""Master Module 23 tests: frontmatter, pages/ownership, lint L1-L5 + C1/C5, seed.

Everything runs in temporary directories. No network, no real vault, no real
DEV root: the fixture builds its own registry and its own source files so
C1 has something to grep.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import os
import tempfile
import unittest

import yaml
from datetime import date, datetime, timedelta, timezone
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
    # Round 100 (L7): a policed type gets a far-future stale_after unless the test passes one, or None to omit it.
    stale = kw.pop("stale_after", "default")
    if stale == "default" and type_ in pages.STALENESS_DAYS and kw.get("status") != "deprecated":
        kw["stale_after"] = "2027-12-31T00:00:00Z"
    elif stale not in ("default", None):
        kw["stale_after"] = stale
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
        # Round 105: every real vault has the constitution - it is in OWNED_FILES and every
        # register links it - so a fixture without one is not a smaller vault, it is an
        # impossible one. Its absence made lint L8 report [[WIKI_SCHEMA]] dangling in 30 tests.
        (self.vault / "WIKI_SCHEMA.md").write_text(
            "---\ntype: Concept\ntitle: WIKI_SCHEMA\ndescription: The constitution.\n"
            "generated:\n  by: human:operator\n  at: '2026-09-05T00:00:00Z'\nstatus: stable\n"
            "stale_after: '2030-01-01T00:00:00Z'\n---\n\n# Constitution\n\n"
            "Answer with `[[wikilinks]]`.\n", encoding="utf-8")
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
        # Round 104: --force still clobbers the hand edit (machine-maintained means machine-maintained),
        # but it now rewrites ONLY that page. The other 14 are byte-identical and keep the stamp they
        # earned, so touching MASTER_COMMAND_LIST.txt no longer restamps the whole vault.
        self.assertEqual(third.written, ["wiki/rulings/Ruling_R04.md"])
        self.assertEqual(len(third.unchanged), 14)
        self.assertNotIn("human edit", target.read_text(encoding="utf-8"))

    def test_force_keeps_the_original_stamp_and_any_ratification_on_an_unchanged_page(self):
        seed.seed(self.vault, self.dev_root, self.registry(), at=NOW)
        desk = self.vault / "wiki/desks/Desk_01_HyperLiquid_Monarch.md"
        meta, body = fm.parse(desk.read_text(encoding="utf-8"))
        meta["verified"] = [{"by": "antigravity/architect", "at": pages.iso(NOW)}]
        meta["status"] = "stable"
        meta.setdefault("dev", {})["ratified_by"] = "104-1"
        pages.write_page(pages.Page(desk, meta, body), self.vault, now=NOW)
        later = NOW + timedelta(days=3)                      # as if the registry file had been touched
        report = seed.seed(self.vault, self.dev_root, self.registry(), at=later, force=True)
        self.assertIn("wiki/desks/Desk_01_HyperLiquid_Monarch.md", report.unchanged)
        after, _ = fm.parse(desk.read_text(encoding="utf-8"))
        self.assertEqual(after["generated"]["at"], pages.iso(NOW))     # not restamped to `later`
        self.assertEqual(after["verified"][0]["by"], "antigravity/architect")
        self.assertEqual(after["status"], "stable")
        self.assertEqual(after["dev"]["ratified_by"], "104-1")

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
        {"label": "FOMC 2026-09-16: no change", "market": "7000000000000000000000000000000000000000000000000000000000000000000000000001", "kind": "fed_rate", "field": "change_bps", "op": "==",
         "value": 0, "outcome_if_true": "YES", "yes_price_at_registration": 0.5, "neg_risk": True,
         "question": "Will there be no change in Fed interest rates after the September 2026 meeting?",
         "market_slug": "will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615"},
        {"label": "FOMC 2026-09-16: hike 25 bps", "market": "7000000000000000000000000000000000000000000000000000000000000000000000000002", "kind": "fed_rate", "field": "change_bps", "op": "==",
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
        {"market": "7000000000000000000000000000000000000000000000000000000000000000000000000001", "rule": "FOMC 2026-09-16: no change", "outcome": "YES", "side": "BUY_YES", "stamps": 6,
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
        {"market": "7000000000000000000000000000000000000000000000000000000000000000000000000002", "rule": "FOMC 2026-09-16: hike 25 bps", "outcome": "NO", "side": "BUY_NO", "stamps": 6,
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
            {"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000001", "sport": "FED-RATES", "question": "Will there be no change in Fed interest rates after the September 2026 meeting?",
             "market_slug": "will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615", "condition_id": "0xabc",
             "event_slug": "fed-decision-in-september-2026", "event_title": "Fed decision in September?", "fetched_at": "2026-09-05T19:25:36Z",
             "yes_price": 0.5, "yes_bid": 0.49},
            {"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000002", "sport": "FED-RATES", "question": "Will the Fed increase interest rates by 25 bps after the September 2026 meeting?",
             "market_slug": "will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649", "condition_id": "0xdef",
             "fetched_at": "2026-09-05T19:25:36Z", "yes_price": 0.5},
            {"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000003", "sport": "FED-RATES", "question": "Will no Fed rate cuts happen in 2026?",
             "market_slug": "will-no-fed-rate-cuts-happen-in-2026", "condition_id": "0x123", "fetched_at": "2026-09-05T19:25:36Z", "yes_price": 0.93},
            {"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000004", "sport": "CRYPTO", "question": "Will the price of Bitcoin be above $78,000 on September 6?",
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
        self.assertEqual(meta["dev"]["tokens"], ["7000000000000000000000000000000000000000000000000000000000000000000000000001", "7000000000000000000000000000000000000000000000000000000000000000000000000002"])
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
        (drops / "polymarket_macro_20260906T000000_000000Z.json").write_text(json.dumps([{"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000001"}]), encoding="utf-8")
        c2 = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C2"]
        self.assertEqual(len(c2), 1)
        self.assertIn("7000000000000000000000000000000000000000000000000000000000000000000000000002"[:12], c2[0].message)

    def test_experiments_skip_existing_unless_force_and_cli_guards(self):
        first = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        second = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.assertEqual(second.written, [])
        self.assertEqual(sorted(second.skipped), sorted(first.written))
        third = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW, force=True)
        # Round 112 (R104-3 reaches this adapter): --force over UNCHANGED registrations writes nothing
        # and logs nothing - rewriting identical content is not ingesting it. A real edit still counts.
        self.assertEqual(third.written, [])
        self.assertEqual(len(third.skipped), 2)
        rules = json.loads((self.exp_dir / "fomc_2026-09-16.rules.json").read_text(encoding="utf-8"))
        rules["reading"] = "amended so the page really changes"
        (self.exp_dir / "fomc_2026-09-16.rules.json").write_text(json.dumps(rules), encoding="utf-8")
        fourth = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW, force=True)
        self.assertEqual(fourth.written, ["wiki/experiments/fomc_2026-09-16_rules.md"])
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("**Ingest**"), 2)  # first run + the real edit; the two no-op runs appended nothing
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

    def test_cli_defaults_to_the_exporter_artifact(self):
        """Ruling R102-2: with no --result, read the file the exporter writes beside the dashboard."""
        out = io.StringIO()
        code = ingest_ll.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--tier", "1"], out=out)
        self.assertEqual(code, EXIT_HALT)                       # not written yet -> refuse, with the reason
        self.assertIn("lead_lag_latest_verdict.json", out.getvalue())
        self.assertIn("the exporter writes it on each refresh", out.getvalue())
        artifact = self.dev_root / ingest_ll.DEFAULT_RESULT
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(VERDICT_JSON), encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(ingest_ll.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--tier", "1",
                                         "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("class=polymarket-leads", out.getvalue())
        page = pages.load_page(self.vault / "wiki/experiments/lead_lag_tier1_macro_20260905T2000Z.md")
        self.assertEqual(page.meta["sources"][0]["resource"], "cross_market/data/lead_lag_latest_verdict.json")

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
        nc = next(p for p in profiles if p.meta["dev"]["token_id"] == "7000000000000000000000000000000000000000000000000000000000000000000000000001")
        self.assertEqual(nc.meta["type"], "Reaction Profile")
        self.assertEqual(nc.meta["dev"]["summary"]["half_s"], 1.0)
        self.assertEqual(nc.meta["dev"]["summary"]["notional_seconds"], 785.0)
        self.assertIn("| half of baseline gone by | 1 s |", nc.body)
        self.assertIn("| +1 | $240 | 400 | 0.6 | 2 | yes |", nc.body)   # checkpoint row
        self.assertNotIn("17:59:58", nc.body)                             # the per-second series is not copied
        deferred = next(p for p in profiles if p.meta["dev"]["token_id"] == "7000000000000000000000000000000000000000000000000000000000000000000000000002")
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

## Round 66 findings

- Ruling 66-1: the [x] checkbox | column and the `pid` lock stay as they are.
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
        self.assertEqual((reg["dev"]["item"], reg["dev"]["related_items"]), (14, [8]))  # Round 99 attribution ruling
        # Round 105 (lint L8): this fixture's registry has no Item 14, so the reference degrades to
        # readable plain text instead of emitting a wikilink that resolves to nothing.
        self.assertIn("Item 14: Hyperliquid Whale Cascade Sweeper (Item page not seeded) (primary)", body)
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
        self.assertEqual(sorted(cits), ["Directive 75-1", "Directive 75-2", "Ratification 77-3", "Ruling 39-1", "Ruling 66-1"])
        self.assertEqual(len(cits["Ruling 39-1"].occurrences), 2)
        self.assertEqual(cits["Ruling 39-1"].occurrences[1].section, "Round 39 findings")
        report = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        self.assertEqual(report.found, 5)
        self.assertEqual(sorted(report.written), ["wiki/rulings/Directive_75-1.md", "wiki/rulings/Directive_75-2.md",
                                                  "wiki/rulings/Ratification_77-3.md", "wiki/rulings/Ruling_39-1.md", "wiki/rulings/Ruling_66-1.md"])
        r66, _ = fm.parse((self.vault / "wiki/rulings/Ruling_66-1.md").read_text(encoding="utf-8"))
        self.assertEqual(r66["title"], "Ruling 66-1: the x checkbox column and the pid lock stay as they are")  # no [ ] | in a title
        entries, errors = pages.parse_index((self.vault / "index.md").read_text(encoding="utf-8"))
        self.assertEqual(errors, [])
        self.assertIn("wiki/rulings/Ruling_66-1.md", {e.path for e in entries})
        d, body = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertEqual(d["type"], "Ruling")
        self.assertEqual(d["status"], "draft")
        self.assertNotIn("verified", d)
        self.assertEqual((d["dev"]["round"], d["dev"]["ruling_id"], d["dev"]["kind"]), (75, "D75-1", "directive"))
        self.assertTrue(d["title"].startswith("Directive 75-1: Round 75 complete"), d["title"])  # the whole sentence, cleaned
        self.assertNotIn(").", d["title"])
        # Round 99: a citation that closes a parenthetical must not yield `: ).…`
        cit = ingest_rl.Citation("Ruling", 74, 2, [ingest_rl.Occurrence("Status", 3, "…the maiden run reads tagged stamps only (Ruling 74-2). Tier 1 is untouched…")])
        self.assertEqual(ingest_rl._first_clause(cit), "the maiden run reads tagged stamps only")
        cit2 = ingest_rl.Citation("Directive", 79, 2, [ingest_rl.Occurrence("Status", 3, "Directive 79-2's three manual steps are now one batch file.")])
        self.assertEqual(ingest_rl._first_clause(cit2), "three manual steps are now one batch file")
        self.assertEqual(d["dev"]["asserts"][0]["pattern"], r"Directive\s+75-1\b")
        # a citation wrapped across a line break must still be found by extraction AND by the pinned assert
        wrapped = AGENTS_FIXTURE + "\n## Round 76 findings\n\nThe watcher restart followed Directive\n76-2 exactly.\n"
        self.assertIn("Directive 76-2", ingest_rl.extract_citations(wrapped))
        self.assertIsNotNone(__import__("re").search(r"Directive\s+76-2\b", wrapped, __import__("re").M))
        self.assertIn("**Status** (line 5)", body)
        reg, _ = fm.parse((self.vault / "wiki/concepts/rulings_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], 7 + 5)  # R-series seeds + extracted
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        # rewriting the log so a citation disappears is a C1 finding
        (self.dev_root / "AGENTS.md").write_text(AGENTS_FIXTURE.replace("Ratification 77-3", "Ratification 77-4"), encoding="utf-8")
        self.assertTrue(any(x.code == "C1" and "Ratification" in x.message for x in lint.lint_vault(self.vault, self.dev_root, now=NOW)))

    def test_skip_force_and_cli(self):
        first = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        second = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        self.assertEqual((second.written, sorted(second.skipped)), ([], sorted(first.written)))
        third = ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW, force=True)
        self.assertEqual(len(third.written), 5)
        out = io.StringIO()
        self.assertEqual(ingest_rl.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), EXIT_OK)
        self.assertIn("5 distinct citation(s)", out.getvalue())
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
        self.assertEqual(report.tokens, 3)  # two rule tokens + 7000000000000000000000000000000000000000000000000000000000000000000000000003 (FED-RATES); the CRYPTO record is not in the family
        names = sorted(Path(r).name for r in report.written)
        self.assertEqual(names, ["will-no-fed-rate-cuts-happen-in-2026.md",
                                 "will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649.md",
                                 "will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615.md"])
        m, body = fm.parse((self.vault / "wiki/markets/will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615.md")
                           .read_text(encoding="utf-8"))
        self.assertEqual(m["type"], "Market")
        self.assertEqual(m["resource"], "polymarket:token:7000000000000000000000000000000000000000000000000000000000000000000000000001")
        self.assertEqual((m["dev"]["token_id"], m["dev"]["family"], m["dev"]["neg_risk"], m["dev"]["rule_label"]),
                         ("7000000000000000000000000000000000000000000000000000000000000000000000000001", "FED-RATES", True, "FOMC 2026-09-16: no change"))
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
            {"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000001", "sport": "FED-RATES"}, {"token_id": "7000000000000000000000000000000000000000000000000000000000000000000000000002", "sport": "FED-RATES"}]), encoding="utf-8")
        before = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C2"]
        self.assertEqual(len(before), 1)
        self.assertIn("7000000000000000000000000000000000000000000000000000000000000000000000000003"[:12], before[0].message)
        out = io.StringIO()
        code = lint.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--fix-safe"], out=out)
        self.assertEqual(code, EXIT_OK)  # after the fix the vault is clean again
        self.assertIn("[FIX-SAFE] deprecated 1 Market page(s)", out.getvalue())
        m, _ = fm.parse((self.vault / "wiki/markets/will-no-fed-rate-cuts-happen-in-2026.md").read_text(encoding="utf-8"))
        self.assertEqual(m["status"], "deprecated")
        self.assertIn("not in the newest drops", m["dev"]["deprecated"]["reason"])
        self.assertIn("* **Lint**: --fix-safe deprecated 1 Market page(s)", (self.vault / "log.md").read_text(encoding="utf-8"))
        self.assertIn("[index](index.md) rebuilt", (self.vault / "log.md").read_text(encoding="utf-8"))  # Ruling 98-5
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_cli_guards(self):
        out = io.StringIO()
        self.assertEqual(ingest_mk.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--family", "CRYPTO",
                                         "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("bitcoin-above-78k-on-september-6-2026", out.getvalue())
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ingest_mk.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class RegistersAndSeedLinksTests(IngestFixture):
    def test_every_desk_links_the_hub_and_the_hub_lists_every_register(self):
        """Ruling R111-1.C: one hop from a desk to any register, through the catalogue."""
        body = (self.vault / "wiki/desks/Desk_04_Quant_Trading_Lab.md").read_text(encoding="utf-8")
        self.assertIn("[[registers_register|", body)
        for stem in registers.REGISTER_STEMS:
            if stem != registers.HUB_STEM:
                self.assertNotIn(f"[[{stem}|", body)        # the bloat is gone from the desk
        hub = (self.vault / "wiki/concepts/registers_register.md").read_text(encoding="utf-8")
        for stem in registers.REGISTER_STEMS:
            if stem != registers.HUB_STEM:
                self.assertIn(f"[[{stem}\\|", hub)          # and every one of them is in the hub
        self.assertNotIn(f"[[{registers.HUB_STEM}\\|", hub)   # which does not list itself
        self.assertEqual(len(registers.REGISTER_STEMS), 11)
        self.assertEqual(registers.REGISTER_STEMS[-1], registers.HUB_STEM)   # LAST: seed writes in order

    def test_register_columns_and_cells(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        reg = registers.update_register(self.vault, "Experiment", at=NOW)
        # Round 112: a `progress` column follows `kind`; a rules registration has no sample bar, so `-`
        self.assertIn("| [[fomc_2026-09-16_rules\\|Experiment: latency_sniper_fomc_2026-09-16]] | sniper_rules | - | draft |", reg.body)


# ---------------------------------------------------------------- Round 99: CRM seeds + ratification

import sqlite3  # noqa: E402

from knowledge import ratify as ratify_mod  # noqa: E402
from knowledge.ingest import entities as ingest_ent  # noqa: E402

EOA_WHALE = "0xaaaa000000000000000000000000000000000001"
EOA_SHARP = "0xbbbb000000000000000000000000000000000002"
EOA_NOWHERE = "0xcccc000000000000000000000000000000000003"
W2, W3 = "0xdddd000000000000000000000000000000000004", "0xeeee000000000000000000000000000000000005"
SHARP1, SHARP2 = "0x1111000000000000000000000000000000000011", "0x2222000000000000000000000000000000000022"


class CRMFixture(IngestFixture):
    def setUp(self):
        super().setUp()
        (self.dev_root / "cross_market" / "titan_identities_cache.json").write_text(json.dumps({
            EOA_WHALE: {"proxy_wallet": "0xp1", "pseudonym": "VBVIT"},          # whale with a proxy nobody has seen trade: NOT a titan
            EOA_SHARP: {"proxy_wallet": SHARP1, "pseudonym": "Blue-Smith"},     # proxy is a sharp wallet and the sharp's EOA matches: titan
            W2: {"proxy_wallet": SHARP2, "pseudonym": "Applewood-HL"},          # whale whose proxy is a sharp wallet: titan
            EOA_NOWHERE: {"proxy_wallet": "0xp3", "pseudonym": "Ghost"},        # on neither venue's tables: NOT a titan
        }), encoding="utf-8")
        hl = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data"
        hl.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(hl / "hyperliquid_data.db")
        c.execute("CREATE TABLE whale_wallets (address TEXT PRIMARY KEY, discovered_at INTEGER, first_coin TEXT, first_notional REAL, "
                  "total_position_value REAL, account_value REAL, is_liquidator INTEGER, last_scanned_at INTEGER)")
        c.executemany("INSERT INTO whale_wallets VALUES (?,?,?,?,?,?,?,?)", [
            (EOA_WHALE, 1788111351386, "BTC", 65003.8, 158093023.15, 73059495.55, 1, 1788111353767),
            (W2, 1788111351386, "ETH", 199200.0, 17903035.1, 475093.45, 0, 1788111353767),
            (W3, 1788111351386, "SOL", 1000.0, 1000.0, 100.0, 0, 1788111353767),
        ])
        c.commit(); c.close()
        pm = self.dev_root / "Polymarket" / "Polymarket_Monarch" / "data"
        pm.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(pm / "polymarket_whales.db")
        c.execute("CREATE TABLE sharp_traders (wallet TEXT PRIMARY KEY, pseudonym TEXT, pnl_7d REAL, volume_7d REAL, trades_7d INTEGER, win_rate REAL, "
                  "is_sharp INTEGER, polymarket_link TEXT, last_scanned TEXT, realized_pnl_7d REAL, unrealized_pnl REAL, open_positions INTEGER, "
                  "closed_positions_7d INTEGER, volume_is_partial INTEGER, proxy_wallet TEXT, eoa_address TEXT, identity_resolved_at TEXT)")
        c.executemany("INSERT INTO sharp_traders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            (SHARP1, "Blue-Smith", 19366.75, 8403.79, 477, 100.0, 1, "https://polymarket.com/profile/" + SHARP1, "2026-09-02 04:17:41",
             27634.51, -8267.76, 3, 40, 0, SHARP1, EOA_SHARP, "2026-08-31 04:08:02"),
            (SHARP2, "Assured-Applewood", 0.0, 0.0, 0, 0.0, 0, "https://polymarket.com/profile/" + SHARP2, "2026-08-30 01:35:22",
             0.0, 0.0, 0, None, 0, SHARP2, None, None),
        ])
        c.execute("CREATE TABLE tracked_wallets (wallet TEXT PRIMARY KEY, pseudonym TEXT, first_seen TEXT, last_seen TEXT, trade_count INTEGER, "
                  "total_volume_usd REAL, last_scanned TEXT)")
        c.execute("INSERT INTO tracked_wallets VALUES (?,?,?,?,?,?,?)", (SHARP1, "Blue-Smith", "2026-08-30 01:00:00", "2026-09-02 04:00:00", 477, 8403.79, "2026-09-02 04:17:41"))
        c.commit(); c.close()
        sp = self.dev_root / "Sports_Desk" / "data"
        sp.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(sp / "sports_market.db")
        c.execute("CREATE TABLE fair_odds_measurements (id INTEGER PRIMARY KEY, timestamp TEXT, sportsbook TEXT)")
        c.executemany("INSERT INTO fair_odds_measurements VALUES (?,?,?)", [(1, "2026-09-04T04:01:42+00:00", "pinnacle"), (2, "2026-09-04T05:01:42+00:00", "pinnacle")])
        c.execute("CREATE TABLE edge_opportunities (id INTEGER PRIMARY KEY, timestamp TEXT, sport TEXT, market_type TEXT, sharp_book TEXT, retail_book TEXT, "
                  "gross_edge REAL, clears_hurdle INTEGER)")
        c.executemany("INSERT INTO edge_opportunities VALUES (?,?,?,?,?,?,?,?)", [
            (1, "2026-09-04T04:01:42+00:00", "NFL", "moneyline", "pinnacle", "draftkings", -0.0087, 0),
            (2, "2026-09-04T05:01:42+00:00", "NFL", "moneyline", "pinnacle", "draftkings", 0.0210, 1),
            (3, "2026-09-04T05:01:42+00:00", "NFL", "totals", "pinnacle", "fanduel", 0.0150, 0),
        ])
        c.commit(); c.close()


class EntitiesIngestTests(CRMFixture):
    def test_titans_are_the_intersection_and_pages_link_both_ways(self):
        report = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW)
        self.assertEqual(report.counts, {"titans": 2, "whales": 3, "sharps": 2, "books": 3})
        self.assertEqual(report.missing_sources, [])
        self.assertEqual(len(report.created), 2 + 3 + 2 + 3)
        self.assertFalse((self.vault / f"crm/titans/titan_{EOA_NOWHERE}.md").exists())  # cached but on neither venue's tables
        self.assertFalse((self.vault / f"crm/titans/titan_{EOA_WHALE}.md").exists())    # a whale with an unseen proxy is not a titan
        t, body = fm.parse((self.vault / f"crm/titans/titan_{EOA_SHARP}.md").read_text(encoding="utf-8"))
        self.assertEqual(t["type"], "Entity/Titan")
        self.assertEqual((t["dev"]["in_whales"], t["dev"]["in_polymarket"], t["dev"]["pseudonym"]), (False, True, "Blue-Smith"))
        self.assertIn(f"[[sharp_{SHARP1}|sharp page]]", body)
        t2, body2 = fm.parse((self.vault / f"crm/titans/titan_{W2}.md").read_text(encoding="utf-8"))
        self.assertEqual((t2["dev"]["in_whales"], t2["dev"]["proxy_wallet"]), (True, SHARP2))
        self.assertIn(f"[[whale_{W2}|whale page]]", body2)
        w, wbody = fm.parse((self.vault / f"crm/whales/whale_{EOA_WHALE}.md").read_text(encoding="utf-8"))
        self.assertEqual(w["dev"]["rank_at_seed"], 1)
        self.assertNotIn("titan", w["dev"])
        self.assertEqual(w["dev"]["evidence"][0]["account_value"], 73059495.55)
        self.assertEqual(w["dev"]["evidence"][0]["at"], "2026-08-30T17:35:53Z")  # epoch ms 1788111353767 -> ISO
        # Round 105 (lint L8): the exporter-owned note is linked only when it EXISTS, and this
        # fixture writes none - 85 CRM pages used to link notes that were never there.
        self.assertIn(f"none written for `{EOA_WHALE}`", wbody)
        (self.vault / "Whales" / f"{EOA_WHALE}.md").write_text("# w\n", encoding="utf-8")
        ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW + timedelta(hours=1))
        wbody2 = fm.parse((self.vault / f"crm/whales/whale_{EOA_WHALE}.md").read_text(encoding="utf-8"))[1]
        self.assertIn(f"[[Whales/{EOA_WHALE}|whale note]]", wbody2)  # linked, still never written by us
        w2, _ = fm.parse((self.vault / f"crm/whales/whale_{W2}.md").read_text(encoding="utf-8"))
        self.assertEqual((w2["dev"]["rank_at_seed"], w2["dev"]["titan"]), (2, f"titan_{W2}"))
        s, sbody = fm.parse((self.vault / f"crm/sharps/sharp_{SHARP1}.md").read_text(encoding="utf-8"))
        self.assertEqual((s["dev"]["eoa_address"], s["dev"]["titan"], s["dev"]["first_seen"]), (EOA_SHARP, f"titan_{EOA_SHARP}", "2026-08-30T01:00:00Z"))
        self.assertEqual(s["dev"]["evidence"][0]["is_sharp"], True)
        s2, _ = fm.parse((self.vault / f"crm/sharps/sharp_{SHARP2}.md").read_text(encoding="utf-8"))
        self.assertEqual(s2["dev"]["titan"], f"titan_{W2}")  # linked through the proxy, not the EOA
        b, bbody = fm.parse((self.vault / "crm/books/book_draftkings.md").read_text(encoding="utf-8"))
        self.assertEqual((b["type"], b["dev"]["role"]), ("Entity/Sportsbook", "soft"))
        self.assertEqual(b["dev"]["evidence"][0]["edges"], 2)
        self.assertEqual(b["dev"]["evidence"][0]["cleared"], 1)
        pin, _ = fm.parse((self.vault / "crm/books/book_pinnacle.md").read_text(encoding="utf-8"))
        self.assertEqual((pin["dev"]["role"], pin["dev"]["measurements"]), ("sharp", 2))
        reg, _ = fm.parse((self.vault / "wiki/concepts/crm_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], 10)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_judgement_and_human_fields_survive_reingest_and_evidence_appends(self):
        ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW)
        p = self.vault / f"crm/whales/whale_{EOA_WHALE}.md"
        text = p.read_text(encoding="utf-8")
        text = text.replace(ingest_ent.JUDGEMENT_PLACEHOLDER, "Adds to BTC longs into funding spikes; never seen on the short side.")
        text = text.replace("status: draft", "status: stable\nverified:\n- by: human:operator\n  at: '2026-09-05T21:00:00Z'")
        p.write_text(text, encoding="utf-8")
        # a new scan in the database -> one more evidence row, judgement and human fields intact
        c = sqlite3.connect(self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db")
        c.execute("UPDATE whale_wallets SET account_value = 80000000.0, last_scanned_at = 1788200000000 WHERE address = ?", (EOA_WHALE,))
        c.commit(); c.close()
        report = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW + timedelta(days=1))
        self.assertIn(f"crm/whales/whale_{EOA_WHALE}.md", report.updated)
        w, body = fm.parse(p.read_text(encoding="utf-8"))
        self.assertIn("Adds to BTC longs into funding spikes", body)
        self.assertEqual(w["status"], "stable")
        self.assertEqual(w["verified"], [{"by": "human:operator", "at": "2026-09-05T21:00:00Z"}])
        self.assertEqual([r["account_value"] for r in w["dev"]["evidence"]], [73059495.55, 80000000.0])
        # same scan again -> no duplicate row
        ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW + timedelta(days=2))
        w, _ = fm.parse(p.read_text(encoding="utf-8"))
        self.assertEqual(len(w["dev"]["evidence"]), 2)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW + timedelta(days=2)), [])

    def test_limits_missing_sources_and_cli(self):
        report = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW, limit_whales=1, limit_titans=1)
        self.assertEqual((report.counts["whales"], report.counts["titans"]), (1, 1))
        self.assertTrue((self.vault / f"crm/titans/titan_{W2}.md").exists())  # the titan with whale equity ranks first
        (self.dev_root / "Sports_Desk" / "data" / "sports_market.db").unlink()
        report = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW)
        self.assertEqual(report.missing_sources, ["Sports_Desk/data/sports_market.db"])
        self.assertEqual(report.counts["books"], 0)
        out = io.StringIO()
        self.assertEqual(ingest_ent.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--at", "2026-09-05T20:00:00Z"], out=out), EXIT_OK)
        self.assertIn("[SKIP]  source not found: Sports_Desk/data/sports_market.db", out.getvalue())
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ingest_ent.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class RatifyTests(RulingsIngestTests):
    def test_ratify_extracted_rulings_only_and_idempotent(self):
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        report = ratify_mod.ratify(self.vault, type_="Ruling", tag="extracted", ruling="98-1", at=NOW + timedelta(hours=1))
        self.assertEqual((report.selected, len(report.ratified), report.already), (5, 5, []))
        d, _ = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertEqual(d["status"], "stable")
        self.assertEqual(d["verified"], [{"by": "antigravity/architect", "at": "2026-09-05T21:00:00Z"}])
        self.assertEqual(d["dev"]["ratified_by"], "98-1")
        r1, _ = fm.parse((self.vault / "wiki/rulings/Ruling_R01.md").read_text(encoding="utf-8"))
        self.assertNotIn("verified", r1)  # the R-series is not tagged `extracted`: untouched
        again = ratify_mod.ratify(self.vault, type_="Ruling", tag="extracted", ruling="98-1", at=NOW + timedelta(hours=2))
        self.assertEqual((again.ratified, len(again.already)), ([], 5))
        # a forced re-extraction keeps the ratification (Round 99 invariant, shared carry_human_fields)
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW + timedelta(hours=3), force=True)
        d, _ = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertEqual((d["status"], d["verified"][0]["by"], d["dev"]["ratified_by"]), ("stable", "antigravity/architect", "98-1"))
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("**Ratify**"), 1)
        self.assertIn("Ruling 98-1: 5 Ruling page(s) tagged `extracted` verified by `antigravity/architect`", log)
        reg, _ = fm.parse((self.vault / "wiki/concepts/rulings_register.md").read_text(encoding="utf-8"))
        self.assertIn("| directive | 75 | stable |", registers.update_register(self.vault, "Ruling", at=NOW).body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW + timedelta(hours=3)), [])

    def test_ratify_never_covers_a_later_round(self):
        (self.dev_root / "AGENTS.md").write_text(AGENTS_FIXTURE + "\n## Round 99 findings\n\nRuling 99-2 says carry human fields everywhere.\n", encoding="utf-8")
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        report = ratify_mod.ratify(self.vault, type_="Ruling", tag="extracted", ruling="98-1", at=NOW)
        self.assertEqual(report.skipped_later, ["wiki/rulings/Ruling_99-2.md"])
        self.assertEqual(report.selected, 5)  # the four Round 39-77 pages + Ruling 66-1; 99-2 is later than round 98
        r, _ = fm.parse((self.vault / "wiki/rulings/Ruling_99-2.md").read_text(encoding="utf-8"))
        self.assertNotIn("verified", r)
        self.assertEqual(ratify_mod.ruling_round("98-1"), 98)
        self.assertIsNone(ratify_mod.ruling_round("R95"))

    def test_ratify_one_page_by_stem(self):
        """Round 103b: ratifying a single registration must not sweep every page of that type."""
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        report = ratify_mod.ratify(self.vault, type_="Ruling", stem="Directive_75-1", ruling="103-1", at=NOW)
        self.assertEqual((report.selected, report.ratified), (1, ["wiki/rulings/Directive_75-1.md"]))
        d, _ = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertEqual((d["status"], d["dev"]["ratified_by"]), ("stable", "103-1"))
        other, _ = fm.parse((self.vault / "wiki/rulings/Directive_75-2.md").read_text(encoding="utf-8"))
        self.assertNotIn("verified", other)
        out = io.StringIO()
        self.assertEqual(ratify_mod.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--type", "Ruling",
                                          "--stem", "Ruling_39-1", "--ruling", "103-1"], out=out), EXIT_OK)
        self.assertIn("1 selected, 1 verified", out.getvalue())

    def test_ratify_cli_and_actor_check(self):
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        out = io.StringIO()
        self.assertEqual(ratify_mod.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--type", "Ruling", "--tag", "extracted",
                                          "--ruling", "98-1", "--dry-run"], out=out), EXIT_OK)
        self.assertIn("[DRY]", out.getvalue())
        self.assertIn("5 selected", out.getvalue())
        d, _ = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertNotIn("verified", d)  # dry run wrote nothing
        self.assertEqual(ratify_mod.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--type", "Ruling", "--ruling", "98-1",
                                          "--by", "antigravity"], out=io.StringIO()), EXIT_HALT)  # not an OKF actor
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ratify_mod.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--type", "Ruling", "--ruling", "98-1"],
                                         out=io.StringIO()), EXIT_HALT)


# ---------------------------------------------------------------- Round 100: journal + calibration, relations, staleness, carry-over

from knowledge import journal as journal_mod  # noqa: E402

RECEIPT_HEADER = "timestamp,symbol,side,quantity,price,fee,tx_hash,source,notes\n"


class JournalTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.receipts = self.dev_root / "cross_market" / "data" / "paper_receipts"
        self.receipts.mkdir(parents=True)
        (self.receipts / "fills_polymarket_latency_sniper_20260905_180000_a1b2c3d4.csv").write_text(
            RECEIPT_HEADER + "2026-09-05T18:00:03+00:00,FOMC-NOCHANGE-YES,BUY,1000.00000000,0.50000000,0.00000000,paper-1,polymarket,"
            "strategy:latency_sniper; edge:0.9950; hurdle:0.9820; paper:1;\n",
            encoding="utf-8")
        (self.receipts / "fills_polymarket_polymarket_amm_20260905_181500_e5f6a7b8.csv").write_text(
            RECEIPT_HEADER + "2026-09-05T18:15:00+00:00,BTC-78K-YES,SELL,100.00000000,0.98000000,0.00000000,paper-2,polymarket,strategy=polymarket_amm; paper\n"
            + "2026-09-04T23:59:00+00:00,OLD,BUY,1,1,0,paper-0,polymarket,strategy=polymarket_amm\n",
            encoding="utf-8")
        self.day = date(2026, 9, 5)

    def test_day_page_from_receipts_with_debrief_and_preserved_plan(self):
        page = journal_mod.write_day(self.vault, self.dev_root, self.day, at=NOW)
        self.assertIsNotNone(page)
        self.assertEqual(page.path.name, "2026-09-05.md")
        d = page.meta["dev"]
        self.assertEqual((d["receipts"], d["turnover_total"]), (2, 598.0))          # 1000*0.5 + 100*0.98; the 09-04 row is not this day
        self.assertEqual(d["debrief"]["drawdown_check"], "UNCHECKED")              # Ruling 100-c: fills are not realised loss
        self.assertEqual(d["debrief"]["drawdown_budget_usd"], 3500.0)
        self.assertEqual(d["debrief"]["hurdle_check"], "PASS")                     # one receipt carries edge >= hurdle, the other is unchecked
        self.assertEqual(d["debrief"]["hurdle_counts"], {"PASS": 1, "UNCHECKED": 1})
        self.assertEqual(d["debrief"]["by_strategy"], {"latency_sniper": 500.0, "polymarket_amm": 98.0})
        self.assertEqual(d["parameters"][0]["name"], "daily_drawdown_killswitch_usd")
        self.assertNotIn("stale_after", page.meta)                                 # journals are never stale
        self.assertIn("| 2026-09-05T18:00:03+00:00 | polymarket | latency_sniper | FOMC-NOCHANGE-YES | BUY | 1000 | 0.5 | $500.00 | 0 | 0.9950 | 0.9820 | PASS |", page.body)
        self.assertIn("Daily Paper Notional Turnover: $598.00", page.body)
        # the operator writes a plan; a re-run keeps it and re-renders everything else
        text = page.path.read_text(encoding="utf-8").replace(journal_mod.PLAN_PLACEHOLDER, "Sit out the BTC ladders; drill card at T-2.")
        page.path.write_text(text, encoding="utf-8")
        again = journal_mod.write_day(self.vault, self.dev_root, self.day, at=NOW + timedelta(hours=1))
        self.assertIn("Sit out the BTC ladders; drill card at T-2.", again.body)
        self.assertEqual(again.meta["dev"]["receipts"], 2)
        reg, _ = fm.parse((self.vault / "wiki/concepts/journal_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["count"], 1)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_quiet_day_needs_create_and_a_receipt_below_its_hurdle_flags(self):
        quiet = date(2026, 9, 7)
        self.assertIsNone(journal_mod.write_day(self.vault, self.dev_root, quiet, at=NOW))
        page = journal_mod.write_day(self.vault, self.dev_root, quiet, at=NOW, create=True)
        self.assertEqual(page.meta["dev"]["debrief"], {"executions": 0, "turnover_total": 0.0, "by_strategy": {}, "drawdown_check": "N/A", "hurdle_check": "N/A"})
        (self.receipts / "fills_polymarket_latency_sniper_20260907_x.csv").write_text(
            RECEIPT_HEADER + "2026-09-07T18:00:03+00:00,BELOW,BUY,100.00000000,0.50000000,0,paper-9,polymarket,strategy:latency_sniper; edge=0.0300;hurdle=0.0380;\n",
            encoding="utf-8")
        page = journal_mod.write_day(self.vault, self.dev_root, quiet, at=NOW)
        self.assertEqual(page.meta["dev"]["debrief"]["hurdle_check"], "FLAG")     # 0.030 < 0.038; `=` separators accepted too
        self.assertIn("| 0.0300 | 0.0380 | FLAG |", page.body)
        self.assertEqual(page.meta["dev"]["debrief"]["drawdown_check"], "UNCHECKED")

    def test_predict_then_score_against_the_event_payload(self):
        # two predictions before the print: one right at 0.9, one wrong at 0.8
        journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="fomc_2026-09-16", field_="change_bps", op="==", value=0, p=0.9, at=NOW)
        journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="fomc_2026-09-16", field_="change_bps", op=">=", value=25, p=0.8,
                                   at=NOW + timedelta(minutes=1))
        page = journal_mod.load_page(journal_mod.page_path(self.vault, "Journal Entry", "2026-09-05"))
        self.assertEqual(page.meta["dev"]["predictions_n"], 2)
        self.assertTrue(all(p["brier"] is None for p in page.meta["dev"]["predictions"]))
        # no Event page yet -> everything pending
        self.assertEqual(journal_mod.score_predictions(self.vault, self.dev_root, at=NOW + timedelta(hours=1)), {"scored": 0, "pending": 2})
        # the print lands: clob ingest writes the Event with payload change_bps 0
        ingest_clob.ingest_survival(CURVE_JSON, self.vault, self.dev_root, event_id="fomc_2026-09-16", source="curve.json",
                                    at=datetime(2026, 9, 16, 18, 10, tzinfo=timezone.utc))
        res = journal_mod.score_predictions(self.vault, self.dev_root, at=datetime(2026, 9, 16, 18, 20, tzinfo=timezone.utc))
        self.assertEqual(res, {"scored": 2, "pending": 0})
        page = journal_mod.load_page(journal_mod.page_path(self.vault, "Journal Entry", "2026-09-05"))
        preds = page.meta["dev"]["predictions"]
        self.assertEqual([(p["outcome"], p["brier"]) for p in preds], [(1, 0.01), (0, 0.64)])
        self.assertEqual(preds[0]["by"], "human:operator")
        cal, body = fm.parse((self.vault / "wiki/concepts/calibration.md").read_text(encoding="utf-8"))
        self.assertEqual((cal["dev"]["count"], cal["dev"]["mean_brier"]), (2, 0.325))
        self.assertEqual(cal["dev"]["reliability"], [{"bin": "0.8-0.9", "n": 1, "mean_p": 0.8, "observed": 0.0},
                                                     {"bin": "0.9-1.0", "n": 1, "mean_p": 0.9, "observed": 1.0}])
        self.assertIn("| 0.9-1.0 | 1 | 0.90 | 1.00 | +0.10 |", body)
        # scoring is idempotent and a scored prediction is never re-written
        self.assertEqual(journal_mod.score_predictions(self.vault, self.dev_root, at=NOW + timedelta(days=20)), {"scored": 0, "pending": 0})
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW + timedelta(days=20)), [])
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertIn("**Journal**: prediction on [[fomc_2026-09-16]]: `change_bps == 0` with p=0.90", log)
        self.assertIn("**Journal**: scored 2 prediction(s)", log)

    def test_free_text_claim_scores_only_by_hand(self):
        journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="fomc_2026-09-16", claim="Powell says 'data dependent' at least twice", p=0.7, at=NOW)
        journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="fomc_2026-09-16", field_="change_bps", op="==", value=0, p=0.9, at=NOW)
        ingest_clob.ingest_survival(CURVE_JSON, self.vault, self.dev_root, event_id="fomc_2026-09-16", source="curve.json",
                                    at=datetime(2026, 9, 16, 18, 10, tzinfo=timezone.utc))
        res = journal_mod.score_predictions(self.vault, self.dev_root, at=datetime(2026, 9, 16, 18, 20, tzinfo=timezone.utc))
        self.assertEqual(res, {"scored": 1, "pending": 1})  # the rule scored mechanically; the claim waits for a hand outcome
        res = journal_mod.score_predictions(self.vault, self.dev_root, at=datetime(2026, 9, 16, 19, 0, tzinfo=timezone.utc),
                                            event="fomc_2026-09-16", manual_outcome=1)
        self.assertEqual(res, {"scored": 1, "pending": 0})
        page = journal_mod.load_page(journal_mod.page_path(self.vault, "Journal Entry", "2026-09-05"))
        claim = next(p for p in page.meta["dev"]["predictions"] if p.get("claim"))
        self.assertEqual((claim["outcome"], claim["brier"], claim["scored_by"]), (1, 0.09, "human:operator"))
        self.assertIn("| `Powell says 'data dependent' at least twice` | 0.70 | 1 | 0.0900 |", page.body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=datetime(2026, 9, 16, 19, 0, tzinfo=timezone.utc)), [])

    def test_prediction_validation_and_cli(self):
        with self.assertRaises(ValueError):
            journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="e", field_="f", op="==", value=0, p=1.0, at=NOW)
        with self.assertRaises(ValueError):
            journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="e", field_="f", op="~", value=0, p=0.5, at=NOW)
        with self.assertRaises(ValueError):
            journal_mod.add_prediction(self.vault, self.dev_root, self.day, event="e", claim="   ", p=0.5, at=NOW)
        base = ["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--at", "2026-09-05T20:00:00Z"]
        out = io.StringIO()
        self.assertEqual(journal_mod.main(base + ["--date", "2026-09-05"], out=out), EXIT_OK)
        self.assertIn("2 execution(s)", out.getvalue())
        out = io.StringIO()
        self.assertEqual(journal_mod.main(base + ["--date", "2026-09-08"], out=out), EXIT_OK)
        self.assertIn("nothing written", out.getvalue())
        self.assertEqual(journal_mod.main(base + ["--predict", "--event", "fomc_2026-10-28", "--field", "change_bps", "--op", "==", "--value", "0", "--p", "0.7"],
                                          out=io.StringIO()), EXIT_OK)
        page = journal_mod.load_page(journal_mod.page_path(self.vault, "Journal Entry", "2026-09-05"))
        self.assertEqual(page.meta["dev"]["predictions"][0]["value"], 0)  # "0" parsed as an int
        self.assertEqual(journal_mod.main(base + ["--predict", "--event", "x"], out=io.StringIO()), EXIT_HALT)
        self.assertEqual(journal_mod.main(base + ["--predict", "--event", "x", "--claim", "free text", "--p", "0.6"], out=io.StringIO()), EXIT_OK)
        self.assertEqual(journal_mod.main(base + ["--score", "--outcome", "1"], out=io.StringIO()), EXIT_HALT)  # --outcome needs --event
        out = io.StringIO()
        self.assertEqual(journal_mod.main(base + ["--score"], out=out), EXIT_OK)
        self.assertIn("pending 2", out.getvalue())
        out = io.StringIO()
        self.assertEqual(journal_mod.main(base + ["--score", "--event", "x", "--outcome", "0"], out=out), EXIT_OK)
        self.assertIn("scored 1, pending 1", out.getvalue())
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(journal_mod.main(base + ["--date", "2026-09-05"], out=io.StringIO()), EXIT_HALT)


class RelationsLintTests(TempVault):
    def page(self, rel, **kw):
        return self.write(rel, page_text(**kw))

    def test_l6_supersedes_contradicts_measured_enforced_depends(self):
        self.page("wiki/rulings/Ruling_R09.md", type_="Ruling", title="R9", body="# R9\n\n[[old]] [[c]]\n", stale_after="2027-01-01T00:00:00Z")
        self.page("wiki/rulings/old.md", type_="Ruling", title="old", body="# old\n\n[[Ruling_R09]]\n", status="deprecated")
        self.page("wiki/experiments/exp1.md", type_="Experiment", title="exp1", body="# e\n\n[[c]]\n", dev={"tests_run": 1})
        self.page("wiki/concepts/c.md", title="c", body="# c\n\n[[Ruling_R09]] [[exp1]] [[old]]\n", stale_after="2027-01-01T00:00:00Z", dev={"relations": [
            {"type": "supersedes", "target": "old"},                                   # ok: exists and deprecated
            {"type": "supersedes", "target": "Ruling_R09"},                            # warning: not deprecated
            {"type": "contradicts", "target": "old"},                                  # error unless resolved_by names a Ruling
            {"type": "measured_by", "target": "exp1"},                                 # ok
            {"type": "measured_by", "target": "Ruling_R09"},                           # error: not an Experiment
            {"type": "enforced_in", "target": "cross_market/latency_sniper.py"},        # ok: exists in the fixture
            {"type": "enforced_in", "target": "cross_market/nope.py"},                 # error
            {"type": "depends_on", "target": "ghost"},                                 # warning
        ]})
        pages.write_index(self.vault)
        l6 = [x for x in self.findings() if x.code == "L6"]
        msgs = [x.message for x in l6]
        self.assertEqual(sorted(x.severity for x in l6), ["error", "error", "error", "warning", "warning"])
        self.assertTrue(any("supersedes Ruling_R09, which is not `deprecated`" in m for m in msgs))
        self.assertTrue(any("contradicts old without a `resolved_by`" in m for m in msgs))
        self.assertTrue(any("measured_by target is not an existing Experiment page: Ruling_R09" in m for m in msgs))
        self.assertTrue(any("enforced_in target is not a file in the repository: cross_market/nope.py" in m for m in msgs))
        self.assertTrue(any("depends_on target not found: ghost" in m for m in msgs))
        # add the resolving ruling -> the contradicts error clears
        self.page("wiki/concepts/c.md", title="c", body="# c\n\n[[Ruling_R09]] [[exp1]] [[old]]\n", stale_after="2027-01-01T00:00:00Z", dev={"relations": [
            {"type": "contradicts", "target": "old"}, {"type": "resolved_by", "target": "Ruling_R09"}]})
        self.assertEqual([x for x in self.findings() if x.code == "L6"], [])

    def test_l6_cycle_and_frontmatter_shape(self):
        self.page("wiki/concepts/a.md", title="a", body="# a\n\n[[b]]\n", status="deprecated", dev={"relations": [{"type": "supersedes", "target": "b"}]})
        self.page("wiki/concepts/b.md", title="b", body="# b\n\n[[a]]\n", status="deprecated", dev={"relations": [{"type": "supersedes", "target": "a"}]})
        pages.write_index(self.vault)
        cyc = [x for x in self.findings() if x.code == "L6" and "cyclic" in x.message]
        self.assertEqual(len(cyc), 2)
        self.assertTrue(any("dev.relations[0] needs type in" in i for i in fm.validate({"type": "X", "dev": {"relations": [{"type": "likes", "target": "b"}]}})))
        self.assertEqual(fm.validate({"type": "X", "dev": {"relations": [{"type": "enforced_in", "target": "a.py"}], "tests_run": 3}}), [])
        self.assertTrue(fm.validate({"type": "X", "dev": {"tests_run": -1}}))


class StalenessTests(IngestFixture):
    def test_l7_policy_and_seeded_rulings_carry_stale_after(self):
        r4, _ = fm.parse((self.vault / "wiki/rulings/Ruling_R04.md").read_text(encoding="utf-8"))
        self.assertEqual(r4["stale_after"], "2027-03-04T20:00:00Z")   # NOW + 180 d
        r1, _ = fm.parse((self.vault / "wiki/rulings/Ruling_R01.md").read_text(encoding="utf-8"))
        self.assertNotIn("stale_after", r1)                             # deprecated: no review clock
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        self.write("wiki/concepts/loose.md", page_text(title="Loose", body="# L\n\n[[Desk_01_HyperLiquid_Monarch]]\n", stale_after=None))
        self.write("wiki/rulings/Ruling_R08.md", page_text("Ruling", title="R8", body="# R8\n\n[[loose]]\n", stale_after=None))
        self.write("wiki/desks/Desk_01_HyperLiquid_Monarch.md",
                   (self.vault / "wiki/desks/Desk_01_HyperLiquid_Monarch.md").read_text(encoding="utf-8").replace("## Other desks", "[[loose]] [[Ruling_R08]]\n\n## Other desks"))
        pages.write_index(self.vault)
        l7 = sorted((x.path, x.message) for x in self.findings() if x.code == "L7")
        self.assertEqual([p for p, _ in l7], ["wiki/concepts/loose.md", "wiki/rulings/Ruling_R08.md"])
        self.assertIn("policy: 90 d", l7[0][1])
        # registers and history pages are exempt
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.assertFalse(any(x.code == "L7" and "register" in x.path for x in self.findings()))
        self.assertEqual(pages.default_stale_after("Event", NOW), None)

    def test_tests_run_counter_on_registrations_and_verdicts(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        m, _ = fm.parse((self.vault / "wiki/experiments/fomc_2026-09-16_rules.md").read_text(encoding="utf-8"))
        self.assertEqual(m["dev"]["tests_run"], 0)
        for i in range(3):
            v, _ = ingest_ll.ingest_verdict(VERDICT_JSON, self.vault, self.dev_root, tier="1", source="verdict.json", at=NOW + timedelta(hours=i))
        self.assertEqual(v.meta["dev"]["tests_run"], 3)
        v2, _ = ingest_ll.ingest_verdict(dict(VERDICT_JSON, subfamily="crypto"), self.vault, self.dev_root, tier="1", source="verdict.json",
                                         at=NOW + timedelta(hours=5))
        self.assertEqual(v2.meta["dev"]["tests_run"], 1)  # a different scope starts its own count


class CarryOverTests(IngestFixture):
    def test_force_rewrites_keep_verified_status_and_stale_after_everywhere(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        computations.write_computations(self.vault, self.dev_root, at=NOW)
        cal_dir = Path(knowledge_pkg.__file__).parent / "calendars"
        ingest_cal.ingest_calendars(cal_dir, self.vault, self.dev_root, at=NOW)
        ingest_mk.ingest_markets(self.vault, self.dev_root, at=NOW)
        targets = ["wiki/experiments/fomc_2026-09-16_rules.md", "wiki/computations/knowledge_lint.md", "wiki/events/fomc_2026-10-28.md",
                   "wiki/markets/will-no-fed-rate-cuts-happen-in-2026.md"]
        for rel in targets:
            p = self.vault / rel
            text = p.read_text(encoding="utf-8").replace("status: draft", "status: stable\nstale_after: '2027-06-01T00:00:00Z'\nverified:\n- by: human:operator\n  at: '2026-09-05T21:00:00Z'", 1)
            p.write_text(text, encoding="utf-8")
        later = NOW + timedelta(days=1)
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=later, force=True)
        computations.write_computations(self.vault, self.dev_root, at=later, force=True)
        ingest_cal.ingest_calendars(cal_dir, self.vault, self.dev_root, at=later, force=True)
        ingest_mk.ingest_markets(self.vault, self.dev_root, at=later, force=True)
        for rel in targets:
            m, _ = fm.parse((self.vault / rel).read_text(encoding="utf-8"))
            self.assertEqual((m["status"], m["stale_after"], m["verified"][0]["by"]), ("stable", "2027-06-01T00:00:00Z", "human:operator"), rel)
            # Round 105 (Ruling R104-3): a --force over unchanged content no longer restamps. The
            # human fields above are carried, so each page is identical to its regeneration and keeps
            # the `generated.at` it earned; restamping would claim work that never happened.
            self.assertEqual(m["generated"]["at"], pages.iso(NOW), rel)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=later), [])


# ---------------------------------------------------------------- Round 101: views, theses, receipt hurdle, effects, back-annotation

from knowledge import views as views_mod  # noqa: E402
from knowledge.ingest import theses as ingest_th  # noqa: E402

THESIS_MODULE = '''"""Item 12, Phase 1: the latency sniper - OFFLINE ENGINE.

THE THESIS. When a scheduled number prints, the resting book is stale for a few
seconds and a reader of the statement can lift it before it is pulled.

WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS
HALT.flag refuses everything; confidence under 0.99 refuses everything; a book
older than 10 s is skipped; a market without a rule is never touched.

NOTE: this one-liner is not a heading.
Ordinary prose here.
"""
X = 1
'''


class ViewsTests(IngestFixture):
    def test_bases_and_templates_are_written_valid_and_skipped_by_lint(self):
        written, skipped = views_mod.write_views(self.vault, force=False)
        self.assertEqual(len(written), len(views_mod.VIEWS) + len(views_mod.TEMPLATES))
        base = yaml.safe_load((self.vault / "wiki/_views/rulings.base").read_text(encoding="utf-8"))
        self.assertEqual(base["filters"]["and"][0], 'file.inFolder("wiki/rulings")')
        self.assertEqual(base["views"][0]["type"], "table")
        self.assertIn("title", base["views"][0]["order"])
        self.assertEqual(base["properties"]["stale_after"]["displayName"], "stale after")
        for v in views_mod.VIEWS:
            yaml.safe_load((self.vault / f"wiki/_views/{v.name}.base").read_text(encoding="utf-8"))
        # a template's frontmatter is OKF-valid before any placeholder is filled
        tpl = (self.vault / "wiki/_templates/thesis.md").read_text(encoding="utf-8")
        meta, _ = fm.parse(tpl.replace("{{title}}", "T").replace("{{date:YYYY-MM-DD}}", "2026-09-05").replace("{{time:HH:mm:ss}}", "12:00:00"))
        self.assertEqual(fm.validate(meta), [])
        self.assertEqual(meta["generated"]["by"], "human:operator")
        # underscore folders are tooling: not pages, not indexed, not linted
        self.assertFalse(any("_templates" in p.path.as_posix() for p in pages.load_pages(self.vault)))
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        again_written, again_skipped = views_mod.write_views(self.vault)
        self.assertEqual((again_written, len(again_skipped)), ([], len(written)))
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(views_mod.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class ThesesTests(IngestFixture):
    def setUp(self):
        super().setUp()
        (self.dev_root / "cross_market" / "thesis_demo.py").write_text(THESIS_MODULE, encoding="utf-8")

    def test_sections_extracted_pinned_and_registered(self):
        secs = ingest_th.extract_sections(ast_docstring := __import__("ast").get_docstring(__import__("ast").parse(THESIS_MODULE)))
        self.assertEqual([s.heading for s in secs], ["THE THESIS", "WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS"])
        self.assertTrue(secs[0].text.startswith("When a scheduled number prints"))
        report = ingest_th.ingest_theses(["cross_market"], self.vault, self.dev_root, at=NOW)
        self.assertIn("wiki/concepts/thesis_cross_market_thesis_demo.md", report.written)
        self.assertGreaterEqual(report.scanned, 3)  # latency_sniper.py and amm_rewards.py stubs have no headings -> skipped
        m, body = fm.parse((self.vault / "wiki/concepts/thesis_cross_market_thesis_demo.md").read_text(encoding="utf-8"))
        self.assertEqual((m["type"], m["dev"]["kind"], m["dev"]["desk"]), ("Concept", "thesis", 3))
        self.assertEqual(m["dev"]["headings"], ["THE THESIS", "WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS"])
        self.assertEqual(m["dev"]["asserts"][0]["file"], "cross_market/thesis_demo.py")
        self.assertEqual(m["dev"]["requires_files"], ["cross_market/thesis_demo.py"])
        self.assertEqual(m["stale_after"], "2026-12-04T20:00:00Z")  # Concept policy: 90 d
        self.assertIn("## The Thesis", body)
        self.assertIn("## What It Refuses, Fail-Closed On Every Axis", body)
        reg, _ = fm.parse((self.vault / "wiki/concepts/theses_register.md").read_text(encoding="utf-8"))
        self.assertEqual(reg["dev"]["pages"], ["thesis_cross_market_thesis_demo"])
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        # deleting a heading from the docstring is a C1 finding
        (self.dev_root / "cross_market" / "thesis_demo.py").write_text(THESIS_MODULE.replace("WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS", "REFUSALS"), encoding="utf-8")
        c1 = [x for x in lint.lint_vault(self.vault, self.dev_root, now=NOW) if x.code == "C1"]
        self.assertTrue(any("FAIL-CLOSED" in x.message for x in c1))
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        self.assertEqual(ingest_th.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=io.StringIO()), EXIT_HALT)


class ReceiptHurdleTests(TempVault):
    def test_writer_stamps_edge_and_hurdle_into_notes(self):
        from Tax_Reserve_Agent.interfaces import receipts as rc
        self.assertEqual(rc.build_notes("latency_sniper", None, "paper:1;", gross_edge=0.995, after_tax_hurdle=0.982),
                         "strategy:latency_sniper; edge:0.9950; hurdle:0.9820; paper:1;")
        self.assertEqual(rc.build_notes("amm", "tp", None), "strategy:amm; exit_reason:tp;")  # unchanged when absent
        target = self.root / "receipts"
        path = rc.log_execution_receipt("TOK", "BUY", 10, 0.5, "latency_sniper", venue="polymarket", imports_dir=target,
                                        timestamp="2026-09-05T18:00:03+00:00", gross_edge=0.995, after_tax_hurdle=0.982)
        self.assertIsNotNone(path)
        rows = journal_mod.load_executions(target, date(2026, 9, 5))
        self.assertEqual((rows[0].edge, rows[0].hurdle, rows[0].hurdle_check, rows[0].strategy), (0.995, 0.982, "PASS", "latency_sniper"))


class RulingEffectTests(RulingsIngestTests):
    def test_a_ratifying_ruling_lists_the_pages_it_ratified(self):
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW)
        ratify_mod.ratify(self.vault, type_="Ruling", tag="extracted", ruling="99-1", at=NOW + timedelta(hours=1))  # a Round 99 ruling covers them all
        # the log now cites "Ruling 99-1" as a ruling id too
        (self.dev_root / "AGENTS.md").write_text(AGENTS_FIXTURE + "\n## Round 99 findings\n\nRuling 99-1 applied: the pages were ratified.\n", encoding="utf-8")
        ingest_rl.ingest_rulings(self.dev_root / "AGENTS.md", self.vault, self.dev_root, at=NOW + timedelta(hours=2), force=True)
        m, body = fm.parse((self.vault / "wiki/rulings/Ruling_99-1.md").read_text(encoding="utf-8"))
        self.assertTrue(m["description"].startswith("Ratification of 5 wiki page(s): "), m["description"])
        self.assertIn("## Effect in this wiki", body)
        self.assertIn("- [[Directive_75-2]]", body)
        self.assertNotIn("verified", m)  # the ratifying ruling's own page is not verified by its own batch
        d, _ = fm.parse((self.vault / "wiki/rulings/Directive_75-1.md").read_text(encoding="utf-8"))
        self.assertEqual(d["dev"]["ratified_by"], "99-1")  # carried through the --force


class BackAnnotationTests(IngestFixture):
    def test_verdict_count_written_back_onto_the_registration_page(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        reg = self.vault / "wiki/experiments/lead_lag_tier2_meta.md"
        self.assertEqual(fm.parse(reg.read_text(encoding="utf-8"))[0]["dev"]["tests_run"], 0)
        for i in range(2):
            ingest_ll.ingest_verdict(dict(VERDICT_JSON, subfamily="crypto"), self.vault, self.dev_root, tier="2", source="verdict.json", at=NOW + timedelta(hours=i))
        self.assertEqual(fm.parse(reg.read_text(encoding="utf-8"))[0]["dev"]["tests_run"], 2)
        ingest_ll.ingest_verdict(VERDICT_JSON, self.vault, self.dev_root, tier="1", source="verdict.json", at=NOW + timedelta(hours=3))
        self.assertEqual(fm.parse(reg.read_text(encoding="utf-8"))[0]["dev"]["tests_run"], 2)  # Tier 1 has no registration page
        # the raw meta file is untouched
        self.assertEqual(json.loads((self.exp_dir / "lead_lag_tier2.meta.json").read_text(encoding="utf-8")), META_JSON)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW + timedelta(hours=4)), [])



# --------------------------------------------------------------------------------------
# Round 104: the funding regime and cascade replay adapters
# --------------------------------------------------------------------------------------
from knowledge.ingest import cascade_replay as ingest_cr  # noqa: E402
from knowledge.ingest import funding as ingest_fund  # noqa: E402
from knowledge.ingest import md_cell  # noqa: E402

BARS_PY = "BASIS_MIN_FUNDING_APR = 25.0   # gross bar\nBASIS_MIN_NET_APR = 20.0       # after spread\n"

REPLAY_REG = {
    "experiment": "whale_sweeper_cascade_replay",
    "registered_utc": "2026-09-06T02:06:00+00:00",
    "grade_of_evidence": {"kind": "RETROSPECTIVE REPLAY, NOT A FORWARD TEST",
                          "consequence": "A PASS IS NOT AN UN-GATING."},
    "data": {"state_at_registration": {"rows": 28544}},
    "sample_requirements": {"min_events": 500, "min_coins": 20,
                            "max_single_coin_share": 0.2, "max_hhi": 0.15},
    "acceptance_bar": {"PASS": "P >= 1.25 > 0.90", "RETUNE": "0.50 <= P <= 0.90",
                       "FAIL": "P < 0.50", "INSUFFICIENT": "any sample requirement unmet"},
}

REPLAY_ART = {
    "experiment": "whale_sweeper_cascade_replay", "verdict": "INSUFFICIENT",
    "primary_metric": {"name": "fade_ratio_30m", "value": 0.6124, "cluster_p_ge_1_25": 0.0,
                       "acceptance_threshold": 1.25},
    "sample_gates": {"passed": False, "metrics": {"events": 14336, "coins": 58, "top_coin": "PONS",
                                                  "top_coin_share": 0.2248, "hhi": 0.14299}},
    "data_audit": {"total_in_table": 29350, "raw_loaded": 14675, "truncated_count": 226,
                   "null_30m_count": 339, "qualifying_count": 14336},
    "horizons": {h: {"n": 14336, "median_mfe": 0.37, "median_mae": 0.60, "median_fade_ratio": 0.61,
                     "win_share": 43.8, "dollar_expectancy": -0.04} for h in ("5m", "15m", "30m", "60m")},
    "asymmetry": {"side_A_sell_fade_buys": {"n": 6835, "median_fade_ratio_30m": 0.2784,
                                            "dollar_expectancy": -0.061, "cluster_p_ge_1_25": 0.0103},
                  "side_B_buy_fade_sells": {"n": 7501, "median_fade_ratio_30m": 1.7378,
                                            "dollar_expectancy": -0.025, "cluster_p_ge_1_25": 0.4808}},
    "regime_breakdown": {"VOL_MID|FUND_FLAT": {"n": 4788, "median_fade_ratio": 0.4291,
                                               "dollar_expectancy": -0.0468}},
    "bootstrap_config": {"resamples": 10000, "seed": 7, "threshold": 1.25},
}

WINDOW_COLS = ("asset", "realised_apr", "quote_apr_entry", "net_apr_after_fees", "fee_basis",
               "coverage", "regime_tag")


class Round104Fixture(IngestFixture):
    def setUp(self):
        super().setUp()
        cfg = self.dev_root / "HyperLiquid" / "HL_Monarch" / "config"
        cfg.mkdir(parents=True)
        (cfg / "settings.py").write_text(BARS_PY, encoding="utf-8")
        self.db = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.write_windows(self.default_windows())
        self.exp_dir_hl = self.db.parent / "experiments"
        self.exp_dir_hl.mkdir(exist_ok=True)
        self.registration = self.exp_dir_hl / "whale_sweeper_cascade_replay.meta.json"
        self.registration.write_text(json.dumps(REPLAY_REG), encoding="utf-8")
        self.artifact = self.exp_dir_hl / "whale_sweeper_cascade_replay.verdict.json"   # beside the registration (R114-1.D)
        self.artifact.parent.mkdir(parents=True, exist_ok=True)
        self.artifact.write_text(json.dumps(REPLAY_ART), encoding="utf-8")

    def default_windows(self):
        # 4 entry-qualifying (quote_apr_entry >= 25): realised 30, 28, 24, -5
        #   -> median 26.0, two at or above the 25 bar, one negative
        # 4 non-qualifying: realised 5, 6, 7, 8. Pooled median is therefore 7.5, not 26.
        rows = [("BTC", 30.0, 40.0, 21.0, "measured", 0.9, "VOL_MID|FUND_FLAT"),
                ("ETH", 28.0, 30.0, None, "unmeasured", 0.8, "VOL_MID|FUND_FLAT"),
                ("SOL", 24.0, 26.0, None, "unmeasured", 0.8, "VOL_LOW|FUND_FLAT"),
                ("ARB", -5.0, 25.0, None, "unmeasured", 0.7, "VOL_LOW|FUND_FLAT")]
        rows += [("DOGE", 5.0, 10.0, None, "unmeasured", 0.8, "UNKNOWN"),
                 ("PONS", 6.0, 11.0, None, "unmeasured", 0.8, "UNKNOWN"),
                 ("XRP", 7.0, 12.0, None, "unmeasured", 0.9, "UNKNOWN"),
                 ("LTC", 8.0, 13.0, None, "unmeasured", 0.9, "UNKNOWN")]
        return rows

    def write_windows(self, rows):
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE IF EXISTS basis_realised_windows")
        conn.execute("CREATE TABLE basis_realised_windows (%s)" % ", ".join(WINDOW_COLS))
        conn.executemany("INSERT INTO basis_realised_windows VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        conn.close()


class FundingIngestTests(Round104Fixture):
    def test_bars_are_read_from_settings_not_invented(self):
        self.assertEqual(ingest_fund.read_bars(self.dev_root),
                         {"BASIS_MIN_FUNDING_APR": 25.0, "BASIS_MIN_NET_APR": 20.0})

    def test_the_two_populations_are_measured_separately(self):
        m = ingest_fund.measure(ingest_fund.load_windows(self.db), ingest_fund.read_bars(self.dev_root))
        self.assertEqual(m["rows"], 8)
        self.assertEqual(m["assets"], 8)
        self.assertEqual(m["all_windows"]["n"], 8)
        self.assertEqual(m["all_windows"]["median"], 7.5)
        # only the four whose QUOTED apr cleared the GROSS bar - a superset of what the live
        # scanner would take, since it also requires the net bar and a measured spread
        self.assertEqual(m["gross_bar_only_n"], 4)
        self.assertEqual(m["gross_bar_only"]["median"], 26.0)
        self.assertEqual(m["gross_bar_only"]["at_or_above_bar"], 2)          # 30 and 28, not 24
        self.assertEqual(m["gross_bar_only"]["negative_pct"], 25.0)          # the -5 window

    def test_net_bar_is_declared_unmeasurable_on_thin_fee_coverage(self):
        m = ingest_fund.measure(ingest_fund.load_windows(self.db), ingest_fund.read_bars(self.dev_root))
        self.assertEqual(m["net"]["measured_rows"], 1)
        self.assertEqual(m["net"]["measured_pct"], 12.5)
        self.assertTrue(m["net"]["verdict"].startswith("UNMEASURABLE"))

    def test_page_pins_both_bars_to_settings_and_lints_clean(self):
        report, page = ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db, at=NOW)
        self.assertTrue(report.written)
        # the desk links its compiled pages only once they exist (lint L8), so a re-seed after the
        # ingest is what makes the new Regime page reachable - exactly the live operating order.
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW, force=True)
        meta, body = fm.parse((self.vault / "wiki/regimes/hl_funding_regime.md").read_text(encoding="utf-8"))
        names = {p["name"]: p["value"] for p in meta["dev"]["parameters"]}
        self.assertEqual(names, {"basis_min_funding_apr": 25.0, "basis_min_net_apr": 20.0})
        self.assertIn("UNMEASURABLE", body)
        self.assertIn("Clears the GROSS bar only", body)
        self.assertIn("upper bound, not a backtest", body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_c1_fires_when_a_bar_is_edited_and_the_page_is_not_recompiled(self):
        ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db, at=NOW)
        (self.dev_root / "HyperLiquid" / "HL_Monarch" / "config" / "settings.py").write_text(
            BARS_PY.replace("25.0", "15.0"), encoding="utf-8")
        codes = [(f.code, f.message) for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)]
        self.assertTrue(any(c == "C1" and "basis_min_funding_apr" in msg for c, msg in codes), codes)

    def test_history_records_measurements_not_runs(self):
        """Round 105: two runs over an unmoved table are ONE observation, not two."""
        ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db, at=NOW)
        ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db, at=NOW + timedelta(hours=1))
        path = self.vault / "wiki/regimes/hl_funding_regime.md"
        meta, _ = fm.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(len(meta["dev"]["history"]), 1)
        self.assertEqual(meta["dev"]["history"][0]["at"], pages.iso(NOW))   # the first sighting stands
        # a table that has actually moved is a new observation and does append
        rows = self.default_windows() + [("NEW", 12.0, 40.0, None, "unmeasured", 0.9, "UNKNOWN")]
        self.write_windows(rows)
        ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db, at=NOW + timedelta(hours=2))
        meta, _ = fm.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(len(meta["dev"]["history"]), 2)
        self.assertEqual(meta["dev"]["history"][-1]["rows"], 9)

    def test_history_rows_written_before_the_104b_rename_still_render(self):
        """A key rename that KeyErrors on an existing page is worse than the wording it fixed."""
        ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db, at=NOW)
        path = self.vault / "wiki/regimes/hl_funding_regime.md"
        meta, body = fm.parse(path.read_text(encoding="utf-8"))
        row = meta["dev"]["history"][0]
        for new, old in (("gross_n", "qual_n"), ("gross_median", "qual_median"),
                         ("gross_at_bar_pct", "qual_at_bar_pct")):
            row[old] = row.pop(new)                      # as a page written before Round 104b holds it
        pages.write_page(pages.Page(path, meta, body), self.vault, now=NOW)
        report, page = ingest_fund.ingest_funding(self.vault, self.dev_root, db=self.db,
                                                  at=NOW + timedelta(hours=1))
        self.assertTrue(report.written)
        self.assertEqual(len(page.meta["dev"]["history"]), 2)
        self.assertIn("| 4 | 26.0 | 50.0% |", page.body)  # the pre-rename row still renders its values

    def test_missing_table_refuses_rather_than_writing_an_empty_page(self):
        out = io.StringIO()
        code = ingest_fund.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root),
                                 "--db", str(self.dev_root / "nope.db")], out=out)
        self.assertEqual(code, 3)
        self.assertIn("[REFUSE]", out.getvalue())
        self.assertFalse((self.vault / "wiki/regimes/hl_funding_regime.md").exists())


class CascadeReplayIngestTests(Round104Fixture):
    def test_bands_follow_the_registration_including_the_boundaries(self):
        self.assertEqual(ingest_cr.band_of(0.95, REPLAY_REG), "PASS")
        self.assertEqual(ingest_cr.band_of(0.90, REPLAY_REG), "RETUNE")    # PASS is strictly > 0.90
        self.assertEqual(ingest_cr.band_of(0.50, REPLAY_REG), "RETUNE")    # RETUNE is inclusive at 0.50
        self.assertEqual(ingest_cr.band_of(0.4808, REPLAY_REG), "FAIL")    # the artifact's real side-B value
        self.assertEqual(ingest_cr.band_of(0.5020, REPLAY_REG), "RETUNE")  # the transcribed one: another band
        self.assertEqual(ingest_cr.band_of(None, REPLAY_REG), "INSUFFICIENT")

    def test_every_sample_gate_is_rechecked_here(self):
        ok = {"events": 14336, "coins": 58, "top_coin_share": 0.19, "hhi": 0.14}
        self.assertEqual(ingest_cr.gate_failures(ok, REPLAY_REG), [])
        self.assertEqual(len(ingest_cr.gate_failures(dict(ok, events=499), REPLAY_REG)), 1)
        self.assertEqual(len(ingest_cr.gate_failures(dict(ok, coins=19), REPLAY_REG)), 1)
        self.assertEqual(len(ingest_cr.gate_failures(dict(ok, top_coin_share=0.2248), REPLAY_REG)), 1)
        self.assertEqual(len(ingest_cr.gate_failures(dict(ok, hhi=0.16), REPLAY_REG)), 1)
        self.assertEqual(len(ingest_cr.gate_failures({}, REPLAY_REG)), 4)   # nothing reported: all unmet

    def test_a_failed_gate_beats_a_passing_probability(self):
        """The registration's whole point: a narrow sample produces NO verdict, not a strong one."""
        art = json.loads(json.dumps(REPLAY_ART))
        art["primary_metric"]["cluster_p_ge_1_25"] = 0.99           # would be a PASS on the bands alone
        g = ingest_cr.grade(art, REPLAY_REG)
        self.assertEqual(g["band_if_sample_qualified"], "PASS")
        self.assertEqual(g["grade"], "INSUFFICIENT")

    def test_disagreement_with_the_engine_is_recorded_not_reconciled(self):
        art = json.loads(json.dumps(REPLAY_ART))
        art["verdict"] = "RETUNE"                                   # engine drifted from the registration
        g = ingest_cr.grade(art, REPLAY_REG)
        self.assertEqual((g["grade"], g["engine_verdict"], g["agrees"]), ("INSUFFICIENT", "RETUNE", False))
        self.artifact.write_text(json.dumps(art), encoding="utf-8")
        page = ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                       registration=self.registration, at=NOW)
        self.assertIn("THEY DISAGREE", page.body)
        self.assertFalse(page.meta["dev"]["grades_agree"])

    def test_verdict_page_pins_the_registration_and_lints_clean(self):
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW)
        # the desk links a compiled page only once it exists (lint L8), so the re-seed is what makes
        # the new page reachable and keeps L3 quiet - the live operating order, not a workaround.
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW, force=True)
        meta, body = fm.parse((self.vault / "wiki/experiments/whale_sweeper_cascade_replay_verdict.md")
                              .read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["grade"], "INSUFFICIENT")
        self.assertEqual({p["name"] for p in meta["dev"]["parameters"]},
                         {"cascade_replay_min_events", "cascade_replay_min_coins",
                          "cascade_replay_max_single_coin_share", "cascade_replay_max_hhi"})
        self.assertIn("RETROSPECTIVE REPLAY, NOT A FORWARD TEST", body)
        self.assertIn("is not a verdict", body)
        # Round 105: the registration page is compiled by a different adapter, so when it is absent
        # the reference degrades to plain text rather than dangling (lint L8). The stem is still the
        # real one - guessing it wrong was the Round 104 defect that motivated L8.
        self.assertIn("The pre-registration (B15)", body)
        self.assertEqual(ingest_cr.REGISTRATION_STEM, "whale_sweeper_cascade_replay_meta")
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_c1_fires_if_the_acceptance_bar_is_edited_after_the_data_was_seen(self):
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW)
        moved = json.loads(json.dumps(REPLAY_REG))
        moved["sample_requirements"]["max_single_coin_share"] = 0.25   # would make this very run "qualify"
        self.registration.write_text(json.dumps(moved), encoding="utf-8")
        codes = [(f.code, f.message) for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)]
        self.assertTrue(any(c == "C1" and "max_single_coin_share" in m for c, m in codes), codes)

    def test_reingesting_an_unchanged_artifact_does_not_fabricate_an_observation(self):
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW)
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW + timedelta(hours=1))
        meta, _ = fm.parse((self.vault / "wiki/experiments/whale_sweeper_cascade_replay_verdict.md")
                           .read_text(encoding="utf-8"))
        self.assertEqual(len(meta["dev"]["history"]), 1)
        # Round 105: the deduped row keeps the `at` of the FIRST sighting - the observation did not
        # change, so neither did when we first recorded it (and bumping it would defeat R104-3).
        self.assertEqual(meta["dev"]["history"][0]["at"], pages.iso(NOW))
        # a genuinely new run (new mtime, new numbers) does append
        art = json.loads(json.dumps(REPLAY_ART))
        art["data_audit"]["total_in_table"] = 30000
        self.artifact.write_text(json.dumps(art), encoding="utf-8")
        os.utime(self.artifact, (1, 1))
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW + timedelta(hours=2))
        meta, _ = fm.parse((self.vault / "wiki/experiments/whale_sweeper_cascade_replay_verdict.md")
                           .read_text(encoding="utf-8"))
        self.assertEqual(len(meta["dev"]["history"]), 2)

    def test_regime_tags_containing_a_pipe_do_not_split_the_table(self):
        page = ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                       registration=self.registration, at=NOW)
        row = [ln for ln in page.body.splitlines() if "VOL_MID" in ln and ln.startswith("|")]
        self.assertEqual(len(row), 1, page.body)
        self.assertIn(chr(92) + "|FUND_FLAT", row[0])
        self.assertEqual(row[0].count("|") - row[0].count(chr(92) + "|"), 5)   # 4 cells -> 5 real bars
        self.assertEqual(md_cell("A|B"), "A" + chr(92) + "|B")

    def test_missing_artifact_refuses_and_names_the_command(self):
        out = io.StringIO()
        self.artifact.unlink()
        code = ingest_cr.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out)
        self.assertEqual(code, 3)
        self.assertIn("cascade_replay --json", out.getvalue())



# --------------------------------------------------------------------------------------
# Round 105: lint L8, the _artifact envelope, write idempotence, cascade anatomy
# --------------------------------------------------------------------------------------
from knowledge.ingest import cascade_anatomy as ingest_ca  # noqa: E402

SETTINGS_105 = "EXCURSION_CONTROL_MULTIPLE = 1              # matched random entries per event\n"


class LintL8Tests(TempVault):
    def _page(self, stem: str, body: str, type_="Concept"):
        path = self.vault / "wiki" / "concepts" / f"{stem}.md"
        pages.write_page(pages.Page(path, pages.make_meta(type_, stem, "A page.", at=NOW), body), self.vault, now=NOW)
        return path

    def test_a_dangling_wikilink_is_an_error(self):
        self._page("a", "# a\n\n- [[b|the other page]]\n")
        self._page("b", "# b\n\n- [[a]]\n")
        self.assertEqual([f.code for f in lint.check_l8(pages.load_documents(self.vault), self.vault)], [])
        self._page("a", "# a\n\n- [[b]]\n- [[nowhere]]\n")
        found = lint.check_l8(pages.load_documents(self.vault), self.vault)
        self.assertEqual([(f.code, f.severity) for f in found], [("L8", "error")])
        self.assertIn("[[nowhere]]", found[0].message)

    def test_links_inside_code_are_not_links(self):
        """The constitution documents the syntax; a checker that reads inside code is unusable."""
        self._page("b", "# b\n\n- [[a]]\n")
        self._page("a", "# a\n\n- [[b]]\n\nAnswer with `[[wikilinks]]`.\n\n```\n[[also_not_a_link]]\n```\n")
        self.assertEqual(lint.check_l8(pages.load_documents(self.vault), self.vault), [])
        self.assertEqual(pages.wikilink_targets("`[[x]]` and [[y]]"), {"y"})
        self.assertEqual(pages.wikilink_targets("```\n[[x]]\n```\n[[y]]"), {"y"})

    def test_a_link_resolves_by_filename_or_path_but_never_by_title(self):
        self._page("b", "# b\n\n- [[a]]\n")
        path = self.vault / "wiki" / "concepts" / "a.md"
        pages.write_page(pages.Page(path, pages.make_meta("Concept", "A Long Human Title", "d.", at=NOW),
                                    "# a\n\n- [[b]]\n"), self.vault, now=NOW)
        names = lint.link_namespace(pages.load_documents(self.vault), self.vault)
        self.assertIn("a", names)
        self.assertIn("wiki/concepts/a", names)
        self.assertNotIn("A Long Human Title", names)   # Obsidian would render that broken

    def test_the_whole_vault_is_linkable_not_only_owned_pages(self):
        """Desks link the exporter-owned Monarch_Hub; scoping to owned pages reported 183 false errors."""
        (self.vault / "Monarch_Hub.md").write_text("# hub\n", encoding="utf-8")
        (self.vault / "Whales").mkdir(exist_ok=True)
        (self.vault / "Whales" / "0xabc.md").write_text("# whale\n", encoding="utf-8")
        self._page("b", "# b\n\n- [[a]]\n")
        self._page("a", "# a\n\n- [[b]]\n- [[Monarch_Hub]]\n- [[Whales/0xabc|note]]\n")
        self.assertEqual(lint.check_l8(pages.load_documents(self.vault), self.vault), [])

    def test_l8_runs_as_part_of_the_vault_lint(self):
        self._page("b", "# b\n\n- [[a]]\n")
        self._page("a", "# a\n\n- [[b]]\n- [[missing_page]]\n")
        self.assertIn("L8", {f.code for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)})


class WriteIdempotenceTests(TempVault):
    """Ruling R104-3, enforced at the single writer rather than in eight adapters."""

    def _page(self, at, body="# p\n", desc="A page."):
        return pages.Page(self.vault / "wiki" / "concepts" / "p.md",
                          pages.make_meta("Concept", "p", desc, at=at), body)

    def test_identical_content_keeps_its_earned_stamp_and_is_not_rewritten(self):
        pages.write_page(self._page(NOW), self.vault, now=NOW)
        path = self.vault / "wiki" / "concepts" / "p.md"
        before = path.read_bytes()
        later = NOW + timedelta(days=2)
        page = self._page(later)
        pages.write_page(page, self.vault, now=later)
        self.assertEqual(path.read_bytes(), before)                       # byte-identical: no write
        self.assertEqual(page.meta["generated"]["at"], pages.iso(NOW))    # caller sees what is on disk

    def test_changed_content_is_written_and_restamped(self):
        pages.write_page(self._page(NOW), self.vault, now=NOW)
        later = NOW + timedelta(days=2)
        pages.write_page(self._page(later, body="# p\n\nnew line\n"), self.vault, now=later)
        meta, body = fm.parse((self.vault / "wiki/concepts/p.md").read_text(encoding="utf-8"))
        self.assertIn("new line", body)
        self.assertEqual(meta["generated"]["at"], pages.iso(later))

    def test_a_metadata_only_change_still_writes(self):
        pages.write_page(self._page(NOW), self.vault, now=NOW)
        later = NOW + timedelta(days=2)
        pages.write_page(self._page(later, desc="A different description."), self.vault, now=later)
        meta, _ = fm.parse((self.vault / "wiki/concepts/p.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["description"], "A different description.")
        self.assertEqual(meta["generated"]["at"], pages.iso(later))


class ArtifactEnvelopeTests(Round104Fixture):
    def test_written_at_prefers_the_envelope_over_the_mtime(self):
        art = json.loads(json.dumps(REPLAY_ART))
        art["_artifact"] = {"written_at": "2026-09-06T04:54:00Z", "writer": "engine",
                            "rows_in_table": 29612, "seed": 7}
        stamp, source = ingest_cr.written_at(art, self.artifact)
        self.assertEqual(stamp, "2026-09-06T04:54:00Z")
        self.assertIn("_artifact", source)

    def test_an_artifact_without_an_envelope_falls_back_and_says_so(self):
        stamp, source = ingest_cr.written_at(REPLAY_ART, self.artifact)   # the fixture has no envelope
        self.assertIn("mtime", source)
        self.assertTrue(stamp.endswith("Z"))

    def test_the_verdict_page_reports_the_envelope_and_its_provenance(self):
        art = json.loads(json.dumps(REPLAY_ART))
        art["_artifact"] = {"written_at": "2026-09-06T04:54:00Z", "writer": "engine",
                            "rows_in_table": 29612, "seed": 7}
        self.artifact.write_text(json.dumps(art), encoding="utf-8")
        page = ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                       registration=self.registration, at=NOW)
        self.assertIn("artifact written at **2026-09-06T04:54:00Z**", page.body)
        self.assertIn("29,612 rows", page.body)
        self.assertEqual(page.meta["dev"]["observed_from"], "the artifact's own `_artifact.written_at`")

    def test_reingesting_the_same_artifact_writes_nothing_and_logs_nothing(self):
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW)
        path = self.vault / "wiki/experiments/whale_sweeper_cascade_replay_verdict.md"
        before, log_before = path.read_bytes(), (self.vault / "log.md").read_text(encoding="utf-8")
        ingest_cr.ingest_replay(self.vault, self.dev_root, result=self.artifact,
                                registration=self.registration, at=NOW + timedelta(hours=3))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.vault / "log.md").read_text(encoding="utf-8"), log_before)


class CascadeAnatomyTests(Round104Fixture):
    def setUp(self):
        super().setUp()
        (self.dev_root / "HyperLiquid" / "HL_Monarch" / "config" / "settings.py").write_text(
            BARS_PY + SETTINGS_105, encoding="utf-8")

    def test_the_control_identity_is_checked_not_asserted(self):
        audit = ingest_ca.control_audit(REPLAY_ART, 1)
        self.assertEqual(audit["treatment_share"], 0.5)
        self.assertEqual(audit["expected_share"], 0.5)
        self.assertTrue(audit["holds"])
        # a table that is NOT 1-to-1 must fail the check rather than be described as holding
        art = json.loads(json.dumps(REPLAY_ART))
        art["data_audit"]["raw_loaded"] = 20000
        self.assertFalse(ingest_ca.control_audit(art, 1)["holds"])
        self.assertTrue(ingest_ca.control_audit(art, 1)["treatment_share"] > 0.5)

    def test_containment_of_truncation_in_nulls_is_derived_from_the_counts(self):
        audit = ingest_ca.control_audit(REPLAY_ART, 1)
        self.assertEqual(audit["excluded"], 14675 - 14336)
        self.assertEqual(audit["excluded"], REPLAY_ART["data_audit"]["null_30m_count"])
        self.assertTrue(audit["truncation_within_null"])
        art = json.loads(json.dumps(REPLAY_ART))
        art["data_audit"]["null_30m_count"] = 10
        self.assertFalse(ingest_ca.control_audit(art, 1)["truncation_within_null"])

    def test_page_records_both_sides_and_refuses_to_call_side_b_a_finding(self):
        page = ingest_ca.ingest_anatomy(self.vault, self.dev_root, result=self.artifact, at=NOW)
        self.assertIsNotNone(page)
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW, force=True)

        body = page.body
        self.assertIn("0.2784", body)                       # side A median, from the artifact
        self.assertIn("1.7378", body)                       # side B median, reported
        self.assertIn("does not grade sides", body)         # and explicitly not graded
        self.assertIn("median/mean divergence", body.lower())
        self.assertEqual([p["value"] for p in page.meta["dev"]["parameters"]], [1])
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_c1_fires_if_the_control_multiple_changes_without_recompiling(self):
        ingest_ca.ingest_anatomy(self.vault, self.dev_root, result=self.artifact, at=NOW)
        (self.dev_root / "HyperLiquid" / "HL_Monarch" / "config" / "settings.py").write_text(
            BARS_PY + "EXCURSION_CONTROL_MULTIPLE = 3\n", encoding="utf-8")
        codes = [(f.code, f.message) for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)]
        self.assertTrue(any(c == "C1" and "excursion_control_multiple" in m for c, m in codes), codes)

    def test_missing_artifact_refuses(self):
        out = io.StringIO()
        self.artifact.unlink()
        self.assertEqual(ingest_ca.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), 3)
        self.assertIn("cascade_replay --json", out.getvalue())



# --------------------------------------------------------------------------------------
# Round 106: the Adapter Lifecycle Maintenance Invariant (R105-2) and git provenance (B19/B20)
# --------------------------------------------------------------------------------------

class WindowInvarianceTests(CRMFixture):
    """Ruling R105-2: an adapter maintains every page it emitted, or says it no longer can."""

    def test_a_titan_below_the_cap_is_re_admitted_not_frozen(self):
        first = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW, limit_titans=2)
        titans = sorted(p.stem for p in (self.vault / "crm" / "titans").glob("titan_*.md"))
        self.assertGreaterEqual(len(titans), 1, titans)
        # squeeze the window to nothing: without re-admission these pages would never be rebuilt
        report = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW + timedelta(hours=1),
                                            limit_titans=0)
        still = sorted(p.stem for p in (self.vault / "crm" / "titans").glob("titan_*.md"))
        self.assertEqual(still, titans)                       # nothing deleted
        self.assertEqual(report.unmaintained, [])             # and nothing abandoned: all re-admitted

    def test_a_page_whose_source_row_is_gone_is_named_not_silently_frozen(self):
        ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW)
        orphan = self.vault / "crm" / "sharps" / "sharp_0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef.md"
        pages.write_page(pages.Page(orphan, pages.make_meta("Entity/Sharp Trader", "Sharp gone",
                                                            "A sharp pruned from the source table.", at=NOW),
                                    "# gone\n\n- [[crm_register|CRM register]]\n"), self.vault, now=NOW)
        report = ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW + timedelta(hours=1))
        self.assertIn("0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef", report.unmaintained)


class MarketWindowTests(IngestFixture):
    def _ingest(self, at, drops=None):
        return ingest_mk.ingest_markets(self.vault, self.dev_root, exp_dir=self.exp_dir, at=at,
                                        drops=drops if drops is not None else None)

    def test_a_market_that_ages_out_of_the_drop_keeps_its_identity_and_its_path(self):
        """The naive union writes a placeholder page at a NEW slug and orphans the good one."""
        self._ingest(NOW)
        page = next(p for p in pages.load_pages(self.vault) if p.type == "Market"
                    and (p.meta.get("dev") or {}).get("token_id") == "7000000000000000000000000000000000000000000000000000000000000000000000000001")
        before_path, before_title = page.path, page.meta["title"]
        self.assertNotIn("Polymarket token", before_title)
        # every drop replaced by one that no longer carries this token
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        for f in drops.glob("*.json"):
            f.unlink()
        (drops / "polymarket_macro_20260907T000000_000000Z.json").write_text(json.dumps([]), encoding="utf-8")
        self._ingest(NOW + timedelta(days=1))
        after = pages.load_page(before_path)
        self.assertIsNotNone(after, "the page was orphaned at its old path")
        self.assertEqual(after.meta["title"], before_title)          # not degraded to a placeholder
        self.assertEqual(len([p for p in pages.load_pages(self.vault) if p.type == "Market"
                              and (p.meta.get("dev") or {}).get("token_id") == "7000000000000000000000000000000000000000000000000000000000000000000000000001"]), 1)

    def test_first_seen_is_the_first_sighting_not_the_latest(self):
        self._ingest(NOW)
        path = next(p.path for p in pages.load_pages(self.vault) if p.type == "Market"
                    and (p.meta.get("dev") or {}).get("token_id") == "7000000000000000000000000000000000000000000000000000000000000000000000000001")
        first = pages.load_page(path).meta["dev"]["first_seen"]
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        newest = json.loads(sorted(drops.glob("*.json"))[-1].read_text(encoding="utf-8"))
        for r in newest:
            r["fetched_at"] = "2026-09-09T00:00:00Z"          # a much later sighting
        (drops / "polymarket_macro_20260909T000000_000000Z.json").write_text(json.dumps(newest), encoding="utf-8")
        self._ingest(NOW + timedelta(days=3))
        self.assertEqual(pages.load_page(path).meta["dev"]["first_seen"], first)


class GitProvenanceTests(TempVault):
    """Backlog B19/B20: a ruling that cites a commit is making a checkable claim."""

    def test_citations_are_read_from_both_spellings(self):
        meta = {"sources": [{"resource": "git:da48cf3"}, {"resource": "AGENTS.md"}],
                "dev": {"citations": ["deadbee", {"commit": "ec98342"}]}}
        self.assertEqual(lint.git_citations(meta),
                         [("sources[0].resource", "da48cf3"),
                          ("dev.citations[0]", "deadbee"),
                          ("dev.citations[1].commit", "ec98342")])

    def test_outside_a_repository_the_check_is_skipped_not_passed(self):
        """A temp dir is not a repo; reporting either verdict there would be a lie."""
        self.assertFalse(lint.is_git_repo(self.dev_root))
        self.write("wiki/concepts/a.md", page_text(body="# a\n", sources=[{"id": "c", "resource": "git:deadbee",
                                                                           "title": "commit deadbee"}]))
        self.assertEqual([f for f in lint.check_l5(pages.load_documents(self.vault), self.vault, self.dev_root)
                          if "commit" in f.message], [])

    def test_inside_a_repository_an_unresolvable_hash_is_an_error(self):
        real = Path(__file__).resolve().parents[2]          # the DEV repo this test file lives in
        if not lint.is_git_repo(real):                      # pragma: no cover - CI without git history
            self.skipTest("not a git repository")
        self.assertTrue(lint.commit_exists("da48cf3", real))      # a commit this repo really has
        self.assertFalse(lint.commit_exists("deadbee", real))     # well-formed but not a commit
        self.assertFalse(lint.commit_exists("nothex!", real))     # not even a hash
        self.write("wiki/concepts/a.md", page_text(body="# a\n", sources=[{"id": "c", "resource": "git:deadbee",
                                                                           "title": "commit deadbee"}]))
        found = [f for f in lint.check_l5(pages.load_documents(self.vault), self.vault, real)
                 if "not in this repository" in f.message]
        self.assertEqual([(f.code, f.severity) for f in found], [("L5", "error")])

    def test_the_seeded_rulings_cite_commits_that_exist(self):
        """The real vault's rulings pass; this is the check earning its place rather than passing empty."""
        real = Path(__file__).resolve().parents[2]
        if not lint.is_git_repo(real):                      # pragma: no cover
            self.skipTest("not a git repository")
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW)
        cited = [(d.path.stem, sha) for d in pages.load_documents(self.vault) if d.meta
                 for _, sha in lint.git_citations(d.meta)]
        self.assertTrue(cited, "no ruling cited a commit; the check would be vacuous")
        for stem, sha in cited:
            self.assertTrue(lint.commit_exists(sha, real), f"{stem} cites missing commit {sha}")



# --------------------------------------------------------------------------------------
# Round 107: rank_at_seed freezing (R106-1.E) and the pre-baked query cards (s.Query)
# --------------------------------------------------------------------------------------
from knowledge import query as query_mod  # noqa: E402


class RankAtSeedTests(CRMFixture):
    def test_rank_at_seed_is_frozen_while_rank_now_tracks(self):
        """AT SEED means at seed: Round 106 made these pages refreshable, which put the field in
        the same trap `first_seen` fell into on markets."""
        ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW)
        path = self.vault / f"crm/whales/whale_{EOA_WHALE}.md"
        first = fm.parse(path.read_text(encoding="utf-8"))[0]["dev"]
        self.assertEqual(first["rank_at_seed"], 1)
        self.assertEqual(first["rank_now"], 1)
        # demote it: another whale overtakes on equity
        conn = sqlite3.connect(self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db")
        conn.execute("UPDATE whale_wallets SET account_value = 1.0 WHERE lower(address) = ?", (EOA_WHALE,))
        conn.commit()
        conn.close()
        ingest_ent.ingest_entities(self.vault, self.dev_root, at=NOW + timedelta(hours=1))
        after, body = fm.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(after["dev"]["rank_at_seed"], 1)            # frozen
        self.assertGreater(after["dev"]["rank_now"], 1)              # and the live rank moved
        # the body must agree with the frontmatter, or the page contradicts itself
        self.assertIn(f"rank by equity at seed: 1 (now {after['dev']['rank_now']})", body)


class QueryCardTests(IngestFixture):
    def setUp(self):
        super().setUp()
        cal_dir = Path(knowledge_pkg.__file__).parent / "calendars"
        ingest_cal.ingest_calendars(cal_dir, self.vault, self.dev_root, at=NOW)
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.event = "fomc_2026-09-16"

    def card(self, *argv, now=None):
        out = io.StringIO()
        code = query_mod.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)]
                              + list(argv) + (["--now", pages.iso(now)] if now else []), out=out)
        return code, out.getvalue()

    def test_the_card_fits_on_a_screen(self):
        """WIKI_SCHEMA.md s.Query: under 60 lines. A card that scrolls loses its last line, which
        is the one that says what NOT to do."""
        code, text = self.card("--drill-card", self.event)
        self.assertEqual(code, EXIT_OK)
        self.assertLess(len(text.splitlines()), query_mod.MAX_LINES, text)

    def test_the_countdown_is_computed_and_the_unit_matches_the_decision(self):
        release = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(query_mod.countdown(release, release - timedelta(minutes=2)), "T-2m")
        self.assertEqual(query_mod.countdown(release, release - timedelta(hours=3, minutes=5)), "T-3h 05m")
        self.assertEqual(query_mod.countdown(release, release - timedelta(days=10)), "T-10d 0h")
        self.assertIn("the print has happened", query_mod.countdown(release, release + timedelta(minutes=5)))
        self.assertIn("not recorded", query_mod.countdown(None, release))
        _, text = self.card("--drill-card", self.event, now=datetime(2026, 9, 16, 17, 58, tzinfo=timezone.utc))
        self.assertIn("T-2m", text)

    def test_inside_the_window_the_card_says_the_pages_are_frozen(self):
        _, text = self.card("--drill-card", self.event, now=datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc))
        self.assertIn("INSIDE THE WINDOW", text)
        _, before = self.card("--drill-card", self.event, now=datetime(2026, 9, 16, 17, 0, tzinfo=timezone.utc))
        self.assertNotIn("INSIDE THE WINDOW", before)

    def test_the_card_writes_nothing_at_all(self):
        """Read-only is the property that lets this be run at T-2 inside a frozen window."""
        def snap():
            return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(self.vault.rglob("*.md"))}
        before = snap()
        self.card("--drill-card", self.event)
        self.card("--regime", "BTC")
        self.card("--list")
        self.assertEqual(snap(), before)

    def test_the_card_carries_the_rules_and_the_human_only_step(self):
        _, text = self.card("--drill-card", self.event)
        self.assertIn("THE ONE THING ONLY YOU CAN DO", text)
        self.assertIn("change_bps", text)
        self.assertIn(">= 0.99 ONLY from the statement", text)
        self.assertIn("fomc_2026-09-16_rules", text)          # the registration, by link
        self.assertIn("Ruling R4", text)                      # the neg_risk refusal

    def test_a_standing_forecast_is_surfaced_from_the_journal(self):
        day = self.vault / "journal" / "2026-09-06.md"
        meta = pages.make_meta("Journal Entry", "Journal 2026-09-06", "A day.", at=NOW,
                               dev={"date": "2026-09-06", "predictions": [
                                   {"event": "fomc_2026-09-16", "field": "change_bps", "op": "==",
                                    "value": 0, "p": 0.9, "outcome": None}]})
        pages.write_page(pages.Page(day, meta, "# day\n\n- [[journal_register|Journal register]]\n"),
                         self.vault, now=NOW)
        _, text = self.card("--drill-card", self.event)
        self.assertIn("YOUR STANDING FORECAST", text)
        self.assertIn("p=0.9", text)
        self.assertIn("change_bps == 0", text)                # claim built from field/op/value

    def test_a_missing_event_refuses_and_names_what_exists(self):
        code, text = self.card("--drill-card", "no-such-event")
        self.assertEqual(code, EXIT_HALT)
        self.assertIn("[REFUSE]", text)
        self.assertIn("fomc_2026-09-16", text)                # the known events, so the operator can retry
        self.assertIn("blank card", text)

    def test_the_event_name_is_accepted_in_any_spelling(self):
        self.assertEqual(query_mod.normalise("FOMC 2026-09-16"), "fomc_2026_09_16")
        self.assertEqual(query_mod.normalise("fomc-2026-09-16"), query_mod.normalise("fomc_2026-09-16"))
        for spelling in ("fomc-2026-09-16", "fomc_2026-09-16", "FOMC 2026 09 16"):
            code, _ = self.card("--drill-card", spelling)
            self.assertEqual(code, EXIT_OK, spelling)

    def test_the_regime_card_reports_the_current_classification(self):
        ingest_ll.ingest_verdict(VERDICT_JSON, self.vault, self.dev_root, tier="1",
                                 source="verdict.json", at=NOW)
        code, text = self.card("--regime", "BTC")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("btc_macro_regime", text)
        self.assertIn("consensus(3)", text)
        code, text = self.card("--regime", "nothing-like-this")
        self.assertIn("no Regime page matches", text)
        self.assertIn("btc_macro_regime", text)               # and says what there is

    def test_halt_refuses_even_though_a_query_writes_nothing(self):
        (self.dev_root / "HALT.flag").write_text("{}", encoding="utf-8")
        code, text = self.card("--drill-card", self.event)
        self.assertEqual(code, EXIT_HALT)
        self.assertIn("[HALT]", text)



# --------------------------------------------------------------------------------------
# Round 108: lint L9, structured dev.rules, drill-card ergonomics, regime match priority
# --------------------------------------------------------------------------------------

class LintL9Tests(TempVault):
    """Ruling R107-1.D: a link to a git-ignored file lints clean here and fails L8 on a fresh clone."""

    def _repo(self):
        """A real git repo in the temp dir, with one ignored dashboard."""
        run = lambda *a: subprocess.run(["git"] + list(a), cwd=str(self.dev_root),
                                        capture_output=True, text=True)
        if run("init", "-q").returncode != 0:                       # pragma: no cover - no git
            self.skipTest("git unavailable")
        (self.dev_root / ".gitignore").write_text("obsidian_vault/Volatile_Dashboard.md\n", encoding="utf-8")
        (self.vault / "Volatile_Dashboard.md").write_text("# dashboard\n", encoding="utf-8")
        (self.vault / "Tracked_Dashboard.md").write_text("# tracked\n", encoding="utf-8")
        run("add", "-A")
        run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        return run

    def _page(self, stem, body):
        self.write(f"wiki/concepts/{stem}.md", page_text(body=body))

    def test_an_untracked_dashboard_nothing_links_is_fine(self):
        self._repo()
        self._page("a", "# a\n\n- [[Tracked_Dashboard]]\n")
        self.assertEqual(lint.check_l9(pages.load_documents(self.vault), self.vault, self.dev_root), [])

    def test_linking_a_git_ignored_file_is_an_error(self):
        self._repo()
        self._page("a", "# a\n\n- [[Volatile_Dashboard]]\n")
        found = lint.check_l9(pages.load_documents(self.vault), self.vault, self.dev_root)
        self.assertEqual([(f.code, f.severity) for f in found], [("L9", "error")])
        self.assertIn("Volatile_Dashboard.md", found[0].message)
        self.assertIn("fresh clones will fail L8", found[0].message)

    def test_every_linking_page_is_named_not_just_the_first(self):
        self._repo()
        self._page("a", "# a\n\n- [[Volatile_Dashboard]]\n")
        self._page("b", "# b\n\n- [[Volatile_Dashboard|dash]]\n")
        found = lint.check_l9(pages.load_documents(self.vault), self.vault, self.dev_root)
        self.assertEqual(len(found), 2)
        self.assertEqual({f.path for f in found}, {"wiki/concepts/a.md", "wiki/concepts/b.md"})

    def test_outside_a_repository_l9_is_skipped_not_passed(self):
        self._page("a", "# a\n\n- [[Volatile_Dashboard]]\n")
        (self.vault / "Volatile_Dashboard.md").write_text("# d\n", encoding="utf-8")
        self.assertFalse(lint.is_git_repo(self.dev_root))
        self.assertEqual(lint.check_l9(pages.load_documents(self.vault), self.vault, self.dev_root), [])

    def test_the_ignore_listing_is_complete_not_just_the_first_match(self):
        """git check-ignore returned ONE match per batch here; this is the regression that caught it."""
        self._repo()
        (self.dev_root / ".gitignore").write_text(
            "obsidian_vault/Volatile_Dashboard.md\nobsidian_vault/Second_Dashboard.md\n", encoding="utf-8")
        (self.vault / "Second_Dashboard.md").write_text("# two\n", encoding="utf-8")
        found = lint.ignored_under(self.vault, self.dev_root)
        self.assertIn("obsidian_vault/Volatile_Dashboard.md", found)
        self.assertIn("obsidian_vault/Second_Dashboard.md", found)   # the SECOND one, not just the first


class StructuredRulesTests(IngestFixture):
    def test_rules_are_serialised_into_frontmatter_with_whole_token_ids(self):
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        meta, body = fm.parse((self.vault / "wiki/experiments/fomc_2026-09-16_rules.md")
                              .read_text(encoding="utf-8"))
        rules = meta["dev"]["rules"]
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["label"], "FOMC 2026-09-16: no change")
        self.assertEqual(rules[0]["condition"], "change_bps == 0")
        self.assertEqual(rules[0]["outcome"], "YES")
        self.assertEqual(rules[0]["market"], "7000000000000000000000000000000000000000000000000000000000000000000000000001")         # whole id, not truncated
        # the rendered table still truncates for readability - that is why the card stopped using it
        self.assertIn("|", body)


class CardErgonomicsTests(QueryCardTests):
    def test_the_card_shows_whole_token_ids_from_dev_rules(self):
        _, text = self.card("--drill-card", self.event)
        self.assertIn("token 7000000000000000000000000000000000000000000000000000000000000000000000000001", text)
        self.assertNotIn("7000000000000000000000000000000000000000000000000000000000000000000000000001\u2026", text)                    # never the truncated form
        self.assertNotIn("legacy page", text)

    def test_a_legacy_page_without_dev_rules_still_renders(self):
        path = self.vault / "wiki/experiments/fomc_2026-09-16_rules.md"
        meta, body = fm.parse(path.read_text(encoding="utf-8"))
        meta["dev"].pop("rules")
        pages.write_page(pages.Page(path, meta, body), self.vault, now=NOW)
        _, text = self.card("--drill-card", self.event)
        self.assertIn("REGISTERED RULES", text)
        self.assertIn("legacy page", text)                           # and says why the id is short

    def test_the_post_print_command_is_copy_pasteable(self):
        """At T+1 nobody should be recalling flags, and no path may be a guess."""
        _, text = self.card("--drill-card", self.event)
        self.assertIn("./event.json", text)
        self.assertIn("--survival-curve", text)
        self.assertIn("--event ./event.json", text)
        self.assertIn("--rules cross_market/experiments/fomc_2026-09-16.rules.json", text)
        # the books path the DRILL actually records into, not latency_sniper's bare default
        self.assertIn("--books cross_market/data/clob_books/fomc_2026-09-16", text)
        self.assertNotIn("...", text)
        self.assertLess(len(text.splitlines()), query_mod.MAX_LINES)

    def test_regime_exact_and_prefix_match_beat_substring(self):
        ingest_ll.ingest_verdict(VERDICT_JSON, self.vault, self.dev_root, tier="1",
                                 source="verdict.json", at=NOW)
        other = pages.page_path(self.vault, "Regime", "btc_macro_regime_archive")
        pages.write_page(pages.Page(other, pages.make_meta("Regime", "Archive", "Old rows.", at=NOW,
                                                           dev={"history": []}),
                                    "# archive\n\n- [[btc_macro_regime]]\n"), self.vault, now=NOW)
        _, exact = self.card("--regime", "btc_macro_regime")
        self.assertIn("btc_macro_regime]]", exact)
        self.assertNotIn("btc_macro_regime_archive]]", exact)         # exact wins outright
        self.assertNotIn("matched", exact)
        _, sub = self.card("--regime", "macro")                       # substring: both, and it says so
        self.assertIn("matched 2 pages on substring", sub)



# --------------------------------------------------------------------------------------
# Round 109: C1 over dev.rules (R108-1.E), dev.books_dir (R108-1.D), work-chain digests (B5)
# --------------------------------------------------------------------------------------
from knowledge.ingest import digests as ingest_dg  # noqa: E402

AGENTS_DIGEST_FIXTURE = """# DEV

## Status

Round 109 complete (2026-09-06): THE NEWEST FORMAT, WITH A DATE.
A second line of the same entry.

Round 73 complete: AN OLDER ENTRY WITH NO DATE AT ALL.
The log changed shape somewhere around round 74.

Round 50 complete - MILESTONE. A third shape, with a dash.
It mentions [[Whales/0xabc]] and [[wikilinks]] as SYNTAX, not as links.

## Round 109 findings

Not part of any round entry.
"""


class RulesDriftTests(IngestFixture):
    """Ruling R108-1.E: dev.rules is a second copy of the pre-registered mapping. C1 guards it."""

    def setUp(self):
        super().setUp()
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.page = self.vault / "wiki/experiments/fomc_2026-09-16_rules.md"
        self.raw = self.exp_dir / "fomc_2026-09-16.rules.json"

    def _findings(self):
        return [f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "C1"]

    def test_a_faithful_page_is_clean(self):
        self.assertEqual(self._findings(), [])

    def test_editing_the_page_copy_trips_c1(self):
        meta, body = fm.parse(self.page.read_text(encoding="utf-8"))
        meta["dev"]["rules"][0]["market"] = "TAMPERED"
        pages.write_page(pages.Page(self.page, meta, body), self.vault, now=NOW)
        found = self._findings()
        self.assertTrue(found)
        self.assertIn("dev.rules[0].market drift", found[0].message)

    def test_editing_the_raw_registration_trips_c1(self):
        raw = json.loads(self.raw.read_text(encoding="utf-8"))
        raw["rules"][0]["value"] = 999
        self.raw.write_text(json.dumps(raw), encoding="utf-8")
        found = self._findings()
        self.assertTrue(found)
        self.assertIn("condition drift", found[0].message)

    def test_a_removed_rule_trips_c1_on_the_count(self):
        raw = json.loads(self.raw.read_text(encoding="utf-8"))
        raw["rules"].pop()
        self.raw.write_text(json.dumps(raw), encoding="utf-8")
        found = self._findings()
        self.assertTrue(found)
        self.assertIn("page has 2 rule(s)", found[0].message)

    def test_a_missing_registration_is_reported_not_ignored(self):
        self.raw.unlink()
        found = self._findings()
        self.assertTrue(any("dev.registration missing on disk" in f.message for f in found), found)

    def test_the_compiler_and_the_checker_share_one_transform(self):
        """Two transcriptions of the same mapping would drift the way C1 exists to catch."""
        from knowledge.ingest.experiments import rules_from_raw as compiler_side
        self.assertIs(compiler_side, lint.rules_from_raw)


class BooksDirTests(QueryCardTests):
    def test_the_event_declares_where_its_recorder_writes(self):
        meta, _ = fm.parse((self.vault / "wiki/events/fomc_2026-09-16.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["books_dir"], "cross_market/data/clob_books/fomc_2026-09-16")

    def test_the_card_reads_the_declaration_over_the_constructed_path(self):
        path = self.vault / "wiki/events/fomc_2026-09-16.md"
        meta, body = fm.parse(path.read_text(encoding="utf-8"))
        meta["dev"]["books_dir"] = "somewhere/else/entirely"
        pages.write_page(pages.Page(path, meta, body), self.vault, now=NOW)
        _, text = self.card("--drill-card", self.event)
        self.assertIn("--books somewhere/else/entirely", text)

    def test_an_event_without_the_field_falls_back(self):
        path = self.vault / "wiki/events/fomc_2026-09-16.md"
        meta, body = fm.parse(path.read_text(encoding="utf-8"))
        meta["dev"].pop("books_dir")
        pages.write_page(pages.Page(path, meta, body), self.vault, now=NOW)
        _, text = self.card("--drill-card", self.event)
        self.assertIn("--books cross_market/data/clob_books/fomc_2026-09-16", text)


class DigestTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.agents = self.dev_root / "AGENTS.md"
        self.agents.write_text(AGENTS_DIGEST_FIXTURE, encoding="utf-8")

    def test_all_three_log_formats_are_parsed(self):
        """A regex for only the newest format silently covered a third of the real log."""
        rounds = ingest_dg.parse_rounds(AGENTS_DIGEST_FIXTURE)
        self.assertEqual([r["round"] for r in rounds], [50, 73, 109])
        by_n = {r["round"]: r for r in rounds}
        self.assertEqual(by_n[109]["date"], "2026-09-06")
        self.assertIsNone(by_n[73]["date"])                       # undated, not guessed
        self.assertIsNone(by_n[50]["date"])
        self.assertIn("A second line", by_n[109]["summary"])       # the whole entry, not just line 1
        self.assertNotIn("Not part of any round", by_n[50]["summary"])   # the ## heading ends it

    def test_quoted_wikilinks_are_neutralised(self):
        """The log discusses link syntax; copied bare it would trip L8 and L9."""
        self.assertEqual(ingest_dg.neutralise("see [[Whales/0xabc]] here"), "see `[[Whales/0xabc]]` here")
        self.assertEqual(ingest_dg.neutralise("`[[already]]`"), "`[[already]]`")   # not double-wrapped
        total, _ = ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents, at=NOW)
        self.assertEqual(total, 3)
        body = (self.vault / "wiki/digests/round_50.md").read_text(encoding="utf-8")
        self.assertIn("`[[Whales/0xabc]]`", body)
        self.assertNotIn("\n- [[Whales/0xabc]]", body)
        self.assertEqual(pages.wikilink_targets(fm.parse(body)[1]), {"digests_register"})

    def test_pages_register_and_lint_clean(self):
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents, at=NOW)
        reg = self.vault / "wiki/concepts/digests_register.md"
        self.assertTrue(reg.is_file())
        meta, body = fm.parse(reg.read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["count"], 3)
        self.assertIn("Round 109", body)
        self.assertIn("| - |", body)                              # an undated round shows a dash, not None
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW, force=True)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])

    def test_the_source_cites_the_log_with_an_anchor(self):
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents, at=NOW)
        meta, _ = fm.parse((self.vault / "wiki/digests/round_109.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["sources"][0]["resource"], "AGENTS.md#round-109-complete")
        # L5 must resolve the FILE and ignore the fragment; the whole string is not a filename
        self.assertEqual([f for f in lint.check_l5(pages.load_documents(self.vault), self.vault,
                                                   self.dev_root) if "agents" in f.message.lower()], [])

    def test_reingesting_an_unchanged_log_writes_nothing(self):
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents, at=NOW)
        def snap():
            return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(self.vault.rglob("*.md"))}
        before = snap()
        total, written = ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents,
                                                  at=NOW + timedelta(hours=2))
        self.assertEqual((total, written), (3, 0))
        self.assertEqual(snap(), before)

    def test_since_limits_the_range(self):
        total, _ = ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents, since=100, at=NOW)
        self.assertEqual(total, 1)
        self.assertTrue((self.vault / "wiki/digests/round_109.md").is_file())
        self.assertFalse((self.vault / "wiki/digests/round_50.md").is_file())

    def test_a_log_with_no_round_entries_refuses(self):
        self.agents.write_text("# nothing here\n", encoding="utf-8")
        out = io.StringIO()
        code = ingest_dg.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out)
        self.assertEqual(code, 3)
        self.assertIn("[REFUSE]", out.getvalue())



# --------------------------------------------------------------------------------------
# Round 110: the digests register via SPECS (R109-1.F), the assert drift guard (R109-1.E),
# and announced truncation (R109-1.C)
# --------------------------------------------------------------------------------------

class DigestRegisterTests(IngestFixture):
    def test_seed_guarantees_the_digests_register_so_desks_can_link_it(self):
        """R109-1.F: Round 109 left it out because seed could not create it. Now seed can."""
        self.assertIn("Digest", registers.SPECS)                       # what makes seed write it
        # Round 112 (R111-1.C): desks reach every register THROUGH the hub, not by direct link
        self.assertEqual(seed.REGISTER_LINKS, (("registers_register", "Registers catalogue"),))
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW)
        reg = self.vault / "wiki/concepts/digests_register.md"
        self.assertTrue(reg.is_file(), "seed must write an EMPTY register, not skip it")
        meta, body = fm.parse(reg.read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["register_for"], "Digest")
        self.assertEqual(meta["dev"]["count"], 0)
        self.assertIn("0 page(s).", body)
        # and it is reachable from every desk via the hub without dangling - the Round 109 failure
        hub = (self.vault / "wiki/concepts/registers_register.md").read_text(encoding="utf-8")
        self.assertIn("[[digests_register\\|", hub)
        self.assertEqual([f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)
                          if f.code in ("L8", "L3")], [])

    def test_one_writer_only_so_seed_and_the_adapter_agree(self):
        """Both used to build this page with different content and overwrite each other silently."""
        agents = self.dev_root / "AGENTS.md"
        agents.write_text(AGENTS_DIGEST_FIXTURE, encoding="utf-8")
        reg = self.vault / "wiki/concepts/digests_register.md"
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW)
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=agents, at=NOW)
        after_adapter = reg.read_bytes()
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW, force=True)
        self.assertEqual(reg.read_bytes(), after_adapter, "seed and the adapter disagree about the register")
        meta, _ = fm.parse(reg.read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["count"], 3)


class DigestGuardTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.agents = self.dev_root / "AGENTS.md"
        self.agents.write_text(AGENTS_DIGEST_FIXTURE, encoding="utf-8")
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self.agents, at=NOW)

    def _c1(self):
        return [f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "C1"]

    def test_a_faithful_log_is_clean(self):
        self.assertEqual(self._c1(), [])

    def test_the_digest_pins_the_heading_it_was_compiled_from(self):
        meta, _ = fm.parse((self.vault / "wiki/digests/round_109.md").read_text(encoding="utf-8"))
        a = meta["dev"]["asserts"][0]
        self.assertEqual(a["file"], "AGENTS.md")
        self.assertEqual(a["pattern"], "^Round 109 complete")

    def test_renaming_a_round_heading_trips_c1_on_that_digest(self):
        self.agents.write_text(
            AGENTS_DIGEST_FIXTURE.replace("Round 73 complete:", "Round 73 finished:"), encoding="utf-8")
        found = self._c1()
        self.assertTrue(found)
        self.assertEqual(found[0].path, "wiki/digests/round_73.md")
        self.assertIn("^Round 73 complete", found[0].message)

    def test_deleting_a_round_entry_trips_c1_rather_than_leaving_a_stale_page(self):
        keep = AGENTS_DIGEST_FIXTURE.split("Round 50 complete")[0]
        self.agents.write_text(keep, encoding="utf-8")
        found = self._c1()
        self.assertTrue(any(f.path == "wiki/digests/round_50.md" for f in found), found)


class DigestTruncationTests(IngestFixture):
    """R109-1.C: 250 lines, and a digest that drops the end of a round must SAY so."""

    def _log(self, n_lines: int) -> Path:
        body = "\n".join(f"line {i} of the round entry." for i in range(n_lines))
        agents = self.dev_root / "AGENTS.md"
        agents.write_text(f"# DEV\n\n## Status\n\nRound 42 complete (2026-09-06): A LONG ONE.\n{body}\n",
                          encoding="utf-8")
        return agents

    def test_the_ceiling_is_250(self):
        self.assertEqual(ingest_dg.MAX_BODY_LINES, 250)

    def test_a_short_entry_is_not_marked_truncated(self):
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self._log(10), at=NOW)
        meta, body = fm.parse((self.vault / "wiki/digests/round_42.md").read_text(encoding="utf-8"))
        self.assertFalse(meta["dev"]["truncated"])
        self.assertNotIn("[!NOTE]", body)

    def test_a_long_entry_is_clipped_and_says_so(self):
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self._log(400), at=NOW)
        meta, body = fm.parse((self.vault / "wiki/digests/round_42.md").read_text(encoding="utf-8"))
        self.assertTrue(meta["dev"]["truncated"])
        self.assertIn("> [!NOTE]", body)
        self.assertIn("truncated at 250 of ", body)
        self.assertRegex(body, r"truncated at 250 of (\d+) lines")
        self.assertGreater(int(re.search(r"truncated at 250 of (\d+) lines", body).group(1)), 250)
        self.assertIn("`AGENTS.md`", body)
        self.assertIn("Round 42 complete", body)
        self.assertNotIn("line 399 of the round entry", body)     # the tail really is gone

    def test_the_callout_is_not_a_wikilink(self):
        """AGENTS.md is at the REPO ROOT, not in the vault: a wikilink to it fails L8, so every
        truncated digest would break lint on the line telling the reader where the rest is."""
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self._log(400), at=NOW)
        body = fm.parse((self.vault / "wiki/digests/round_42.md").read_text(encoding="utf-8"))[1]
        self.assertNotIn("[[AGENTS", body)
        self.assertEqual(pages.wikilink_targets(body), {"digests_register"})
        self.assertEqual([f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)
                          if f.code in ("L8", "L9")], [])



# --------------------------------------------------------------------------------------
# Round 111: summary column (R110-1.A), durable truncation warning (R110-1.E),
# query filing and OPT-IN usage counting (B16)
# --------------------------------------------------------------------------------------

class DigestSummaryColumnTests(IngestFixture):
    def test_the_register_carries_the_summary_without_a_second_builder(self):
        """R110-1.A: _cell prefers page.meta, so `description` lands in the generic table."""
        self.assertEqual(registers.SPECS["Digest"][3], ("round", "date", "description"))
        agents = self.dev_root / "AGENTS.md"
        agents.write_text(AGENTS_DIGEST_FIXTURE, encoding="utf-8")
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=agents, at=NOW)
        body = fm.parse((self.vault / "wiki/concepts/digests_register.md").read_text(encoding="utf-8"))[1]
        self.assertIn("| Page | round | date | description | Status | Generated |", body)
        self.assertIn("THE NEWEST FORMAT", body)          # the summary itself, in the table

    def test_no_description_can_split_the_table(self):
        """An unescaped pipe in a cell grows a phantom column - the Round 104 regime-table bug."""
        agents = self.dev_root / "AGENTS.md"
        agents.write_text("# DEV\n\n## Status\n\nRound 7 complete (2026-09-06): A | B piped summary.\n",
                          encoding="utf-8")
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=agents, at=NOW)
        body = fm.parse((self.vault / "wiki/concepts/digests_register.md").read_text(encoding="utf-8"))[1]
        row = [l for l in body.splitlines() if "round_7" in l][0]
        header = [l for l in body.splitlines() if l.startswith("| Page |")][0]
        self.assertEqual(row.count("|") - row.count(r"\|"), header.count("|"),
                         f"row splits into a different column count than the header:\n{row}")


class DigestWarningTests(IngestFixture):
    def _log(self, n_lines: int) -> Path:
        body = "\n".join(f"line {i}." for i in range(n_lines))
        agents = self.dev_root / "AGENTS.md"
        agents.write_text(f"# DEV\n\n## Status\n\nRound 42 complete (2026-09-06): LONG.\n{body}\n",
                          encoding="utf-8")
        return agents

    def test_a_truncated_digest_warns_durably_in_the_log(self):
        """R110-1.E: stdout is gone the moment an unattended run ends; log.md is not."""
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self._log(400), at=NOW)
        log = (self.vault / "log.md").read_text(encoding="utf-8")
        self.assertIn("**Warning**", log)
        self.assertIn("Round 42 digest truncated at 250 lines", log)
        self.assertIn("line(s) omitted", log)
        meta, body = fm.parse((self.vault / "wiki/digests/round_42.md").read_text(encoding="utf-8"))
        self.assertTrue(meta["dev"]["truncated"])
        self.assertGreater(meta["dev"]["dropped_lines"], 0)
        self.assertIn("> [!NOTE]", body)                   # BOTH the page callout and the log bullet

    def test_a_short_digest_writes_no_warning(self):
        ingest_dg.ingest_digests(self.vault, self.dev_root, agents=self._log(10), at=NOW)
        self.assertNotIn("**Warning**", (self.vault / "log.md").read_text(encoding="utf-8"))


class QueryFilingTests(QueryCardTests):
    def _snap(self):
        return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.vault.rglob("*.md"))}

    def test_the_card_still_writes_nothing_by_default(self):
        """Round 107's guarantee must survive B16. It is why the card is safe inside a window."""
        before = self._snap()
        self.card("--drill-card", self.event)
        self.card("--regime", "BTC")
        self.assertEqual(self._snap(), before)

    def test_file_scaffolds_a_question_and_never_invents_an_answer(self):
        code, text = self.card("--drill-card", self.event, "--file", "Does the 50bps rule fire?")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("[FILE]", text)
        # Round 112 (R111-1.D): the stem carries a 4-hex digest, so locate by prefix, not fixed name
        matches = sorted((self.vault / "wiki/concepts").glob("query_does_the_50bps_rule_fire_*.md"))
        self.assertEqual(len(matches), 1, matches)
        path = matches[0]
        meta, body = fm.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["kind"], "filed_query")
        self.assertEqual(meta["dev"]["question"], "Does the 50bps rule fire?")
        self.assertIn("_(not answered yet)_", body)          # a scaffold, never a manufactured answer
        self.assertIn("## Open when asked", body)
        self.assertIn(f"[[{self.event}", body)               # what was open when it was asked
        self.assertIn("stale_after", meta)                   # L7: a Concept page carries a review clock
        self.assertIn("**Query**", (self.vault / "log.md").read_text(encoding="utf-8"))

    def test_refiling_the_same_question_keeps_a_written_answer(self):
        self.card("--drill-card", self.event, "--file", "Keep my answer?")
        path = sorted((self.vault / "wiki/concepts").glob("query_keep_my_answer_*.md"))[0]
        meta, body = fm.parse(path.read_text(encoding="utf-8"))
        pages.write_page(pages.Page(path, meta, body.replace("_(not answered yet)_", "Yes, it does.")),
                         self.vault, now=NOW)
        self.card("--drill-card", self.event, "--file", "Keep my answer?")
        self.assertIn("Yes, it does.", path.read_text(encoding="utf-8"))

    def test_usage_counting_is_opt_in(self):
        before = self._snap()
        self.card("--drill-card", self.event)
        self.assertEqual(self._snap(), before, "the card counted usage without being asked")
        code, text = self.card("--drill-card", self.event, "--count-usage")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("[USAGE] recorded on", text)
        meta, _ = fm.parse((self.vault / f"wiki/events/{self.event}.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["usage"]["count"], 1)
        self.assertEqual(meta["dev"]["usage"]["window_days"], query_mod.USAGE_WINDOW_DAYS)
        self.card("--drill-card", self.event, "--count-usage")
        meta, _ = fm.parse((self.vault / f"wiki/events/{self.event}.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["usage"]["count"], 2)

    def test_inside_the_window_usage_is_skipped_not_attempted(self):
        """write_page REFUSES a page inside its own window. Counting there would raise WriteRefused
        at T-2 and hand the operator a traceback instead of a briefing card."""
        inside = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)
        code, text = self.card("--drill-card", self.event, "--count-usage", now=inside)
        self.assertEqual(code, EXIT_OK)                      # no WriteRefused, no traceback
        self.assertIn("INSIDE THE WINDOW", text)             # the card still renders
        self.assertIn("skipped (inside their own registration window)", text)
        meta, _ = fm.parse((self.vault / f"wiki/events/{self.event}.md").read_text(encoding="utf-8"))
        self.assertNotIn("usage", meta.get("dev", {}))

    def test_the_footer_no_longer_claims_nothing_was_written(self):
        _, text = self.card("--drill-card", self.event, "--file", "A question.")
        self.assertIn("the CARD is read-only", text)
        self.assertNotIn("wrote nothing", text)              # --file DID write; do not claim otherwise

    def test_filed_queries_are_registered_and_lint_clean(self):
        self.card("--drill-card", self.event, "--file", "Registered?")
        seed.seed(self.vault, self.dev_root, self.dev_root / "MASTER_COMMAND_LIST.txt", at=NOW, force=True)
        reg = self.vault / "wiki/concepts/queries_register.md"
        self.assertTrue(reg.is_file())
        self.assertIn("query_registered", reg.read_text(encoding="utf-8"))
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])



# --------------------------------------------------------------------------------------
# Round 112: slug digest (R111-1.D), registers hub (R111-1.C), the drill-card contract as one
# explicit test (D3), and dev.progress + lint L10 (R112-OOB.2)
# --------------------------------------------------------------------------------------

class SlugDigestTests(QueryCardTests):
    def test_questions_sharing_sixty_characters_file_to_different_pages(self):
        base = "What is the expected reaction of the fed-rates market when the "
        q1, q2 = base + "statement holds", base + "statement hikes"
        self.assertEqual(q1[:60], q2[:60])
        self.card("--drill-card", self.event, "--file", q1)
        self.card("--drill-card", self.event, "--file", q2)
        pages_ = sorted(p.name for p in (self.vault / "wiki/concepts").glob("query_*.md"))
        self.assertEqual(len(pages_), 2, pages_)
        for name in pages_:
            self.assertRegex(name, r"_[0-9a-f]{4}\.md$")        # a 4-hex digest suffix, always

    def test_the_same_question_still_files_to_the_same_page(self):
        """The digest is of the whole question, so re-filing keeps a written answer."""
        self.card("--drill-card", self.event, "--file", "Same question twice?")
        first = sorted(p.name for p in (self.vault / "wiki/concepts").glob("query_*.md"))
        self.card("--drill-card", self.event, "--file", "Same question twice?")
        self.assertEqual(sorted(p.name for p in (self.vault / "wiki/concepts").glob("query_*.md")), first)
        self.assertEqual(len(first), 1)


class DrillCardContractTests(QueryCardTests):
    """D3: the three properties the FOMC drill depends on, asserted together, with a realistic token."""

    REAL_TOKEN = "5615282760875985231868508008056959876238536896643315063916840237042205273721"

    def test_under_sixty_lines_whole_token_ids_and_zero_writes(self):
        rules = self.vault / "wiki/experiments/fomc_2026-09-16_rules.md"
        meta, body = fm.parse(rules.read_text(encoding="utf-8"))
        meta["dev"]["rules"][0]["market"] = self.REAL_TOKEN          # the shape the live drop has
        pages.write_page(pages.Page(rules, meta, body), self.vault, now=NOW)
        # C1 guards dev.rules against the raw JSON; keep them in step for this contract test
        raw = json.loads((self.exp_dir / "fomc_2026-09-16.rules.json").read_text(encoding="utf-8"))
        raw["rules"][0]["market"] = self.REAL_TOKEN
        (self.exp_dir / "fomc_2026-09-16.rules.json").write_text(json.dumps(raw), encoding="utf-8")
        before = {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.vault.rglob("*.md"))}
        code, text = self.card("--drill-card", "fomc-2026-09-16")
        self.assertEqual(code, EXIT_OK)
        lines = text.splitlines()
        self.assertLess(len(lines), 60, f"{len(lines)} lines")
        self.assertIn(self.REAL_TOKEN, text)                          # all 76 digits, no ellipsis
        self.assertNotIn(self.REAL_TOKEN[:12] + "\u2026", text)
        after = {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.vault.rglob("*.md"))}
        self.assertEqual(after, before)                                # zero files written


class ProgressAndL10Tests(IngestFixture):
    """Ruling R112-OOB.2: a pre-registration says on its own page how far it has got."""

    REG = {
        "experiment": "stall_v1", "registered_utc": None,
        "control": "data/experiments/nothing.json",
        "acceptance_bar": {"min_closed_trades": 50, "PASS": "win rate >= 54%"},
        "commitments": ["No mid-flight parameter changes before N=50."],
        "amendments": [],
    }

    def setUp(self):
        super().setUp()
        self.hl = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "experiments"
        self.hl.mkdir(parents=True, exist_ok=True)
        self.state = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "paper_trading_state.json"

    def _register(self, days_ago: int, closed: int | None = 0, parked: bool = False):
        reg = json.loads(json.dumps(self.REG))
        reg["registered_utc"] = pages.iso(NOW - timedelta(days=days_ago))
        if parked:
            reg["amendments"].append({"utc": pages.iso(NOW), "closed_trades_at_amendment": 0,
                                      "action": "parked", "why": "never flown"})
        (self.hl / "stall_v1.meta.json").write_text(json.dumps(reg), encoding="utf-8")
        if closed is not None:
            self.state.write_text(json.dumps({"closed_trades": closed}), encoding="utf-8")
        elif self.state.exists():
            self.state.unlink()
        ingest_exp.ingest_experiments([self.hl], self.vault, self.dev_root, at=NOW, force=True)
        return fm.parse((self.vault / "wiki/experiments/stall_v1_meta.md").read_text(encoding="utf-8"))

    def _l10(self):
        return [f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "L10"]

    def test_progress_is_measured_from_the_paper_state(self):
        meta, _ = self._register(days_ago=5, closed=7)
        p = meta["dev"]["progress"]
        self.assertEqual((p["accumulated"], p["target"], p["unit"], p["status"]), (7, 50, "closed_trades", "accumulating"))

    def test_a_stalled_registration_is_an_l10_warning(self):
        self._register(days_ago=5, closed=0)
        found = self._l10()
        self.assertEqual([(f.code, f.severity) for f in found], [("L10", "warning")])
        self.assertIn("0 recorded progress toward 50 closed_trades", found[0].message)

    def test_a_young_registration_at_zero_is_not_yet_a_warning(self):
        self._register(days_ago=1, closed=0)
        self.assertEqual(self._l10(), [])

    def test_progress_silences_the_warning(self):
        self._register(days_ago=5, closed=1)
        self.assertEqual(self._l10(), [])

    def test_parking_is_a_decision_and_silences_the_warning(self):
        meta, body = self._register(days_ago=5, closed=0, parked=True)
        self.assertEqual(meta["dev"]["progress"]["status"], "parked")
        self.assertIn("**PARKED", body)                          # the page SAYS so
        self.assertEqual(meta["status"], "draft")                # OKF status stays in vocabulary (L1)
        self.assertEqual(self._l10(), [])

    def test_an_unreadable_source_is_unmeasured_not_a_false_alarm(self):
        meta, _ = self._register(days_ago=5, closed=None)
        self.assertIsNone(meta["dev"]["progress"]["accumulated"])
        self.assertEqual(meta["dev"]["progress"]["status"], "unmeasured")
        self.assertEqual(self._l10(), [])

    def test_the_register_renders_progress_as_a_fraction(self):
        self._register(days_ago=5, closed=0, parked=True)
        reg = registers.update_register(self.vault, "Experiment", at=NOW).body
        self.assertIn("| 0/50 (0%) · parked |", reg)



# --------------------------------------------------------------------------------------
# Round 113: write_register cascades to the hub (Antigravity's b3c4493), `ready` is EVERY gate
# (Ruling R112-1.C corrected), lint L11, and the FOMC drill rehearsal (D4)
# --------------------------------------------------------------------------------------

class HubCascadeTests(IngestFixture):
    """A register write refreshes the hub row in the SAME call, so nothing is one pass behind."""

    REG = {"experiment": "cascade_probe", "registered_utc": None, "control": "data/experiments/nothing.json",
           "acceptance_bar": {"min_closed_trades": 5}, "commitments": [], "amendments": []}

    def _hub_row(self):
        hub = (self.vault / "wiki/concepts/registers_register.md").read_text(encoding="utf-8")
        return next(l for l in hub.splitlines() if "[[experiments_register\\|" in l)

    def _reg_at(self):
        meta, _ = fm.parse((self.vault / "wiki/concepts/experiments_register.md").read_text(encoding="utf-8"))
        return meta["generated"]["at"]

    def test_a_register_write_refreshes_the_hub_row_in_the_same_call(self):
        registers.write_register(self.vault, "Experiment", at=NOW)
        first = self._reg_at()
        self.assertIn(first, self._hub_row())
        # unchanged content: the register keeps its stamp (R104-3), so the hub row does not move either
        _, changed = registers.write_register(self.vault, "Experiment", at=NOW + timedelta(hours=1))
        self.assertFalse(changed)
        self.assertEqual(self._reg_at(), first)
        self.assertIn(first, self._hub_row())
        # a real change, written by an ADAPTER (not seed): the register moves and the hub follows at once
        later = NOW + timedelta(hours=2)
        hl = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "experiments"
        hl.mkdir(parents=True, exist_ok=True)
        reg = dict(self.REG, registered_utc=pages.iso(NOW))
        (hl / "cascade_probe.meta.json").write_text(json.dumps(reg), encoding="utf-8")
        ingest_exp.ingest_experiments([hl], self.vault, self.dev_root, at=later, force=True)
        self.assertEqual(self._reg_at(), pages.iso(later))
        self.assertIn(pages.iso(later), self._hub_row())
        self.assertNotIn(first, self._hub_row())


class ReadyAndL11Tests(IngestFixture):
    """Ruling R112-1.C, corrected: `ready` means EVERY sample gate passes, dated from first observation."""

    REG = {"experiment": "fade_v2", "registered_utc": None, "status": "PASSIVE - accumulates, does not trade",
           "sample_requirements": {"window_days": 7, "min_events": 500, "min_coins": 20, "max_single_coin_share": 0.2}}

    def setUp(self):
        super().setUp()
        self.hl = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "experiments"
        self.hl.mkdir(parents=True, exist_ok=True)
        self.db = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"

    def _seed_db(self, rows):
        import sqlite3
        if self.db.exists():
            self.db.unlink()
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE cascade_excursions (event_id INTEGER, coin TEXT, timestamp_utc INTEGER, source TEXT)")
        c.executemany("INSERT INTO cascade_excursions VALUES (?,?,?,?)",
                      [(i + 1, coin, ts, "live") for i, (coin, ts) in enumerate(rows)])
        c.execute("INSERT INTO cascade_excursions VALUES (0, 'CTRL', 0, 'control:x')")     # excluded by the WHERE
        c.commit()
        c.close()

    def _rows(self, n=600, coins=30, span_days=8):
        start = int((NOW - timedelta(days=span_days)).timestamp() * 1000)
        step = span_days * 86_400_000 // n
        return [(f"C{i % coins}", start + i * step) for i in range(n)]

    def _register(self, at, days_registered=6):
        reg = json.loads(json.dumps(self.REG))
        reg["registered_utc"] = pages.iso(NOW - timedelta(days=days_registered))
        (self.hl / "fade_v2.meta.json").write_text(json.dumps(reg), encoding="utf-8")
        ingest_exp.ingest_experiments([self.hl], self.vault, self.dev_root, at=at, force=True)
        return fm.parse((self.vault / "wiki/experiments/fade_v2_meta.md").read_text(encoding="utf-8"))

    def _l11(self, now):
        return [f for f in lint.lint_vault(self.vault, self.dev_root, now=now) if f.code == "L11"]

    def test_every_gate_passing_is_ready_and_the_page_and_register_say_so(self):
        self._seed_db(self._rows())
        meta, body = self._register(at=NOW)
        p = meta["dev"]["progress"]
        self.assertEqual((p["accumulated"], p["target"], p["unit"], p["status"]), (600, 500, "events", "ready"))
        self.assertEqual(p["ready_since"], pages.iso(NOW))
        self.assertEqual({k: g["pass"] for k, g in p["gates"].items()},
                         {"min_events": True, "min_coins": True, "max_single_coin_share": True, "window_days": True})
        self.assertIn("**READY (since", body)
        self.assertIn("| 600/500 (100%) · ready |", registers.update_register(self.vault, "Experiment", at=NOW).body)

    def test_a_count_past_its_floor_with_one_coin_dominating_is_not_ready(self):
        rows = [("WHALE" if i < 200 else c, ts) for i, (c, ts) in enumerate(self._rows())]      # one coin at 33%
        self._seed_db(rows)
        meta, body = self._register(at=NOW)
        p = meta["dev"]["progress"]
        self.assertEqual(p["status"], "accumulating")
        self.assertTrue(p["gates"]["min_events"]["pass"])              # the count ALONE would have said ready
        self.assertFalse(p["gates"]["max_single_coin_share"]["pass"])
        self.assertAlmostEqual(p["gates"]["max_single_coin_share"]["value"], 200 / 600, places=3)
        self.assertNotIn("ready_since", p)
        self.assertNotIn("**READY", body)
        self.assertEqual(self._l11(NOW + timedelta(days=30)), [])

    def test_ready_since_is_first_observed_and_carried_over(self):
        self._seed_db(self._rows())
        self._register(at=NOW)
        meta, _ = self._register(at=NOW + timedelta(days=2))
        self.assertEqual(meta["dev"]["progress"]["ready_since"], pages.iso(NOW))

    def test_l11_fires_after_three_days_ready_and_a_verdict_silences_it(self):
        self._seed_db(self._rows())
        self._register(at=NOW)
        self.assertEqual(self._l11(NOW + timedelta(days=lint.STALL_DAYS - 1)), [])
        found = self._l11(NOW + timedelta(days=lint.STALL_DAYS))
        self.assertEqual([(f.code, f.severity) for f in found], [("L11", "warning")])
        self.assertIn("every gate passing", found[0].message)
        self.assertIn("600 >= 500 events", found[0].message)
        verdict = self.vault / "wiki/experiments/fade_v2_verdict.md"
        pages.write_page(pages.Page(verdict, pages.make_meta("Experiment", "fade_v2 verdict", "a verdict",
                                                             tags=["experiment"], generated_by="human:test", at=NOW,
                                                             status="draft"), "# verdict"), self.vault, now=NOW)
        meta, _ = self._register(at=NOW + timedelta(days=lint.STALL_DAYS))
        self.assertEqual(meta["dev"]["progress"]["status"], "evaluated")
        self.assertEqual(self._l11(NOW + timedelta(days=lint.STALL_DAYS)), [])

    def test_an_unreadable_source_is_unmeasured_and_carries_no_gates(self):
        if self.db.exists():
            self.db.unlink()
        meta, _ = self._register(at=NOW)
        p = meta["dev"]["progress"]
        self.assertEqual((p["accumulated"], p["status"]), (None, "unmeasured"))
        self.assertNotIn("gates", p)
        self.assertEqual(self._l11(NOW + timedelta(days=30)), [])


class FomcRehearsalTests(QueryCardTests):
    """D4: the pre-flight, with its ONE external tool (Task Scheduler) injected. Never touches the scheduler."""

    RECORDER = 'parser.add_argument("--record-loop", action="store_true")'

    def setUp(self):
        super().setUp()
        from knowledge.drills import fomc_rehearsal as rehearsal
        self.rh = rehearsal
        self.ev = query_mod.find_event(self.vault, self.event)
        self.release = fm.parse_iso8601(self.ev.meta["dev"]["release_utc"])
        self.tokens = [str(r["market"]) for r in query_mod.rules_for(self.vault, self.ev).meta["dev"]["rules"]]
        self.now = self.release - timedelta(days=3)
        self.bat_path = self.dev_root / rehearsal.BAT

    def task(self, **over):
        fire = (self.release - self.rh.LEAD).astimezone()
        t = {"exists": True, "state": "Ready", "enabled": True,
             "triggers": [fire.replace(tzinfo=None).isoformat()], "actions": [f'"{self.bat_path}"'],
             "disallow_start_on_batteries": False, "stop_if_going_on_batteries": False, "wake_to_run": False,
             "logon_type": "Interactive", "next_run": fire.strftime("%m/%d/%Y %H:%M:%S"),
             "last_result": self.rh.NEVER_RAN, "battery_status": 2, "battery_pct": 100, "free_gb": 50.0,
             "multiple_instances": "IgnoreNew", "recorder_pids": [], "time_service": "Running",
             "clock_offset_s": 0.05}
        t.update(over)
        return t

    def bat(self, tokens=None, dur=420):
        import sys
        books = query_mod.books_dir(self.ev).replace("/", "\\")
        return ("@echo off\r\nset DUR=%1\r\nif \"%DUR%\"==\"\" set DUR=" + str(dur)
                + "\r\nset BOOKS=%2\r\nif \"%BOOKS%\"==\"\" set BOOKS=" + books + "\r\n"
                + sys.executable + " -m cross_market.latency_sniper --record-loop --tokens "
                + ",".join(tokens or self.tokens) + " --interval 1 --duration %DUR% --books %BOOKS%\r\n")

    def checks(self, **kw):
        args = dict(task=self.task(), bat_text=self.bat(), recorder_text=self.RECORDER, bat_path=self.bat_path,
                    bat_tracked=True, writable=(True, "probe ok"))
        args.update(kw)
        return self.rh.run_checks(self.vault, self.dev_root, self.event, self.now, **args)

    @staticmethod
    def levels(checks):
        return {c.name: c.level for c in checks}

    def test_a_consistent_setup_has_no_failures(self):
        lv = self.levels(self.checks())
        self.assertEqual([n for n, l in lv.items() if l == "FAIL"], [], lv)
        for name in ("window is T-2..T+5", "rules.json tokens == page tokens", "rules.json release == event release",
                     "card wrote nothing", "card carries whole token ids", "batch tokens == registered tokens",
                     "batch default duration == window length", "batch books dir == event books_dir",
                     "task fires at T-2 local time", "task action is the drill batch", "recorder has --record-loop",
                     "batch tracked in git", "books dir writable", "stamp paths fit under MAX_PATH",
                     "task ignores a second launch", "no recorder already running", "Windows Time service",
                     "clock offset vs NTP"):
            self.assertEqual(lv[name], "PASS", name)
        self.assertEqual(lv["logon type"], "WARN")            # interactive-only is always worth a line

    def test_an_untracked_batch_is_a_failure_and_git_silence_is_a_warning(self):
        """Ruling R113-1.F: the entry point the scheduler runs must be under version control."""
        self.assertEqual(self.levels(self.checks(bat_tracked=False))["batch tracked in git"], "FAIL")
        self.assertEqual(self.levels(self.checks(bat_tracked=True))["batch tracked in git"], "PASS")
        # the fixture dev_root is not a git repository: git answers "not tracked", never silence
        self.assertFalse(self.rh.git_tracked(self.bat_path, self.dev_root))

    def test_the_machine_checks_warn_and_never_fail_closed_on_their_own(self):
        lv = self.levels(self.checks(task=self.task(time_service="Stopped", clock_offset_s=2.5,
                                                    recorder_pids=[4242], multiple_instances="Parallel")))
        self.assertEqual(lv["Windows Time service"], "WARN")
        self.assertEqual(lv["clock offset vs NTP"], "WARN")
        self.assertEqual(lv["no recorder already running"], "WARN")
        self.assertEqual(lv["task ignores a second launch"], "WARN")
        self.assertEqual([n for n, l in lv.items() if l == "FAIL"], [])

    def test_an_unmeasured_clock_is_reported_not_assumed(self):
        lv = self.levels(self.checks(task=self.task(clock_offset_s=None)))
        self.assertEqual(lv["clock offset vs NTP"], "WARN")

    def test_an_unwritable_books_dir_is_a_failure(self):
        lv = self.levels(self.checks(writable=(False, "denied")))
        self.assertEqual(lv["books dir writable"], "FAIL")

    def test_the_real_probe_writes_and_removes_one_file_outside_the_vault(self):
        target = self.dev_root / "cross_market" / "data" / "clob_books" / "fomc_2026-09-16"
        (self.dev_root / "cross_market" / "data").mkdir(parents=True, exist_ok=True)
        before_vault = self.rh.hash_vault(self.vault)
        ok, detail = self.rh.probe_writable(target)
        self.assertTrue(ok, detail)
        self.assertIn("nearest existing ancestor", detail)          # the books dir itself does not exist yet
        self.assertEqual(sorted(p.name for p in (self.dev_root / "cross_market" / "data").iterdir()), [])
        self.assertEqual(self.rh.hash_vault(self.vault), before_vault)

    def test_online_token_resolution_uses_the_recorders_fetch(self):
        """Round 117: --online proves the tokens resolve through the recorder's own fetch; offline by default."""
        seen = []

        def good(t):
            seen.append(t)
            return {"asset_id": t, "bids": [{"price": "0.4", "size": "1"}], "asks": []}
        lv = self.levels(self.checks(online=good))
        self.assertEqual(lv["tokens resolve on the CLOB (--online)"], "PASS")
        self.assertEqual(seen, self.tokens)

        def forbidden(t):
            raise OSError("HTTP Error 403: Forbidden")
        self.assertEqual(self.levels(self.checks(online=forbidden))["tokens resolve on the CLOB (--online)"], "FAIL")

        def wrong(t):
            return {"asset_id": "999", "bids": [{"price": "0.4", "size": "1"}], "asks": []}
        self.assertEqual(self.levels(self.checks(online=wrong))["tokens resolve on the CLOB (--online)"], "FAIL")
        self.assertNotIn("tokens resolve on the CLOB (--online)", self.levels(self.checks()))

    def test_a_trigger_one_minute_off_is_a_failure(self):
        off = (self.release - timedelta(minutes=1)).astimezone().replace(tzinfo=None).isoformat()
        self.assertEqual(self.levels(self.checks(task=self.task(triggers=[off])))["task fires at T-2 local time"], "FAIL")

    def test_battery_flags_are_a_warning_not_a_failure(self):
        lv = self.levels(self.checks(task=self.task(disallow_start_on_batteries=True, stop_if_going_on_batteries=True)))
        self.assertEqual(lv["battery flags"], "WARN")
        self.assertEqual([n for n, l in lv.items() if l == "FAIL"], [])

    def test_a_token_that_drifted_in_the_batch_is_a_failure(self):
        lv = self.levels(self.checks(bat_text=self.bat(tokens=self.tokens[:-1] + ["1" * 76])))
        self.assertEqual(lv["batch tokens == registered tokens"], "FAIL")

    def test_a_shorter_recording_than_the_window_is_a_failure(self):
        self.assertEqual(self.levels(self.checks(bat_text=self.bat(dur=300)))["batch default duration == window length"], "FAIL")

    def test_a_missing_batch_and_a_missing_task_fail_closed(self):
        lv = self.levels(self.checks(bat_text=None, task={"exists": False, "error": "no such task"}))
        self.assertEqual((lv["drill batch file"], lv["scheduled task"]), ("FAIL", "FAIL"))

    def test_the_cli_is_read_only_and_exits_nonzero_on_a_fresh_clone(self):
        """The batch is git-ignored, so this fixture IS a fresh clone: the drill file is missing."""
        before = self.rh.hash_vault(self.vault)
        out = io.StringIO()
        code = self.rh.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--event", self.event,
                             "--now", pages.iso(self.now), "--no-task"], out=out)
        self.assertEqual(code, self.rh.EXIT_FINDINGS)
        self.assertIn("fresh clone has NO drill", out.getvalue())
        self.assertIn("[WARN] scheduled task: not queried", out.getvalue())
        self.assertEqual(self.rh.hash_vault(self.vault), before)



# --------------------------------------------------------------------------------------
# Round 114: the passive-fade rebenchmark verdict (R113-1.C option 3), graded independently; the
# progress mirror learns the registered POPULATION, the max_hhi gate, and that INSUFFICIENT is not
# terminal
# --------------------------------------------------------------------------------------

class FadeRebenchmarkIngestTests(IngestFixture):
    REG = {"experiment": "passive_fade_rebenchmark", "registered_utc": "2026-09-01T05:42:16Z",
           "status": "PASSIVE - sweeps accumulate",
           "sample_requirements": {"window_days": 7, "min_events": 500, "min_coins": 20, "max_single_coin_share": 0.2},
           "population": {"source": "trade_sweep", "recorded_utc": "2026-09-06T19:20:00Z"},
           "reopening_bar": {"rule": "P(ratio >= 1.25) > 0.90 under a CLUSTER bootstrap resampling coins",
                             "rationale": "Deliberately asymmetric."}}

    def setUp(self):
        super().setUp()
        from knowledge.ingest import fade_rebenchmark as ingest_fade
        self.fade = ingest_fade
        self.exp = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "experiments"
        self.exp.mkdir(parents=True, exist_ok=True)
        self.registration = self.exp / "passive_fade_rebenchmark.meta.json"
        self.registration.write_text(json.dumps(self.REG), encoding="utf-8")
        self.result = self.exp / "passive_fade_rebenchmark.verdict.json"
        self.db = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"

    def art(self, *, verdict="INSUFFICIENT", events=13645, coins=46, share=0.2678, span=5.49, p=0.0, ratio=0.79,
            source="trade_sweep", written="2026-09-06T19:30:00Z", rows=38016):
        h = {"signal": {"n": events - 92, "ratio": ratio}, "control": {"n": 3 * events, "ratio": 0.95},
             "edge_vs_control": ratio - 0.95, "coins_measured": coins, "hhi": 0.12, "top_coin_share": share,
             "top_coin": "ZEC", "cluster_p_ge_1": 0.01, "cluster_p_ge_reopen": p}
        return {"_artifact": {"written_at": written, "writer": "HyperLiquid.HL_Monarch.analytics.fade_rebenchmark",
                              "rows_in_table": rows, "seed": 7, "resamples": 20000},
                "experiment": "passive_fade_rebenchmark", "source": source, "verdict": verdict, "verdict_reasons": ["x"],
                "decision_horizon_minutes": 30.0, "registered_horizons_minutes": [5.0, 15.0, 30.0],
                "reopening_bar": {"ratio": 1.25, "confidence": 0.9, "min_events": 500, "min_coins": 20,
                                  "max_single_coin_share": 0.2, "window_days": 7.0},
                "primary_metric": {"name": "ratio_30m", "value": ratio, "n": events - 92, "cluster_p_ge_1_25": p,
                                   "cluster_p_ge_1": 0.01, "control_ratio": 0.95, "edge_vs_control": ratio - 0.95},
                "sample_gates": {"engine": {"status": "x", "eligible": share <= 0.2},
                                 "metrics": {"events": events, "coins": coins, "top_coin_share": share, "top_coin": "ZEC",
                                             "hhi": 0.12, "span_days": span, "window_days_required": 7.0,
                                             "window_covered": span >= 7}},
                "horizons": {k: dict(h, registered=(k != "60m")) for k in ("5m", "15m", "30m", "60m")},
                "data_audit": {"total_in_table": rows, "treatment_rows": events, "control_rows": events,
                               "first_event_utc": "2026-09-01T05:00:00Z", "last_event_utc": "2026-09-06T17:00:00Z",
                               "measurable_at_decision_horizon": events - 92}}

    def ingest(self, art, at=NOW):
        self.result.write_text(json.dumps(art), encoding="utf-8")
        return self.fade.ingest_rebenchmark(self.vault, self.dev_root, at=at)

    def page(self):
        return fm.parse((self.vault / "wiki/experiments/passive_fade_rebenchmark_verdict.md").read_text(encoding="utf-8"))

    def test_the_real_shape_is_insufficient_and_says_which_gates_block(self):
        self.ingest(self.art())
        meta, body = self.page()
        d = meta["dev"]
        self.assertEqual((d["grade"], d["engine_verdict"], d["grades_agree"]), ("INSUFFICIENT", "INSUFFICIENT", True))
        self.assertEqual(len(d["gate_failures"]), 2)
        self.assertTrue(any(f.startswith("top_coin_share=") for f in d["gate_failures"]))
        self.assertTrue(any(f.startswith("span_days=") for f in d["gate_failures"]))
        self.assertIn("no verdict is issued", body)
        self.assertIn("it is not a verdict", body)
        self.assertEqual(d["bar"], {"ratio": 1.25, "confidence": 0.9})     # parsed from the registration's text
        self.assertEqual(d["measurement"]["source"], "trade_sweep")
        reg = registers.update_register(self.vault, "Experiment", at=NOW).body
        self.assertIn("[[passive_fade_rebenchmark_verdict\\|", reg)

    def test_pass_and_fail_follow_the_bar_only_when_every_gate_passes(self):
        self.ingest(self.art(verdict="PASS", share=0.15, span=7.5, p=0.95, ratio=1.4))
        self.assertEqual(self.page()[0]["dev"]["grade"], "PASS")
        self.ingest(self.art(verdict="FAIL", share=0.15, span=7.5, p=0.30, ratio=1.1, written="2026-09-07T00:00:00Z"))
        meta, body = self.page()
        self.assertEqual(meta["dev"]["grade"], "FAIL")
        self.assertIn("stays retired", body)

    def test_a_disagreement_with_the_engine_is_a_finding(self):
        self.ingest(self.art(verdict="PASS", share=0.30, span=7.5, p=0.95))     # engine claims PASS on a narrow sample
        meta, body = self.page()
        self.assertEqual((meta["dev"]["grade"], meta["dev"]["grades_agree"]), ("INSUFFICIENT", False))
        self.assertIn("THEY DISAGREE", body)

    def test_the_wrong_population_is_insufficient_whatever_the_numbers_say(self):
        self.ingest(self.art(verdict="PASS", source="trade_flow", share=0.15, span=7.5, p=0.99))
        meta, body = self.page()
        self.assertEqual(meta["dev"]["grade"], "INSUFFICIENT")
        self.assertTrue(any(f.startswith("population:") for f in meta["dev"]["gate_failures"]))
        self.assertIn("NOT the registered population", body)

    def test_the_artifact_is_the_unit_of_observation(self):
        self.ingest(self.art())
        first = (self.vault / "wiki/experiments/passive_fade_rebenchmark_verdict.md").read_bytes()
        self.ingest(self.art(), at=NOW + timedelta(hours=1))          # same artifact, later run: nothing moves
        self.assertEqual((self.vault / "wiki/experiments/passive_fade_rebenchmark_verdict.md").read_bytes(), first)
        self.assertEqual(len(self.page()[0]["dev"]["history"]), 1)
        self.ingest(self.art(events=14000, rows=39000, written="2026-09-07T00:00:00Z"), at=NOW + timedelta(days=1))
        self.assertEqual(len(self.page()[0]["dev"]["history"]), 2)

    def test_the_cli_refuses_without_an_artifact_and_writes_with_one(self):
        out = io.StringIO()
        code = self.fade.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out)
        self.assertEqual(code, 3)
        self.assertIn("analytics.fade_rebenchmark", out.getvalue())
        self.result.write_text(json.dumps(self.art()), encoding="utf-8")
        out = io.StringIO()
        code = self.fade.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--at", pages.iso(NOW)], out=out)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("grade INSUFFICIENT", out.getvalue())

    def test_the_artifact_beside_the_registration_is_not_compiled_as_a_registration(self):
        """Round 114: the experiments ingest and this adapter were both writing _verdict.md - a double writer."""
        self.result.write_text(json.dumps(self.art()), encoding="utf-8")
        report = ingest_exp.ingest_experiments([self.exp], self.vault, self.dev_root, at=NOW, force=True)
        self.assertIn("passive_fade_rebenchmark.verdict.json", report.ignored)
        self.assertFalse((self.vault / "wiki/experiments/passive_fade_rebenchmark_verdict.md").exists())
        self.ingest(self.art())
        meta, _ = self.page()
        self.assertEqual(meta["dev"]["kind"], "rebenchmark_verdict")
        ingest_exp.ingest_experiments([self.exp], self.vault, self.dev_root, at=NOW + timedelta(hours=1), force=True)
        self.assertEqual(self.page()[0]["dev"]["kind"], "rebenchmark_verdict")     # still ours

    # --- the registration page's progress after a verdict exists ---

    def _progress(self):
        ingest_exp.ingest_experiments([self.exp], self.vault, self.dev_root, at=NOW, force=True)
        meta, body = fm.parse((self.vault / "wiki/experiments/passive_fade_rebenchmark_meta.md").read_text(encoding="utf-8"))
        return meta["dev"]["progress"], body

    def test_an_insufficient_verdict_does_not_close_the_question(self):
        self.ingest(self.art())
        p, body = self._progress()
        self.assertNotEqual(p["status"], "evaluated")
        self.assertEqual(p["last_verdict"]["grade"], "INSUFFICIENT")
        self.assertEqual(p["last_verdict"]["page"], "passive_fade_rebenchmark_verdict")

    def test_a_pass_or_fail_verdict_closes_it(self):
        self.ingest(self.art(verdict="FAIL", share=0.15, span=7.5, p=0.3))
        p, _ = self._progress()
        self.assertEqual(p["status"], "evaluated")

    # --- the mirror measures the REGISTERED population ---

    def _seed_db(self, rows):
        import sqlite3
        if self.db.exists():
            self.db.unlink()
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE cascade_excursions (event_id INTEGER, coin TEXT, timestamp_utc INTEGER, source TEXT)")
        c.executemany("INSERT INTO cascade_excursions VALUES (?,?,?,?)",
                      [(i + 1, coin, ts, src) for i, (coin, ts, src) in enumerate(rows)])
        c.commit()
        c.close()

    def test_gates_are_measured_over_the_registered_population_not_the_table(self):
        start = int((NOW - timedelta(days=8)).timestamp() * 1000)
        step = 8 * 86_400_000 // 600
        sweep = [("WHALE" if i < 200 else f"S{i % 30}", start + i * step, "trade_sweep") for i in range(600)]   # one coin at 33%
        flow = [(f"F{i % 40}", start + i * step, "trade_flow") for i in range(600)]                             # broad
        self._seed_db(sweep + flow)
        p, body = self._progress()
        self.assertEqual(p["population"], "trade_sweep")
        self.assertEqual(p["accumulated"], 600)                       # not 1,200
        self.assertFalse(p["gates"]["max_single_coin_share"]["pass"])
        self.assertEqual(p["status"], "accumulating")
        self.assertIn("**ACCUMULATING**", body)
        self.assertIn("population `trade_sweep`", body)
        # drop the population block: the mirror pools every treatment row, and the pooled sample passes
        reg = dict(self.REG)
        reg.pop("population")
        self.registration.write_text(json.dumps(reg), encoding="utf-8")
        p, _ = self._progress()
        self.assertEqual((p["population"], p["accumulated"], p["status"]), ("pooled", 1200, "ready"))
        # Round 115: a registration may SAY it pools (the cascade-replay engine does by construction)
        reg["population"] = {"source": "pooled", "recorded_utc": "2026-09-06T22:40:00Z"}
        self.registration.write_text(json.dumps(reg), encoding="utf-8")
        p, _ = self._progress()
        self.assertEqual((p["population"], p["accumulated"]), ("pooled", 1200))

    def test_the_forward_series_requirement_narrows_the_counted_population(self):
        """Round 115: min_samples_60m_per_event is part of the registered population, as in the engine."""
        import sqlite3
        if self.db.exists():
            self.db.unlink()
        start = int((NOW - timedelta(days=8)).timestamp() * 1000)
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE cascade_excursions (event_id INTEGER, coin TEXT, timestamp_utc INTEGER, source TEXT, samples_60m INTEGER)")
        c.executemany("INSERT INTO cascade_excursions VALUES (?,?,?,?,?)",
                      [(i + 1, f"S{i % 30}", start + i * 1_000_000, "trade_sweep", 0 if i < 100 else 5) for i in range(600)])
        c.commit()
        c.close()
        reg = json.loads(json.dumps(self.REG))
        reg["sample_requirements"]["min_samples_60m_per_event"] = 1
        self.registration.write_text(json.dumps(reg), encoding="utf-8")
        p, _ = self._progress()
        self.assertEqual(p["accumulated"], 500)          # the 100 truncated events do not count

    def test_max_hhi_is_a_gate_when_the_registration_names_one(self):
        start = int((NOW - timedelta(days=8)).timestamp() * 1000)
        rows = [("WHALE" if i < 100 else f"S{i % 30}", start + i * 1_000_000, "trade_sweep") for i in range(600)]
        self._seed_db(rows)
        reg = json.loads(json.dumps(self.REG))
        reg["sample_requirements"]["max_hhi"] = 0.02
        self.registration.write_text(json.dumps(reg), encoding="utf-8")
        p, _ = self._progress()
        self.assertIn("max_hhi", p["gates"])
        self.assertFalse(p["gates"]["max_hhi"]["pass"])           # WHALE alone contributes (100/600)^2 = 0.0278



# --------------------------------------------------------------------------------------
# Round 116 (self-directed): the live dress rehearsal, run offline through injected fetch/clock/wall
# --------------------------------------------------------------------------------------

class FomcLiveRehearsalTests(QueryCardTests):
    class FakeClock:
        def __init__(self, base):
            self.t, self.base = 0.0, base

        def clock(self):
            return self.t

        def sleep(self, s):
            self.t += max(0.0, s)

        def wall(self):
            return self.base + timedelta(seconds=self.t)

    def setUp(self):
        super().setUp()
        from knowledge.drills import fomc_live_rehearsal as live
        self.live = live
        self.calls = 0
        self.scratch = self.dev_root / "scratch"
        self.fc = self.FakeClock(datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc))
        # the live drop's tokens are 76-digit decimals; the fixture's TOK_* names would not survive the stamp
        # filename regex (no underscores in a token), which is exactly what the rehearsal now checks
        rules_page = self.vault / "wiki/experiments/fomc_2026-09-16_rules.md"
        meta, body = fm.parse(rules_page.read_text(encoding="utf-8"))
        raw_path = self.exp_dir / "fomc_2026-09-16.rules.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        for i, (pr, rr) in enumerate(zip(meta["dev"]["rules"], raw["rules"])):
            pr["market"] = rr["market"] = str(5615282760875985231868508008056959876238536896643315063916840237042205273720 + i)
        pages.write_page(pages.Page(rules_page, meta, body), self.vault, now=NOW)
        raw_path.write_text(json.dumps(raw), encoding="utf-8")

    def fetch(self, token):
        self.calls += 1
        k = self.calls
        return {"hash": f"h{k}", "neg_risk": False,
                "bids": [{"price": "0.44", "size": str(100 + k)}, {"price": "0.43", "size": "300"}],
                "asks": [{"price": "0.46", "size": str(100 + k)}, {"price": "0.47", "size": "300"}]}

    def run_live(self, **kw):
        args = dict(seconds=10, interval=1.0, scratch=self.scratch, fetch=self.fetch, clock=self.fc.clock,
                    sleep=self.fc.sleep, wall=self.fc.wall, checks=[], assume_defaults=True, now=NOW)
        args.update(kw)
        return self.live.run_live(self.vault, self.dev_root, self.event, **args)

    @staticmethod
    def levels(checks):
        return {c.name: c.level for c in checks}

    def test_the_whole_post_print_path_runs_into_scratch_and_nothing_real_moves(self):
        before = self.live.hash_vault(self.vault)
        checks, summary = self.run_live()
        lv = self.levels(checks)
        self.assertEqual([c.name + ": " + c.detail for c in checks if c.level == "FAIL"], [])
        n_rules = len(query_mod.rules_for(self.vault, query_mod.find_event(self.vault, self.event)).meta["dev"]["rules"])
        self.assertEqual(summary["stats"]["stamps"], 10 * n_rules)          # ten polls, every token, every poll
        self.assertEqual(summary["markets"], n_rules)
        self.assertTrue((self.scratch / "event.json").exists())
        self.assertIn("NOT a Federal Reserve statement", json.loads((self.scratch / "event.json").read_text(encoding="utf-8"))["source"])
        self.assertTrue((self.scratch / "curve.json").exists())
        self.assertEqual(len(summary["profiles"]), n_rules)
        self.assertTrue(any((self.scratch / "vault" / "wiki" / "profiles").glob("*.md")))
        self.assertEqual(lv["rehearsal pages lint without errors"], "PASS")
        self.assertEqual(self.live.hash_vault(self.vault), before)           # the REAL vault
        self.assertFalse((self.dev_root / "event.json").exists())          # the drill card's file was not written
        self.assertFalse(any((self.vault / "wiki" / "profiles").glob("*.md")) if (self.vault / "wiki" / "profiles").exists() else False)

    def test_a_failing_pre_flight_records_nothing(self):
        checks, summary = self.run_live(checks=[self.live.Check("batch tokens == registered tokens", "FAIL", "drifted")])
        self.assertEqual(self.levels(checks)["pre-flight"], "FAIL")
        self.assertIsNone(summary["stats"])
        self.assertEqual(self.calls, 0)
        self.assertFalse((self.scratch / "books").exists())

    def test_the_halt_flag_stops_it_before_the_first_fetch(self):
        (self.dev_root / "HALT.flag").write_text("stop", encoding="utf-8")
        checks, summary = self.run_live()
        self.assertEqual(self.levels(checks)["HALT flag"], "FAIL")
        self.assertEqual(self.calls, 0)

    def test_a_flaky_fetch_is_a_warning_and_a_dead_one_is_a_failure(self):
        attempts = {"n": 0}

        def flaky(token):
            attempts["n"] += 1
            if attempts["n"] % 5 == 0:                     # one fetch in five fails: 80% yield, the floor
                raise OSError("timeout")
            return self.fetch(token)
        lv = self.levels(self.run_live(fetch=flaky)[0])
        self.assertEqual(lv["fetch failures"], "WARN")
        self.assertEqual(lv["stamp yield"], "PASS")                         # 80% of polls still stamped
        def dead(token):
            raise OSError("403")
        self.calls = 0
        lv = self.levels(self.run_live(fetch=dead, scratch=self.dev_root / "scratch2")[0])
        self.assertEqual(lv["stamp yield"], "FAIL")
        self.assertEqual(lv["every token stamped"], "FAIL")

    def test_the_cli_is_read_only_on_the_real_vault(self):
        """--no-task in a fixture with no batch file: the pre-flight FAILS and the CLI refuses to record."""
        before = self.live.hash_vault(self.vault)
        out = io.StringIO()
        code = self.live.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--event", self.event,
                               "--seconds", "1", "--no-task", "--assume-defaults", "--scratch", str(self.scratch)], out=out)
        self.assertEqual(code, self.live.EXIT_FINDINGS)
        self.assertIn("[FAIL] pre-flight", out.getvalue())
        self.assertEqual(self.live.hash_vault(self.vault), before)



# --------------------------------------------------------------------------------------
# Round 118: token shape at registration (compile + lint C6), scratch pruning
# --------------------------------------------------------------------------------------

class TokenShapeTests(QueryCardTests):
    RULES_PAGE = "wiki/experiments/fomc_2026-09-16_rules.md"

    def test_a_non_digit_market_id_compiles_with_a_c6_error_not_a_refusal(self):
        raw_path = self.exp_dir / "fomc_2026-09-16.rules.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        raw["rules"][0]["market"] = "TOK_BAD"
        raw_path.write_text(json.dumps(raw), encoding="utf-8")
        report = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW, force=True)
        self.assertNotIn("fomc_2026-09-16.rules.json", report.ignored)          # compiled, not refused
        meta, _ = fm.parse((self.vault / self.RULES_PAGE).read_text(encoding="utf-8"))
        self.assertEqual(meta["dev"]["invalid_tokens"], ["TOK_BAD"])
        c6 = [f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "C6"]
        self.assertEqual([(f.severity, f.path) for f in c6], [("error", self.RULES_PAGE)])
        self.assertIn("TOK_BAD", c6[0].message)

    def test_digit_ids_carry_no_invalid_tokens_and_no_c6(self):
        meta, _ = fm.parse((self.vault / self.RULES_PAGE).read_text(encoding="utf-8"))
        self.assertNotIn("invalid_tokens", meta["dev"])
        self.assertTrue(all(t.isdigit() for t in meta["dev"]["tokens"]))       # the fixture is realistic now
        self.assertEqual([f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "C6"], [])


class ScratchPruningTests(QueryCardTests):
    def test_prune_keeps_the_newest_three_stamped_dirs_only(self):
        from knowledge.drills import fomc_live_rehearsal as live
        root = self.dev_root / live.SCRATCH_ROOT
        for s in ("20260901T000000Z", "20260902T000000Z", "20260903T000000Z", "20260904T000000Z",
                  "probe_20260905T000000Z", "notes"):
            (root / s).mkdir(parents=True)
            (root / s / "x.txt").write_text("x", encoding="utf-8")
        self.assertEqual(live.prune_scratch(root, keep=3), ["20260901T000000Z"])
        self.assertEqual(sorted(p.name for p in root.iterdir()),
                         ["20260902T000000Z", "20260903T000000Z", "20260904T000000Z", "notes", "probe_20260905T000000Z"])
        self.assertEqual(live.prune_scratch(root, keep=3), [])                  # idempotent
        self.assertEqual(live.prune_scratch(self.dev_root / "nowhere", keep=3), [])



# --------------------------------------------------------------------------------------
# Round 121: event.json writer, data gaps + L12, daemon streams in the pre-flight, regime dedupe
# --------------------------------------------------------------------------------------

class EventJsonTests(unittest.TestCase):
    def setUp(self):
        from knowledge.drills import event_json as ej
        self.ej = ej
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "event.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_number_in_a_complete_event_out(self):
        ev = self.ej.build_event(25, observed_at=NOW)
        self.assertEqual(ev, {"kind": "fed_rate", "payload": {"change_bps": 25}, "source": "federalreserve.gov statement",
                              "confidence": 0.995, "observed_at": pages.iso(NOW)})
        self.assertTrue(self.ej.write_event(self.path, ev))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), ev)

    def test_it_refuses_to_overwrite_without_force(self):
        self.ej.write_event(self.path, self.ej.build_event(0, observed_at=NOW))
        self.assertFalse(self.ej.write_event(self.path, self.ej.build_event(25, observed_at=NOW)))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["payload"]["change_bps"], 0)
        self.assertTrue(self.ej.write_event(self.path, self.ej.build_event(25, observed_at=NOW), force=True))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["payload"]["change_bps"], 25)

    def test_the_cli_writes_prints_and_refuses(self):
        out = io.StringIO()
        code = self.ej.main(["--bps", "-25", "--out", str(self.path), "--observed-at", pages.iso(NOW)], out=out)
        self.assertEqual(code, EXIT_OK)
        self.assertIn('"change_bps": -25', out.getvalue())
        out = io.StringIO()
        self.assertEqual(self.ej.main(["--bps", "0", "--out", str(self.path)], out=out), self.ej.EXIT_FINDINGS)
        self.assertIn("[REFUSE]", out.getvalue())


class DataGapTests(FadeRebenchmarkIngestTests):
    GAP = {"gaps": [{"id": "test_gap", "desk": 1, "start_utc": "2026-09-03T00:00:00Z", "end_utc": "2026-09-03T09:00:00Z",
                     "tables": ["asset_snapshots (none)"], "cause": "test", "affected_evaluations": ["x"], "round": 0,
                     "detected_utc": "2026-09-03T09:00:00Z", "resolved_utc": "2026-09-03T09:00:00Z", "resolution": "r"}]}

    def setUp(self):
        super().setUp()
        from knowledge.ingest import data_gaps as dg
        self.dg = dg
        (self.dev_root / "knowledge").mkdir(exist_ok=True)
        (self.dev_root / "knowledge" / "data_gaps.json").write_text(json.dumps(self.GAP), encoding="utf-8")

    def test_a_gap_becomes_an_event_page_in_the_events_register(self):
        pages_ = self.dg.ingest_gaps(self.vault, self.dev_root, at=NOW)
        self.assertEqual([p.path.stem for p in pages_], ["data_gap_test_gap"])
        meta, body = fm.parse((self.vault / "wiki/events/data_gap_test_gap.md").read_text(encoding="utf-8"))
        self.assertEqual((meta["type"], meta["dev"]["kind"], meta["dev"]["gap_hours"]), ("Event", "data_gap", 9.0))
        self.assertIn("**9.0 h with no recording**", body)
        self.assertIn("[[data_gap_test_gap\\|", registers.update_register(self.vault, "Event", at=NOW).body)
        self.assertEqual(self.dg.overlapping_gaps(self.vault, "2026-09-02T20:00:00Z", "2026-09-03T01:00:00Z"), ["data_gap_test_gap"])
        self.assertEqual(self.dg.overlapping_gaps(self.vault, "2026-09-03T10:00:00Z", "2026-09-04T00:00:00Z"), [])
        self.assertEqual(self.dg.overlapping_gaps(self.vault, None, "2026-09-04T00:00:00Z"), [])

    def test_l12_fires_on_an_unacknowledged_span_and_the_fade_adapter_acknowledges(self):
        self.dg.ingest_gaps(self.vault, self.dev_root, at=NOW)
        # a verdict whose measured span (first..last event) crosses the gap, compiled by the fade adapter
        art = self.art()
        art["data_audit"]["first_event_utc"] = "2026-09-01T05:00:00Z"
        art["data_audit"]["last_event_utc"] = "2026-09-06T17:00:00Z"
        self.ingest(art)
        meta, body = self.page()
        self.assertEqual(meta["dev"]["data_gaps"], ["data_gap_test_gap"])         # acknowledged by the adapter
        self.assertIn("**data gaps inside this span**: [[data_gap_test_gap]]", body)
        self.assertEqual([f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "L12"], [])
        # strip the acknowledgement: L12 speaks
        p = self.vault / "wiki/experiments/passive_fade_rebenchmark_verdict.md"
        meta["dev"]["data_gaps"] = []
        pages.write_page(pages.Page(p, meta, body), self.vault, now=NOW)
        l12 = [f for f in lint.lint_vault(self.vault, self.dev_root, now=NOW) if f.code == "L12"]
        self.assertEqual([(f.severity, f.path) for f in l12], [("warning", "wiki/experiments/passive_fade_rebenchmark_verdict.md")])
        self.assertIn("data_gap_test_gap", l12[0].message)


class DaemonStreamTests(FomcRehearsalTests):
    def test_stream_ages_are_judged_only_when_asked_and_never_fail_closed_silently(self):
        self.assertFalse(any(c.name.endswith(" stream") for c in self.checks()))                # offline: not judged
        lv = self.levels(self.checks(ages={"collector": 12.0, "watcher": 200.0, "exporter": 20.0}))
        self.assertEqual([lv[k] for k in ("collector stream", "watcher stream", "exporter stream")], ["PASS"] * 3)
        lv = self.levels(self.checks(ages={"collector": 34000.0, "watcher": 200.0, "exporter": None}))
        self.assertEqual(lv["collector stream"], "FAIL")                                          # the 9 h failure mode
        self.assertEqual(lv["exporter stream"], "FAIL")                                           # unreadable is a FAIL, not a pass
        self.assertEqual(lv["watcher stream"], "PASS")

    def test_daemon_ages_reads_a_db_a_directory_and_a_file(self):
        import sqlite3
        db = self.dev_root / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(db)
        c.execute("CREATE TABLE asset_snapshots (timestamp INTEGER)")
        c.execute("INSERT INTO asset_snapshots VALUES (?)", (int((NOW.timestamp() - 120) * 1000),))
        c.commit()
        c.close()
        drops = self.dev_root / "Sports_Desk" / "data" / "polymarket_drops"
        drops.mkdir(parents=True, exist_ok=True)
        (drops / "d.json").write_text("{}", encoding="utf-8")
        ages = self.rh.daemon_ages(self.dev_root, now=NOW)
        self.assertAlmostEqual(ages["collector"], 120.0, places=1)
        self.assertIsNotNone(ages["watcher"])
        self.assertIsNone(ages["exporter"])                                                        # no log file in the fixture


class RegimeHistoryDedupeTests(IngestFixture):
    def test_re_ingesting_the_same_verdict_replaces_its_row(self):
        from knowledge.ingest import lead_lag as ll
        art = {"events": 7, "price_points": 100, "max_lag": 60, "sufficient": True, "reason": "", "best_lag_minutes": 38,
               "correlation": -0.3, "n": 900, "interpretation": "x", "curve": [], "latency_minutes": 5.0,
               "family": "macro", "subfamily": "crypto", "subfamily_from": "tags", "price_error": ""}
        f = self.dev_root / "a.json"
        f.write_text(json.dumps(art), encoding="utf-8")
        at = datetime(2026, 9, 7, 2, 30, 34, tzinfo=timezone.utc)
        ll.ingest_verdict(art, self.vault, self.dev_root, tier="2b", source="a.json", at=at)
        ll.ingest_verdict(art, self.vault, self.dev_root, tier="2b", source="b.json", at=at)
        meta, _ = fm.parse((self.vault / "wiki/regimes/btc_macro_regime.md").read_text(encoding="utf-8"))
        rows = [r for r in meta["dev"]["history"] if r["page"].startswith("lead_lag_tier2b_macro_crypto_")]
        self.assertEqual(len(rows), 1)
        page = fm.parse((self.vault / "wiki/experiments" / (rows[0]["page"] + ".md")).read_text(encoding="utf-8"))[0]
        self.assertEqual(page["dev"]["tests_run"], 1)                       # not inflated by the re-ingest
        log1 = (self.vault / "log.md").read_text(encoding="utf-8")
        ll.ingest_verdict(art, self.vault, self.dev_root, tier="2b", source="b.json", at=at)
        self.assertEqual((self.vault / "log.md").read_text(encoding="utf-8"), log1)     # unchanged verdict, no log line


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
