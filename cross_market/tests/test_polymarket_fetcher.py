"""
Round 34 Target 2: the collector that gives the cross-market desk its first question.

`Cross_Market_Arb.md` reported 0 questions because nothing had ever written into
`Sports_Desk/data/polymarket_drops/`. These tests pin that the sample is in the
exact shape the matcher parses, that it MATCHES the odds sample's fixtures end to
end through the real watcher and the real scan, that the Gamma normaliser reads
the two market shapes seen live (yes/no, and team-vs-team), that the live path
never touches the network unless asked, and that polling writes only on change.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cross_market.hud import scan_cross_market
from cross_market.ingestors.polymarket_fetcher import (DEFAULT_DROP_DIR, DEFAULT_DROP_NAME,
                                                       SPORTS_TAG_ID, FetchError, fetch_events,
                                                       fingerprint, json_list, looks_like_team, main,
                                                       normalise_event, normalise_events, poll,
                                                       sample_questions, sport_of,
                                                       validate_questions, write_drop)
from cross_market.interfaces.obsidian_exporter import DEFAULT_QUESTIONS_DIR, load_questions
from cross_market.matcher import MONEYLINE, SPREAD, TOTALS, parse_polymarket_question
from Sports_Desk.ingestors.odds_fetcher import run_watcher, sample_rows
from Sports_Desk.ingestors.odds_fetcher import write_drop as write_odds_drop

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


class FakeHook:
    config = {"tax_rates": {"short_term_capital_gains": 0.24,
                            "state_tax_rate": 0.0637, "safety_buffer_pct": 0.02}}

    def get_safe_bankroll(self, live_cash=None):
        return 10_000.0


class Base(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drop = self.root / "polymarket_drops"

    def tearDown(self):
        self.temp.cleanup()


# ---------------------------------------------------------------------------
# The sample
# ---------------------------------------------------------------------------

class TestSample(Base):

    def test_every_sample_question_is_in_the_shape_the_consumer_reads(self):
        questions = sample_questions(now=NOW)
        self.assertGreaterEqual(len(questions), 6)
        for q in questions:
            for key in ("question", "yes_price", "token_id", "sport"):
                self.assertIn(key, q)
            self.assertTrue(0.0 < q["yes_price"] < 1.0)
            self.assertEqual(q["fee_rate"], 0.0)
            self.assertEqual(q["fetched_at"], "2026-09-04T12:00:00Z")

    def test_every_sample_question_parses_into_a_hedgeable_market(self):
        kinds = []
        for q in sample_questions(now=NOW):
            parsed = parse_polymarket_question(q["question"], sport=q["sport"],
                                               token_id=q["token_id"], yes_price=q["yes_price"])
            self.assertIsNotNone(parsed, q["question"])
            kinds.append(parsed.market_type)
        self.assertIn(MONEYLINE, kinds)
        self.assertIn(TOTALS, kinds)
        self.assertIn(SPREAD, kinds)

    def test_the_drop_dir_is_the_one_the_exporter_reads(self):
        self.assertEqual(DEFAULT_DROP_DIR, DEFAULT_QUESTIONS_DIR)

    def test_sample_matches_the_odds_samples_fixtures_end_to_end(self):
        """
        THE POINT OF THE TARGET: questions -> matcher -> real sports_market.db rows
        -> priced pairs, every market type included.
        """
        odds_drop = self.root / "odds_drops"
        db = self.root / "sports_market.db"
        write_odds_drop(sample_rows(now=NOW), odds_drop, name="odds.csv")
        run_watcher(odds_drop, db, archive=False)
        self.assertTrue(db.exists())

        results, pairs = scan_cross_market(FakeHook(), sample_questions(now=NOW), db_path=db,
                                           capital=1_000.0)
        # Round 35 (Ruling 5.B): the spread leg is stored under its own signed
        # handicap, so the seventh question matches too - 7 of 7.
        self.assertEqual(len(pairs), 7)
        matched = {p.market.market_type for p in pairs}
        self.assertEqual(matched, {MONEYLINE, TOTALS, SPREAD})
        spread = [p for p in pairs if p.market.market_type == SPREAD][0]
        self.assertEqual((spread.book_selection, spread.target.line), ("Cowboys", "+6.5"))
        # Every sample pair is priced, and none survives the tax: the worst branch
        # returns less than the capital staked. Real cross-market arbs pay 1-3%.
        self.assertEqual(len(results), len(pairs))
        self.assertTrue(all(r.worst_after_tax < r.capital for r in results),
                        [(r.gross_arb, r.worst_after_tax) for r in results])
        self.assertTrue(all(r.gross_arb < 0.10 for r in results))

    def test_fingerprint_is_by_price_not_by_timestamp(self):
        a = sample_questions(now=NOW)
        b = sample_questions(now=datetime(2026, 9, 5, tzinfo=timezone.utc))
        self.assertEqual(fingerprint(a), fingerprint(b))
        b[0]["yes_price"] += 0.01
        self.assertNotEqual(fingerprint(a), fingerprint(b))


# ---------------------------------------------------------------------------
# Gamma normalisation - the two shapes seen live on 2026-09-04
# ---------------------------------------------------------------------------

def gamma_event(**overrides):
    event = {
        "title": "St. Louis Cardinals vs. Los Angeles Dodgers",
        "slug": "mlb-stl-lad-2026-09-03", "startDate": "2026-09-03T23:10:00Z",
        "volume24hr": "12345.6",
        "tags": [{"id": "1", "label": "Sports", "slug": "sports"},
                 {"id": "100", "label": "MLB", "slug": "mlb"}],
        "markets": [{
            "question": "St. Louis Cardinals vs. Los Angeles Dodgers",
            "conditionId": "0xabc", "slug": "mlb-stl-lad-2026-09-03",
            "outcomes": '["St. Louis Cardinals", "Los Angeles Dodgers"]',
            "outcomePrices": '["0.595", "0.405"]',
            "clobTokenIds": '["876119152467", "744473264035"]',
            "bestAsk": 0.6, "bestBid": 0.59, "spread": 0.01,
            "active": True, "closed": False, "takerBaseFee": 0,
        }],
    }
    event.update(overrides)
    return event


class TestGammaNormalisation(unittest.TestCase):

    def test_json_encoded_lists_are_decoded(self):
        self.assertEqual(json_list('["a", "b"]'), ["a", "b"])
        self.assertEqual(json_list(["a"]), ["a"])
        self.assertEqual(json_list("junk"), [])
        self.assertEqual(json_list(None), [])

    def test_sport_comes_from_the_tags(self):
        self.assertEqual(sport_of(gamma_event()), "MLB")
        tennis = gamma_event(tags=[{"label": "Sports", "slug": "sports"}, {"label": "Tennis", "slug": "tennis"}])
        self.assertIsNone(sport_of(tennis))

    def test_a_fixture_market_becomes_two_derived_questions_that_resolve(self):
        out = normalise_event(gamma_event(), fetched_at="2026-09-04T12:00:00Z")
        self.assertEqual(out["skipped"], {})
        self.assertEqual(len(out["questions"]), 2)
        first, second = out["questions"]
        self.assertEqual(first["question"], "Will the St. Louis Cardinals beat the Los Angeles Dodgers?")
        self.assertEqual(first["yes_price"], 0.6)                 # bestAsk: what a YES costs to buy
        self.assertEqual(first["price_basis"], "best_ask")
        self.assertEqual(first["token_id"], "876119152467")
        self.assertEqual(second["question"], "Will the Los Angeles Dodgers beat the St. Louis Cardinals?")
        # Round 35: outcome 1's executable ask is the WORSE of its posted price
        # (0.405) and 1 - outcome 0's bid (1 - 0.59 = 0.41).
        self.assertAlmostEqual(second["yes_price"], 0.41, places=9)
        self.assertEqual(second["price_basis"], "mirrored_bid")
        self.assertEqual(second["token_id"], "744473264035")
        for q in (first, second):
            self.assertEqual(q["derived_from"], "St. Louis Cardinals vs. Los Angeles Dodgers")
            self.assertEqual(q["sport"], "MLB")
            self.assertEqual(q["fee_rate"], 0.0)                  # never inferred
            self.assertEqual(q["taker_base_fee_raw"], 0)
            parsed = parse_polymarket_question(q["question"], sport=q["sport"])
            self.assertIsNotNone(parsed, q["question"])
            self.assertEqual(parsed.market_type, MONEYLINE)
        self.assertEqual(parse_polymarket_question(first["question"], sport="MLB").yes_team.canonical,
                         "STL_CARDINALS")
        self.assertEqual(parse_polymarket_question(second["question"], sport="MLB").yes_team.canonical,
                         "LAD_DODGERS")

    def test_a_yes_no_market_is_one_question_priced_at_the_ask(self):
        event = gamma_event(markets=[{
            "question": "Will the Chiefs beat the Ravens?", "conditionId": "0x1",
            "outcomes": '["Yes", "No"]', "outcomePrices": '["0.55", "0.45"]',
            "clobTokenIds": '["t-yes", "t-no"]', "bestAsk": 0.56, "bestBid": 0.54}],
            tags=[{"label": "Sports"}, {"label": "NFL"}])
        out = normalise_event(event)
        self.assertEqual(len(out["questions"]), 1)
        q = out["questions"][0]
        self.assertEqual((q["question"], q["yes_price"], q["token_id"], q["sport"]),
                         ("Will the Chiefs beat the Ravens?", 0.56, "t-yes", "NFL"))
        self.assertEqual(q["yes_bid"], 0.54)

    def test_second_leg_falls_back_to_the_posted_price_without_a_bid(self):
        event = gamma_event()
        del event["markets"][0]["bestBid"]
        second = normalise_event(event)["questions"][1]
        self.assertEqual((second["yes_price"], second["price_basis"]), (0.405, "outcome_price"))
        # A posted price ABOVE the mirrored bid is kept: the worse number wins.
        event = gamma_event()
        event["markets"][0]["outcomePrices"] = '["0.55", "0.45"]'
        second = normalise_event(event)["questions"][1]
        self.assertEqual((second["yes_price"], second["price_basis"]), (0.45, "outcome_price"))

    def test_totals_and_spread_outcomes_are_not_rewritten_as_fixtures(self):
        for outcomes in ('["Over 47.5", "Under 47.5"]', '["Eagles -6.5", "Cowboys +6.5"]',
                         '["O 47.5", "Under"]'):
            event = gamma_event()
            event["markets"][0]["outcomes"] = outcomes
            out = normalise_event(event)
            self.assertEqual(out["questions"], [], outcomes)
            self.assertEqual(out["skipped"], {"not_a_fixture_market": 1}, outcomes)
        self.assertTrue(looks_like_team("St. Louis Cardinals"))
        self.assertTrue(looks_like_team("49ers"))                 # a digit alone is not a spread
        self.assertFalse(looks_like_team("Chiefs -3.5"))
        self.assertFalse(looks_like_team(""))

    def test_what_is_skipped_is_counted_by_reason(self):
        tennis = gamma_event(tags=[{"label": "Tennis"}])
        self.assertEqual(normalise_event(tennis)["skipped"], {"not_a_traded_league": 1})

        closed = gamma_event()
        closed["markets"][0]["closed"] = True
        self.assertEqual(normalise_event(closed)["skipped"], {"closed_or_inactive": 1})

        dead = gamma_event()
        dead["markets"][0].update({"bestAsk": 0.001, "outcomePrices": '["0", "1"]'})
        self.assertEqual(normalise_event(dead)["skipped"], {"dead_or_unpriced": 1})

        futures = gamma_event()
        futures["markets"][0].update({"outcomes": '["A", "B", "C"]', "clobTokenIds": '["1","2","3"]'})
        self.assertEqual(normalise_event(futures)["skipped"], {"not_two_outcomes": 1})

        both = normalise_events([gamma_event(), tennis, closed])
        self.assertEqual(both["events"], 3)
        self.assertEqual(len(both["questions"]), 2)
        self.assertEqual(both["skipped"], {"not_a_traded_league": 1, "closed_or_inactive": 1})


# ---------------------------------------------------------------------------
# Fetching and validation
# ---------------------------------------------------------------------------

class TestFetch(unittest.TestCase):

    def test_fetch_pages_with_the_verified_tag_id_and_never_the_ignored_tag_slug(self):
        calls = []

        def getter(url, params, timeout):
            calls.append(dict(params))
            if params["offset"] == 0:
                return [gamma_event(slug="a")] * 2
            return [gamma_event(slug="b")]

        events = fetch_events("http://example.invalid/events", limit=2, pages=5, getter=getter)
        self.assertEqual(len(events), 3)
        self.assertEqual([c["offset"] for c in calls], [0, 2])
        for c in calls:
            self.assertEqual(c["tag_id"], SPORTS_TAG_ID)
            self.assertEqual(c["closed"], "false")
            self.assertNotIn("tag", c)

    def test_a_non_list_payload_is_refused(self):
        with self.assertRaises(FetchError):
            fetch_events("http://example.invalid", getter=lambda u, p, t: {"error": "nope"})

    def test_the_offline_path_never_imports_requests(self):
        import sys
        before = "requests" in sys.modules
        sample_questions()
        normalise_events([gamma_event()])
        if not before:
            self.assertNotIn("requests", sys.modules)

    def test_validation_refuses_what_the_consumer_could_not_price(self):
        with self.assertRaises(FetchError):
            validate_questions({"not": "a list"})
        with self.assertRaises(FetchError):
            validate_questions([])
        with self.assertRaises(FetchError):
            validate_questions([{"question": "x", "yes_price": 0.5}])          # no token
        with self.assertRaises(FetchError):
            validate_questions([{"question": "x", "yes_price": 1.5, "token_id": "t"}])
        ok = validate_questions([{"question": "x", "yes_price": "0.5", "token_id": "t"}])
        self.assertEqual(len(ok), 1)


# ---------------------------------------------------------------------------
# Writing and polling
# ---------------------------------------------------------------------------

class TestWriteAndPoll(Base):

    def test_write_drop_overwrites_one_current_file_that_the_exporter_loads(self):
        target = write_drop(sample_questions(now=NOW), self.drop)
        self.assertEqual(target.name, DEFAULT_DROP_NAME)
        loaded = load_questions(self.drop)
        self.assertEqual(len(loaded), len(sample_questions(now=NOW)))
        changed = sample_questions(now=NOW)
        changed[0]["yes_price"] = 0.61
        write_drop(changed, self.drop)
        self.assertEqual(len(list(self.drop.glob("*.json"))), 1)
        self.assertEqual([q for q in load_questions(self.drop) if q["token_id"] == changed[0]["token_id"]][0]["yes_price"], 0.61)

    def test_poll_writes_only_when_prices_change(self):
        prices = iter([0.55, 0.55, 0.60, 0.60])
        logs = []

        def source():
            qs = sample_questions(now=NOW)
            qs[0]["yes_price"] = next(prices)
            return qs

        stats = poll(source, self.drop, interval=0, max_polls=4, sleep=lambda s: None, log=logs.append)
        self.assertEqual(stats, {"polls": 4, "drops": 2, "skipped_unchanged": 2, "errors": 0,
                                 "stamped": 0, "pruned": 0})                     # Round 52: stamp counters, off here
        self.assertTrue(any(line.startswith("[SKIP]") for line in logs))
        self.assertEqual(load_questions(self.drop)[0]["yes_price"], 0.60)

    def test_poll_survives_a_failing_source(self):
        calls = {"n": 0}

        def source():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("gamma down")
            return sample_questions(now=NOW)

        stats = poll(source, self.drop, interval=0, max_polls=2, sleep=lambda s: None, log=lambda m: None)
        self.assertEqual((stats["errors"], stats["drops"]), (1, 1))

    def test_cli_sample_and_watch_run_offline(self):
        self.assertEqual(main(["--sample", "--folder", str(self.drop)]), 0)
        self.assertTrue((self.drop / DEFAULT_DROP_NAME).exists())
        self.assertEqual(main(["--sample", "--folder", str(self.drop), "--watch", "--interval", "0",
                               "--max-polls", "2"]), 0)
        # Round 52 (Ruling 51-1): --watch also writes ONE stamped copy per change beside the canonical file.
        names = sorted(f.name for f in self.drop.glob("*.json"))
        self.assertEqual(len(names), 2)
        self.assertIn(DEFAULT_DROP_NAME, names)
        self.assertTrue(any(n.startswith("polymarket_2") and n.endswith("Z.json") for n in names))
        self.assertEqual(main(["--sample", "--folder", str(self.drop), "--watch", "--interval", "0",
                               "--max-polls", "1", "--no-stamp"]), 0)
        self.assertEqual(len(list(self.drop.glob("*.json"))), 2)                 # --no-stamp adds nothing


class TestExporterDedup(Base):

    def test_the_newest_file_wins_for_the_same_market(self):
        import os
        import time
        self.drop.mkdir()
        old = self.drop / "a.json"
        new = self.drop / "b.json"
        old.write_text(json.dumps([{"question": "q", "yes_price": 0.3, "token_id": "t"}]), encoding="utf-8")
        new.write_text(json.dumps([{"question": "q", "yes_price": 0.4, "token_id": "t"},
                                   {"question": "other", "yes_price": 0.5, "token_id": "u"}]), encoding="utf-8")
        stamp = time.time()
        os.utime(old, (stamp - 100, stamp - 100))
        os.utime(new, (stamp, stamp))
        loaded = load_questions(self.drop)
        self.assertEqual(len(loaded), 2)
        self.assertEqual([q["yes_price"] for q in loaded if q["token_id"] == "t"], [0.4])


class TestStampedDrops(Base):
    """Round 52 (Ruling 51-1): a change writes the canonical file AND a stamped copy; old copies are pruned by name."""

    def test_stamped_copies_accumulate_only_on_change_and_the_exporter_still_reads_the_latest(self):
        from datetime import timedelta
        from cross_market.ingestors.polymarket_fetcher import (is_stamped_drop, poll, prune_stamped_drops,
                                                               stamp_of, stamped_drop_name)
        from cross_market import lead_lag
        moments = iter(NOW + timedelta(minutes=5 * i) for i in range(20))
        prices = iter([0.55, 0.55, 0.60, 0.60])
        base = sample_questions(now=NOW)

        def source():
            price = next(prices)
            return [dict(base[0], yes_price=str(price))] + base[1:]

        logs = []
        stats = poll(source, self.drop, interval=0, max_polls=4, sleep=lambda s: None, log=logs.append,
                     stamped=True, clock=lambda: next(moments))
        self.assertEqual((stats["drops"], stats["stamped"], stats["skipped_unchanged"]), (2, 2, 2))
        files = sorted(self.drop.glob("*.json"))
        stamped = [f for f in files if is_stamped_drop(f)]
        self.assertEqual(len(stamped), 2)
        self.assertIn(self.drop / DEFAULT_DROP_NAME, files)
        self.assertFalse(is_stamped_drop(self.drop / DEFAULT_DROP_NAME))
        self.assertEqual(stamp_of(stamped[0]), NOW)                              # the clock, to the microsecond
        self.assertIsNone(stamp_of(self.drop / DEFAULT_DROP_NAME))
        self.assertEqual(stamped_drop_name(NOW), "polymarket_20260904T120000_000000Z.json")
        # The exporter still sees ONE price per market - the newest.
        loaded = load_questions(self.drop)
        self.assertEqual([float(q["yes_price"]) for q in loaded if q["token_id"] == base[0]["token_id"]], [0.6])
        # And Item 18 sees the series: two observations of the moved market.
        series = lead_lag.probability_series(lead_lag.load_drop_records([self.drop]))
        self.assertEqual(len(series[base[0]["token_id"]]), 3)                    # canonical + 2 stamped
        self.assertEqual(len(lead_lag.probability_shifts(series, min_shift=0.02)), 1)
        # Retention prunes by the stamp in the name, never the canonical file.
        deleted = prune_stamped_drops(self.drop, retention_hours=192.0, now=NOW + timedelta(hours=192, minutes=1))
        self.assertEqual([d.name for d in deleted], [stamped[0].name])           # the first copy is 192h01m old
        self.assertTrue((self.drop / DEFAULT_DROP_NAME).exists())
        self.assertEqual(len([f for f in self.drop.glob("*.json") if is_stamped_drop(f)]), 1)
        self.assertEqual(prune_stamped_drops(self.root / "absent"), [])

    def test_watch_without_stamps_behaves_as_before(self):
        from cross_market.ingestors.polymarket_fetcher import poll
        stats = poll(lambda: sample_questions(now=NOW), self.drop, interval=0, max_polls=2,
                     sleep=lambda s: None, log=lambda m: None, stamped=False)
        self.assertEqual((stats["drops"], stats["stamped"]), (1, 0))
        self.assertEqual([f.name for f in self.drop.glob("*.json")], [DEFAULT_DROP_NAME])


class TestTagsAndKeywords(unittest.TestCase):
    """Round 52 (Ruling 51-2): one watcher, several Gamma tags; non-sports tags are labelled and keyword-filtered."""

    @staticmethod
    def crypto_event(question, ask, token):
        return {"slug": "btc-100k", "title": question, "tags": [{"label": "Crypto"}], "volume24hr": "1000",
                "markets": [{"question": question, "outcomes": json.dumps(["Yes", "No"]),
                             "outcomePrices": json.dumps(["0.6", "0.4"]), "clobTokenIds": json.dumps([token, token + "n"]),
                             "bestAsk": ask, "bestBid": ask - 0.02, "active": True, "closed": False,
                             "conditionId": "c-" + token, "slug": "m-" + token}]}

    def test_fetch_by_tag_slug_sends_the_slug_and_not_the_sports_id(self):
        from cross_market.ingestors.polymarket_fetcher import fetch_events
        calls = []

        def getter(url, params, timeout):
            calls.append(dict(params))
            return []

        fetch_events("http://example.invalid/events", getter=getter, tag_slug="crypto")
        self.assertEqual(calls[0]["tag_slug"], "crypto")
        self.assertNotIn("tag_id", calls[0])

    def test_a_non_sports_event_is_kept_under_its_category_only_when_asked(self):
        from cross_market.ingestors.polymarket_fetcher import normalise_event
        event = self.crypto_event("Will Bitcoin hit $100k in 2026?", 0.64, "tok-btc")
        self.assertEqual(normalise_event(event)["skipped"], {"not_a_traded_league": 1})
        result = normalise_event(event, category="crypto")
        self.assertEqual(len(result["questions"]), 1)
        q = result["questions"][0]
        self.assertEqual((q["sport"], q["yes_price"], q["token_id"]), ("CRYPTO", 0.64, "tok-btc"))

    def test_keywords_narrow_non_sports_tags_and_tokens_are_deduplicated(self):
        from cross_market.ingestors.polymarket_fetcher import collect_live_questions, filter_by_keywords
        from cross_market.tests.test_polymarket_fetcher import gamma_event
        payload = {"sports": [gamma_event(slug="a")],
                   "crypto": [self.crypto_event("Will Bitcoin hit $100k in 2026?", 0.64, "tok-btc"),
                              self.crypto_event("Will Ethereum flip Bitcoin?", 0.05, "tok-flip"),
                              self.crypto_event("Kraken IPO by 2027?", 0.30, "tok-ipo")],
                   "fed-rates": [self.crypto_event("Fed rate cut in September?", 0.88, "tok-fed")]}
        calls = []

        def getter(url, params, timeout):
            calls.append(dict(params))
            if params.get("offset"):
                return []
            return payload["sports"] if "tag_id" in params else payload[params["tag_slug"]]

        questions = collect_live_questions("http://example.invalid/events", ["sports", "crypto", "fed-rates"],
                                           keywords=["bitcoin", "fed"], getter=getter, log=lambda m: None)
        sports = [q for q in questions if q["sport"] not in ("CRYPTO", "FED-RATES")]
        self.assertGreaterEqual(len(sports), 1)                                    # the fixture path is untouched
        self.assertEqual({q["token_id"] for q in questions if q["sport"] == "CRYPTO"}, {"tok-btc", "tok-flip"})
        self.assertEqual([q["token_id"] for q in questions if q["sport"] == "FED-RATES"], ["tok-fed"])
        self.assertNotIn("tok-ipo", {q["token_id"] for q in questions})            # no keyword: dropped
        self.assertEqual([c.get("tag_id") for c in calls if "tag_id" in c], [SPORTS_TAG_ID])
        self.assertEqual({c["tag_slug"] for c in calls if "tag_slug" in c}, {"crypto", "fed-rates"})
        self.assertEqual(filter_by_keywords([{"question": "A"}], []), [{"question": "A"}])
        # And the Titan macro lookup reads these questions straight from a drop.
        from cross_market.titan_correlator import BTC_MILESTONE_KEYWORDS, FED_CUT_KEYWORDS, find_market_probability
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "polymarket_macro.json").write_text(json.dumps(questions), encoding="utf-8")
            self.assertAlmostEqual(find_market_probability(BTC_MILESTONE_KEYWORDS, [Path(tmp)])["probability"], 0.64)
            self.assertAlmostEqual(find_market_probability(FED_CUT_KEYWORDS, [Path(tmp)])["probability"], 0.88)


    def test_a_market_under_several_tags_keeps_its_first_label_and_records_every_tag(self):
        # Round 76 (Directive 76-2): additive `tags`; `sport` unchanged so Tier 1, the registered Tier 2
        # filter and the sportsbook matcher read exactly what they read before.
        from cross_market.ingestors.polymarket_fetcher import collect_live_questions, validate_questions, write_drop
        from cross_market.lead_lag import record_subfamily
        from cross_market.tests.test_polymarket_fetcher import gamma_event
        both = self.crypto_event("Will the Fed cut send Bitcoin to $100k?", 0.42, "tok-both")
        payload = {"sports": [gamma_event(slug="a")],
                   "crypto": [both, self.crypto_event("Will Bitcoin hit $100k in 2026?", 0.64, "tok-btc")],
                   "fed-rates": [both, self.crypto_event("Fed rate cut in September?", 0.88, "tok-fed")]}

        def getter(url, params, timeout):
            if params.get("offset"):
                return []
            return payload["sports"] if "tag_id" in params else payload[params["tag_slug"]]

        questions = collect_live_questions("http://example.invalid/events", ["sports", "crypto", "fed-rates"],
                                           keywords=["bitcoin", "fed"], getter=getter, log=lambda m: None)
        by_token = {q["token_id"]: q for q in questions}
        self.assertEqual(len(questions), len(by_token))                       # still one record per token
        self.assertEqual((by_token["tok-both"]["sport"], by_token["tok-both"]["tags"]), ("CRYPTO", ["crypto", "fed-rates"]))
        self.assertEqual(by_token["tok-btc"]["tags"], ["crypto"])
        self.assertEqual(by_token["tok-fed"]["tags"], ["fed-rates"])
        sports = [q for q in questions if q["sport"] not in ("CRYPTO", "FED-RATES")]
        self.assertTrue(sports and all(q["tags"] == ["sports"] for q in sports))
        self.assertEqual(record_subfamily(by_token["tok-both"]), "crypto")     # the registered filter is untouched
        # the field survives validation and lands in the drop
        clean = validate_questions(questions)
        with tempfile.TemporaryDirectory() as tmp:
            target = write_drop(clean, Path(tmp), name="polymarket_macro.json")
            stored = json.loads(Path(target).read_text(encoding="utf-8"))
            self.assertEqual(next(q for q in stored if q["token_id"] == "tok-both")["tags"], ["crypto", "fed-rates"])


class TestTagFamilies(Base):
    """Round 53 (Ruling 53-3): sports and macro questions land in separate canonical files, stamped per family."""

    def test_multi_tag_polls_write_one_canonical_file_per_family(self):
        from datetime import timedelta
        from cross_market.ingestors.polymarket_fetcher import (MACRO_DROP_NAME, family_of, is_stamped_drop,
                                                               poll, prune_stamped_drops, split_families, stamp_of)
        from cross_market import lead_lag
        sports = sample_questions(now=NOW)
        macro = [{"question": "Will Bitcoin reach $100,000 in September?", "yes_price": "0.05", "yes_bid": "0.04",
                  "token_id": "tok-btc", "sport": "CRYPTO", "fetched_at": "2026-09-04T12:00:00Z", "source": "gamma",
                  "fee_rate": 0.0, "event_slug": "btc", "start_time": ""},
                 {"question": "Fed rate cut in September?", "yes_price": "0.88", "yes_bid": "0.87",
                  "token_id": "tok-fed", "sport": "FED-RATES", "fetched_at": "2026-09-04T12:00:00Z", "source": "gamma",
                  "fee_rate": 0.0, "event_slug": "fed", "start_time": ""}]
        self.assertEqual(family_of(sports[0]), "sports")
        self.assertEqual(family_of(macro[0]), "macro")
        self.assertEqual({k: len(v) for k, v in split_families(sports + macro).items()}, {"sports": len(sports), "macro": 2})

        prices = iter([0.05, 0.05, 0.12, 0.12])             # only the BTC macro market moves, on poll 3
        moments = iter(NOW + timedelta(minutes=5 * i) for i in range(20))

        def source():
            price = next(prices)
            return sports + [dict(macro[0], yes_price=str(price)), macro[1]]

        stats = poll(source, self.drop, interval=0, max_polls=4, sleep=lambda s: None, log=lambda m: None,
                     stamped=True, clock=lambda: next(moments), split=True)
        # Poll 1 writes both families; poll 3 rewrites macro only (sports unchanged, not re-stamped).
        self.assertEqual((stats["drops"], stats["stamped"], stats["skipped_unchanged"]), (3, 3, 5))
        sports_file = json.loads((self.drop / DEFAULT_DROP_NAME).read_text(encoding="utf-8"))
        macro_file = json.loads((self.drop / MACRO_DROP_NAME).read_text(encoding="utf-8"))
        self.assertTrue(all(q["sport"] not in ("CRYPTO", "FED-RATES") for q in sports_file))   # the arb desk's file is clean
        self.assertEqual({q["token_id"] for q in macro_file}, {"tok-btc", "tok-fed"})
        self.assertEqual(float(next(q for q in macro_file if q["token_id"] == "tok-btc")["yes_price"]), 0.12)
        names = sorted(f.name for f in self.drop.glob("polymarket_*Z.json"))
        self.assertEqual([n.split("_")[1] for n in names], ["macro", "macro", "sports"])
        self.assertTrue(all(is_stamped_drop(self.drop / n) and stamp_of(self.drop / n) is not None for n in names))
        # The exporter's dedup still yields one price per market; Item 18 sees the macro series and its one shift.
        loaded = load_questions(self.drop)
        self.assertEqual([float(q["yes_price"]) for q in loaded if q["token_id"] == "tok-btc"], [0.12])
        series = lead_lag.probability_series(lead_lag.load_drop_records([self.drop]))
        self.assertEqual(len(lead_lag.probability_shifts({"tok-btc": series["tok-btc"]}, min_shift=0.02)), 1)
        # Retention prunes family-stamped copies by name too. The fake clock ticks 5 min per call
        # (write, then prune), so the poll-1 copies are stamped NOW (sports) and NOW+10m (macro).
        deleted = prune_stamped_drops(self.drop, retention_hours=192.0, now=NOW + timedelta(hours=192, minutes=11))
        self.assertEqual(sorted(d.name.split("_")[1] for d in deleted), ["macro", "sports"])   # the two poll-1 copies
        self.assertTrue((self.drop / DEFAULT_DROP_NAME).exists() and (self.drop / MACRO_DROP_NAME).exists())

    def test_a_single_tag_run_keeps_one_file_and_unstamped_names(self):
        from cross_market.ingestors.polymarket_fetcher import poll, stamped_drop_name
        stats = poll(lambda: sample_questions(now=NOW), self.drop, interval=0, max_polls=1,
                     sleep=lambda s: None, log=lambda m: None, stamped=True, clock=lambda: NOW)
        self.assertEqual(stats["drops"], 1)
        self.assertEqual(sorted(f.name for f in self.drop.glob("*.json")),
                         sorted([DEFAULT_DROP_NAME, "polymarket_20260904T120000_000000Z.json"]))
        self.assertEqual(stamped_drop_name(NOW, family="macro"), "polymarket_macro_20260904T120000_000000Z.json")


if __name__ == "__main__":
    unittest.main()


class TestWatcherLock(Base):
    """
    Round 55 (Directive 55-1). One watcher per drop folder. Semantics mirror
    the collector supervisor: dead / corrupt / not-a-watcher pid files are
    swept, a live watcher refuses the newcomer, orderly exits release, and the
    liveness probe never touches the process it inspects.
    """

    def setUp(self):
        super().setUp()
        self.folder = Path(self.temp.name)
        self.lock = self.folder / "polymarket_watcher.pid"

    @staticmethod
    def watcher_cmdline(pid):
        return "python -m cross_market.ingestors.polymarket_fetcher --live --watch"

    def test_acquire_claims_and_release_removes_only_our_own_file(self):
        from cross_market.ingestors import pid_lock
        self.assertIsNone(pid_lock.acquire(self.lock, pid=os.getpid()))
        self.assertEqual(pid_lock.read_pid_file(self.lock), os.getpid())
        self.assertIsNone(pid_lock.acquire(self.lock, pid=os.getpid()))      # re-acquire by the holder: fine
        self.assertFalse(pid_lock.release(self.lock, pid=os.getpid() + 1))  # not ours: left alone
        self.assertTrue(self.lock.exists())
        self.assertTrue(pid_lock.release(self.lock, pid=os.getpid()))
        self.assertFalse(self.lock.exists())
        self.assertFalse(pid_lock.release(self.lock, pid=os.getpid()))      # already gone

    def test_stale_files_are_swept_dead_corrupt_or_not_a_watcher(self):
        from cross_market.ingestors import pid_lock
        self.lock.write_text("garbage", encoding="utf-8")
        self.assertTrue(pid_lock.is_stale(self.lock))
        self.assertIsNone(pid_lock.acquire(self.lock, pid=os.getpid()))      # corrupt: swept, claimed
        self.lock.write_text("0", encoding="utf-8")
        self.assertTrue(pid_lock.is_stale(self.lock))                       # non-positive: corrupt
        self.lock.write_text(str(os.getppid()), encoding="utf-8")
        self.assertTrue(pid_lock.is_stale(self.lock, alive=lambda pid: False))          # dead
        self.assertTrue(pid_lock.is_stale(self.lock, probe=lambda pid: "cmd.exe /c something"))  # live, not a watcher
        self.assertFalse(pid_lock.is_stale(self.lock, probe=self.watcher_cmdline))       # live watcher: holder
        self.assertFalse(pid_lock.is_stale(self.lock, probe=lambda pid: None))           # no psutil: assume holder
        self.assertTrue(pid_lock.remove_stale_pid_file(self.lock, probe=lambda pid: "explorer.exe"))
        self.assertFalse(self.lock.exists())
        self.assertFalse(pid_lock.remove_stale_pid_file(self.lock))         # nothing to remove

    def test_a_live_watcher_refuses_the_newcomer(self):
        from cross_market.ingestors import pid_lock
        parent = os.getppid()
        self.lock.write_text("%d\n" % parent, encoding="utf-8")
        self.assertEqual(pid_lock.acquire(self.lock, pid=os.getpid(), probe=self.watcher_cmdline), parent)
        self.assertEqual(pid_lock.read_pid_file(self.lock), parent)         # untouched
        # The same live pid that is NOT a watcher is a reused pid: swept and claimed.
        self.assertIsNone(pid_lock.acquire(self.lock, pid=os.getpid(), probe=lambda pid: "notepad.exe"))
        self.assertEqual(pid_lock.read_pid_file(self.lock), os.getpid())

    def test_two_starters_that_both_saw_a_stale_file_cannot_both_claim(self):
        # Round 55: two watchers starting within the same second both find the
        # predecessor's stale file and both sweep it; a plain write would let
        # both run. The exclusive create leaves exactly one; the loser gets the
        # winner's pid, or -1 while the winner's pid is not readable yet.
        from unittest import mock
        from cross_market.ingestors import pid_lock
        parent = os.getppid()
        self.lock.write_text("999999\n", encoding="utf-8")                   # the dead predecessor
        real_sweep = pid_lock.remove_stale_pid_file

        def sweep_then_lose_the_race(path, probe=None, mark=pid_lock.WATCHER_MARK, alive=None):
            removed = real_sweep(path, probe, mark, alive)
            Path(path).write_text("%d\n" % parent, encoding="utf-8")        # the other starter claimed first
            return removed

        with mock.patch.object(pid_lock, "remove_stale_pid_file", sweep_then_lose_the_race):
            self.assertEqual(pid_lock.acquire(self.lock, pid=os.getpid(), probe=self.watcher_cmdline,
                                              alive=lambda pid: pid == parent), parent)
        self.assertEqual(pid_lock.read_pid_file(self.lock), parent)         # the winner's file is intact
        self.lock.write_text("", encoding="utf-8")                          # exists, not readable yet
        with mock.patch.object(pid_lock, "remove_stale_pid_file", lambda *a, **k: False), \
                mock.patch.object(pid_lock.time, "sleep", lambda s: None):
            self.assertEqual(pid_lock.acquire(self.lock, pid=os.getpid()), -1)
        # A dead holder that reappears between sweep and create is swept on the retry.
        calls = {"n": 0}

        def sweep_then_a_dead_holder_reappears(path, probe=None, mark=pid_lock.WATCHER_MARK, alive=None):
            removed = real_sweep(path, probe, mark, alive)
            calls["n"] += 1
            if calls["n"] == 1:
                Path(path).write_text("999999\n", encoding="utf-8")
            return removed

        self.lock.unlink()
        with mock.patch.object(pid_lock, "remove_stale_pid_file", sweep_then_a_dead_holder_reappears), \
                mock.patch.object(pid_lock.time, "sleep", lambda s: None):
            self.assertIsNone(pid_lock.acquire(self.lock, pid=os.getpid(), alive=lambda pid: pid == os.getpid()))
        self.assertEqual(pid_lock.read_pid_file(self.lock), os.getpid())

    def test_pid_is_alive_inspects_without_killing(self):
        import subprocess
        import sys
        from cross_market.ingestors import pid_lock
        self.assertTrue(pid_lock.pid_is_alive(os.getpid()))
        self.assertFalse(pid_lock.pid_is_alive(0))
        self.assertFalse(pid_lock.pid_is_alive(-5))
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            self.assertTrue(pid_lock.pid_is_alive(child.pid))
            self.assertIsNone(child.poll())                                   # still running: the probe did not kill it
        finally:
            child.kill()
            child.wait(timeout=10)
        self.assertFalse(pid_lock.pid_is_alive(child.pid))

    def test_install_cleanup_registers_atexit_and_signal_handlers(self):
        import signal
        from cross_market.ingestors import pid_lock
        pid_lock.acquire(self.lock, pid=4242)
        registered, handlers = [], {}
        cleanup, on_signal, installed = pid_lock.install_cleanup(
            self.lock, pid=4242, register=registered.append, signals=(signal.SIGINT, 999),
            set_handler=lambda sig, fn: handlers.__setitem__(sig, fn) if sig != 999 else (_ for _ in ()).throw(ValueError("no")))
        self.assertEqual(registered, [cleanup])
        self.assertEqual(installed, (signal.SIGINT,))                       # the unsupported one was skipped
        self.assertIs(handlers[signal.SIGINT], on_signal)
        with self.assertRaises(SystemExit) as ctx:
            on_signal(signal.SIGINT, None)
        self.assertEqual(ctx.exception.code, 128 + int(signal.SIGINT))
        self.assertFalse(self.lock.exists())                                # released by the handler
        self.assertFalse(cleanup())                                         # atexit after the handler: nothing left

    def test_main_watch_refuses_a_live_watcher_and_releases_after_its_own_run(self):
        from unittest import mock
        from cross_market.ingestors import pid_lock, polymarket_fetcher
        parent = os.getppid()
        self.lock.write_text("%d\n" % parent, encoding="utf-8")
        with mock.patch.object(pid_lock, "process_cmdline", self.watcher_cmdline), \
                mock.patch("builtins.print") as fake_print:
            rc = polymarket_fetcher.main(["--watch", "--max-polls", "1", "--interval", "0",
                                          "--folder", str(self.folder)])
        self.assertEqual(rc, 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("already_running", printed)
        self.assertIn(str(parent), printed)
        self.assertFalse((self.folder / DEFAULT_DROP_NAME).exists())        # it never polled
        self.assertEqual(pid_lock.read_pid_file(self.lock), parent)         # the holder's file is intact
        # No live holder: the run claims the lock, polls once, and releases it on the way out.
        self.lock.unlink()
        with mock.patch("builtins.print"), mock.patch.object(pid_lock, "install_cleanup", lambda *a, **k: None):
            rc = polymarket_fetcher.main(["--watch", "--max-polls", "1", "--interval", "0",
                                          "--folder", str(self.folder)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.folder / DEFAULT_DROP_NAME).exists())
        self.assertFalse(self.lock.exists())
        # --pid-file relocates the lock.
        custom = self.folder / "elsewhere" / "w.pid"
        with mock.patch("builtins.print"), mock.patch.object(pid_lock, "install_cleanup", lambda *a, **k: None),                 mock.patch.object(polymarket_fetcher, "poll",
                                                             lambda *a, **k: self.assertEqual(pid_lock.read_pid_file(custom), os.getpid())):
            polymarket_fetcher.main(["--watch", "--max-polls", "1", "--folder", str(self.folder), "--pid-file", str(custom)])
        self.assertFalse(custom.exists())


class TestWatcherStatus(Base):
    """
    Round 56 (Directive 56-1). --status is the operator's read-only view: who
    holds the folder lock, whether a stale lock is lying around, and how fresh
    the newest stamped drop of each family is. Exit 0 = running, 3 = stopped,
    so a batch file can decide without parsing text.
    """

    def setUp(self):
        super().setUp()
        self.folder = Path(self.temp.name)
        self.lock = self.folder / "polymarket_watcher.pid"
        self.now = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)

    @staticmethod
    def watcher_cmdline(pid):
        return "python -m cross_market.ingestors.polymarket_fetcher --live --watch"

    def test_empty_folder_is_stopped_with_no_stamps_and_exit_3(self):
        from unittest import mock
        from cross_market.ingestors.polymarket_fetcher import (STATUS_EXIT_STOPPED, format_status, main,
                                                               watcher_status)
        info = watcher_status(self.folder, now=self.now)
        self.assertFalse(info["running"])
        self.assertIsNone(info["holder_pid"])
        self.assertFalse(info["stale_pid_file"])
        self.assertEqual(info["pid_file"], str(self.lock))
        for key in ("newest_macro_stamp", "newest_macro_age_s", "newest_sports_stamp", "newest_sports_age_s"):
            self.assertIsNone(info[key])
        text = format_status(info)
        self.assertIn("STOPPED - no lock", text)
        self.assertIn("macro:  newest stamp none", text)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(main(["--status", "--folder", str(self.folder)]), STATUS_EXIT_STOPPED)
        self.assertIn("STOPPED", fake_print.call_args_list[0].args[0])
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(main(["--status", "--json", "--folder", str(self.folder)]), STATUS_EXIT_STOPPED)
        parsed = json.loads(fake_print.call_args_list[0].args[0])
        self.assertEqual(set(parsed) >= {"running", "holder_pid", "pid_file", "newest_macro_stamp",
                                         "newest_macro_age_s", "newest_sports_stamp", "newest_sports_age_s"}, True)
        self.assertFalse((self.folder / DEFAULT_DROP_NAME).exists())        # --status never writes

    def test_newest_stamp_per_family_and_a_stale_lock(self):
        from cross_market.ingestors.polymarket_fetcher import (format_status, newest_stamped_drop,
                                                               watcher_status, write_stamped_copy)
        qs = sample_questions(now=NOW)
        write_stamped_copy(qs, self.folder, now=self.now - timedelta(minutes=10), family="macro")
        newest_macro = write_stamped_copy(qs, self.folder, now=self.now - timedelta(minutes=2), family="macro")
        write_stamped_copy(qs, self.folder, now=self.now - timedelta(minutes=30), family="sports")
        unprefixed = write_stamped_copy(qs, self.folder, now=self.now - timedelta(minutes=1))   # single-tag run
        (self.folder / "polymarket_macro.json").write_text("[]", encoding="utf-8")            # canonical: ignored
        self.assertEqual(newest_stamped_drop(self.folder, "macro")[0], newest_macro)
        self.assertEqual(newest_stamped_drop(self.folder, "sports")[0], unprefixed)            # unprefixed = sports
        self.assertIsNone(newest_stamped_drop(self.folder / "nowhere", "macro"))
        self.lock.write_text("999999\n", encoding="utf-8")                                     # a dead holder
        info = watcher_status(self.folder, now=self.now, alive=lambda pid: False)
        self.assertFalse(info["running"])
        self.assertTrue(info["stale_pid_file"])
        self.assertEqual((info["newest_macro_stamp"], info["newest_macro_age_s"]), (newest_macro.name, 120.0))
        self.assertEqual((info["newest_sports_stamp"], info["newest_sports_age_s"]), (unprefixed.name, 60.0))
        text = format_status(info)
        self.assertIn("stale lock", text)
        self.assertIn("age 2.0 min", text)
        self.assertTrue(self.lock.exists())                                                     # never swept here

    def test_a_live_holder_is_reported_with_exit_0(self):
        from unittest import mock
        from cross_market.ingestors import pid_lock
        from cross_market.ingestors.polymarket_fetcher import format_status, main, watcher_status
        parent = os.getppid()
        self.lock.write_text("%d\n" % parent, encoding="utf-8")
        info = watcher_status(self.folder, now=self.now, probe=self.watcher_cmdline)
        self.assertTrue(info["running"])
        self.assertEqual(info["holder_pid"], parent)
        self.assertFalse(info["stale_pid_file"])
        self.assertIsNotNone(info["holder_started"])                                            # psutil on this box
        text = format_status(info)
        self.assertIn("RUNNING - pid %d" % parent, text)
        with mock.patch.object(pid_lock, "process_cmdline", self.watcher_cmdline), \
                mock.patch("builtins.print") as fake_print:
            self.assertEqual(main(["--status", "--folder", str(self.folder)]), 0)
        self.assertIn("RUNNING", fake_print.call_args_list[0].args[0])
        custom = self.folder / "elsewhere.pid"
        custom.write_text("%d\n" % parent, encoding="utf-8")
        self.assertEqual(watcher_status(self.folder, pid_file=custom, probe=self.watcher_cmdline)["pid_file"],
                         str(custom))


class TestStopAndTags(Base):
    """Round 79 (Directive 79-2): --stop ends the live holder and sweeps; --status says whether the newest macro stamp carries tags."""

    def setUp(self):
        super().setUp()
        self.folder = Path(self.temp.name)
        self.lock = self.folder / "polymarket_watcher.pid"
        self.now = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)

    @staticmethod
    def watcher_cmdline(pid):
        return "pythonw -m cross_market.ingestors.polymarket_fetcher --live --watch"

    def test_stop_refuses_without_a_live_holder_sweeps_stale_and_terminates_a_live_watcher(self):
        from unittest import mock
        from cross_market.ingestors import pid_lock
        from cross_market.ingestors import polymarket_fetcher as pf
        killed = []
        info = pf.stop_watcher(self.folder, terminate=killed.append)                       # nothing to stop
        self.assertEqual((info["holder_pid"], info["terminated"], info["swept"]), (None, False, False))
        self.assertEqual(pf.stop_exit_code(info), pf.STATUS_EXIT_STOPPED)
        self.assertIn("nothing to stop", pf.format_stop(info))
        pid = os.getpid() + 40_000
        self.lock.write_text("%d\n" % pid, encoding="utf-8")                                # stale: swept, nobody killed
        info = pf.stop_watcher(self.folder, terminate=killed.append, alive=lambda p: False)
        self.assertTrue(info["swept"]) ; self.assertFalse(self.lock.exists()) ; self.assertEqual(killed, [])
        self.assertEqual(pf.stop_exit_code(info), pf.STATUS_EXIT_STOPPED)
        self.lock.write_text("%d\n" % pid, encoding="utf-8")                                # live: terminated, swept
        alive = {pid: True}

        def terminate(p):
            killed.append(p)
            alive[p] = False
        info = pf.stop_watcher(self.folder, terminate=terminate, alive=lambda p: alive.get(p, False),
                               probe=self.watcher_cmdline, sleep=lambda s: None)
        self.assertEqual((info["holder_pid"], info["terminated"], info["still_alive"], info["swept"]), (pid, True, False, True))
        self.assertEqual(killed, [pid]) ; self.assertFalse(self.lock.exists())
        self.assertEqual(pf.stop_exit_code(info), 0) ; self.assertIn("terminated", pf.format_stop(info))
        self.lock.write_text("%d\n" % pid, encoding="utf-8")                                # ignores termination
        info = pf.stop_watcher(self.folder, terminate=killed.append, alive=lambda p: True, probe=self.watcher_cmdline,
                               sleep=lambda s: None, wait_s=0.5)
        self.assertTrue(info["still_alive"]) ; self.assertTrue(self.lock.exists()) ; self.assertEqual(pf.stop_exit_code(info), 1)
        self.assertIn("STILL ALIVE", pf.format_stop(info))
        # a live process that is NOT a watcher is a stale lock, never a target
        self.lock.write_text("%d\n" % os.getpid(), encoding="utf-8")
        before = len(killed)
        info = pf.stop_watcher(self.folder, terminate=killed.append, probe=lambda p: "python -m unittest")
        self.assertEqual((info["holder_pid"], len(killed)), (None, before)) ; self.assertTrue(info["swept"])
        # the CLI: --stop with a live holder (mocked liveness + terminate), then nothing to stop, then JSON
        self.lock.write_text("%d\n" % pid, encoding="utf-8")
        alive[pid] = True
        with mock.patch.object(pid_lock, "pid_is_alive", side_effect=lambda p: alive.get(p, False)), \
                mock.patch.object(pid_lock, "process_cmdline", self.watcher_cmdline), \
                mock.patch.object(pf, "_terminate_pid", terminate), mock.patch("builtins.print") as fake_print:
            self.assertEqual(pf.main(["--stop", "--folder", str(self.folder)]), 0)
            self.assertEqual(pf.main(["--stop", "--folder", str(self.folder)]), pf.STATUS_EXIT_STOPPED)
            self.assertEqual(pf.main(["--stop", "--json", "--folder", str(self.folder)]), pf.STATUS_EXIT_STOPPED)
        printed = [str(c.args[0]) for c in fake_print.call_args_list]
        self.assertIn("terminated", printed[0]) ; self.assertIn("nothing to stop", printed[1])
        self.assertFalse(json.loads(printed[2])["terminated"])
        # the restart launcher: --stop, then the guarded launcher, then --status; no if-block traps
        dev = Path(__file__).resolve().parents[2]
        bat = (dev / "restart_polymarket_watcher.bat").read_text(encoding="utf-8", errors="replace")
        self.assertIn("polymarket_fetcher --stop", bat) ; self.assertIn('call "%~dp0start_polymarket_watcher.bat"', bat)
        self.assertLess(bat.index("--stop"), bat.index('call "%~dp0start_polymarket_watcher.bat"'))
        self.assertLess(bat.index('call "%~dp0start_polymarket_watcher.bat"'), bat.index("polymarket_fetcher --status"))
        self.assertNotIn("if errorlevel", bat)

    def test_status_reports_whether_the_newest_macro_stamp_carries_tags(self):
        from cross_market.ingestors.polymarket_fetcher import (format_status, newest_stamp_has_tags, stamped_drop_name,
                                                               watcher_status)
        self.assertIsNone(newest_stamp_has_tags(self.folder, "macro"))
        self.assertIsNone(watcher_status(self.folder, now=self.now)["newest_macro_tags"])
        self.assertNotIn("tags:", format_status(watcher_status(self.folder, now=self.now)))
        (self.folder / stamped_drop_name(self.now - timedelta(minutes=10), family="macro")).write_text(json.dumps([
            {"question": "Q?", "token_id": "t", "yes_price": 0.5, "sport": "CRYPTO"}]), encoding="utf-8")
        self.assertFalse(newest_stamp_has_tags(self.folder, "macro"))
        info = watcher_status(self.folder, now=self.now)
        self.assertFalse(info["newest_macro_tags"]) ; self.assertIn("has NO tags", format_status(info))
        (self.folder / stamped_drop_name(self.now - timedelta(minutes=5), family="macro")).write_text(json.dumps([
            {"question": "Q?", "token_id": "t", "yes_price": 0.5, "sport": "CRYPTO", "tags": ["crypto"]}]), encoding="utf-8")
        self.assertTrue(newest_stamp_has_tags(self.folder, "macro"))
        info = watcher_status(self.folder, now=self.now)
        self.assertTrue(info["newest_macro_tags"]) ; self.assertIn("carries tags", format_status(info))


class TestCallTimeDefaults(unittest.TestCase):
    """Rounds 77 and 80: poll() resolves print and time.sleep at call time, never at import time."""

    def test_log_and_sleep_defaults_are_call_time_helpers(self):
        import inspect
        from unittest import mock
        from cross_market.ingestors import polymarket_fetcher as pf
        params = inspect.signature(pf.poll).parameters
        self.assertIs(params["log"].default, pf._emit)
        self.assertIs(params["sleep"].default, pf._sleep)
        self.assertIs(inspect.signature(pf.collect_live_questions).parameters["log"].default, pf._emit)
        with mock.patch("time.sleep") as fake_sleep, mock.patch("builtins.print") as fake_print:
            pf._sleep(0.25)
            pf._emit("x")
        fake_sleep.assert_called_once_with(0.25)
        fake_print.assert_called_once_with("x")
