"""
Unit tests for Monarch_Shark - the interactive betslip and execution CLV.

The interaction is driven through injected `read`/`write` callables, so the
terminal loop is tested rather than hand-waved. An interactive tool that can only
be exercised by a human does not get exercised.

The assertions that matter are refusals: what the betslip declines to record, and
why. A betslip that writes down whatever it is told is worse than none, because
the execution numbers it produces would then be fiction.
"""
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from Sports_Desk.data.db import (execution_clv, init_market_db,
                                 record_fair_value_measurement, query_placed_bets,
                                 record_placed_bet)
from Sports_Desk.engine.arbitrage import scan_market_db
from Sports_Desk.engine.fair_value import calculate_fair_value
from Sports_Desk.ingestors.odds_watcher import OddsWatcher
from Sports_Desk.interfaces.monarch_shark import Betslip, render_execution_clv
from Tax_Reserve_Agent.database.db import init_db
from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

QUOTED = "2026-09-03T18:00:00Z"
STARTS = "2026-09-03T23:00:00Z"
NOW = datetime(2026, 9, 3, 18, 2, 0)

EDGE_MARKET = (
    "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,start_time\n"
    f"G1,NFL,moneyline,Chiefs,Pinnacle,-140,1,{QUOTED},{STARTS}\n"
    f"G1,NFL,moneyline,Ravens,Pinnacle,+120,1,{QUOTED},{STARTS}\n"
    f"G1,NFL,moneyline,Ravens,DraftKings,+185,0,{QUOTED},{STARTS}\n"
)
ARB_MARKET = (
    "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,start_time\n"
    f"G2,NFL,moneyline,A,Pinnacle,-105,1,{QUOTED},{STARTS}\n"
    f"G2,NFL,moneyline,B,Pinnacle,-115,1,{QUOTED},{STARTS}\n"
    f"G2,NFL,moneyline,B,DraftKings,+130,0,{QUOTED},{STARTS}\n"
)


class SharkTestBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drop = self.root / "odds"
        self.drop.mkdir()
        self.db = self.root / "sports_market.db"
        self.ledger = self.root / "tax.db"
        init_market_db(self.db)
        init_db(self.ledger)
        self.written = []

    def tearDown(self):
        self.temp.cleanup()

    def _hook(self, treatment="professional_schedule_c"):
        return MonarchBankrollHook(db_path=self.ledger, config={
            "tax_rates": {"short_term_capital_gains": 0.28,
                          "long_term_capital_gains": 0.15,
                          "state_tax_rate": 0.05, "safety_buffer_pct": 0.02},
            "portfolio": {"default_cash_balance_usdc": 50000.0, "tax_year": 2026},
            "gambling": {"tax_treatment": treatment, "loss_deduction_pct": 0.90},
            "bot_integration": {"assumed_round_trip_fee": 0.02,
                                "max_position_pct": 0.05, "min_order_usd": 1.0,
                                "strategies": {"sports_betting": 0.15,
                                               "sandbox": 0.85}}})

    def _ingest(self, text=EDGE_MARKET, name="odds.csv", hook=None):
        (self.drop / name).write_text(text, encoding="utf-8")
        hook = hook or self._hook()
        watcher = OddsWatcher(
            drop_folder=self.drop, db_path=self.db,
            after_tax_hurdle=lambda odds: hook.breakeven_gross_edge(
                category="sports", decimal_odds=odds))
        watcher.scan_once()
        watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)

    def _slip(self, hook=None, answers=("y",)):
        replies = list(answers)
        return Betslip(hook or self._hook(), db_path=self.db,
                       read=lambda prompt: replies.pop(0) if replies else "q",
                       write=self.written.append, bankroll=50000.0, now=NOW)

    def _said(self, fragment):
        return any(fragment in line for line in self.written)


