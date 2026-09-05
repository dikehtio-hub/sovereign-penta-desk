"""
Item 12, Phase 1 (Round 87): the latency sniper, 100% offline. What must be true: a
rule resolves a market from an event and nothing else does; HALT.flag and low
confidence refuse everything; a stale or missing book is skipped; the walk takes
levels only while confidence clears the after-tax breakeven and stops at the
quarter-Kelly cap; a NO outcome hits YES bids at (1 - bid); receipts are PAPER,
tagged latency_sniper, and land under the paper folder; the recorder stamps books
through an injected fetch and the loader picks the newest stamp per token.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from cross_market import latency_sniper as ls

NOW = datetime(2026, 9, 17, 18, 0, 5, tzinfo=timezone.utc)


def fair_breakeven(odds):
    return 1.0 / odds


def cap_150(win_prob, odds):
    return 150.0


class SniperBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.halt = self.root / "HALT.flag"
        self.event = ls.Event(kind="fed_rate", payload={"change_bps": -25}, source="federalreserve.gov", confidence=0.995,
                              observed_at=NOW - timedelta(seconds=3))
        self.rules = [ls.Rule(market="CUT25", kind="fed_rate", field="change_bps", op="==", value=-25, label="cut 25"),
                      ls.Rule(market="HOLD", kind="fed_rate", field="change_bps", op="==", value=0, label="hold"),
                      ls.Rule(market="CPI", kind="cpi_yoy", field="yoy_pct", op=">", value=3.0, label="cpi > 3")]

    def tearDown(self):
        self.temp.cleanup()

    def book(self, market, asks=(), bids=(), age_s=2.0, fee_rate=0.02):
        return ls.Book.from_clob(market, {"asks": [{"price": p, "size": s} for p, s in asks],
                                          "bids": [{"price": p, "size": s} for p, s in bids]},
                                 NOW - timedelta(seconds=age_s), fee_rate=fee_rate)


class TestRulesAndBooks(SniperBase):

    def test_rules_resolve_only_their_own_event_kind_and_field(self):
        self.assertEqual(self.rules[0].resolve(self.event), "YES")
        self.assertEqual(self.rules[1].resolve(self.event), "NO")                     # the other side of a binary market
        self.assertIsNone(self.rules[2].resolve(self.event))                          # a CPI rule says nothing about the Fed
        self.assertIsNone(self.rules[0].resolve(ls.Event("fed_rate", {"statement": "x"}, "s", 1.0, NOW)))   # field missing
        self.assertIsNone(self.rules[0].resolve(ls.Event("fed_rate", {"change_bps": "twenty-five"}, "s", 1.0, NOW)))
        no_rule = ls.Rule(market="M", kind="Fed_Rate", field="change_bps", op="<=", value=-50, outcome_if_true="no")
        self.assertEqual(no_rule.resolve(self.event), "YES")                          # -25 <= -50 is false -> the other side
        with self.assertRaises(ValueError):
            ls.Rule(market="M", kind="k", field="f", op="~", value=1)
        with self.assertRaises(ValueError):
            ls.Rule(market="M", kind="k", field="f", op="==", value=1, outcome_if_true="MAYBE")
        # the committed sample loads and is a placeholder by its own status line
        rules = ls.load_rules(ls.SAMPLE_RULES)
        self.assertGreaterEqual(len(rules), 4)
        self.assertIn("placeholder", json.loads(ls.SAMPLE_RULES.read_text(encoding="utf-8"))["status"])
        path = self.root / "rules.json"
        path.write_text(json.dumps([{"market": "X", "kind": "cpi_yoy", "field": "yoy_pct", "op": "in", "value": [3.1, 3.2], "extra": "ignored"}]), encoding="utf-8")
        self.assertEqual(ls.load_rules(path)[0].resolve(ls.Event("cpi_yoy", {"yoy_pct": 3.1}, "bls", 1.0, NOW)), "YES")

    def test_books_parse_sort_skip_junk_and_know_their_age(self):
        book = ls.Book.from_clob("M", {"asks": [{"price": "0.95", "size": "10"}, {"price": "0.90", "size": "5"}, {"price": "1.2", "size": "9"},
                                              {"price": "x", "size": "1"}, {"price": "0.5", "size": "0"}],
                                       "bids": [{"price": "0.80", "size": "1"}, {"price": "0.85", "size": "2"}]},
                                 "2026-09-17T18:00:00Z", fee_rate=0.02)
        self.assertEqual([(l.price, l.size) for l in book.asks], [(0.90, 5.0), (0.95, 10.0)])
        self.assertEqual([l.price for l in book.bids], [0.85, 0.80])
        self.assertAlmostEqual(book.age_s(NOW), 5.0)
        self.assertAlmostEqual(ls.net_payoff_per_share(0.90, 0.02), 0.998)
        self.assertAlmostEqual(ls.effective_odds(0.90, 0.02), 0.998 / 0.90)


class TestEvaluate(SniperBase):

    def test_halt_and_low_confidence_refuse_everything(self):
        books = {"CUT25": self.book("CUT25", asks=[(0.90, 100)])}
        self.halt.write_text("{}", encoding="utf-8")
        out = ls.evaluate(self.event, self.rules, books, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)
        self.assertTrue(out["halted"]) ; self.assertIn("HALT.flag present", out["refused"]) ; self.assertEqual(out["opportunities"], [])
        self.halt.unlink()
        shaky = ls.Event("fed_rate", {"change_bps": -25}, "rumour", 0.9, NOW)
        out = ls.evaluate(shaky, self.rules, books, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)
        self.assertFalse(out["halted"]) ; self.assertIn("confidence 0.900 < 0.99", out["refused"]) ; self.assertEqual(out["opportunities"], [])

    def test_the_walk_takes_levels_that_clear_breakeven_and_stops_at_the_cap(self):
        # asks 0.90 x 100, 0.95 x 200, 0.99 x 500; fee 2%; confidence 0.995; breakeven = fair + 1 pt.
        # 0.99: odds (1 - 0.02*0.01)/0.99 = 1.00990.., fair breakeven 0.99020 + 0.01 -> 1.0002 > 0.995: fails.
        strict = lambda odds: 1.0 / odds + 0.01
        books = {"CUT25": self.book("CUT25", asks=[(0.90, 100), (0.95, 200), (0.99, 500)]),
                 "HOLD": self.book("HOLD", bids=[(0.05, 1000), (0.02, 1000)]),
                 "CPI": self.book("CPI", asks=[(0.5, 10)])}
        out = ls.evaluate(self.event, self.rules, books, strict, cap_150, now=NOW, halt_path=self.halt)
        self.assertIsNone(out["refused"])
        by_market = {o.market: o for o in out["opportunities"]}
        self.assertEqual(sorted(by_market), ["CUT25", "HOLD"])                       # CPI: no rule resolves the Fed event
        cut = by_market["CUT25"]
        self.assertEqual((cut.outcome, cut.side, cut.capped_by, len(cut.fills)), ("YES", "BUY_YES", "cap", 2))
        self.assertAlmostEqual(cut.fills[0].shares, 100.0) ; self.assertAlmostEqual(cut.fills[0].notional, 90.0)
        self.assertAlmostEqual(cut.fills[1].notional, 60.0, places=6)                 # the cap: 150 - 90
        self.assertAlmostEqual(cut.notional, 150.0, places=6) ; self.assertAlmostEqual(cut.cap_notional, 150.0)
        self.assertGreater(cut.expected_profit, 0) ; self.assertAlmostEqual(cut.vwap, 150.0 / cut.shares)
        self.assertTrue(all(f.edge_per_share > 0 for f in cut.fills))
        hold = by_market["HOLD"]                                                       # NO: hit YES bids at (1 - bid)
        self.assertEqual((hold.outcome, hold.side), ("NO", "BUY_NO"))
        self.assertAlmostEqual(hold.fills[0].price, 0.95)
        # the hurdle stops the walk before the cap: only the 0.90 level clears a 0.99+ breakeven
        picky = lambda odds: 1.0 / odds + 0.045
        out = ls.evaluate(self.event, self.rules[:1], {"CUT25": books["CUT25"]}, picky, lambda p, o: 10_000.0, now=NOW, halt_path=self.halt)
        opp = out["opportunities"][0]
        self.assertEqual((len(opp.fills), opp.capped_by), (1, "hurdle"))
        self.assertAlmostEqual(opp.notional, 90.0)
        # nothing clears: skipped with the reason, never an empty opportunity
        out = ls.evaluate(self.event, self.rules[:1], {"CUT25": books["CUT25"]}, lambda odds: 1.5, cap_150, now=NOW, halt_path=self.halt)
        self.assertEqual(out["opportunities"], []) ; self.assertEqual(out["skipped"][0]["reason"], "no level clears the hurdle")
        # a zero cap takes nothing
        out = ls.evaluate(self.event, self.rules[:1], {"CUT25": books["CUT25"]}, fair_breakeven, lambda p, o: 0.0, now=NOW, halt_path=self.halt)
        self.assertEqual(out["opportunities"], [])

    def test_missing_and_stale_books_are_skipped_with_reasons(self):
        books = {"CUT25": self.book("CUT25", asks=[(0.90, 100)], age_s=30.0)}
        out = ls.evaluate(self.event, self.rules, books, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)
        self.assertEqual(out["opportunities"], [])
        reasons = {s["market"]: s["reason"] for s in out["skipped"]}
        self.assertTrue(reasons["CUT25"].startswith("book stale (age 30.0s > 10s)"))
        self.assertEqual(reasons["HOLD"], "no book snapshot")
        books = {"CUT25": self.book("CUT25", asks=[(0.90, 100)], age_s=-5.0)}           # from the future: not trusted
        out = ls.evaluate(self.event, self.rules[:1], books, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)
        self.assertIn("book stale", out["skipped"][0]["reason"])

    def test_the_hook_economics_are_read_from_the_tax_agent_and_assumed_ones_are_fair(self):
        class FakeHook:
            def after_tax_edge_hurdle(self, decimal_odds):
                return {"breakeven_win_probability": 1.0 / decimal_odds + 0.02}
            def after_tax_kelly_fraction(self, p, odds):
                return 0.8
            def get_safe_bankroll(self):
                return 2000.0
            def max_position_size(self):
                return 300.0
        breakeven, cap = ls.hook_economics(FakeHook())
        self.assertAlmostEqual(breakeven(1.1), 1.0 / 1.1 + 0.02)
        self.assertAlmostEqual(cap(0.99, 1.1), 300.0)                                 # min(0.25 * 0.8 * 2000 = 400, ceiling 300)
        breakeven, cap = ls.assumed_economics(bankroll=1000.0)
        self.assertAlmostEqual(breakeven(1.25), 0.8)
        self.assertAlmostEqual(cap(0.995, 1.1), 0.25 * ((0.995 * 0.1 - 0.005) / 0.1) * 1000.0)
        self.assertEqual(cap(0.5, 1.0), 0.0)


class TestReceiptsRecorderAndCli(SniperBase):

    def test_paper_receipts_are_tagged_and_land_under_the_paper_folder(self):
        books = {"CUT25": self.book("CUT25", asks=[(0.90, 100), (0.95, 200)])}
        opp = ls.evaluate(self.event, self.rules[:1], books, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)["opportunities"][0]
        seen = {}

        def writer(**kwargs):
            seen.update(kwargs)
            return Path("receipt.csv")
        self.assertEqual(ls.record_paper(opp, self.event, receipts_dir=self.root / "paper", writer=writer, stamp="2026-09-17T18:00:05Z"), Path("receipt.csv"))
        self.assertEqual((seen["symbol"], seen["side"], seen["strategy"], seen["venue"]), ("CUT25", "BUY", "latency_sniper", "polymarket"))
        self.assertAlmostEqual(seen["quantity"], opp.shares, places=5) ; self.assertAlmostEqual(seen["price"], opp.vwap, places=5)
        self.assertEqual(seen["imports_dir"], self.root / "paper")
        for expect in ("paper:1", "strategy:latency_sniper", "event:fed_rate", "rule:cut 25", "outcome:YES", "capped_by:cap"):
            self.assertIn(expect, seen["extra_notes"])
        self.assertTrue(str(ls.PAPER_RECEIPTS_DIR).replace("\\", "/").endswith("cross_market/data/paper_receipts"))
        # the real writer accepts these arguments and writes one file into the given folder
        real = ls.record_paper(opp, self.event, receipts_dir=self.root / "real")
        self.assertIsNotNone(real) ; self.assertTrue(Path(real).exists()) ; self.assertIn("polymarket", Path(real).name)
        self.assertIn("latency_sniper", Path(real).read_text(encoding="utf-8"))
        # a writer that raises is a warning, not a crash
        with mock.patch("builtins.print"):
            self.assertIsNone(ls.record_paper(opp, self.event, writer=lambda **k: (_ for _ in ()).throw(OSError("disk"))))

    def test_the_recorder_stamps_books_and_the_loader_picks_the_newest_per_token(self):
        payloads = {"A": {"bids": [{"price": "0.4", "size": "10"}], "asks": [{"price": "0.6", "size": "10"}]},
                    "B": {"bids": [], "asks": [{"price": "0.7", "size": "3"}]}}

        def fetch(token):
            if token == "C":
                raise OSError("timeout")
            return payloads[token]
        out = self.root / "books"
        with mock.patch("builtins.print"):
            first = ls.stamp_books(["A", "B", "C", ""], out, fetch, now=NOW - timedelta(seconds=8), fee_rate=0.02)
            second = ls.stamp_books(["A"], out, fetch, now=NOW - timedelta(seconds=2))
        self.assertEqual([p.name[:6] for p in first], ["clob_A", "clob_B"]) ; self.assertEqual(len(second), 1)
        (out / "clob_A_20260917T180010_000000Z.json").write_text("{not json", encoding="utf-8")   # corrupt: skipped
        (out / "clob_B_20260917T190000_000000Z.json").write_text(json.dumps({"observed_at": "2026-09-17T19:00:00Z", "asks": []}), encoding="utf-8")
        books = ls.load_books(out, now=NOW)
        self.assertEqual(sorted(books), ["A", "B"])
        self.assertAlmostEqual(books["A"].age_s(NOW), 2.0)                             # the newer stamp wins
        self.assertEqual(books["A"].fee_rate, 0.0) ; self.assertEqual(books["B"].fee_rate, 0.02)
        self.assertAlmostEqual(books["B"].age_s(NOW), 8.0)                             # the 19:00 stamp is after `now`: ignored
        self.assertEqual(ls.load_books(self.root / "absent"), {})

    def test_cli_evaluates_replays_writes_paper_and_honours_the_halt_flag(self):
        books = self.root / "books"
        ls.stamp_books(["CUT25"], books, lambda t: {"asks": [{"price": "0.90", "size": "100"}], "bids": []}, now=NOW - timedelta(seconds=2))
        event = self.root / "event.json"
        event.write_text(json.dumps({"kind": "fed_rate", "payload": {"change_bps": -25}, "source": "fed", "confidence": 0.995,
                                     "observed_at": (NOW - timedelta(seconds=3)).isoformat()}), encoding="utf-8")
        rules = self.root / "rules.json"
        rules.write_text(json.dumps({"rules": [{"label": "cut 25", "market": "CUT25", "kind": "fed_rate", "field": "change_bps", "op": "==", "value": -25}]}), encoding="utf-8")
        common = ["--event", str(event), "--rules", str(rules), "--books", str(books), "--halt-flag", str(self.halt),
                  "--now", NOW.isoformat(), "--assume-defaults"]
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(common), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("BUY_YES CUT25 (cut 25)", printed) ; self.assertIn("places nothing", printed)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(common + ["--json"]), 0)
        payload = json.loads(fake_print.call_args_list[0].args[0])
        self.assertEqual(payload["opportunities"][0]["side"], "BUY_YES")
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(common + ["--paper", "--receipts-dir", str(self.root / "paper")]), 0)
        self.assertEqual(len(list((self.root / "paper").glob("*.csv"))), 1)
        self.assertIn("[PAPER] CUT25", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        # a replay 30 s later finds the stamp stale; the halt flag refuses with exit 3
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(common[:-3] + ["--now", (NOW + timedelta(seconds=30)).isoformat(), "--assume-defaults"]), 0)
        self.assertIn("book stale", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        self.halt.write_text("{}", encoding="utf-8")
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(common), ls.EXIT_HALTED)
        self.assertIn("REFUSED: HALT.flag present", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        # --record uses the injected-by-patch fetch; no socket in tests
        with mock.patch.object(ls, "default_fetch", lambda token, timeout=5.0: {"asks": [{"price": "0.5", "size": "1"}], "bids": []}), \
                mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(["--record", "--tokens", "T1, T2", "--books", str(self.root / "rec")]), 0)
            self.assertEqual(ls.main(["--record", "--tokens", "", "--books", str(self.root / "rec")]), 1)
        self.assertEqual(len(list((self.root / "rec").glob("clob_*.json"))), 2)


class TestLiveShape(SniperBase):
    """Round 87b: the wire, probed once for real - Cloudflare wants a User-Agent; the stamp keeps the book's provenance."""

    def test_default_fetch_sends_a_user_agent_and_stamps_keep_the_api_fields(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"bids": [{"price": "0.4", "size": "1"}], "asks": [], "hash": "abc",
                                   "min_order_size": "5", "neg_risk": False, "last_trade_price": "0.41",
                                   "asset_id": "T", "market": "0xm"}).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["headers"] = {k.lower(): v for k, v in request.header_items()}
            return FakeResponse()
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            payload = ls.default_fetch("T")
        self.assertTrue(captured["url"].endswith("book?token_id=T"))
        self.assertIn("mozilla", captured["headers"]["user-agent"].lower())
        self.assertEqual(payload["hash"], "abc")
        written = ls.stamp_books(["T"], self.root / "books", lambda t: payload, now=NOW)
        stamp = json.loads(written[0].read_text(encoding="utf-8"))
        for key in ("market", "asset_id", "hash", "last_trade_price", "min_order_size", "neg_risk"):
            self.assertIn(key, stamp)
        self.assertEqual(stamp["token_id"], "T")
        self.assertEqual(ls.load_books(self.root / "books", now=NOW)["T"].bids[0].price, 0.4)


