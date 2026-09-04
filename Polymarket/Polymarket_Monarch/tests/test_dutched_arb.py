"""
Tests for the negative-risk dutching scanner.

Everything here is offline - synthetic event and book payloads. The two things
worth pinning are the two mistakes the live run actually surfaced: one-sided
books inflating the sum into nonsense, and the CLOB returning asks in DESCENDING
price order (so the naive [0] prices the arb off the worst level in the book).
"""

import json
import unittest
from unittest import mock

import dutched_arb


def market(ask, bid=None, title="Outcome", token="tok"):
    return {
        "groupItemTitle": title,
        "bestAsk": ask,
        "bestBid": bid if bid is not None else (None if ask is None else round(float(ask) - 0.01, 4)),
        "clobTokenIds": json.dumps([token, token + "_no"]),
    }


def event(asks, neg_risk=True, title="Test Event"):
    return {
        "title": title,
        "slug": "test-event",
        "negRisk": neg_risk,
        "volume24hr": 1000.0,
        "markets": [market(a, title=f"O{i}", token=f"t{i}") for i, a in enumerate(asks)],
    }


class TestEventPricing(unittest.TestCase):
    def test_a_dutch_book_is_detected(self):
        r = dutched_arb.evaluate_event(event([0.30, 0.30, 0.30]))
        self.assertAlmostEqual(r["ask_sum"], 0.90, places=9)
        self.assertAlmostEqual(r["edge_pct"], 10.0, places=6)

    def test_a_normal_book_prices_above_one(self):
        r = dutched_arb.evaluate_event(event([0.34, 0.34, 0.34]))
        self.assertGreater(r["ask_sum"], 1.0)
        self.assertLess(r["edge_pct"], 0.0)

    def test_too_few_outcomes_is_not_priced(self):
        self.assertIsNone(dutched_arb.evaluate_event(event([0.4, 0.6]), min_outcomes=3))

    def test_leg_count_and_tokens_are_carried_through(self):
        r = dutched_arb.evaluate_event(event([0.3, 0.3, 0.3]))
        self.assertEqual(r["outcomes"], 3)
        self.assertEqual(r["legs"][1]["yes_token_id"], "t1")


class TestOneSidedBooksAreRejected(unittest.TestCase):
    """
    The defect the live run exposed. Illiquid long-tail outcomes quote an ask at
    or near 1.00 with nothing behind it; summing them produced totals of 77 and
    88 on real 128-outcome election events. An unbuyable leg makes the event
    UNPRICEABLE, which is not the same as expensive - so it is dropped, never
    scored.
    """

    def test_a_missing_ask_makes_the_event_unpriceable(self):
        ev = event([0.3, 0.3, 0.3])
        ev["markets"][1]["bestAsk"] = None
        self.assertIsNone(dutched_arb.evaluate_event(ev))

    def test_a_missing_bid_makes_the_event_unpriceable(self):
        ev = event([0.3, 0.3, 0.3])
        ev["markets"][1]["bestBid"] = None
        self.assertIsNone(dutched_arb.evaluate_event(ev))

    def test_an_ask_at_one_is_treated_as_no_offer(self):
        """Buying at 1.00 cannot profit even if every other leg were free."""
        self.assertIsNone(dutched_arb.evaluate_event(event([0.3, 0.3, 1.0])))

    def test_a_zero_ask_is_rejected_rather_than_read_as_free(self):
        self.assertIsNone(dutched_arb.evaluate_event(event([0.3, 0.3, 0.0])))

    def test_unparseable_prices_do_not_raise(self):
        ev = event([0.3, 0.3, 0.3])
        ev["markets"][0]["bestAsk"] = "not-a-number"
        self.assertIsNone(dutched_arb.evaluate_event(ev))


class TestBookWalking(unittest.TestCase):
    """
    The CLOB returns asks price-DESCENDING - best price LAST. Reading [0] would
    price every arb off the worst level in the book and make real edges vanish.
    """

    def book(self, levels):
        resp = mock.Mock()
        resp.json.return_value = {"asks": [{"price": str(p), "size": str(s)} for p, s in levels]}
        return resp

    def test_the_cheapest_level_is_consumed_first(self):
        with mock.patch.object(dutched_arb, "_get",
                               return_value=self.book([("0.50", "100"), ("0.30", "100")])):
            avg, filled = dutched_arb.walk_asks("t", 100)
        self.assertAlmostEqual(avg, 0.30, places=9)
        self.assertEqual(filled, 100)

    def test_a_large_order_walks_up_into_worse_levels(self):
        with mock.patch.object(dutched_arb, "_get",
                               return_value=self.book([("0.50", "100"), ("0.30", "100")])):
            avg, filled = dutched_arb.walk_asks("t", 200)
        self.assertAlmostEqual(avg, 0.40, places=9)
        self.assertEqual(filled, 200)

    def test_a_thin_book_reports_the_partial_size_honestly(self):
        with mock.patch.object(dutched_arb, "_get", return_value=self.book([("0.30", "25")])):
            avg, filled = dutched_arb.walk_asks("t", 100)
        self.assertEqual(filled, 25)
        self.assertAlmostEqual(avg, 0.30, places=9)

    def test_an_empty_book_is_none_not_zero(self):
        with mock.patch.object(dutched_arb, "_get", return_value=self.book([])):
            self.assertIsNone(dutched_arb.walk_asks("t", 100))

    def test_a_failed_request_is_none(self):
        with mock.patch.object(dutched_arb, "_get", return_value=None):
            self.assertIsNone(dutched_arb.walk_asks("t", 100))


