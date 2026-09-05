"""
Round 64 (Directive 64-3 groundwork): the stale-quote core. Offline: quotes are
built in memory or in a temp sports_market.db. What must be true: a sharp move
is a move only when it is both large and fast, a retail quote is stale only when
it predates the move and is still fresh enough to act on, and only the cheap
side is flagged.
"""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from Sports_Desk.data.db import init_market_db
from Sports_Desk.engine import stale_quotes as sq

T = datetime(2026, 9, 5, 18, 0, tzinfo=timezone.utc)


def q(book, odds, minutes_ago, selection="Ravens", event="G1", market="moneyline", line=""):
    return sq.Quote(book=book, selection=selection, decimal_odds=odds, quoted_at=T - timedelta(minutes=minutes_ago),
                    event_id=event, market_type=market, line=line)


class TestSharpMoves(unittest.TestCase):

    def test_implied_and_sharp_classification(self):
        self.assertAlmostEqual(sq.implied(2.0), 0.5)
        with self.assertRaises(ValueError):
            sq.implied(1.0)
        self.assertTrue(sq.is_sharp("Pinnacle") and sq.is_sharp("circa"))
        self.assertFalse(sq.is_sharp("DraftKings"))
        self.assertEqual((sq.MIN_SHARP_MOVE_PROB, sq.MIN_VELOCITY_PROB_PER_MIN, sq.MIN_RETAIL_LAG_SECONDS,
                          sq.MAX_QUOTE_AGE_SECONDS, sq.MIN_EDGE_PROB), (0.02, 0.005, 60, 900, 0.02))

    def test_a_move_must_be_both_large_and_fast(self):
        fast = [q("Pinnacle", 2.00, 9), q("Pinnacle", 1.80, 5)]                  # +5.6 pts in 4 min
        moves = sq.detect_sharp_moves(fast)
        self.assertEqual(len(moves), 1)
        move = moves[0]
        self.assertEqual((move.book, move.direction), ("Pinnacle", "shortened"))
        self.assertAlmostEqual(move.delta_prob, 1 / 1.80 - 0.5, places=6)
        self.assertAlmostEqual(move.minutes, 4.0, places=6)
        self.assertGreater(move.velocity, sq.MIN_VELOCITY_PROB_PER_MIN)
        small = [q("Pinnacle", 2.00, 9), q("Pinnacle", 1.96, 5)]                 # +1.0 pt: wobble
        self.assertEqual(sq.detect_sharp_moves(small), [])
        slow = [q("Pinnacle", 2.00, 180), q("Pinnacle", 1.80, 5)]                # +5.6 pts over 175 min: drift
        self.assertEqual(sq.detect_sharp_moves(slow), [])
        retail_only = [q("DraftKings", 2.00, 9), q("DraftKings", 1.80, 5)]      # retail moves are not signals
        self.assertEqual(sq.detect_sharp_moves(retail_only), [])
        # The most recent qualifying step per series is the move reported.
        two_steps = [q("Pinnacle", 2.20, 30), q("Pinnacle", 2.00, 25), q("Pinnacle", 1.80, 21)]   # both fast
        moves = sq.detect_sharp_moves(two_steps)
        self.assertEqual(len(moves), 1)
        self.assertEqual((moves[0].from_odds, moves[0].to_odds), (2.00, 1.80))
        # ...but a slow second step is not a move, so the first step stays the latest qualifying one.
        slow_second = [q("Pinnacle", 2.20, 30), q("Pinnacle", 2.00, 25), q("Pinnacle", 1.80, 5)]  # 20 min step
        self.assertEqual((sq.detect_sharp_moves(slow_second)[0].from_odds,
                          sq.detect_sharp_moves(slow_second)[0].to_odds), (2.20, 2.00))
        drift = sq.detect_sharp_moves([q("Circa", 1.80, 9), q("Circa", 2.00, 5)])
        self.assertEqual(drift[0].direction, "drifted")


