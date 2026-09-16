"""Reading intake (2026-09-12): inbox links -> fetched snapshots -> Source Summary pages -> the second strategy
family search. Every test is offline: the fetcher's transports are injected, and a guard test proves the
compiling half imports nothing that can open a socket."""
import ast
import hashlib
import io
import json
import unittest
from datetime import timedelta
from pathlib import Path

from knowledge import fetch_reading as fr, frontmatter as fm, lint
from knowledge import reading as rd
from knowledge.ingest import reading as ir
from knowledge.tests.test_knowledge import NOW, IngestFixture

PKG = Path(__file__).resolve().parents[1]

INBOX = """---
type: raw
---
# Reading inbox

## Links
- (example — delete me) https://www.youtube.com/watch?v=xxxx — the lecture I want summarized
- https://www.youtube.com/watch?v=zjkBMFhNj_g&t=120s — mean reversion talk, watch the cost section
- https://youtu.be/zjkBMFhNj_g?si=abc — same video again
- [a blog](https://example.com/posts/vol-regimes/?utm_source=x&id=7) - volatility regime switching
- https://en.wikipedia.org/wiki/Mean_reversion_(finance).
https://arxiv.org/pdf/2401.01234v2.pdf
- https://dead.example.org/gone

## Notes / raw text
```
https://inside.a.fence/should-not-count
```
"""

HTML = ("<html><head><title>Vol regimes</title><meta name='author' content='A. Quant'></head><body><nav>menu</nav>"
        "<article><h1>Volatility regimes</h1><p>" + ("Buy the dip when realised volatility compresses. " * 20) +
        "</p><script>track()</script></article><footer>(c)</footer></body></html>")


class _Resp:
    def __init__(self, status=200, text="", content=b"", ctype="text/html", data=None):
        self.status_code, self.text, self.content, self.headers, self._data = status, text, content or text.encode(), {"content-type": ctype}, data

    def json(self):
        return self._data


def fake_get(url, timeout=None, headers=None):
    if "oembed" in url:
        return _Resp(data={"title": "Mean reversion in crypto", "author_name": "Some Channel"})
    if "example.com" in url or "wikipedia.org" in url:
        return _Resp(text=HTML)
    if "arxiv.org/abs" in url:
        return _Resp(text="<html><head><meta name='citation_title' content='A Paper'></head><body><main>" + "abstract " * 80 + "</main></body></html>")
    if "arxiv.org/pdf" in url:
        return _Resp(status=404)
    raise ConnectionError(f"no route to {url}")


def fake_transcript(video_id):
    return [(0.0, "hi everyone"), (30.0, "fade the move"), (61.5, "costs matter"), (125.0, "hold for days")]


def campaign_meta(dev_root: Path, hurdle=40.0) -> Path:
    p = dev_root / ir.DEFAULT_CAMPAIGN_META
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"campaign_tag": "c4_test", "timeframe": "1h",
                             "assets": [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}],
                             "gates": {"max_tunables": 6, "max_grid_combinations": 27, "min_oos_trades_per_asset": 40,
                                       "max_oos_drawdown_pct_of_equity": 8.0},
                             "holdout_gates": {"promotion_min_trades": 50},
                             "gate_zero": {"hurdle_bps": hurdle}}), encoding="utf-8")
    return p


