"""
Monarch_Shark - the interactive betslip.

The point at which a recommendation becomes a wager. Everything upstream of this
is analysis; this is the only module that writes down that money moved.

WHAT IT IS NOT. It does not place bets with a sportsbook - there is no API to
place them through, and building one would be the least interesting and most
dangerous part of this system. It shows the hotlist, takes a decision, and
records what was staked at what price. The human does the clicking.

WHY RECORDING MATTERS MORE THAN IT LOOKS. `edge_opportunities` holds what was
OFFERED; `placed_bets` holds what was TAKEN. The gap between them is execution
slippage, and it is completely invisible unless both are kept. A desk that logs
only its ideas will conclude it has an edge long after the prices it can actually
get have stopped supporting one.

TWO THINGS THIS DELIBERATELY REFUSES TO DO
  * It will not stake a bet the bankroll gate rejected. The gate already knows
    about the after-tax hurdle, the strategy bucket and the escrow; overriding it
    from a betslip would make all three advisory.
  * It will not stake the same capital twice. THE GATE IS PER-ORDER, and it
    measures existing exposure from the TAX LEDGER - which does not learn about a
    wager until the book's export is imported, possibly days later. Left alone,
    every bet in a session is approved against a bucket that looks empty:
    measured on a $750 bucket, forty $31 bets went through for $1,249, or 1.7x.
    So the betslip reports its own open exposure to the gate on every order.
  * It does not write to the tax ledger. `Tax_Reserve_Agent` is fed by the book's
    own export, because the escrow must reserve against what the BOOK says
    happened, not what this desk believes it did. The confirmation says so every
    time, because forgetting it is how the escrow silently goes stale.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from Sports_Desk.data.db import (DEFAULT_DB_PATH, desk_performance, execution_clv,
                                 mark_exported, open_desk_exposure,
                                 query_placed_bets, record_placed_bet,
                                 unsynced_placed_bets)
from Sports_Desk.engine.arbitrage import render_arbitrage, scan_market_db
from Sports_Desk.interfaces.cli_hotlist import build_hotlist, render_hotlist

BANNER = "Monarch_Shark"

# How long a placed bet may sit without the tax ledger hearing about it before it
# is called out. Three days is a working week's slack: long enough that a Sunday
# card imported on Tuesday is not nagged about, short enough that a forgotten
# import surfaces inside the same quarter.
SYNC_ALERT_DAYS = 3.0

# Where the tax agent looks for drop-in CSVs.
TAX_DROP_DIR = (Path(__file__).resolve().parents[2]
                / "Tax_Reserve_Agent" / "data" / "imports")
TAX_EXPORT_NAME = "monarch_shark_bets.csv"


def _american(decimal_odds: float) -> str:
    if decimal_odds >= 2.0:
        return f"+{round((decimal_odds - 1) * 100):d}"
    return f"{round(-100 / (decimal_odds - 1)):d}"


class Betslip:
    """
    Drives the terminal session.

    `read` and `write` are injected so the whole thing is testable without a
    terminal - an interactive tool that can only be tested by hand does not get
    tested.
    """

    def __init__(self, hook: Any, db_path: Path = DEFAULT_DB_PATH,
                 read: Optional[Callable[[str], str]] = None,
                 write: Optional[Callable[[str], None]] = None,
                 bankroll: Optional[float] = None,
                 now: Optional[datetime] = None):
        self.hook = hook
        self.db_path = Path(db_path)
        self.read = read or input
        self.write = write or print
        self.bankroll = bankroll
        self.now = now

    # -- presentation -------------------------------------------------------

    def open_exposure(self, strategy: str = "sports_betting") -> float:
        """
        What the strategy already has at risk, from BOTH sources.

        The max rather than the sum, deliberately: once the book's export reaches
        the tax ledger a bet appears in both places, and adding them would
        double-count it into a permanent phantom exposure. Before the import the
        desk figure is the only one that knows; after it, the ledger figure is at
        least as large. Taking the larger is right in both regimes.
        """
        ledger = float(self.hook.get_strategy_open_exposure(strategy) or 0.0)
        return max(ledger, open_desk_exposure(db_path=self.db_path))

    def open_event_exposure(self, event_id: str) -> float:
        """
        Everything already staked on ONE event, settled bets excluded.

        BRIDGE C, THE CANNIBALISATION GUARD. Chiefs ML and Chiefs -3.5 are close
        to the same bet, and the sizer treats them as independent - so backing
        both puts double the intended risk on a single outcome. Kelly on
        correlated positions is not additive, and the honest simplification is to
        make one GAME share one position cap rather than pretend to know the
        correlation.
        """
        return sum(float(bet["stake"]) for bet in query_placed_bets(db_path=self.db_path)
                   if bet["event_id"] == event_id and not bet.get("outcome"))

    def event_cap(self, strategy: str = "sports_betting") -> float:
        """
        The most that may sit on ONE game: the same cap a single order gets.

        SCALED TO THE STRATEGY BUCKET, NOT THE WHOLE BANKROLL. The obvious reading
        - 5% of the safe bankroll - is 6.7x looser than the per-order cap once
        bucketing is on (the default), so it would take about seven legs on one
        game before it bound and the guard would be nearly inert. Making it the
        SAME number as the per-order cap is what actually expresses the intent:
        one game gets one position's worth of risk, however many legs it is
        sliced into.
        """
        safe = float(self.hook.get_safe_bankroll(self.bankroll))
        budget = self.hook.strategy_budget(strategy, safe, 0.0)
        pool = budget.budget if budget.enforced else safe
        return float(pool) * float(self.hook.max_position_pct)

    def show_hotlist(self, min_edge: float = 0.0,
                     strategy: str = "sports_betting") -> List[Dict[str, Any]]:
        rows = build_hotlist(self.hook, db_path=self.db_path, now=self.now,
                             min_edge=min_edge, bankroll=self.bankroll,
                             strategy=strategy,
                             already_deployed=self.open_exposure(strategy),
                             include_rejected=False)
        safe = self.hook.get_safe_bankroll(self.bankroll)
        self.write(render_hotlist(rows, bankroll=safe))
        return rows

    def show_arbitrage(self) -> List[Any]:
        opportunities = scan_market_db(self.hook, db_path=self.db_path, now=self.now)
        self.write(render_arbitrage(opportunities,
                                    bankroll=self.hook.get_safe_bankroll(self.bankroll)))
        return opportunities

    def show_cross_market(self, questions: Optional[Sequence[Dict[str, Any]]] = None,
                          gambling_win_capacity: float = 0.0,
                          capital_gain_capacity: float = 0.0,
                          prediction_is_wagering: bool = False) -> List[Any]:
        """
        Polymarket against the sportsbooks, priced through the asymmetric tax.

        Kept OUT of the ordinary arbitrage panel on purpose. A same-venue arb and
        a cross-market one look identical in dollars and are governed by
        completely different tax mechanics - one delta, versus two reliefs that
        each depend on income the other leg does not produce. Merging them into
        one list would invite the reader to compare a 2% here with a 2% there as
        though the numbers meant the same thing, and they do not.
        """
        from cross_market.hud import render_cross_market, scan_cross_market
        results, pairs = scan_cross_market(
            self.hook, questions or self._load_polymarket_questions(),
            db_path=self.db_path,
            capital=self.hook.get_safe_bankroll(self.bankroll),
            gambling_win_capacity=gambling_win_capacity,
            capital_gain_capacity=capital_gain_capacity,
            prediction_is_wagering=prediction_is_wagering)
        self.write(render_cross_market(results, pairs))
        self.cross_market_pairs = list(pairs)            # Round 63: kept so a pick can be staked
        return results

    def stake_cross_market(self, result: Any, pair: Any, confirm: bool = True, paper: bool = False,
                           imports_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """
        Round 63 (Directive 63-2): record an EXECUTED cross-market dutch - the
        Polymarket leg as an execution receipt for the Tax agent, the book leg in
        placed_bets - under one arb_group and one timestamp, through
        cross_market.execution_log.record_dutch.

        REFUSED WHOLESALE when the pair loses on its worse branch after tax
        (worst_after_tax below the capital): one leg of a rejected dutch is a
        naked bet. `paper=True` records both legs as paper receipts only; the tax
        ledger and the desk's exposure never see a paper fill.
        """
        from cross_market.execution_log import STAMP_FORMAT, format_record, record_dutch
        if float(result.worst_after_tax) < float(result.capital):
            self.write(f"  [refused] cross-market dutch returns ${float(result.worst_after_tax):,.2f} after tax "
                       f"on ${float(result.capital):,.2f} staked on its worse branch - every time, not on average.")
            return None
        legs = ((result.leg_a, result.stake_a), (result.leg_b, result.stake_b))
        pm = [(leg, stake) for leg, stake in legs if str(getattr(leg, "venue", "")).lower() == "polymarket"]
        book = [(leg, stake) for leg, stake in legs if str(getattr(leg, "venue", "")).lower() != "polymarket"]
        if len(pm) != 1 or len(book) != 1:
            self.write("  [refused] a cross-market dutch needs exactly one Polymarket leg and one book leg.")
            return None
        (pm_leg, pm_stake), (book_leg, book_stake) = pm[0], book[0]
        price = float(getattr(pm_leg, "raw_price", None) or (1.0 / float(pm_leg.decimal_odds)))
        shares = float(pm_stake) / price if price > 0 else 0.0
        if confirm:
            self.write(f"  Record {'PAPER ' if paper else ''}dutch: ${float(pm_stake):,.2f} of Polymarket "
                       f"{pm_leg.selection} @ {price:.4f} ({shares:,.2f} shares) + ${float(book_stake):,.2f} on "
                       f"{book_leg.selection} @ {float(book_leg.decimal_odds):.3f} ({book_leg.venue}) for "
                       f"{float(result.gross_arb) * 100:.2f}% gross?")
            if not _yes(self.read("  [y/N] ")):
                self.write("  [cancelled] nothing recorded.")
                return None
        market = getattr(pair, "market", None)
        record = record_dutch(
            pm_market=str(getattr(market, "token_id", "") or getattr(market, "question", "") or pm_leg.selection),
            pm_price=price, pm_shares=shares, book=str(book_leg.venue), selection=str(book_leg.selection),
            decimal_odds=float(book_leg.decimal_odds), stake=float(book_stake),
            event_id=str(getattr(pair, "event_id", "") or ""), sport=str(getattr(market, "sport", "") or ""),
            market_type=str(getattr(market, "market_type", "") or ""), line=str(getattr(market, "line", "") or ""),
            pm_tx_hash=None, timestamp=(self.now.strftime(STAMP_FORMAT) if self.now else None),
            edge_at_placement=float(result.gross_arb), sports_db=self.db_path, imports_dir=imports_dir, paper=paper)
        self.write(format_record(record))
        if paper:
            self.write("  Paper: neither the tax ledger nor placed_bets saw this. Receipts are under "
                       f"{record['receipts_dir']}.")
        else:
            self.write("  The Polymarket leg is a tagged execution receipt for the Tax agent. The book leg is "
                       "NOT a tax record - import the book's own export through Tax_Reserve_Agent.")
        return record

    def _load_polymarket_questions(self) -> List[Dict[str, Any]]:
        """
        Live Polymarket questions, from the drop folder when one is present.

        Returns an empty list rather than reaching for the network. This CLI is
        offline by construction and every test in the suite runs without a socket;
        a silent HTTP call here would make the panel's output depend on whether
        the machine happens to have connectivity, which is not something the
        operator can see from the screen.
        """
        import json
        drop = Path(__file__).resolve().parents[1] / "data" / "polymarket_drops"
        if not drop.exists():
            return []
        found: List[Dict[str, Any]] = []
        for path in sorted(drop.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.write("  [WARN] %s is not readable JSON (%s); skipped." % (path.name, exc))
                continue
            found.extend(payload if isinstance(payload, list) else [payload])
        return found

    # -- Bridge A: is the tax ledger in step? -------------------------------

    def check_sync(self, older_than_days: float = SYNC_ALERT_DAYS,
                   tax_db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Placed bets the tax ledger has never heard of.

        THE ESCROW IS ONLY AS GOOD AS THE IMPORT, and until now nothing checked.
        Every other guard in this system can be working and the reserve still be
        wrong, because the ledger learns about a wager only when the book's export
        is dropped in.
        """
        stale = unsynced_placed_bets(tax_db_path=tax_db_path,
                                     older_than_days=older_than_days,
                                     now=self.now, db_path=self.db_path)
        if not stale:
            return []
        owed = sum(float(b["stake"]) for b in stale)
        self.write(f"  [!] {len(stale)} placed bet(s) totalling ${owed:,.2f} are more "
                   f"than {older_than_days:.0f} days old and DO NOT appear in the tax "
                   f"ledger. The escrow is under-reserving by whatever they win.")
        for bet in stale[:10]:
            age = bet.get("age_days")
            self.write(f"      ${float(bet['stake']):>8,.2f}  {bet['selection']:<20}"
                       f"{bet['book']:<13}{'' if age is None else f'{age:.0f}d old'}"
                       f"{'  (loose match only)' if bet['match_confidence'] == 'loose' else ''}")
        self.write("      Import the book's export, or run --export-to-tax-agent.")
        return stale

    def export_to_tax_agent(self, tax_db_path: Optional[Path] = None,
                            drop_dir: Optional[Path] = None,
                            older_than_days: Optional[float] = None) -> Optional[Path]:
        """
        Writes un-synced bets into the tax agent's drop folder as a CSV the
        existing `SportsBettingIngestor` already understands.

        A STOPGAP, NOT A REPLACEMENT FOR THE BOOK'S EXPORT. This carries what the
        DESK believes it staked; the book is the authority on what actually
        happened, including the settlement, which is not here at all. The point is
        that the escrow should not be blind in the meantime.

        IDEMPOTENCY DEPENDS ON THE TICKET ID. The ingestor builds its `tx_hash` as
        `{book}_{ticket}_bet`, and the ledger's UNIQUE constraint ignores a repeat.
        So a row exported WITH the book's ticket id will be silently ignored when
        the real export arrives - correct, one wager, one lot. A row exported
        WITHOUT one gets a desk-generated id that the book's file cannot match, so
        importing both would book the wager TWICE. Those rows are still written,
        because leaving them out understates the escrow, but they are flagged in
        the notes and called out on the way past.
        """
        pending = unsynced_placed_bets(tax_db_path=tax_db_path,
                                       older_than_days=older_than_days,
                                       now=self.now, db_path=self.db_path)
        if not pending:
            self.write("  [ok] every placed bet is already in the tax ledger.")
            return None

        target_dir = Path(drop_dir) if drop_dir else TAX_DROP_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / TAX_EXPORT_NAME

        import csv as _csv
        unmatched = 0
        with open(target, "w", encoding="utf-8", newline="") as handle:
            writer = _csv.writer(handle)
            writer.writerow(["ticket_id", "sportsbook", "sport", "market_type",
                             "selection", "wager", "odds", "odds_format",
                             "timestamp", "notes"])
            for bet in pending:
                ticket = bet.get("ticket_id")
                if not ticket:
                    unmatched += 1
                    ticket = f"SHARK{int(bet['id'])}"
                writer.writerow([
                    ticket, bet["book"], bet["sport"], bet["market_type"],
                    bet["selection"], f"{float(bet['stake']):.2f}",
                    f"{float(bet['decimal_odds']):.6f}", "decimal",
                    bet["placed_at"],
                    "source:monarch_shark" + ("" if bet.get("ticket_id")
                                              else ";no_book_ticket_id:true"),
                ])
        mark_exported([b["id"] for b in pending], db_path=self.db_path)
        self.write(f"  [export] {len(pending)} bet(s) -> {target}")
        self.write(f"           run: python -m Tax_Reserve_Agent.main import")
        if unmatched:
            self.write(f"  [!] {unmatched} of them had NO book ticket id, so the "
                       f"sportsbook's own export will NOT collide with them - "
                       f"importing both would book those wagers twice. Record the "
                       f"ticket id at stake time to avoid this.")
        return target

    def show_performance(self) -> Dict[str, Any]:
        stats = desk_performance(db_path=self.db_path)
        self.write(render_performance(stats))
        return stats

    def show_clv(self) -> List[Dict[str, Any]]:
        rows = execution_clv(db_path=self.db_path)
        self.write(render_execution_clv(rows))
        return rows

    # -- staking ------------------------------------------------------------

    def stake(self, row: Dict[str, Any], amount: Optional[float] = None,
              confirm: bool = True) -> Optional[int]:
        """
        Records one wager from a hotlist row.

        `amount` defaults to what the bankroll gate approved. A LARGER amount is
        refused outright rather than clamped: a betslip that quietly halves what
        you typed is worse than one that says no, because you would place the
        number you typed at the book and the ledger would disagree with reality.
        """
        strategy = row.get("strategy", "sports_betting")

        # RE-GATE AT STAKE TIME against exposure as it stands NOW. The hotlist
        # was sized when it was built; three bets later the bucket is smaller.
        regated = self.hook.check_order(
            float(row.get("approved_notional") or 0.0) or 1.0,
            live_cash=self.bankroll, category="sports", strategy=strategy,
            already_deployed=self.open_exposure(strategy),
            expected_edge=row.get("gross_edge"),
            decimal_odds=row.get("retail_offered_odds"))
        if regated.approved:
            row = dict(row)
            row["approved_notional"] = regated.approved_notional
        else:
            row = dict(row)
            row["actionable"] = False
            row["reason"] = regated.reason

        # BRIDGE C: one game, one position cap.
        cap = self.event_cap(strategy)
        on_event = self.open_event_exposure(row["event_id"])
        headroom = max(0.0, cap - on_event)
        if headroom <= 0:
            self.write(f"  [refused] {row.get('selection')}: ${on_event:,.2f} is already "
                       f"staked on {row['event_id']}, at the ${cap:,.2f} single-game cap. "
                       f"Legs on one game are close to the same bet - the sizer treats "
                       f"them as independent and they are not.")
            return None
        row = dict(row)
        row["approved_notional"] = min(float(row.get("approved_notional") or 0.0), headroom)

        approved = float(row.get("approved_notional") or 0.0)
        if not row.get("actionable") or approved <= 0:
            self.write(f"  [refused] {row.get('selection')}: the bankroll gate did not "
                       f"approve this ({row.get('reason') or 'not actionable'}).")
            return None

        stake = approved if amount is None else float(amount)
        if stake > approved + 1e-9:
            self.write(f"  [refused] ${stake:,.2f} exceeds the ${approved:,.2f} the gate "
                       f"approved. Lower the stake or raise the bankroll - this is not "
                       f"clamped on purpose, so what you place is what is recorded.")
            return None
        if stake <= 0:
            self.write("  [refused] stake must be positive.")
            return None

        ticket_id = None
        if confirm:
            self.write(f"  Stake ${stake:,.2f} on {row['selection']} "
                       f"@ {_american(float(row['retail_offered_odds']))} "
                       f"({row['retail_book']})?")
            if not _yes(self.read("  [y/N] ")):
                self.write("  [cancelled] nothing recorded.")
                return None
            # THE BOOK'S OWN TICKET ID, asked for while it is on screen. It is the
            # only thing that lets the tax export produce the same `tx_hash` the
            # sportsbook CSV will produce later - without it the two imports do
            # not collide and the wager is booked TWICE.
            ticket_id = (self.read("  book ticket id [blank = none] ") or "").strip() or None

        bet_id = record_placed_bet(
            event_id=row["event_id"], sport=row["sport"],
            market_type=row["market_type"], line=row.get("line", ""),
            selection=row["selection"], book=row["retail_book"],
            decimal_odds=float(row["retail_offered_odds"]), stake=stake,
            fair_prob_at_placement=row.get("sharp_fair_prob"),
            edge_at_placement=row.get("gross_edge"),
            after_tax_hurdle=row.get("after_tax_hurdle"),
            kelly_fraction=row.get("after_tax_kelly"),
            ticket_id=ticket_id,
            placed_at=(self.now.isoformat() if self.now else None),
            db_path=self.db_path)
        self.write(f"  [recorded #{bet_id}] ${stake:,.2f} on {row['selection']} "
                   f"@ {_american(float(row['retail_offered_odds']))} "
                   f"({row['retail_book']})")
        self.write("  Reminder: this is NOT a tax record. Import the book's own export "
                   "through Tax_Reserve_Agent or the escrow will not know about it.")
        return bet_id

    def stake_arbitrage(self, opportunity: Any, bankroll: Optional[float] = None,
                        confirm: bool = True) -> List[int]:
        """
        Records every leg of an arbitrage as one group.

        REFUSED WHOLESALE IF IT DOES NOT CLEAR THE AFTER-TAX HURDLE. An arb is a
        single position - staking the legs one at a time would let a rejected one
        through as a naked bet, which is the opposite of riskless.
        """
        if not opportunity.clears_hurdle:
            self.write(f"  [refused] arbitrage of {opportunity.gross_arb * 100:.2f}% is "
                       f"below the {opportunity.after_tax_hurdle * 100:.2f}% after-tax "
                       f"hurdle. Staking it loses "
                       f"{abs(opportunity.worst_case_after_tax) * 100:.2f}% on the worst "
                       f"leg - every time, not on average.")
            return []

        total = float(bankroll if bankroll is not None
                      else self.hook.get_safe_bankroll(self.bankroll))
        if confirm:
            self.write(f"  Stake ${total:,.2f} across {len(opportunity.legs)} legs "
                       f"for {opportunity.gross_arb * 100:.2f}% gross?")
            if not _yes(self.read("  [y/N] ")):
                self.write("  [cancelled] nothing recorded.")
                return []

        group = f"arb-{opportunity.event_id}-{opportunity.market_type}"
        placed: List[int] = []
        for leg in opportunity.legs:
            placed.append(record_placed_bet(
                event_id=opportunity.event_id, sport=opportunity.sport,
                market_type=opportunity.market_type, line=opportunity.line,
                selection=leg.selection, book=leg.book,
                decimal_odds=leg.decimal_odds, stake=leg.stake_for(total),
                after_tax_hurdle=opportunity.after_tax_hurdle,
                bet_kind="arbitrage", arb_group=group,
                placed_at=(self.now.isoformat() if self.now else None),
                db_path=self.db_path))
            self.write(f"  [recorded #{placed[-1]}] ${leg.stake_for(total):,.2f} on "
                       f"{leg.selection} @ {leg.decimal_odds:.3f} ({leg.book})")
        return placed

    # -- loop ---------------------------------------------------------------

    def run(self) -> int:
        """Interactive session. Returns the number of bets recorded."""
        recorded = 0
        rows = self.show_hotlist()
        while True:
            self.write("")
            self.write("  [n] stake by number   [a] arbitrage   [x] cross-market   [c] execution CLV")
            self.write("  [p] desk performance  [s] tax-ledger sync   [r] refresh   [q] quit")
            choice = (self.read("  > ") or "").strip().lower()
            if choice in ("q", "quit", "exit", ""):
                break
            if choice in ("r", "refresh"):
                rows = self.show_hotlist()
            elif choice in ("a", "arb", "arbitrage"):
                opportunities = self.show_arbitrage()
                if opportunities:
                    pick = (self.read("  stake which? [1-%d, blank to skip] "
                                      % len(opportunities)) or "").strip()
                    index = _index(pick, len(opportunities))
                    if index is not None:
                        recorded += len(self.stake_arbitrage(opportunities[index]))
            elif choice in ("x", "cross", "cross-market"):
                results = self.show_cross_market()
                pairs = getattr(self, "cross_market_pairs", [])
                if results and pairs:
                    pick = (self.read("  record which cross-market dutch? [1-%d, blank to skip] "
                                      % len(results)) or "").strip()
                    index = _index(pick, len(results))
                    if index is not None and index < len(pairs):
                        record = self.stake_cross_market(results[index], pairs[index])
                        recorded += 1 if record and record.get("complete") else 0
            elif choice in ("c", "clv"):
                self.show_clv()
            elif choice in ("p", "perf", "performance"):
                self.show_performance()
            elif choice in ("s", "sync"):
                if not self.check_sync():
                    self.write("  [ok] the tax ledger is in step with every placed bet.")
            else:
                index = _index(choice, len(rows))
                if index is None:
                    self.write("  [?] not a listed number.")
                    continue
                amount = (self.read("  stake [blank = approved size] ") or "").strip()
                try:
                    value = float(amount) if amount else None
                except ValueError:
                    self.write("  [?] not a number.")
                    continue
                if self.stake(rows[index], value) is not None:
                    recorded += 1
        return recorded