class TestStaking(SharkTestBase):

    def test_a_confirmed_bet_is_recorded_with_its_provenance(self):
        self._ingest()
        slip = self._slip()
        rows = slip.show_hotlist()
        self.assertTrue(rows)
        bet_id = slip.stake(rows[0])
        self.assertIsNotNone(bet_id)

        placed = query_placed_bets(db_path=self.db)
        self.assertEqual(len(placed), 1)
        bet = placed[0]
        self.assertEqual(bet["selection"], "Ravens")
        self.assertEqual(bet["book"], "draftkings")
        self.assertAlmostEqual(bet["decimal_odds"], 2.85, places=6)
        self.assertAlmostEqual(bet["stake"], rows[0]["approved_notional"], places=6)
        # The fair value AT PLACEMENT is frozen, not re-derived later.
        self.assertAlmostEqual(bet["fair_prob_at_placement"],
                               rows[0]["sharp_fair_prob"], places=9)
        self.assertIsNotNone(bet["after_tax_hurdle"])
        self.assertEqual(bet["bet_kind"], "single")

    def test_declining_the_confirmation_records_nothing(self):
        self._ingest()
        slip = self._slip(answers=("n",))
        slip.stake(slip.show_hotlist()[0])
        self.assertEqual(query_placed_bets(db_path=self.db), [])
        self.assertTrue(self._said("[cancelled]"))

    def test_a_stake_above_the_approved_size_is_refused_not_clamped(self):
        """
        A betslip that quietly halves what you typed is worse than one that says
        no: you would place the number you typed at the book, and the ledger
        would then disagree with reality.
        """
        self._ingest()
        slip = self._slip()
        row = slip.show_hotlist()[0]
        self.assertIsNone(slip.stake(row, amount=row["approved_notional"] * 2))
        self.assertEqual(query_placed_bets(db_path=self.db), [])
        self.assertTrue(self._said("not clamped on purpose"))

    def test_a_smaller_stake_is_allowed(self):
        self._ingest()
        slip = self._slip()
        row = slip.show_hotlist()[0]
        self.assertIsNotNone(slip.stake(row, amount=10.0))
        self.assertAlmostEqual(query_placed_bets(db_path=self.db)[0]["stake"], 10.0)

    def test_a_row_the_gate_rejected_cannot_be_staked(self):
        """Overriding the gate from a betslip would make the escrow advisory."""
        self._ingest()
        slip = self._slip()
        row = dict(slip.show_hotlist()[0])
        row["actionable"] = False
        row["reason"] = "rejected"
        row["approved_notional"] = 0.0
        self.assertIsNone(slip.stake(row))
        self.assertEqual(query_placed_bets(db_path=self.db), [])

    def test_the_confirmation_says_this_is_not_a_tax_record(self):
        """Forgetting that is how the escrow silently goes stale."""
        self._ingest()
        slip = self._slip()
        slip.stake(slip.show_hotlist()[0])
        self.assertTrue(self._said("NOT a tax record"))


