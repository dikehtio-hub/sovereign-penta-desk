"""
Unit tests for the Sports_Desk actionable-edge hotlist.

100% offline. Almost every test here asserts that something is NOT on the list,
because the whole value of a hotlist is what it leaves out - an edge on a
finished game, a stale quote, or a wager that loses money after tax all look
identical to a live opportunity in the raw edge table.
"""
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from Sports_Desk.data.db import init_market_db, record_settled_result
from Sports_Desk.ingestors.odds_watcher import OddsWatcher
from Sports_Desk.interfaces.cli_hotlist import (REASON_LIVE, REASON_REJECTED,
                                                REASON_SETTLED, REASON_STALE,
                                                REASON_STARTED, REASON_UNTRUSTED,
                                                build_hotlist, render_hotlist)
from Tax_Reserve_Agent.database.db import init_db
from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

NOW = datetime(2026, 9, 3, 18, 2, 0)
QUOTED = "2026-09-03T18:00:00Z"
STARTS = "2026-09-03T23:00:00Z"


def _market(event="G1", quoted=QUOTED, starts=STARTS, retail="+185",
            sport="NFL", extra=""):
    return (
        "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,"
        "start_time,is_live\n"
        f"{event},{sport},moneyline,Chiefs,Pinnacle,-140,1,{quoted},{starts},0\n"
        f"{event},{sport},moneyline,Ravens,Pinnacle,+120,1,{quoted},{starts},0\n"
        f"{event},{sport},moneyline,Ravens,DraftKings,{retail},0,{quoted},{starts},0\n"
        + extra)


class HotlistTestBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drop = self.root / "odds"
        self.drop.mkdir()
        self.db = self.root / "sports_market.db"
        self.ledger = self.root / "tax.db"
        init_market_db(self.db)
        init_db(self.ledger)

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
                                               "sandbox": 0.85}},
        })

    def _ingest(self, text, name="odds.csv", hook=None):
        (self.drop / name).write_text(text, encoding="utf-8")
        hook = hook or self._hook()
        watcher = OddsWatcher(
            drop_folder=self.drop, db_path=self.db,
            after_tax_hurdle=lambda odds: hook.breakeven_gross_edge(
                category="sports", decimal_odds=odds))
        watcher.scan_once()
        watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)

    def _hotlist(self, hook=None, now=NOW, **kwargs):
        params = dict(db_path=self.db, now=now, bankroll=50000.0,
                      include_rejected=True)
        params.update(kwargs)
        return build_hotlist(hook or self._hook(), **params)

    def _reasons(self, rows):
        return {row["reason"] or "actionable" for row in rows}


class TestActionableEdges(HotlistTestBase):

    def test_a_live_edge_clearing_the_hurdle_is_actionable_and_sized(self):
        hook = self._hook()
        self._ingest(_market(), hook=hook)
        rows = self._hotlist(hook)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["actionable"])
        self.assertGreater(row["approved_notional"], 0.0)
        self.assertGreater(row["gross_edge"], row["after_tax_hurdle"])
        self.assertGreater(row["after_tax_kelly"], 0.0)
        self.assertEqual(row["selection"], "Ravens")

    def test_the_list_is_ranked_by_approved_dollars_not_by_edge(self):
        """
        A 40% edge the bankroll gate sizes to $12 deserves less attention than a
        30% edge it sizes to $300. Ranking by edge alone puts the wrong bet first.
        """
        hook = self._hook()
        self._ingest(_market(event="BIG", retail="+185"), name="a.csv", hook=hook)
        self._ingest(_market(event="SMALL", retail="+150"), name="b.csv", hook=hook)
        rows = [r for r in self._hotlist(hook) if r["actionable"]]
        self.assertEqual(len(rows), 2)
        self.assertGreaterEqual(rows[0]["approved_notional"], rows[1]["approved_notional"])

    def test_only_the_newest_quote_per_selection_and_book_is_listed(self):
        """The edge table keeps history on purpose. History is not a shortlist."""
        hook = self._hook()
        self._ingest(_market(quoted="2026-09-03T17:58:00Z", retail="+150"),
                     name="early.csv", hook=hook)
        self._ingest(_market(quoted=QUOTED, retail="+185"), name="late.csv", hook=hook)
        rows = self._hotlist(hook)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["retail_offered_odds"], 2.85, places=6)