def render_performance(stats: Dict[str, Any]) -> str:
    """
    What the desk did with real money.

    Realised P&L is the only line here that can be spent. Everything else -
    CLV, the Brier score, the edge estimates - is a leading indicator, and a
    desk that watches only those can be confidently wrong for a whole season.
    """
    lines = ["=" * 78,
             "          DESK PERFORMANCE - realised, not modelled",
             "=" * 78]
    if not stats["bets_settled"]:
        lines.append(f"  Nothing settled yet ({stats['bets_pending']} bet(s) pending).")
        lines.append("=" * 78)
        return "\n".join(lines)

    pnl = stats["realized_pnl"]
    lines.append(f"  Settled {stats['bets_decided']} bet(s)"
                 + (f" + {stats['pushes']} push(es)" if stats["pushes"] else "")
                 + f" | {stats['bets_pending']} pending")
    lines.append(f"  Turnover        ${stats['turnover']:>12,.2f}")
    lines.append(f"  Realised P&L    ${pnl:>+12,.2f}")
    if stats["roi"] is not None:
        lines.append(f"  ROI             {stats['roi'] * 100:>12.2f}%")
    lines.append("-" * 78)
    if stats["win_rate"] is not None:
        expected = stats["expected_win_rate"]
        lines.append(f"  Win rate        {stats['win_rate'] * 100:>12.2f}%"
                     + (f"   model expected {expected * 100:.2f}%"
                        if expected is not None else ""))
        if expected is not None and stats["bets_decided"] >= 20:
            gap = stats["win_rate"] - expected
            verdict = ("model is CALIBRATED" if abs(gap) < 0.05
                       else "model is MISCALIBRATED - it is not bad luck")
            lines.append(f"                  gap {gap * 100:+.2f} points: {verdict}")
    if stats["avg_clv"] is not None:
        lines.append(f"  Avg execution CLV {stats['avg_clv'] * 100:>+10.2f} points "
                     f"over {stats['clv_measured']} measured bet(s)")
    lines.append("=" * 78)
    lines.append("  A positive CLV with a negative P&L means the prices were right and")
    lines.append("  the sample is small. The reverse means the opposite, and is worse.")
    lines.append("=" * 78)
    return "\n".join(lines)