class TestSessionExposure(SharkTestBase):
    """
    The strategy bucket exists so one strategy cannot reach core capital. A
    betslip that ignores it makes the whole bucketing scheme advisory.
    """

    def _many_markets(self, count=40):
        rows = ["event_id,sport,market_type,selection,book,odds,is_sharp,"
                "timestamp,start_time"]
        for index in range(count):
            rows += [f"E{index},NFL,moneyline,Home,Pinnacle,-140,1,{QUOTED},{STARTS}",
                     f"E{index},NFL,moneyline,Away,Pinnacle,+120,1,{QUOTED},{STARTS}",
                     f"E{index},NFL,moneyline,Away,DraftKings,+185,0,{QUOTED},{STARTS}"]
        return "\n".join(rows) + "\n"

    def _small_hook(self):
        return MonarchBankrollHook(db_path=self.ledger, config={
            "tax_rates": {"short_term_capital_gains": 0.28,
                          "long_term_capital_gains": 0.15,
                          "state_tax_rate": 0.05, "safety_buffer_pct": 0.02},
            "portfolio": {"default_cash_balance_usdc": 5000.0, "tax_year": 2026},
            "gambling": {"tax_treatment": "professional_schedule_c",
                         "loss_deduction_pct": 0.90},
            "bot_integration": {"assumed_round_trip_fee": 0.02,
                                "max_position_pct": 0.05, "min_order_usd": 1.0,
                                "strategies": {"sports_betting": 0.15,
                                               "sandbox": 0.85}}})

    def test_a_session_cannot_stake_past_the_strategy_bucket(self):
        """
        REGRESSION. `check_order` measures existing exposure from the TAX LEDGER,
        which does not learn about a wager until the book's export is imported -
        possibly days later. Every bet in a session was therefore approved against
        a bucket that looked empty: measured, forty bets went through for $1,249
        against a $750 bucket, 1.7x over.
        """
        hook = self._small_hook()
        self._ingest(self._many_markets(), hook=hook)
        slip = Betslip(hook, db_path=self.db, read=lambda p: "y",
                       write=self.written.append, bankroll=5000.0, now=NOW)
        rows = slip.show_hotlist()
        self.assertGreater(len(rows), 20)
        for row in rows:
            slip.stake(row)

        bucket = hook.get_safe_bankroll(5000.0) * 0.15
        staked = sum(b["stake"] for b in query_placed_bets(db_path=self.db))
        self.assertLessEqual(staked, bucket + 1e-6)
        self.assertGreater(staked, bucket * 0.9)      # and it does fill the bucket
        self.assertTrue(self._said("[refused]"))

    def test_open_exposure_is_measured_not_remembered(self):
        """It must survive restarting the betslip, so it is read from the table."""
        hook = self._small_hook()
        self._ingest(self._many_markets(4), hook=hook)
        first = Betslip(hook, db_path=self.db, read=lambda p: "y",
                        write=self.written.append, bankroll=5000.0, now=NOW)
        first.stake(first.show_hotlist()[0])
        staked = sum(b["stake"] for b in query_placed_bets(db_path=self.db))

        fresh = Betslip(hook, db_path=self.db, read=lambda p: "y",
                        write=self.written.append, bankroll=5000.0, now=NOW)
        self.assertAlmostEqual(fresh.open_exposure(), staked, places=6)

    def test_a_settled_bet_stops_counting_as_exposure(self):
        from Sports_Desk.data.db import open_desk_exposure, record_settled_result
        hook = self._small_hook()
        self._ingest(self._many_markets(2), hook=hook)
        slip = Betslip(hook, db_path=self.db, read=lambda p: "y",
                       write=self.written.append, bankroll=5000.0, now=NOW)
        row = slip.show_hotlist()[0]
        slip.stake(row)
        self.assertGreater(open_desk_exposure(db_path=self.db), 0.0)
        record_settled_result(row["event_id"], row["sport"], row["market_type"],
                              row.get("line", ""), row["selection"], 1,
                              db_path=self.db)
        self.assertEqual(open_desk_exposure(db_path=self.db), 0.0)

    def test_exposure_takes_the_max_of_ledger_and_desk_not_the_sum(self):
        """
        Once the book's export reaches the tax ledger a bet is in BOTH places.
        Adding them would double-count it into a permanent phantom exposure.
        """
        hook = self._small_hook()
        self._ingest(self._many_markets(2), hook=hook)
        slip = Betslip(hook, db_path=self.db, read=lambda p: "y",
                       write=self.written.append, bankroll=5000.0, now=NOW)
        slip.stake(slip.show_hotlist()[0])
        from Sports_Desk.data.db import open_desk_exposure
        desk = open_desk_exposure(db_path=self.db)
        ledger = hook.get_strategy_open_exposure("sports_betting") or 0.0
        self.assertAlmostEqual(slip.open_exposure(), max(desk, ledger), places=9)


class TestArbitrageStaking(SharkTestBase):

    def test_every_leg_is_recorded_as_one_group(self):
        self._ingest(ARB_MARKET)
        hook = self._hook("professional_schedule_c")
        slip = self._slip(hook)
        opportunities = scan_market_db(hook, db_path=self.db, now=NOW)
        self.assertTrue(opportunities)
        placed = slip.stake_arbitrage(opportunities[0], bankroll=1000.0)
        self.assertEqual(len(placed), 2)

        bets = query_placed_bets(db_path=self.db)
        self.assertEqual({b["bet_kind"] for b in bets}, {"arbitrage"})
        self.assertEqual(len({b["arb_group"] for b in bets}), 1)
        self.assertAlmostEqual(sum(b["stake"] for b in bets), 1000.0, places=6)
        # Both legs return the same amount, which is what makes it an arb.
        returns = [b["stake"] * b["decimal_odds"] for b in bets]
        self.assertAlmostEqual(returns[0], returns[1], places=6)

    def test_a_sub_hurdle_arb_is_refused_WHOLESALE(self):
        """
        Staking the legs one at a time would let a rejected one through as a
        naked bet - the opposite of riskless.
        """
        casual = self._hook("casual_standard_deduction")
        self._ingest(ARB_MARKET, hook=casual)
        slip = self._slip(casual)
        opportunities = scan_market_db(casual, db_path=self.db, now=NOW,
                                       include_rejected=True)
        self.assertTrue(opportunities)
        self.assertEqual(slip.stake_arbitrage(opportunities[0], bankroll=1000.0), [])
        self.assertEqual(query_placed_bets(db_path=self.db), [])
        self.assertTrue(self._said("below the"))