class TestExclusions(HotlistTestBase):
    """Everything the hotlist must leave out, and why."""

    def test_a_settled_event_is_dropped(self):
        """An edge on a finished game is a data lag, not an opportunity."""
        hook = self._hook()
        self._ingest(_market(), hook=hook)
        self.assertEqual(self._reasons(self._hotlist(hook)), {"actionable"})
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 1,
                              db_path=self.db)
        self.assertEqual(self._reasons(self._hotlist(hook)), {REASON_SETTLED})

    def test_a_stale_quote_is_dropped(self):
        """
        A stale sharp price against a live retail price is a clock difference -
        and the most flattering possible error, because the market has already
        moved to where the phantom edge points.
        """
        hook = self._hook()
        self._ingest(_market(), hook=hook)
        # NFL allows 300s; this is half an hour later.
        late = datetime(2026, 9, 3, 18, 30, 0)
        self.assertEqual(self._reasons(self._hotlist(hook, now=late)), {REASON_STALE})

    def test_the_staleness_limit_tightens_inside_the_last_hour(self):
        """A quote fresh enough at noon is not fresh enough at kickoff minus ten."""
        hook = self._hook()
        # Kickoff 20 minutes after the quote, so the NFL 300s limit halves to 150s.
        self._ingest(_market(quoted="2026-09-03T18:00:00Z",
                             starts="2026-09-03T18:20:00Z"), hook=hook)
        at_200s = datetime(2026, 9, 3, 18, 3, 20)
        self.assertEqual(self._reasons(self._hotlist(hook, now=at_200s)), {REASON_STALE})
        at_100s = datetime(2026, 9, 3, 18, 1, 40)
        self.assertEqual(self._reasons(self._hotlist(hook, now=at_100s)), {"actionable"})

    def test_an_event_that_has_started_is_dropped(self):
        """Pre-game prices do not survive first contact with the game."""
        hook = self._hook()
        self._ingest(_market(quoted="2026-09-03T22:59:00Z", starts=STARTS), hook=hook)
        after_kickoff = datetime(2026, 9, 3, 23, 0, 30)
        self.assertEqual(self._reasons(self._hotlist(hook, now=after_kickoff)),
                         {REASON_STARTED})

    def test_a_live_quote_is_dropped(self):
        """In-play is not comparable to the pre-game fair value it was scored on."""
        hook = self._hook()
        self._ingest(
            "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,"
            "start_time,is_live\n"
            f"L1,NFL,moneyline,Chiefs,Pinnacle,-140,1,{QUOTED},{STARTS},1\n"
            f"L1,NFL,moneyline,Ravens,Pinnacle,+120,1,{QUOTED},{STARTS},1\n"
            f"L1,NFL,moneyline,Ravens,DraftKings,+185,0,{QUOTED},{STARTS},1\n",
            hook=hook)
        self.assertEqual(self._reasons(self._hotlist(hook)), {REASON_LIVE})

    def test_a_divergent_sharp_market_is_dropped(self):
        """
        Two independent estimators disagreeing usually means a mistyped leg, and
        an edge computed from a mistyped leg is the largest edge in the file.

        The retail price here is deliberately GOOD (-200 against a 1.436 fair
        price, a +4.5% edge), so the row survives the min-edge filter and reaches
        the trust check. That is the dangerous shape: a mistyped sharp leg
        manufactures a plausible edge rather than an absurd one.
        """
        hook = self._hook()
        self._ingest(
            "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,"
            "start_time\n"
            f"D1,NFL,moneyline,A,Pinnacle,-110,1,{QUOTED},{STARTS}\n"
            f"D1,NFL,moneyline,B,Pinnacle,-1100,1,{QUOTED},{STARTS}\n"
            f"D1,NFL,moneyline,B,DraftKings,-200,0,{QUOTED},{STARTS}\n",
            hook=hook)
        rows = self._hotlist(hook)
        self.assertTrue(rows)
        self.assertEqual(self._reasons(rows), {REASON_UNTRUSTED})

    def test_a_sub_hurdle_edge_is_rejected_by_the_bankroll_gate(self):
        hook = self._hook()
        self._ingest(_market(retail="+140"), hook=hook)   # +4.55% vs a 6.15% hurdle
        rows = self._hotlist(hook)
        self.assertEqual(self._reasons(rows), {REASON_REJECTED})
        self.assertEqual(rows[0]["approved_notional"], 0.0)

    def test_under_a_standard_deduction_almost_nothing_is_actionable(self):
        """
        Not a bug. IRC 165(d) disallows losses entirely, so an even-money wager
        needs a 21.21% gross edge to break even after tax. The same market that a
        professional can bet is refused for a casual filer.
        """
        professional = self._hook("professional_schedule_c")
        self._ingest(_market(), hook=professional)
        self.assertEqual(self._reasons(self._hotlist(professional)), {"actionable"})
        casual = self._hook("casual_standard_deduction")
        self.assertEqual(self._reasons(self._hotlist(casual)), {REASON_REJECTED})

    def test_rejected_rows_are_hidden_unless_asked_for(self):
        hook = self._hook()
        self._ingest(_market(retail="+140"), hook=hook)
        self.assertEqual(build_hotlist(hook, db_path=self.db, now=NOW,
                                       bankroll=50000.0), [])
        self.assertEqual(len(self._hotlist(hook)), 1)


class TestRendering(HotlistTestBase):

    def test_an_actionable_row_renders_its_numbers(self):
        hook = self._hook()
        self._ingest(_market(), hook=hook)
        text = render_hotlist(self._hotlist(hook), bankroll=50000.0)
        self.assertIn("Ravens", text)
        self.assertIn("draftkings", text)
        self.assertIn("actionable", text)
        self.assertIn("total stake", text)

    def test_an_empty_hotlist_explains_itself(self):
        """
        The most common output under a standard deduction is nothing at all, and
        an operator who does not know why will assume the pipeline is broken.
        """
        text = render_hotlist([], bankroll=50000.0)
        self.assertIn("No actionable edges", text)
        self.assertIn("165(d)", text)
        self.assertIn("21.21%", text)

    def test_rejections_are_summarised_by_reason_when_shown(self):
        hook = self._hook()
        self._ingest(_market(retail="+140"), hook=hook)
        text = render_hotlist(self._hotlist(hook), include_rejected=True)
        self.assertIn("NOT ACTIONABLE", text)
        self.assertIn(REASON_REJECTED, text)

    def test_the_render_warns_that_placing_is_not_recording(self):
        """A wager the ledger never sees is a wager the escrow never reserves for."""
        text = render_hotlist([], bankroll=1000.0)
        self.assertIn("Tax_Reserve_Agent", text)


if __name__ == "__main__":
    unittest.main()