def render_execution_clv(rows: Sequence[Dict[str, Any]]) -> str:
    """CLV on the bets actually placed."""
    lines = ["=" * 96,
             "          EXECUTION CLV - bets placed, not quotes observed",
             "=" * 96]
    if not rows:
        lines.append("  No bets recorded yet.")
        lines.append("=" * 96)
        return "\n".join(lines)

    lines.append(f"  {'STAKE':>9}  {'TOOK':>8}  {'FAIR@BET':>9}  {'CLOSE':>9}  "
                 f"{'CLV':>8}  {'PRICE':>6}  SELECTION")
    lines.append("-" * 96)
    measured = 0
    beat = 0
    for row in rows:
        delta = row.get("clv_prob_delta")
        if delta is None:
            clv = "     n/a"
            price = "   n/a"
        else:
            measured += 1
            beat += 1 if row["beat_close"] else 0
            clv = f"{delta * 100:+7.2f}%"
            price = "  win " if row["beat_closing_price"] else "  lose"
        entry = row.get("fair_prob_at_placement")
        closing = row.get("closing_fair_prob")
        lines.append(
            f"  ${float(row['stake']):>8,.2f}  "
            f"{_american(float(row['decimal_odds'])):>8}  "
            f"{(f'{entry:.4f}' if entry else '     -'):>9}  "
            f"{(f'{closing:.4f}' if closing else '     -'):>9}  "
            f"{clv}  {price}  {row['selection']} ({row['event_id']})")
    lines.append("-" * 96)
    if measured:
        lines.append(f"  Beat the close on {beat} of {measured} measured bet(s) "
                     f"({beat / measured * 100:.0f}%).")
        lines.append("  Below ~50% over a real sample means the edges are not real,")
        lines.append("  however profitable the last few weeks looked.")
    else:
        lines.append("  Nothing measurable yet - no closing lines recorded for these bets.")
    lines.append("=" * 96)
    return "\n".join(lines)