class TestStaleQuotes(unittest.TestCase):

    def test_a_retail_quote_that_predates_the_move_and_is_cheap_is_flagged(self):
        quotes = [q("Pinnacle", 2.00, 9), q("Pinnacle", 1.80, 5),               # sharp shortened Ravens at T-5
                  q("DraftKings", 2.05, 10),                                     # quoted before the move, never re-quoted
                  q("FanDuel", 2.02, 12), q("FanDuel", 1.83, 2),                 # re-quoted after the move
                  q("BetMGM", 2.05, 40)]                                         # too old to trust
        scan = sq.find_stale_quotes(quotes, now=T)
        self.assertEqual(len(scan.moves), 1)
        self.assertEqual([h.retail_book for h in scan.hits], ["DraftKings"])
        hit = scan.hits[0]
        self.assertAlmostEqual(hit.edge_prob, 1 / 1.80 - 1 / 2.05, places=6)   # ~6.8 pts
        self.assertAlmostEqual(hit.lag_seconds, 300.0, places=6)                # quoted 5 min before the move ended
        self.assertAlmostEqual(hit.age_seconds, 600.0, places=6)
        self.assertEqual((scan.not_stale, scan.too_old, scan.overpriced, scan.thin_edge), (1, 1, 0, 0))
        text = sq.render_stale_quotes(scan, now=T)
        self.assertIn("stale retail quotes flagged: 1", text)
        self.assertIn("Pinnacle G1 moneyline Ravens: shortened 2.000 -> 1.800", text)
        self.assertIn("DraftKings still 2.050 on Ravens (quoted 300s before the move ended, 600s old): edge +6.8 pts", text)

    def test_a_drift_makes_the_stale_quote_overpriced_not_cheap_and_thin_edges_are_counted(self):
        drift = [q("Pinnacle", 1.80, 9), q("Pinnacle", 2.00, 5), q("DraftKings", 1.85, 10)]
        scan = sq.find_stale_quotes(drift, now=T)
        self.assertEqual((len(scan.moves), len(scan.hits), scan.overpriced), (1, 0, 1))
        thin = [q("Pinnacle", 2.00, 9), q("Pinnacle", 1.85, 5), q("DraftKings", 1.90, 10)]   # +4.1 pt move, 1.4 pt edge
        scan = sq.find_stale_quotes(thin, now=T)
        self.assertEqual((len(scan.moves), len(scan.hits), scan.thin_edge), (1, 0, 1))
        self.assertIn("no sharp move", sq.render_stale_quotes(sq.find_stale_quotes([q("DraftKings", 2.0, 1)], now=T)))
        # Thresholds are parameters: a looser edge flags the thin one.
        self.assertEqual(len(sq.find_stale_quotes(thin, now=T, min_edge=0.01).hits), 1)

    def test_the_lag_rule_uses_the_move_end_and_the_selection_key_isolates_markets(self):
        quotes = [q("Pinnacle", 2.00, 9), q("Pinnacle", 1.80, 5),
                  q("DraftKings", 2.05, 5.5),                                    # 30 s before the move ended: not yet stale
                  q("DraftKings", 2.05, 10, selection="Chiefs"),                # different selection: irrelevant
                  q("DraftKings", 2.05, 10, market="spread", line="-3.5")]      # different market: irrelevant
        scan = sq.find_stale_quotes(quotes, now=T)
        self.assertEqual((len(scan.hits), scan.not_stale), (0, 1))
        self.assertEqual(len(sq.find_stale_quotes(quotes, now=T, min_lag_seconds=10).hits), 1)


class TestMarketDb(unittest.TestCase):

    def test_scan_reads_measurements_within_the_lookback(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sports_market.db"
            init_market_db(db)
            con = sqlite3.connect(str(db))

            def row(book, odds, minutes_ago, selection="Ravens"):
                stamp = (T - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
                con.execute("INSERT INTO fair_odds_measurements (timestamp, event_id, sport, market_type, line, "
                            "sportsbook, raw_quotes_json, selection, offered_odds, implied_prob_raw, fair_prob, "
                            "fair_odds, expected_value, quarter_kelly, overround, shin_z, power_k, divergent, "
                            "max_oracle_delta, quoted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (stamp, "G1", "NFL", "moneyline", "", book, "[]", selection, odds, 1 / odds, 0.5, 2.0,
                             0.0, 0.0, 0.04, 0.0, 1.0, 0, 0.0, stamp))

            row("Pinnacle", 2.00, 9)
            row("Pinnacle", 1.80, 5)
            row("DraftKings", 2.05, 10)
            row("Caesars", 2.05, 600)                                            # outside the 3 h lookback
            con.commit()
            con.close()
            quotes = sq.load_quotes(db, now=T)
            self.assertEqual(sorted(qq.book for qq in quotes), ["DraftKings", "Pinnacle", "Pinnacle"])
            scan = sq.scan_market_db(db, now=T)
            self.assertEqual([h.retail_book for h in scan.hits], ["DraftKings"])
            self.assertEqual(sq.load_quotes(Path(tmp) / "missing.db", now=T), [])


if __name__ == "__main__":
    unittest.main()