class TestNegRiskRuling(SniperBase):
    """Round 88, Ruling R4: on a neg_risk event only the winning outcome's YES asks are lifted; its NO side waits."""

    def test_neg_risk_books_skip_the_no_side_and_keep_the_yes_side(self):
        cut = ls.Book.from_clob("CUT25", {"asks": [{"price": "0.90", "size": "100"}], "bids": [], "neg_risk": True},
                                NOW - timedelta(seconds=2), fee_rate=0.02)
        hold = ls.Book.from_clob("HOLD", {"asks": [], "bids": [{"price": "0.05", "size": "1000"}]},
                                 NOW - timedelta(seconds=2), fee_rate=0.02, neg_risk=True)
        self.assertTrue(cut.neg_risk and hold.neg_risk)
        out = ls.evaluate(self.event, self.rules, {"CUT25": cut, "HOLD": hold}, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)
        self.assertEqual([o.market for o in out["opportunities"]], ["CUT25"])          # YES on the winner: taken
        skipped = {s["market"]: s["reason"] for s in out["skipped"]}
        self.assertIn("neg_risk market: NO side deferred to Phase 2 (Ruling R4)", skipped["HOLD"])
        # the same NO side on a standalone market is still hit, as before
        plain = ls.Book.from_clob("HOLD", {"asks": [], "bids": [{"price": "0.05", "size": "1000"}]}, NOW - timedelta(seconds=2), fee_rate=0.02)
        self.assertFalse(plain.neg_risk)
        out = ls.evaluate(self.event, self.rules[1:2], {"HOLD": plain}, fair_breakeven, cap_150, now=NOW, halt_path=self.halt)
        self.assertEqual(out["opportunities"][0].side, "BUY_NO")
        # the flag travels from the live stamp through the loader
        out_dir = self.root / "books"
        ls.stamp_books(["T"], out_dir, lambda t: {"asks": [{"price": "0.5", "size": "1"}], "bids": [], "neg_risk": True}, now=NOW)
        self.assertTrue(ls.load_books(out_dir, now=NOW)["T"].neg_risk)


