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
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
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
        self.assertEqual(stats, {"polls": 4, "drops": 2, "skipped_unchanged": 2, "errors": 0})
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
        self.assertEqual(len(list(self.drop.glob("*.json"))), 1)


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


if __name__ == "__main__":
    unittest.main()