def _yes(answer: Optional[str]) -> bool:
    return str(answer or "").strip().lower() in ("y", "yes")


def _index(text: str, count: int) -> Optional[int]:
    try:
        value = int(str(text).strip())
    except (TypeError, ValueError):
        return None
    return value - 1 if 1 <= value <= count else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BANNER} - interactive betslip")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--bankroll", type=float, default=None)
    parser.add_argument("--min-edge", type=float, default=0.0)
    parser.add_argument("--clv", action="store_true", help="print execution CLV and exit")
    parser.add_argument("--arb", action="store_true", help="print arbitrage and exit")
    parser.add_argument("--performance", action="store_true",
                        help="print realised P&L / ROI / calibration and exit")
    # --reconcile is the same switch under the name the desk actually uses for
    # it. Both spellings land on args.check_sync.
    parser.add_argument("--check-sync", "--reconcile", action="store_true",
                        dest="check_sync",
                        help="reconcile placed bets against the tax ledger and "
                             "list any the ledger has not seen")
    parser.add_argument("--cross-market", action="store_true",
                        help="Polymarket vs sportsbook, priced after asymmetric tax")
    parser.add_argument("--gambling-win-capacity", type=float, default=0.0,
                        help="YTD gambling winnings a sportsbook loss can net "
                             "against under NJ 54A:5-1(g). Default 0 - the "
                             "conservative case, and usually the true one")
    parser.add_argument("--capital-gain-capacity", type=float, default=0.0,
                        help="YTD capital gains a Polymarket loss can offset "
                             "under IRC 1211(b) beyond the $3,000 ordinary tranche")
    parser.add_argument("--prediction-as-wagering", action="store_true",
                        help="price the ADVERSE reading, in which a Polymarket "
                             "contract is a wager under IRC 165(d) rather than "
                             "a capital asset")
    parser.add_argument("--export-to-tax-agent", action="store_true",
                        help="write un-synced bets into the tax agent drop folder "
                             "(Tax_Reserve_Agent/data/imports - the path config.yaml "
                             "imports.drop_folder actually watches)")
    args = parser.parse_args(argv)

    from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
    slip = Betslip(get_hook(), db_path=args.db or DEFAULT_DB_PATH,
                   bankroll=args.bankroll)
    if args.clv:
        slip.show_clv()
        return 0
    if args.arb:
        slip.show_arbitrage()
        return 0
    if args.performance:
        slip.show_performance()
        return 0
    if args.cross_market:
        slip.show_cross_market(
            gambling_win_capacity=args.gambling_win_capacity,
            capital_gain_capacity=args.capital_gain_capacity,
            prediction_is_wagering=args.prediction_as_wagering)
        return 0
    if args.check_sync:
        if not slip.check_sync():
            print("  [ok] the tax ledger is in step with every placed bet.")
        return 0
    if args.export_to_tax_agent:
        slip.export_to_tax_agent()
        return 0
    slip.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