class TestExecutionCLV(SharkTestBase):

    def _measure(self, odds, stamp, closing):
        record_fair_value_measurement(
            event_id="G1", sport="NFL", selections=["Chiefs", "Ravens"],
            market_type="moneyline", sportsbook="pinnacle",
            result=calculate_fair_value(odds), timestamp=stamp,
            is_closing=closing, db_path=self.db)

    def test_clv_is_measured_against_the_price_actually_taken(self):
        """
        `measure_clv` answers "did the market move toward the prices we watched".
        This answers the one that costs money: toward the price WE TOOK.
        """
        record_placed_bet("G1", "NFL", "moneyline", "", "Ravens", "draftkings",
                          2.85, 300.0, fair_prob_at_placement=0.435606,
                          edge_at_placement=0.2415, placed_at="2026-09-03T18:05:00Z",
                          db_path=self.db)
        self._measure(["-170", "+145"], "2026-09-03T22:00:00Z", True)
        rows = execution_clv(db_path=self.db)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        # Ravens shortened from 0.4356 to 0.3893: the market moved AWAY.
        self.assertAlmostEqual(row["closing_fair_prob"], 0.389267, places=5)
        self.assertLess(row["clv_prob_delta"], 0.0)
        self.assertFalse(row["beat_close"])
        # But the PRICE taken (2.85) still beat the closing fair odds (2.569).
        self.assertTrue(row["beat_closing_price"])

    def test_the_two_measures_can_disagree_and_both_are_reported(self):
        """
        A bet can beat the close on probability and still be a bad price, and
        vice versa. Reporting one without the other hides half the story.
        """
        record_placed_bet("G1", "NFL", "moneyline", "", "Ravens", "draftkings",
                          2.20, 100.0, fair_prob_at_placement=0.40,
                          placed_at="2026-09-03T18:05:00Z", db_path=self.db)
        self._measure(["-170", "+145"], "2026-09-03T22:00:00Z", True)
        row = execution_clv(db_path=self.db)[0]
        self.assertLess(row["clv_prob_delta"], 0.0)      # market moved away
        self.assertFalse(row["beat_closing_price"])      # and the price was poor

    def test_a_bet_with_no_close_is_reported_not_dropped(self):
        record_placed_bet("G1", "NFL", "moneyline", "", "Ravens", "draftkings",
                          2.85, 300.0, fair_prob_at_placement=0.4356,
                          db_path=self.db)
        row = execution_clv(db_path=self.db)[0]
        self.assertIsNone(row["clv_prob_delta"])
        self.assertIn("no closing line", row["note"])

    def test_a_close_before_the_bet_is_not_a_close(self):
        """Out-of-order import, or the same observation. Not a CLV of zero."""
        self._measure(["-170", "+145"], "2026-09-03T10:00:00Z", True)
        record_placed_bet("G1", "NFL", "moneyline", "", "Ravens", "draftkings",
                          2.85, 300.0, fair_prob_at_placement=0.4356,
                          placed_at="2026-09-03T18:05:00Z", db_path=self.db)
        row = execution_clv(db_path=self.db)[0]
        self.assertIsNone(row["clv_prob_delta"])
        self.assertIn("not strictly after", row["note"])

    def test_the_render_reports_the_hit_rate_and_what_it_means(self):
        record_placed_bet("G1", "NFL", "moneyline", "", "Ravens", "draftkings",
                          2.85, 300.0, fair_prob_at_placement=0.4356,
                          placed_at="2026-09-03T18:05:00Z", db_path=self.db)
        self._measure(["-170", "+145"], "2026-09-03T22:00:00Z", True)
        text = render_execution_clv(execution_clv(db_path=self.db))
        self.assertIn("Beat the close on", text)
        self.assertIn("Below ~50%", text)

    def test_an_empty_ledger_renders_cleanly(self):
        self.assertIn("No bets recorded yet", render_execution_clv([]))


class TestInteractiveLoop(SharkTestBase):

    def test_quitting_immediately_records_nothing(self):
        self._ingest()
        self.assertEqual(self._slip(answers=("q",)).run(), 0)
        self.assertEqual(query_placed_bets(db_path=self.db), [])

    def test_staking_by_number_through_the_loop(self):
        self._ingest()
        # pick row 1 -> blank stake (use approved) -> confirm -> quit
        slip = self._slip(answers=("1", "", "y", "q"))
        self.assertEqual(slip.run(), 1)
        self.assertEqual(len(query_placed_bets(db_path=self.db)), 1)

    def test_an_unlisted_number_is_rejected_without_staking(self):
        self._ingest()
        slip = self._slip(answers=("99", "q"))
        self.assertEqual(slip.run(), 0)
        self.assertTrue(self._said("not a listed number"))

    def test_a_non_numeric_stake_is_rejected(self):
        self._ingest()
        slip = self._slip(answers=("1", "abc", "q"))
        self.assertEqual(slip.run(), 0)
        self.assertTrue(self._said("not a number"))
        self.assertEqual(query_placed_bets(db_path=self.db), [])

    def test_the_clv_view_is_reachable_from_the_loop(self):
        self._ingest()
        self._slip(answers=("c", "q")).run()
        self.assertTrue(self._said("EXECUTION CLV"))