class TestDepthReport(SniperBase):
    """Round 92 (Option 2): level-by-level what a recorded book would hand a sniper; R4 honoured; CLI offline."""

    def test_depth_report_walks_levels_until_breakeven_fails_and_defers_neg_risk_no(self):
        strict = lambda odds: 1.0 / odds + 0.01
        book = self.book("CUT25", asks=[(0.90, 100), (0.95, 200), (0.99, 500)], bids=[(0.05, 1000), (0.02, 1000)])
        yes = ls.depth_report(book, "YES", 0.995, strict, now=NOW)
        self.assertEqual((yes["side"], yes["levels_clearing"], yes["fillable_shares"]), ("BUY_YES", 2, 300.0))
        self.assertAlmostEqual(yes["fillable_notional"], 90.0 + 190.0) ; self.assertAlmostEqual(yes["vwap"], 280.0 / 300.0, places=3)
        self.assertEqual(yes["best_price"], 0.90) ; self.assertFalse(yes["levels"][-1]["clears"])    # 0.99 recorded as failing
        self.assertGreater(yes["expected_profit"], 0)
        no = ls.depth_report(book, "NO", 0.995, strict, now=NOW)
        self.assertEqual((no["side"], no["levels"][0]["price"], no["levels_clearing"]), ("BUY_NO", 0.95, 2))
        neg = ls.Book.from_clob("HOLD", {"asks": [], "bids": [{"price": "0.05", "size": "10"}], "neg_risk": True}, NOW - timedelta(seconds=1))
        deferred = ls.depth_report(neg, "NO", 0.995, strict, now=NOW)
        self.assertIn("Ruling R4", deferred["deferred"]) ; self.assertEqual(deferred["levels"], [])
        self.assertIsNone(ls.depth_report(neg, "YES", 0.995, strict, now=NOW)["deferred"])           # empty side, not deferred
        nothing = ls.depth_report(book, "YES", 0.5, strict, now=NOW)
        self.assertEqual((nothing["levels_clearing"], nothing["vwap"]), (0, None))
        text = ls.format_depth([yes, deferred, nothing], "assumed")
        self.assertIn("2 level(s) clear", text) ; self.assertIn("Ruling R4", text) ; self.assertIn("nothing clears", text)
        # CLI over recorded stamps, assumed economics, JSON and text
        out = self.root / "books"
        ls.stamp_books(["T1"], out, lambda t: {"asks": [{"price": "0.90", "size": "100"}], "bids": [{"price": "0.10", "size": "50"}], "neg_risk": True},
                       now=NOW - timedelta(seconds=2))
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(["--depth-report", "--books", str(out), "--now", NOW.isoformat(), "--assume-defaults"]), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("DEPTH REPORT (Option 2)", printed) ; self.assertIn("Ruling R4", printed) ; self.assertIn("places nothing", printed)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(["--depth-report", "--books", str(out), "--now", NOW.isoformat(), "--assume-defaults", "--json"]), 0)
        payload = json.loads(fake_print.call_args_list[0].args[0])
        self.assertEqual([r["side"] for r in payload], ["BUY_YES", "BUY_NO"])
        with mock.patch("builtins.print"):
            self.assertEqual(ls.main(["--depth-report", "--books", str(self.root / "none"), "--assume-defaults"]), 1)


