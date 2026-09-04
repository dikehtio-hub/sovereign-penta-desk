"""
Tests for the sharp trader consensus scanner.

Two guards carry this module, and both were written because the FIRST LIVE RUN
would have been ruinous without them:

  1. The same two wallets fired "consensus" on BUY Up AND BUY Down of the same
     5-minute Bitcoin market - 50 and 53 trades in six minutes. They were market
     making, not forecasting. Copying both legs buys both outcomes at the ask.
  2. The roster bar (win_rate >= 60%, pnl >= $5k) selects wallets with a 100% win
     rate on ONE closed position. Ranking on win rate would put them at the top.

Fully offline - synthetic trades and a temp SQLite roster.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import consensus_scanner as cs

HOUR = 3600


def trade(wallet, cid="c1", outcome="Yes", side="BUY", ts=0, usd=100.0, price=0.5):
    return {"wallet": wallet, "condition_id": cid, "title": "Test Market",
            "slug": "test", "outcome": outcome, "side": side, "price": price,
            "usd": usd, "timestamp": ts, "asset": "tok1"}


def meta(wallet, win=80.0, pnl=10_000.0):
    return {"wallet": wallet, "pseudonym": wallet, "win_rate": win,
            "realized_pnl": pnl, "closed_positions": 20}


WALLETS = {w: meta(w) for w in ("A", "B", "C")}


class TestConsensusDetection(unittest.TestCase):
    def test_two_distinct_wallets_on_the_same_side_fire_a_signal(self):
        sigs, _ = cs.find_consensus([trade("A", ts=0), trade("B", ts=HOUR)], WALLETS)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0]["n_wallets"], 2)

    def test_one_wallet_scaling_in_is_not_consensus(self):
        """
        Six fills from ONE wallet is one opinion. Counting them as consensus would
        fire on every large order a single sharp places.
        """
        trades = [trade("A", ts=i * 60) for i in range(6)]
        sigs, _ = cs.find_consensus(trades, WALLETS)
        self.assertEqual(sigs, [])

    def test_trades_outside_the_window_do_not_cluster(self):
        sigs, _ = cs.find_consensus([trade("A", ts=0), trade("B", ts=10 * HOUR)], WALLETS)
        self.assertEqual(sigs, [])

    def test_opposite_sides_of_the_same_outcome_are_separate_groups(self):
        """A BUY consensus and a SELL consensus are different signals, not one."""
        sigs, _ = cs.find_consensus(
            [trade("A", side="BUY", ts=0), trade("B", side="SELL", ts=60)], WALLETS)
        self.assertEqual(sigs, [])

    def test_different_markets_do_not_cluster_together(self):
        sigs, _ = cs.find_consensus(
            [trade("A", cid="c1", ts=0), trade("B", cid="c2", ts=60)], WALLETS)
        self.assertEqual(sigs, [])

    def test_a_third_wallet_strengthens_the_signal(self):
        sigs, _ = cs.find_consensus(
            [trade("A", ts=0), trade("B", ts=60), trade("C", ts=120)], WALLETS)
        self.assertEqual(sigs[0]["n_wallets"], 3)

    def test_combined_size_and_aggregate_stats_are_reported(self):
        sigs, _ = cs.find_consensus(
            [trade("A", ts=0, usd=300.0), trade("B", ts=60, usd=700.0)], WALLETS)
        s = sigs[0]
        self.assertAlmostEqual(s["combined_usd"], 1000.0, places=9)
        self.assertAlmostEqual(s["aggregate_win_rate"], 80.0, places=9)
        self.assertAlmostEqual(s["aggregate_pnl"], 20_000.0, places=9)

    def test_average_price_is_size_weighted(self):
        """An equal-weight mean would let a $10 fill move the reported entry."""
        sigs, _ = cs.find_consensus(
            [trade("A", ts=0, usd=900.0, price=0.90),
             trade("B", ts=60, usd=100.0, price=0.10)], WALLETS)
        self.assertAlmostEqual(sigs[0]["avg_price"], 0.82, places=9)

    def test_trades_without_a_condition_id_are_ignored(self):
        t = trade("A", ts=0)
        t["condition_id"] = None
        sigs, _ = cs.find_consensus([t, trade("B", ts=60)], WALLETS)
        self.assertEqual(sigs, [])

    def test_the_window_slides_rather_than_bucketing_to_a_clock(self):
        """
        Two trades 10 minutes apart must always cluster. A fixed 3-hour bucket
        would miss them whenever they straddle a boundary.
        """
        sigs, _ = cs.find_consensus(
            [trade("A", ts=3 * HOUR - 300), trade("B", ts=3 * HOUR + 300)], WALLETS)
        self.assertEqual(len(sigs), 1)


class TestMarketMakingSuppression(unittest.TestCase):
    """The guard that stopped the first live run from copying two market makers."""

    def test_the_same_wallets_on_opposing_outcomes_are_suppressed(self):
        trades = [trade("A", outcome="Up", ts=0), trade("B", outcome="Up", ts=60),
                  trade("A", outcome="Down", ts=90), trade("B", outcome="Down", ts=120)]
        sigs, dropped = cs.find_consensus(trades, WALLETS)
        self.assertEqual(sigs, [])
        self.assertEqual(len(dropped), 2)
        self.assertIn("opposing outcomes", dropped[0]["suppressed_reason"])

    def test_different_wallets_on_opposing_outcomes_are_genuine_disagreement(self):
        """Two camps disagreeing is real information; one desk quoting both is not."""
        trades = [trade("A", outcome="Up", ts=0), trade("B", outcome="Up", ts=60),
                  trade("C", outcome="Down", ts=90), trade("D", outcome="Down", ts=120)]
        wallets = {**WALLETS, "D": meta("D")}
        sigs, dropped = cs.find_consensus(trades, wallets)
        self.assertEqual(len(sigs), 2)
        self.assertEqual(dropped, [])

    def test_high_churn_is_suppressed_as_quoting(self):
        """25 trades per wallet in the window is a quote stream, not a view."""
        trades = ([trade("A", ts=i) for i in range(30)]
                  + [trade("B", ts=i) for i in range(30)])
        sigs, dropped = cs.find_consensus(trades, WALLETS)
        self.assertEqual(sigs, [])
        self.assertIn("per wallet", dropped[0]["suppressed_reason"])

    def test_a_normal_conviction_cluster_survives_both_guards(self):
        trades = [trade("A", ts=0), trade("A", ts=60), trade("B", ts=120)]
        sigs, dropped = cs.find_consensus(trades, WALLETS)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(dropped, [])


class TestRoster(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "w.db"
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE sharp_traders (
            wallet TEXT, proxy_wallet TEXT, pseudonym TEXT, win_rate REAL,
            realized_pnl_7d REAL, closed_positions_7d INTEGER, volume_7d REAL,
            trades_7d INTEGER)""")
        rows = [
            ("0xlucky", "0xlucky", "Lucky",    100.0, 100_000.0, 1),   # 100% on ONE trade
            ("0xsolid", "0xsolid", "Solid",     72.0,  20_000.0, 40),
            ("0xsmall", "0xsmall", "SmallPnL",  80.0,   1_000.0, 40),
            ("0xweak",  "0xweak",  "WeakWin",   40.0,  50_000.0, 40),
        ]
        conn.executemany(
            "INSERT INTO sharp_traders (wallet, proxy_wallet, pseudonym, win_rate,"
            " realized_pnl_7d, closed_positions_7d) VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
        conn.close()

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_lucky_one_trade_wallet_is_excluded_by_the_sample_floor(self):
        """
        The whole reason MIN_CLOSED_POSITIONS exists. Lucky has the highest PnL and
        a 100% win rate on a single closed position - it would otherwise top the
        roster and dominate every signal.
        """
        names = [w["pseudonym"] for w in cs.load_sharp_wallets(self.db, min_closed=10)]
        self.assertNotIn("Lucky", names)
        self.assertIn("Solid", names)

    def test_dropping_the_sample_floor_lets_it_back_in(self):
        names = [w["pseudonym"] for w in cs.load_sharp_wallets(self.db, min_closed=1)]
        self.assertIn("Lucky", names)

    def test_low_pnl_and_low_win_rate_are_both_excluded(self):
        names = [w["pseudonym"] for w in cs.load_sharp_wallets(self.db, min_closed=10)]
        self.assertNotIn("SmallPnL", names)
        self.assertNotIn("WeakWin", names)

    def test_the_roster_is_ranked_by_pnl_not_win_rate(self):
        """Ranking on win rate promotes whoever got lucky most recently."""
        rows = cs.load_sharp_wallets(self.db, min_closed=1)
        self.assertEqual([r["realized_pnl"] for r in rows],
                         sorted([r["realized_pnl"] for r in rows], reverse=True))

    def test_a_missing_database_yields_an_empty_roster(self):
        self.assertEqual(cs.load_sharp_wallets(Path("nope.db")), [])


class TestPaperBook(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.book = cs.ConsensusPaperBook(starting_cash=1_000.0,
                                          path=Path(self._tmp.name) / "p.json")
        self.sig = {"condition_id": "c1", "title": "T", "outcome": "Yes", "side": "BUY",
                    "avg_price": 0.50, "n_wallets": 2, "aggregate_win_rate": 80.0,
                    "asset": "tok1"}

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_copy_fills_at_the_current_ask_not_the_sharps_price(self):
        """
        We see the trade only after it settles. Recording the sharp's price as our
        entry would measure THEIR edge, not ours.
        """
        p = self.book.copy(self.sig, size_usd=100.0, ask=0.55)
        self.assertEqual(p["entry_price"], 0.55)
        self.assertEqual(p["sharp_avg_price"], 0.50)
        self.assertAlmostEqual(p["slippage_pct"], 10.0, places=6)

    def test_slippage_can_be_favourable(self):
        p = self.book.copy(self.sig, size_usd=100.0, ask=0.45)
        self.assertLess(p["slippage_pct"], 0)

    def test_a_consensus_is_copied_once_and_never_pyramided(self):
        self.assertIsNotNone(self.book.copy(self.sig, ask=0.55))
        self.assertIsNone(self.book.copy(self.sig, ask=0.55))

    def test_a_signal_with_no_live_book_is_skipped_and_counted(self):
        self.assertIsNone(self.book.copy(self.sig, ask=None))
        self.assertEqual(self.book.summary()["skipped_no_book"], 1)

    def test_a_copy_larger_than_cash_is_refused(self):
        self.assertIsNone(self.book.copy(self.sig, size_usd=5_000.0, ask=0.55))

    def test_cash_falls_by_the_deployed_size(self):
        self.book.copy(self.sig, size_usd=100.0, ask=0.50)
        self.assertAlmostEqual(self.book.cash, 900.0, places=9)
        self.assertAlmostEqual(self.book.summary()["deployed_usd"], 100.0, places=9)

    def test_shares_are_priced_off_the_actual_fill(self):
        p = self.book.copy(self.sig, size_usd=100.0, ask=0.25)
        self.assertAlmostEqual(p["shares"], 400.0, places=9)

    def test_state_round_trips(self):
        self.book.copy(self.sig, size_usd=100.0, ask=0.55)
        self.book.save()
        b2 = cs.ConsensusPaperBook(path=self.book.path)
        self.assertTrue(b2.load())
        self.assertAlmostEqual(b2.cash, self.book.cash, places=9)
        self.assertEqual(len(b2.positions), 1)

    def test_loading_a_missing_file_is_false(self):
        self.assertFalse(cs.ConsensusPaperBook(path=Path("nope.json")).load())


if __name__ == "__main__":
    unittest.main()


class TestMacroDurationFilter(unittest.TestCase):
    """
    Markets resolving in minutes belong to quoting bots. Getting the DURATION
    METRIC right took two attempts and both failures are pinned here.
    """

    def test_short_lived_markets_are_dropped(self):
        trades = [trade("A", cid="fast"), trade("B", cid="slow")]
        kept, dropped = cs.filter_by_duration(trades, {"fast": 0.25, "slow": 168.0}, 24.0)
        self.assertEqual(dropped, 1)
        self.assertEqual([t["condition_id"] for t in kept], ["slow"])

    def test_a_market_exactly_at_the_threshold_is_kept(self):
        kept, dropped = cs.filter_by_duration([trade("A", cid="x")], {"x": 24.0}, 24.0)
        self.assertEqual((len(kept), dropped), (1, 0))

    def test_an_unknown_duration_is_kept_not_dropped(self):
        """
        Unknown is not evidence of short. Dropping unresolvable markets would bias
        the sample toward whatever Gamma happens to serve; the behavioural
        suppression guards still apply to them downstream.
        """
        kept, dropped = cs.filter_by_duration([trade("A", cid="unknown")], {}, 24.0)
        self.assertEqual((len(kept), dropped), (1, 0))

    def test_duration_uses_the_event_window_not_object_creation(self):
        """
        The first attempt used endDate - startDate and silently failed on exactly
        the markets it targeted: Gamma reports startDate as when the market OBJECT
        was created (~24h early) for a 15-minute binary, giving a phantom ~23.9h
        lifetime that clustered just under the threshold by accident.
        eventStartTime is the real window open.
        """
        market = {"conditionId": "c", "startDate": "2026-08-31T05:38:34Z",
                  "eventStartTime": "2026-09-01T05:30:00Z",
                  "endDate": "2026-09-01T05:45:00Z"}
        start = cs._parse_iso(market["eventStartTime"])
        end = cs._parse_iso(market["endDate"])
        self.assertAlmostEqual((end - start) / 3600.0, 0.25, places=6)
        naive = (end - cs._parse_iso(market["startDate"])) / 3600.0
        self.assertGreater(naive, 23.0)      # what the broken metric reported

    def test_it_falls_back_to_start_date_when_there_is_no_event_window(self):
        m = {"startDate": "2026-05-13T00:00:00Z", "endDate": "2026-09-16T00:00:00Z"}
        hours = (cs._parse_iso(m["endDate"]) - cs._parse_iso(m["startDate"])) / 3600.0
        self.assertGreater(hours, 24.0)

    def test_unparseable_timestamps_are_none_not_a_crash(self):
        self.assertIsNone(cs._parse_iso("not-a-date"))
        self.assertIsNone(cs._parse_iso(None))

    def test_an_empty_trade_list_is_handled(self):
        self.assertEqual(cs.filter_by_duration([], {}, 24.0), ([], 0))


class TestFrontRunGuard(unittest.TestCase):
    """
    "Already priced in". Sharps entering at 0.35 push the contract to 0.65; a copy
    filling at the new price buys the exhausted end of their edge. The move IS the
    signal being consumed.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.book = cs.ConsensusPaperBook(starting_cash=1_000.0,
                                          path=Path(self._tmp.name) / "p.json")
        self.sig = {"condition_id": "c1", "title": "T", "outcome": "Yes", "side": "BUY",
                    "avg_price": 0.35, "n_wallets": 2, "aggregate_win_rate": 80.0,
                    "asset": "tok1"}

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_contract_that_already_ran_is_refused(self):
        self.assertIsNone(self.book.copy(self.sig, ask=0.65))       # +86%
        self.assertEqual(self.book.summary()["skipped_priced_in"], 1)

    def test_a_modest_move_is_still_copied(self):
        self.assertIsNotNone(self.book.copy(self.sig, ask=0.39))    # +11%

    def test_the_boundary_is_inclusive(self):
        """Exactly 15% is allowed; the guard fires above it."""
        self.assertIsNotNone(self.book.copy(self.sig, ask=0.35 * 1.15))

    def test_a_favourable_price_is_never_blocked(self):
        """Buying cheaper than the sharps did is the opposite of front-run."""
        self.assertIsNotNone(self.book.copy(self.sig, ask=0.20))

    def test_the_threshold_is_configurable(self):
        self.assertIsNone(self.book.copy(self.sig, ask=0.40, max_appreciation_pct=5.0))

    def test_refusal_does_not_spend_cash(self):
        self.book.copy(self.sig, ask=0.90)
        self.assertEqual(self.book.cash, 1_000.0)
        self.assertEqual(self.book.positions, {})

    def test_the_refusal_count_persists(self):
        self.book.copy(self.sig, ask=0.90)
        self.book.save()
        b2 = cs.ConsensusPaperBook(path=self.book.path)
        b2.load()
        self.assertEqual(b2.skipped_priced_in, 1)


class TestDurationThreshold(unittest.TestCase):
    def test_six_hours_excludes_rebate_farmers(self):
        """
        Measured: the distribution is NOT bimodal, but rebate-farmed binaries sit
        at <=0.25h and the next band is 4-6h. Any cut between 0.5h and 4h excludes
        every farmer and nothing else.
        """
        self.assertEqual(cs.MIN_MARKET_DURATION_HOURS, 6.0)
        trades = [trade("A", cid="5min"), trade("B", cid="15min"), trade("C", cid="esport")]
        durations = {"5min": 0.083, "15min": 0.25, "esport": 6.0}
        kept, dropped = cs.filter_by_duration(trades, durations, cs.MIN_MARKET_DURATION_HOURS)
        self.assertEqual(dropped, 2)
        self.assertEqual([t["condition_id"] for t in kept], ["esport"])