if __name__ == "__main__":
    unittest.main()


class TestCrossMarketStaking(SharkTestBase):
    """
    Round 63 (Directive 63-2). A cross-market dutch the operator executed is
    recorded through cross_market.execution_log: the Polymarket leg as a tagged
    execution receipt, the book leg in placed_bets, one arb_group, one
    timestamp. Refused wholesale when it loses after tax; paper fills never
    touch the ledger or the desk's exposure.
    """

    def _pair(self, worst=1_030.0):
        from types import SimpleNamespace as NS
        result = NS(leg_a=NS(venue="polymarket", selection="YES", decimal_odds=1 / 0.48, token_id="tok-1", raw_price=0.48),
                    leg_b=NS(venue="betmgm", selection="Buffalo Bills", decimal_odds=2.10, token_id="", raw_price=None),
                    capital=1_000.0, stake_a=502.40, stake_b=497.60, gross_arb=0.0458, worst_after_tax=worst)
        pair = NS(market=NS(token_id="tok-1", question="Will the Bills beat the Chiefs?", market_type="moneyline",
                            line="", sport="NFL"),
                  book="betmgm", book_selection="Buffalo Bills", book_decimal_odds=2.10, event_id="G1", quoted_at=QUOTED)
        return result, pair

    def _bets(self):
        import sqlite3
        con = sqlite3.connect(str(self.db))
        rows = con.execute("SELECT placed_at, book, selection, decimal_odds, stake, bet_kind, arb_group, edge_at_placement "
                           "FROM placed_bets").fetchall()
        con.close()
        return rows

    def test_a_confirmed_cross_market_dutch_records_both_legs_under_one_group(self):
        imports = self.root / "imports"
        imports.mkdir()
        slip = self._slip(answers=("y",))
        record = slip.stake_cross_market(*self._pair(), imports_dir=imports)
        self.assertTrue(record["complete"])
        self.assertFalse(record["paper"])
        receipts = list(imports.glob("fills_polymarket_dutched_arb_*.csv"))
        self.assertEqual(len(receipts), 1)
        self.assertAlmostEqual(record["polymarket"]["shares"], 502.40 / 0.48, places=6)
        self.assertEqual(record["polymarket"]["market"], "tok-1")
        self.assertEqual(record["timestamp"], "2026-09-03 18:02:00")            # the slip's clock, both legs
        rows = self._bets()
        self.assertEqual(len(rows), 1)
        placed_at, book, selection, odds, stake, kind, group, edge = rows[0]
        self.assertEqual((book, selection, odds, stake, kind, group), ("betmgm", "Buffalo Bills", 2.10, 497.60,
                                                                       "arbitrage", record["arb_group"]))
        self.assertEqual(placed_at, "2026-09-03T18:02:00+00:00")
        self.assertAlmostEqual(edge, 0.0458, places=6)
        self.assertTrue(self._said("Record dutch: $502.40 of Polymarket YES @ 0.4800"))
        self.assertTrue(self._said("[DUTCH] xm-"))
        self.assertTrue(self._said("NOT a tax record"))

    def test_a_pair_that_loses_after_tax_is_refused_wholesale(self):
        imports = self.root / "imports"
        slip = self._slip(answers=("y",))
        self.assertIsNone(slip.stake_cross_market(*self._pair(worst=980.0), imports_dir=imports))
        self.assertTrue(self._said("[refused] cross-market dutch returns $980.00 after tax"))
        self.assertFalse(imports.exists())
        self.assertEqual(self._bets(), [])
        # Two book legs (no Polymarket leg) is not a cross-market dutch either.
        result, pair = self._pair()
        result.leg_a.venue = "draftkings"
        self.assertIsNone(slip.stake_cross_market(result, pair, imports_dir=imports))
        self.assertTrue(self._said("exactly one Polymarket leg"))

    def test_declining_the_confirmation_records_nothing(self):
        imports = self.root / "imports"
        slip = self._slip(answers=("n",))
        self.assertIsNone(slip.stake_cross_market(*self._pair(), imports_dir=imports))
        self.assertTrue(self._said("[cancelled] nothing recorded."))
        self.assertEqual(self._bets(), [])
        self.assertFalse(imports.exists())

    def test_a_paper_fill_never_touches_the_ledger_or_the_desk(self):
        paper = self.root / "paper"
        slip = self._slip(answers=("y",))
        record = slip.stake_cross_market(*self._pair(), paper=True, imports_dir=paper)
        self.assertTrue(record["paper"] and record["complete"])
        self.assertEqual(len(list(paper.glob("fills_*_dutched_arb_*.csv"))), 2)
        self.assertEqual(self._bets(), [])
        self.assertTrue(self._said("Record PAPER dutch"))
        self.assertTrue(self._said("Paper: neither the tax ledger nor placed_bets saw this."))

    def test_the_menu_offers_cross_market_and_a_blank_pick_records_nothing(self):
        slip = self._slip(answers=("x", "", "q"))
        recorded = slip.run()
        self.assertEqual(recorded, 0)
        self.assertTrue(self._said("[x] cross-market"))
        self.assertEqual(self._bets(), [])