class TestRecordLoop(SniperBase):
    """Round 93 (Ruling R2b): the recording loop - cadence, duration, HALT, 429 back-off, interrupt; no network."""

    def test_loop_keeps_cadence_stops_on_duration_halt_429_and_interrupt(self):
        clock = {"t": 0.0}
        slept = []

        def tick():
            return clock["t"]

        def sleep(s):
            slept.append(round(s, 3))
            clock["t"] += s
        calls = []

        def fetch(token):
            calls.append(token)
            clock["t"] += 0.3                                          # each fetch costs 0.3 s
            return {"bids": [{"price": "0.4", "size": "1"}], "asks": [{"price": "0.6", "size": "1"}]}
        wall = {"n": 0}

        def now_wall():
            wall["n"] += 1
            return NOW + timedelta(seconds=wall["n"])
        out = self.root / "books"
        with mock.patch("builtins.print"):
            stats = ls.record_loop(["A", "B"], out, fetch, interval=1.0, duration=3.0, clock=tick, sleep=sleep, wall=now_wall,
                                   halt_path=self.halt)
        self.assertEqual((stats["polls"], stats["stamps"], stats["failures"], stats["stopped"]), (3, 6, 0, "duration"))
        self.assertTrue(all(abs(s - 0.4) < 1e-6 for s in slept), slept)                # 1.0 - 2 x 0.3 s of fetching
        self.assertEqual(len(list(out.glob("clob_A_*.json"))), 3)
        # HALT.flag mid-loop stops it with the reason
        clock["t"] = 0.0
        polls = {"n": 0}

        def fetch_then_halt(token):
            polls["n"] += 1
            if polls["n"] == 3:
                self.halt.write_text("{}", encoding="utf-8")
            return fetch(token)
        with mock.patch("builtins.print"):
            stats = ls.record_loop(["A", "B"], out, fetch_then_halt, interval=1.0, duration=60.0, clock=tick, sleep=sleep, wall=now_wall,
                                   halt_path=self.halt)
        self.assertEqual((stats["stopped"], stats["polls"]), ("halt", 2))
        self.halt.unlink()
        # HTTP 429 on one poll: counted, backed off, the loop continues
        clock["t"] = 0.0
        slept.clear()
        state = {"n": 0}

        def flaky(token):
            state["n"] += 1
            if state["n"] == 2:
                err = OSError("too many requests")
                err.code = 429
                raise err
            return fetch(token)
        with mock.patch("builtins.print") as fake_print:
            stats = ls.record_loop(["A"], out, flaky, interval=1.0, duration=3.0, clock=tick, sleep=sleep, wall=now_wall, halt_path=self.halt)
        self.assertEqual(stats["rate_limited"], 1) ; self.assertIn(5.0, slept)
        self.assertIn("rate limited", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        self.assertGreaterEqual(stats["failures"], 1)
        # Ctrl-C from inside a fetch ends the loop cleanly

        def interrupt(token):
            raise KeyboardInterrupt
        with mock.patch("builtins.print"):
            stats = ls.record_loop(["A"], out, interrupt, interval=1.0, duration=3.0, clock=tick, sleep=sleep, wall=now_wall, halt_path=self.halt)
        self.assertEqual(stats["stopped"], "interrupt")
        # the CLI: --record-loop with a patched fetch and a tiny duration; HALT -> exit 3
        with mock.patch.object(ls, "default_fetch", lambda token, timeout=5.0: {"asks": [{"price": "0.5", "size": "1"}], "bids": []}), \
                mock.patch.object(ls.time, "sleep", lambda s: None), mock.patch("builtins.print") as fake_print:
            self.assertEqual(ls.main(["--record-loop", "--tokens", "T1,T2", "--interval", "0", "--duration", "0.05",
                                      "--books", str(self.root / "loop"), "--halt-flag", str(self.halt)]), 0)
            self.assertEqual(ls.main(["--record-loop", "--tokens", "", "--books", str(self.root / "loop")]), 1)
            self.halt.write_text("{}", encoding="utf-8")
            self.assertEqual(ls.main(["--record-loop", "--tokens", "T1", "--duration", "5", "--books", str(self.root / "loop"),
                                      "--halt-flag", str(self.halt)]), ls.EXIT_HALTED)
        self.assertGreaterEqual(len(list((self.root / "loop").glob("clob_T1_*.json"))), 1)
        # the pre-registered FOMC rules load, resolve a hold and a hike, and carry real token ids
        rules = ls.load_rules(Path(__file__).resolve().parents[1] / "experiments" / "fomc_2026-09-17.rules.json")
        self.assertGreaterEqual(len(rules), 3)
        hold = ls.Event("fed_rate", {"change_bps": 0}, "fed", 0.995, NOW)
        hike = ls.Event("fed_rate", {"change_bps": 25}, "fed", 0.995, NOW)
        by_label = {r.label: r for r in rules}
        self.assertEqual(by_label["FOMC 2026-09-17: no change"].resolve(hold), "YES")
        self.assertEqual(by_label["FOMC 2026-09-17: no change"].resolve(hike), "NO")
        self.assertEqual(by_label["FOMC 2026-09-17: hike 25 bps"].resolve(hike), "YES")
        self.assertTrue(all(r.market.isdigit() and len(r.market) > 20 for r in rules))