class TestDepthPricing(unittest.TestCase):
    """Top-of-book is a quote; depth is the trade. These must not be conflated."""

    def fake_book(self, price, size):
        resp = mock.Mock()
        resp.json.return_value = {"asks": [{"price": str(price), "size": str(size)}]}
        return resp

    def test_executable_size_is_the_thinnest_leg(self):
        """
        An arb completable on 2 of 3 legs is a directional position, not an arb,
        so the size is the MINIMUM across legs - never the average or the max.
        """
        c = dutched_arb.evaluate_event(event([0.30, 0.30, 0.30]))
        books = [self.fake_book("0.30", "500"), self.fake_book("0.30", "40"),
                 self.fake_book("0.30", "500")]
        with mock.patch.object(dutched_arb, "_get", side_effect=books):
            out = dutched_arb.price_with_depth(c, 500)
        self.assertEqual(out["executable_shares"], 40)
        self.assertAlmostEqual(out["depth_ask_sum"], 0.90, places=9)
        self.assertAlmostEqual(out["profit_usd"], 0.10 * 40, places=6)

    def test_depth_can_erase_an_apparent_edge(self):
        """Top-of-book says 0.90; walking real depth says 1.05 and no trade."""
        c = dutched_arb.evaluate_event(event([0.30, 0.30, 0.30]))
        books = [self.fake_book("0.35", "500"), self.fake_book("0.35", "500"),
                 self.fake_book("0.35", "500")]
        with mock.patch.object(dutched_arb, "_get", side_effect=books):
            out = dutched_arb.price_with_depth(c, 500)
        self.assertGreater(out["depth_ask_sum"], 1.0)
        self.assertLess(out["profit_usd"], 0)

    def test_an_unfetchable_leg_flags_the_candidate_rather_than_pricing_it(self):
        c = dutched_arb.evaluate_event(event([0.30, 0.30, 0.30]))
        with mock.patch.object(dutched_arb, "_get", return_value=None):
            out = dutched_arb.price_with_depth(c, 100)
        self.assertIn("depth_error", out)
        self.assertNotIn("profit_usd", out)


class TestScanIntegration(unittest.TestCase):
    def test_only_events_under_the_threshold_are_flagged(self):
        events = [event([0.30, 0.30, 0.30], title="ARB"),
                  event([0.40, 0.40, 0.40], title="NORMAL")]
        with mock.patch.object(dutched_arb, "fetch_events", return_value=events):
            r = dutched_arb.scan(check_depth=False)
        self.assertEqual([h["title"] for h in r["hits"]], ["ARB"])
        self.assertEqual(len(r["priced"]), 2)

    def test_the_distribution_is_sorted_tightest_first(self):
        """An empty hit list still has to be informative, so ordering matters."""
        events = [event([0.40] * 3, title="WIDE"), event([0.34] * 3, title="TIGHT")]
        with mock.patch.object(dutched_arb, "fetch_events", return_value=events):
            r = dutched_arb.scan(check_depth=False)
        self.assertEqual([c["title"] for c in r["priced"]], ["TIGHT", "WIDE"])

    def test_unpriceable_events_are_counted_not_silently_dropped(self):
        bad = event([0.3, 0.3, 0.3])
        bad["markets"][0]["bestAsk"] = None
        with mock.patch.object(dutched_arb, "fetch_events", return_value=[bad]):
            r = dutched_arb.scan(check_depth=False)
        self.assertEqual(r["unpriceable"], 1)
        self.assertEqual(r["priced"], [])

    def test_non_negative_risk_events_are_excluded_by_default(self):
        """
        Outcomes that are not mutually exclusive and exhaustive have no dutch
        book at all - summing them is meaningless, not merely risky.
        """
        ev = event([0.30, 0.30, 0.30], neg_risk=False)
        with mock.patch.object(dutched_arb, "fetch_events", return_value=[ev]):
            self.assertEqual(dutched_arb.scan(check_depth=False)["priced"], [])
            self.assertEqual(
                len(dutched_arb.scan(check_depth=False, neg_risk_only=False)["priced"]), 1
            )


if __name__ == "__main__":
    unittest.main()