class TestStalePanel(SharkTestBase):
    """Round 65 (Directive 65-1): the stale-quote panel is display-only and reads the desk's own measurements."""

    def _measure(self, book, odds, minutes_ago, selection="Ravens"):
        import sqlite3
        from datetime import timedelta, timezone
        stamp = (NOW - timedelta(minutes=minutes_ago)).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        con = sqlite3.connect(str(self.db))
        con.execute("INSERT INTO fair_odds_measurements (timestamp, event_id, sport, market_type, line, sportsbook, "
                    "raw_quotes_json, selection, offered_odds, implied_prob_raw, fair_prob, fair_odds, expected_value, "
                    "quarter_kelly, overround, shin_z, power_k, divergent, max_oracle_delta, quoted_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (stamp, "G1", "NFL", "moneyline", "", book, "[]", selection, odds, 1 / odds, 0.5, 2.0, 0.0, 0.0,
                     0.04, 0.0, 1.0, 0, 0.0, stamp))
        con.commit()
        con.close()

    def test_the_panel_shows_the_sharp_move_and_the_stale_retail_quote_and_stakes_nothing(self):
        self._measure("Pinnacle", 2.00, 9)
        self._measure("Pinnacle", 1.80, 5)                                     # shortened Ravens 4 min ago
        self._measure("DraftKings", 2.05, 10)                                  # still at the old price
        slip = self._slip()
        scan = slip.show_stale()
        self.assertEqual((len(scan.moves), len(scan.hits)), (1, 1))
        self.assertEqual(scan.hits[0].retail_book, "DraftKings")
        self.assertTrue(self._said("[STALE] sharp moves: 1"))
        self.assertTrue(self._said("Pinnacle G1 moneyline Ravens: shortened 2.000 -> 1.800"))
        self.assertTrue(self._said("DraftKings still 2.050 on Ravens"))
        self.assertTrue(self._said("Display only"))
        self.assertEqual(query_placed_bets(db_path=self.db), [])                 # nothing was staked
        # A tighter lookback that excludes the quotes finds nothing, and says so.
        self.written.clear()
        scan = slip.show_stale(lookback_minutes=3)
        self.assertEqual((len(scan.moves), len(scan.hits)), (0, 0))
        self.assertTrue(self._said("no sharp move in the window"))

    def test_the_stale_flag_prints_the_panel_and_exits(self):
        from unittest import mock
        from Sports_Desk.interfaces.monarch_shark import main
        self._measure("Pinnacle", 2.00, 9)
        self._measure("Pinnacle", 1.80, 5)
        self._measure("DraftKings", 2.05, 10)
        with mock.patch("builtins.print") as fake_print, \
                mock.patch("Sports_Desk.interfaces.monarch_shark.datetime") as fake_dt:
            fake_dt.now.return_value = NOW
            self.assertEqual(main(["--stale", "--db", str(self.db), "--lookback-minutes", "60"]), 0)
        printed = "\n".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("[STALE] sharp moves:", printed)
        self.assertIn("Display only", printed)

    def test_the_menu_offers_stale_quotes(self):
        slip = self._slip(answers=("t", "q"))
        self.assertEqual(slip.run(), 0)
        self.assertTrue(self._said("[t] stale quotes"))
        self.assertTrue(self._said("[STALE] sharp moves: 0"))