def vault_hash(vault: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(vault.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(vault).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class InboxParseTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.inbox = self.vault / rd.INBOX_DIR
        self.inbox.mkdir(parents=True)
        (self.inbox / "READING.md").write_text(INBOX, encoding="utf-8")

    def test_examples_skipped_duplicates_merged_notes_kept_fences_ignored(self):
        items = {i.kind + ":" + i.key: i for i in rd.parse_inbox(self.inbox)}
        yt = items["youtube:zjkBMFhNj_g"]
        self.assertEqual(yt.note, "mean reversion talk, watch the cost section / same video again")
        self.assertEqual(yt.canonical, "https://www.youtube.com/watch?v=zjkBMFhNj_g")
        blog = next(i for i in items.values() if "example.com" in i.url)
        self.assertEqual(blog.canonical, "https://example.com/posts/vol-regimes?id=7")   # utm dropped, slash trimmed
        self.assertEqual(blog.note, "a blog - volatility regime switching")
        wiki = next(i for i in items.values() if "wikipedia" in i.url)
        self.assertTrue(wiki.url.endswith("Mean_reversion_(finance)"))                  # own parens kept, full stop dropped
        self.assertIn("arxiv:2401.01234", items)                                         # bare line, pdf form, version stripped
        self.assertFalse(any("xxxx" in i.url or "fence" in i.url for i in items.values()))
        self.assertEqual(len(items), 5)

    def test_url_forms_share_one_stem(self):
        a = rd.classify("https://www.youtube.com/shorts/zjkBMFhNj_g")
        b = rd.classify("https://m.youtube.com/watch?v=zjkBMFhNj_g&feature=share")
        self.assertEqual(rd.stem_for(a[0], a[1]), rd.stem_for(b[0], b[1]))
        self.assertEqual(rd.classify("https://arxiv.org/abs/2401.01234v3")[1], rd.classify("https://arxiv.org/pdf/2401.01234")[1])
        self.assertEqual(rd.classify("https://github.com/o/r/blob/main/src/x.py")[2], "o/r/blob/main/src/x.py")
        self.assertEqual(rd.classify("https://github.com/o/r.git")[1], "https://github.com/o/r")
        self.assertEqual(rd.classify("https://host.org/paper.PDF")[0], "pdf")
        self.assertRegex(rd.stem_for("web", "https://x.org"), r"^source_web_[0-9a-f]{10}$")

    def test_a_clipped_article_is_fetched_without_the_network(self):
        (self.inbox / "clip.md").write_text("---\ntitle: Pairs are dead\nsource: https://blog.example/pairs\n---\n" + "Body text. " * 60,
                                            encoding="utf-8")

        def no_network(*a, **k):
            raise AssertionError("a clip must not touch the network")
        rep = fr.run_fetch(self.vault, get=lambda url, **k: no_network() if "blog.example" in url else fake_get(url, **k),
                           transcript=fake_transcript, now=NOW, out=io.StringIO())
        clip = next(i for i in rd.parse_inbox(self.inbox) if i.kind == "clip")
        self.assertIn(clip.stem, rep.fetched)
        headers, text = rd.read_snapshot(rd.snapshot_path(self.vault, clip.stem))
        self.assertEqual((headers["fetcher"], headers["title"]), ("clip", "Pairs are dead"))
        self.assertTrue(text.startswith("Body text."))


class FetchAndIngestTests(IngestFixture):
    def setUp(self):
        super().setUp()
        self.inbox = self.vault / rd.INBOX_DIR
        self.inbox.mkdir(parents=True)
        (self.inbox / "READING.md").write_text(INBOX, encoding="utf-8")
        self.meta_file = campaign_meta(self.dev_root)
        self.items = {i.kind + ":" + i.key: i for i in rd.parse_inbox(self.inbox)}
        self.yt = self.items["youtube:zjkBMFhNj_g"].stem
        self.dead = next(i for i in self.items.values() if "dead.example" in i.url).stem

    def fetch(self, **kw):
        return fr.run_fetch(self.vault, get=fake_get, transcript=fake_transcript, now=NOW, out=io.StringIO(), **kw)

    def test_snapshots_are_written_failures_recorded_and_existing_ones_never_rewritten(self):
        rep = self.fetch()
        self.assertEqual(len(rep.fetched), 4)
        self.assertEqual([s for s, _ in rep.failed], [self.dead])
        headers, text = rd.read_snapshot(rd.snapshot_path(self.vault, self.yt))
        self.assertEqual((headers["title"], headers["author"], headers["status"]), ("Mean reversion in crypto", "Some Channel", "ok"))
        self.assertEqual(text.split("\n\n"), ["[00:00] hi everyone fade the move", "[01:01] costs matter", "[02:05] hold for days"])
        self.assertEqual((headers["sha256"], int(headers["chars"])), (rd.sha256_text(text), len(text)))   # read-back is exactly what was hashed
        blog = next(i for i in self.items.values() if "example.com" in i.url)
        bh, btext = rd.read_snapshot(rd.snapshot_path(self.vault, blog.stem))
        self.assertIn("Buy the dip", btext)
        self.assertNotIn("track()", btext)
        self.assertNotIn("menu", btext)
        arx = rd.read_snapshot(rd.snapshot_path(self.vault, self.items["arxiv:2401.01234"].stem))[0]
        self.assertIn("PDF text unavailable", arx["warning"])
        self.assertIn("ConnectionError", rd.read_snapshot(rd.failure_path(self.vault, self.dead))[0]["error"])
        before = rd.snapshot_path(self.vault, self.yt).read_bytes()
        again = fr.run_fetch(self.vault, get=fake_get, transcript=lambda v: [(0.0, "CHANGED")], now=NOW + timedelta(hours=1), out=io.StringIO())
        self.assertIn(self.yt, again.skipped)
        self.assertEqual(rd.snapshot_path(self.vault, self.yt).read_bytes(), before)       # raw truth does not move silently
        self.assertEqual([s for s, _ in again.failed], [self.dead])                        # failures are retried
        fr.run_fetch(self.vault, refetch=True, get=fake_get, transcript=lambda v: [(0.0, "CHANGED")], now=NOW, out=io.StringIO())
        self.assertIn("CHANGED", rd.read_snapshot(rd.snapshot_path(self.vault, self.yt))[1])

    def test_inline_links_stay_in_their_sentence_and_blocks_break_lines(self):
        # the first live Wikipedia fetch put every link and citation marker on a line of its own
        title, _, text = fr.html_to_text("<html><head><title>T</title></head><body><main><p>For other uses, see "
                                         "<a href='/d'>Mean reversion (disambiguation)</a>.</p><p>Price reverts."
                                         "<sup>[<a>1</a>]</sup></p><ul><li>one</li><li>two</li></ul></main></body></html>")
        self.assertEqual(text.split("\n"), ["For other uses, see Mean reversion (disambiguation).", "", "Price reverts.[1]",
                                            "", "one", "", "two"])

    def test_a_later_success_clears_the_failure_marker(self):
        self.fetch()
        self.assertTrue(rd.failure_path(self.vault, self.dead).is_file())
        fr.run_fetch(self.vault, get=lambda url, **k: _Resp(text=HTML) if "dead.example" in url else fake_get(url, **k),
                     transcript=fake_transcript, now=NOW, out=io.StringIO())
        self.assertFalse(rd.failure_path(self.vault, self.dead).is_file())
        self.assertTrue(rd.snapshot_path(self.vault, self.dead).is_file())

    def test_halt_flag_refuses_before_any_fetch(self):
        (self.dev_root / "HALT.flag").write_text("", encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(fr.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root)], out=out), 3)
        self.assertFalse((self.vault / rd.SNAPSHOT_DIR).exists())

    def test_pages_register_and_search_compile_lint_clean_and_idempotent(self):
        self.fetch()
        rep = ir.ingest_reading(self.vault, self.dev_root, at=NOW)
        self.assertEqual((rep.sources, rep.pending), (5, 5))
        meta, body = fm.parse((self.vault / f"wiki/sources/{self.yt}.md").read_text(encoding="utf-8"))
        self.assertEqual((meta["type"], meta["status"], meta["dev"]["fetch_status"], meta["dev"]["review_status"]),
                         ("Source Summary", "draft", "ok", "pending"))
        self.assertEqual(meta["sources"][1]["resource"], f"obsidian_vault/raw/fetched/{self.yt}.txt")
        self.assertIn(ir.SUMMARY_PLACEHOLDER, body)
        dmeta, dbody = fm.parse((self.vault / f"wiki/sources/{self.dead}.md").read_text(encoding="utf-8"))
        self.assertEqual(dmeta["dev"]["fetch_status"], "failed")
        self.assertIn("status: **failed**", dbody)
        smeta, sbody = fm.parse((self.vault / "wiki/concepts/strategy_family_search.md").read_text(encoding="utf-8"))
        self.assertIn("| Gate Zero: in-sample GROSS edge per trade", sbody)
        self.assertIn("THIS IS FAMILY 1", sbody)
        self.assertEqual({p["name"]: p["value"] for p in smeta["dev"]["parameters"]}["autoresearch_gate_zero_hurdle_bps"], 40.0)
        reg = (self.vault / "wiki/concepts/sources_register.md").read_text(encoding="utf-8")
        self.assertIn("5 page(s).", reg)
        self.assertIn("[[strategy_family_search|Second strategy family search]]", reg)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        before, log = vault_hash(self.vault), (self.vault / "log.md").read_text(encoding="utf-8")
        again = ir.ingest_reading(self.vault, self.dev_root, at=NOW + timedelta(hours=2))
        self.assertEqual(again.written, [])
        self.assertEqual(vault_hash(self.vault), before)                                  # no restamp, no log line
        self.assertEqual((self.vault / "log.md").read_text(encoding="utf-8"), log)

    def test_a_review_ranks_the_source_survives_reingest_and_refuses_bad_input(self):
        self.fetch()
        ir.ingest_reading(self.vault, self.dev_root, at=NOW)
        review = {"summary": "Fades 3-sigma hourly moves.\n\n### Costs\nHolds 2-5 days.", "verdict": "candidate",
                  "family": "Volatility-scaled mean reversion", "mechanism": "overreaction to liquidation-driven hourly moves",
                  "data_needed": "OHLCV", "horizon": "2-5 days", "tunables": 4, "evidence": "costs included, no holdout"}
        ir.review_source(self.vault, self.dev_root, self.yt, review, at=NOW + timedelta(minutes=5))
        blog = next(i for i in self.items.values() if "example.com" in i.url).stem
        ir.review_source(self.vault, self.dev_root, blog, {"summary": "Needs funding rates.", "verdict": "needs-harness-change",
                                                           "family": "Funding carry", "data_needed": "funding"}, at=NOW + timedelta(minutes=6))
        sbody = (self.vault / "wiki/concepts/strategy_family_search.md").read_text(encoding="utf-8")
        self.assertLess(sbody.index("**candidate**"), sbody.index("**needs-harness-change**"))
        self.assertIn("Volatility-scaled mean reversion", sbody)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW + timedelta(minutes=7)), [])
        page_before = (self.vault / f"wiki/sources/{self.yt}.md").read_text(encoding="utf-8")
        ir.ingest_reading(self.vault, self.dev_root, at=NOW + timedelta(hours=3))           # re-ingest keeps the review
        self.assertEqual((self.vault / f"wiki/sources/{self.yt}.md").read_text(encoding="utf-8"), page_before)
        meta, body = fm.parse(page_before)
        self.assertEqual((meta["dev"]["verdict"], meta["dev"]["tunables"], meta["dev"]["reviewed"]["at"]),
                         ("candidate", "4", "2026-09-05T20:05:00Z"))
        self.assertIn("### Costs", body)
        for bad in ({"summary": "x", "verdict": "maybe"}, {"summary": "", "verdict": "reject"},
                    {"summary": "## Heading\nx", "verdict": "reject"}, {"summary": "x", "verdict": "reject", "score": 9}):
            with self.assertRaises(ValueError):
                ir.review_source(self.vault, self.dev_root, self.yt, bad, at=NOW)
        with self.assertRaises(ValueError):
            ir.review_source(self.vault, self.dev_root, "source_web_0000000000", review, at=NOW)

    def test_c1_fires_when_the_next_campaign_moves_a_number(self):
        self.fetch()
        ir.ingest_reading(self.vault, self.dev_root, at=NOW)
        campaign_meta(self.dev_root, hurdle=55.0)
        self.assertTrue(any(f.code == "C1" and "autoresearch_gate_zero_hurdle_bps" in f.message
                            for f in lint.lint_vault(self.vault, self.dev_root, now=NOW)))

    def test_missing_registration_degrades_to_a_note_and_stays_lint_clean(self):
        self.meta_file.unlink()
        ir.ingest_reading(self.vault, self.dev_root, at=NOW)
        smeta, sbody = fm.parse((self.vault / "wiki/concepts/strategy_family_search.md").read_text(encoding="utf-8"))
        self.assertNotIn("parameters", smeta["dev"])
        self.assertIn("registration was not found", sbody)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])


class NetworkIsolationTests(unittest.TestCase):
    def test_only_fetch_reading_may_import_a_network_library(self):
        banned = {"requests", "socket", "urllib.request", "http.client", "youtube_transcript_api", "httpx", "aiohttp"}
        offenders = []
        for py in PKG.rglob("*.py"):
            if "tests" in py.parts or py.name == "fetch_reading.py":
                continue
            for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                offenders += [f"{py.relative_to(PKG)}:{n}" for n in names if n in banned or n.split(".")[0] in {"requests", "socket", "httpx", "aiohttp"}]
        self.assertEqual(offenders, [])
