"""
Sports betting ingestor.

Turns wagers and settlements into the same transaction shape every other
ingestor emits, so the FIFO engine and the escrow calculator need no special
cases beyond `asset_class == "sports_bet"`.

THE TICKET IS THE LOT. This is the single most important decision in the file.
A wager is not fungible with another wager on the same selection: two $20 and
$500 tickets on CHIEFS -3.5 are two distinct lots with two distinct stakes, and
if they share a `symbol` the lot matcher will settle one against the other's
basis. Keying the symbol on the ticket id makes each ticket its own lot family
and makes cross-matching structurally impossible rather than merely unlikely.

  DK:NFL:CHIEFS_-3.5#T1

FRACTIONAL SETTLEMENT. The opening lot carries `quantity = 1.0` - one ticket -
so a settlement of `quantity = f` closes the fraction `f` of it and leaves the
rest open. That is what makes dead heats, partial voids and partial cashouts
representable without a second lot model: settle `f` at `payout / f` and the
engine books `payout` of proceeds against `f x wager` of basis, which is exactly
the arithmetic a book prints on the ticket.

WHAT A SETTLEMENT ROW MEANS
  BET_WIN      ticket won; `price` is the total returned, stake included
  BET_LOSS     ticket lost; proceeds are zero BY DEFINITION, not by price
  BET_PUSH     stake refunded (push, void, postponed, cancelled) - nets to zero
  BET_CASHOUT  settled early for `price`, which may be above OR below the stake.
               A cashout below the stake is a real loss of (stake - price), NOT
               a loss of the stake, which is why it cannot be a BET_LOSS.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..engine.gambling_tax import assess_w2g
from ..engine.odds import OddsFormatError, OddsQuote, parse_odds, payout_discrepancy

ASSET_CLASS = "sports_bet"
DEFAULT_STRATEGY = "sports_betting"

# Result vocabularies, normalised. Books are not consistent about any of these.
WIN_WORDS = frozenset({"WIN", "WON", "WINNER", "W"})
LOSS_WORDS = frozenset({"LOSS", "LOST", "LOSE", "LOSER", "L"})
PUSH_WORDS = frozenset({"PUSH", "VOID", "VOIDED", "CANCELLED", "CANCELED", "REFUND",
                        "REFUNDED", "TIE", "NO_ACTION", "POSTPONED", "P"})
CASHOUT_WORDS = frozenset({"CASHOUT", "CASHED_OUT", "CASH_OUT", "CASHED", "SETTLED_EARLY"})
HALF_WIN_WORDS = frozenset({"HALF_WIN", "HALFWIN", "WIN_HALF", "DEAD_HEAT_WIN"})
HALF_LOSS_WORDS = frozenset({"HALF_LOSS", "HALFLOSS", "LOSS_HALF", "DEAD_HEAT_LOSS"})
OPEN_WORDS = frozenset({"", "OPEN", "PENDING", "UNSETTLED", "LIVE", "PLACED", "ACTIVE"})

# Words a book prints when the stake was theirs, not yours. A wager marked with
# one of these has ZERO cost basis - see `create_bet_placed`.
PROMO_WORDS = frozenset({"FREE", "FREEBET", "FREE_BET", "PROMO", "PROMOTIONAL",
                         "BONUS", "BONUSBET", "BONUS_BET", "TOKEN", "Y", "YES",
                         "TRUE", "1"})
PROMO_COLUMNS = ("promo", "is_promo", "free_bet", "freebet", "is_free_bet",
                 "bonus", "bonus_bet", "bet_type", "wager_type", "stake_type")

# The columns that say a stake was promotional by carrying a NUMBER rather than a
# word. This is how the two biggest books actually export it, and matching only
# on words missed both: FanDuel writes `Cash Wager: 0.00, Bonus Wager: 25.00` and
# DraftKings writes `Stake: 0.00, Free Bet Stake: 50.00`. Neither row contains
# the string "bonus" as a VALUE anywhere, so the whole wager was skipped as a
# missing stake column and its winnings never reached the ledger.
PROMO_AMOUNT_COLUMNS = ("free_bet_stake", "freebet_stake", "bonus_wager",
                        "bonus_stake", "promo_stake", "free_bet_amount",
                        "bonus_amount", "bonus_bet_amount")
# The cash-funded side, where a book splits the two.
CASH_STAKE_COLUMNS = ("cash_wager", "cash_stake", "cash_amount")

_BOOK_STAKE_IS_CASH_RAW = ("betrivers", "sugarhouse", "kambi", "twinspires",
                           "barstool", "espn_bet", "espnbet", "thescore")

# A ticket still running at year end is NOT a realised loss. IRS treats the wager
# as an open position until it settles; reserving against it, or deducting it,
# are both wrong. These rows produce an opening lot and nothing else.
_SETTLEMENT_TOLERANCE = 1e-9


class BetSettlementError(ValueError):
    """A settlement row that cannot be interpreted. Never guessed - always raised."""


def _row_fingerprint(row: Dict[str, Any], source: str) -> str:
    payload = "|".join(f"{k}={row.get(k, '')}" for k in sorted(row.keys()))
    return f"{source}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


# One book, one spelling. `DK` and `DraftKings` produced two different `source`
# values and two different lot families, so a placement imported from one export
# never matched a settlement imported from the other - the settlement then hit
# the zero-basis orphan path and taxed the whole payout. Canonical names are the
# fix; add to this map rather than teaching callers to spell it right.
BOOK_ALIASES = {
    "dk": "draftkings", "draftkings": "draftkings", "draft kings": "draftkings",
    "fd": "fanduel", "fanduel": "fanduel", "fan duel": "fanduel",
    "mgm": "betmgm", "betmgm": "betmgm", "bet mgm": "betmgm",
    "czr": "caesars", "caesars": "caesars", "caesar": "caesars",
    "williamhill": "caesars", "william hill": "caesars",
    "pn": "pinnacle", "pinnacle": "pinnacle", "pinny": "pinnacle",
    "b365": "bet365", "bet365": "bet365", "bet 365": "bet365",
    "pb": "pointsbet", "pointsbet": "pointsbet", "points bet": "pointsbet",
    "espnbet": "espnbet", "espn bet": "espnbet",
    "br": "betrivers", "betrivers": "betrivers", "bet rivers": "betrivers",
    "hr": "hardrock", "hardrock": "hardrock", "hard rock": "hardrock",
    "fanatics": "fanatics", "circa": "circa", "bookmaker": "bookmaker",
}


def canonical_book(name: Any) -> str:
    """
    Folds a book's many spellings onto one name.

    NOT a lossless transform, and it changes `source` - which is part of the
    ledger's UNIQUE key. A ledger already holding rows under `dk` will not
    recognise the same wagers re-imported as `draftkings`; rebuild rather than
    merge if that ever happens. Safe here only because the wagering module is
    new and nothing has been imported under the old spellings.
    """
    raw = str(name or "").strip()
    if not raw:
        return "sportsbook"
    squashed = " ".join(raw.lower().replace("_", " ").replace("-", " ").split())
    if squashed in BOOK_ALIASES:
        return BOOK_ALIASES[squashed]
    compact = squashed.replace(" ", "")
    return BOOK_ALIASES.get(compact, compact or "sportsbook")


# Books whose `stake` column is the CASH side even with no separate cash column,
# so the ticket total is stake + promo. Everywhere else a `stake` at or above the
# promo amount is read as the TOTAL, which gives the lower basis and the higher
# taxable winnings - see `_rows_from_record`.
#
# This set is the ONLY thing that distinguishes the two readings when a book
# reports one stake column and a promo column, because the numbers cannot. Adding
# a book here RAISES its cost basis and LOWERS its taxable winnings, so each entry
# needs a real export behind it, not a guess.
#
# NORMALISED THROUGH `canonical_book` AT IMPORT, because it is compared against
# canonicalised names. Spelled raw it would silently never match: `espn_bet`
# canonicalises to `espnbet`, so the raw form is dead weight - the same way
# `kambi` is dead weight regardless, being the B2B platform behind BetRivers
# rather than a consumer brand that appears in an export.
BOOK_STAKE_IS_CASH = frozenset(canonical_book(name)
                               for name in _BOOK_STAKE_IS_CASH_RAW)


def bet_symbol(sportsbook: str, sport: str, selection: str, ticket_id: str) -> str:
    """
    The lot key. The ticket id is what makes it unique; the rest is there so a
    human reading `tax_lots` can tell what the row was without a join.
    """
    stem = f"{canonical_book(sportsbook)}:{sport}:{selection}".upper().replace(" ", "_")
    return f"{stem}#{str(ticket_id).upper().strip()}"


def _notes(strategy: str, pairs: List[tuple], extra: str = "") -> str:
    """`strategy:` first - `monarch_hook` parses that tag for exposure attribution."""
    body = ";".join(f"{k}:{v}" for k, v in pairs if v not in (None, ""))
    tail = f";{extra.strip()}" if extra.strip() else ""
    return f"strategy:{strategy};{body}{tail}"


class SportsBettingIngestor:
    """Normalises sports wagers and settlements into ledger transactions."""

    @staticmethod
    def create_bet_placed(
        ticket_id: str,
        sportsbook: str,
        sport: str,
        selection: str,
        wager: float,
        odds: Any,
        timestamp: str,
        fee: float = 0.0,
        notes: str = "",
        strategy: str = DEFAULT_STRATEGY,
        odds_format: Optional[str] = None,
        promo: bool = False,
        promo_stake: float = 0.0,
    ) -> Dict[str, Any]:
        """
        The opening lot: one ticket, cost basis = the stake.

        `odds` accepts American (-110 / +150), decimal (1.91), fractional (10/11)
        or the word EVEN. It is normalised and recorded in both conventions so a
        settlement can be checked against it later; it never enters the tax math.

        PROMO / FREE / BONUS BETS carry `promo=True` and get a cost basis of
        ZERO regardless of the stake the book prints on them. You did not buy the
        wager, so you have no basis in it, and everything it returns is winnings
        under IRC 61. The printed stake is kept in the notes as `promo_stake:`
        because it reconciles the row against the export, not because any part of
        it is deductible.

        A zero stake WITHOUT a promo signal is still refused. A free bet and a
        missing stake column are identical in a CSV, and reading the second as the
        first would silently give real wagers a zero basis and tax their whole
        payout. The signal is the only thing that separates them.

        `promo_stake` carries the PROMOTIONAL PORTION of a mixed ticket. Books
        let you stake $75 cash alongside a $25 bonus, and only the cash half is
        basis, so this is not an all-or-nothing flag. `promo=True` is shorthand
        for a wholly promotional ticket.
        """
        wager = float(wager)
        if wager < 0:
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: a wager cannot be negative; got {wager!r}."
            )
        promo_stake = float(promo_stake or 0.0)
        if promo and promo_stake <= 0:
            promo_stake = wager                      # wholly promotional
        if promo_stake < 0:
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: promo_stake cannot be negative; got {promo_stake!r}.")
        if promo_stake > wager + 1e-9:
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: promo_stake {promo_stake} exceeds the {wager} total "
                f"stake. One of the two stake columns is being read wrong.")
        promotional = promo or promo_stake > 0
        if wager == 0 and not promotional:
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: zero stake and no promo signal. If this is a free "
                f"or bonus bet pass promo=True (or give the export a promo / free_bet / "
                f"bet_type / bonus_wager / free_bet_stake column); if it is not, the stake "
                f"column is missing and every dollar the ticket returns would be taxed as "
                f"winnings."
            )
        # Only the cash half is basis. A wholly promotional ticket has none.
        cost_basis = max(0.0, wager - promo_stake)
        quote = _safe_quote(odds, odds_format, ticket_id)
        return {
            "source": canonical_book(sportsbook),
            "tx_hash": f"{canonical_book(sportsbook)}_{ticket_id}_bet",
            "timestamp": timestamp,
            "asset_class": ASSET_CLASS,
            "symbol": bet_symbol(sportsbook, sport, selection, ticket_id),
            "side": "BET",
            "quantity": 1.0,
            "price": cost_basis,
            "fee": float(fee),
            "total_value": cost_basis,
            "notes": _notes(strategy, [
                ("sportsbook", sportsbook),
                ("sport", sport),
                ("ticket", ticket_id),
                ("promo_bet", "true" if promotional else None),
                ("promo_stake", f"{promo_stake:.2f}" if promo_stake > 0 else None),
                ("cash_stake", f"{cost_basis:.2f}" if promotional and cost_basis > 0 else None),
                ("odds_decimal", f"{quote.decimal:.4f}" if quote else None),
                ("odds_american", f"{quote.american:+d}" if quote else None),
                ("implied_prob", f"{quote.implied_probability:.4f}" if quote else None),
            ], notes),
        }

    @staticmethod
    def create_bet_settled(
        ticket_id: str,
        sportsbook: str,
        sport: str,
        selection: str,
        result: str,
        payout: float,
        timestamp: str,
        withholding: float = 0.0,
        fee: float = 0.0,
        notes: str = "",
        strategy: str = DEFAULT_STRATEGY,
        wager: Optional[float] = None,
        stake_fraction: float = 1.0,
        odds: Any = None,
        odds_format: Optional[str] = None,
        tolerance_pct: float = 0.02,
        promo_stake: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Closes all (or `stake_fraction` of) one ticket.

        `payout` is the TOTAL returned including the stake, which is what every
        sportsbook export prints. `wager` is optional and used only for the
        push-refund default and the odds sanity check.
        """
        res = str(result).strip().upper().replace(" ", "_").replace("-", "_")
        payout = float(payout)
        fraction = float(stake_fraction)
        if not (0.0 < fraction <= 1.0 + _SETTLEMENT_TOLERANCE):
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: stake_fraction must be in (0, 1]; got {stake_fraction!r}."
            )
        fraction = min(1.0, fraction)

        if res in WIN_WORDS:
            side = "BET_WIN"
        elif res in LOSS_WORDS:
            side = "BET_LOSS"
            payout = 0.0
        elif res in PUSH_WORDS:
            side = "BET_PUSH"
            if payout <= 0:
                if wager is None:
                    raise BetSettlementError(
                        f"Ticket {ticket_id!r}: a push refunds the stake, so it needs either "
                        f"a payout or `wager=`. Settling it at $0 would book the whole stake "
                        f"as a deductible loss that never happened."
                    )
                payout = float(wager) * fraction
        elif res in CASHOUT_WORDS:
            # Honours the price in BOTH directions. See the module docstring.
            side = "BET_CASHOUT"
            if payout < 0:
                raise BetSettlementError(
                    f"Ticket {ticket_id!r}: cashout payout cannot be negative ({payout!r})."
                )
        elif res in OPEN_WORDS:
            raise BetSettlementError(
                f"Ticket {ticket_id!r} is still open ({result!r}) and has no settlement. "
                f"An unsettled wager is not a realised loss."
            )
        else:
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: unknown settlement result {result!r}. Known: "
                f"win / loss / push / void / cashout / half_win / half_loss."
            )

        # Fractional settlement: `price` is per unit of ticket, so that
        # quantity x price is the cash actually received. See module docstring.
        unit_price = payout / fraction if fraction > 0 else payout

        quote = _safe_quote(odds, odds_format, ticket_id)
        mismatch = None
        if side == "BET_WIN" and wager is not None and fraction >= 1.0:
            mismatch = payout_discrepancy(float(wager), payout, quote, tolerance_pct)

        # FORM W-2G, assessed at ingestion because the wager and the payout are
        # both in hand here and nowhere else. Reg. 1.6041-10 and IRC 3402(q) both
        # test PROCEEDS (received minus staked) against $600/$5,000 AND a 300:1
        # multiple, so most sports bets trigger neither - a $1,000 winner at 2:1
        # is nowhere near it. When one does trigger, the payout arrives 24% short
        # and the operator should not learn that from their bank balance.
        w2g_note = ""
        if side in ("BET_WIN", "BET_CASHOUT") and wager is not None:
            staked = float(wager) * fraction
            assessment = assess_w2g(payout - staked, staked,
                                    promo_stake=float(promo_stake or 0.0) * fraction)
            w2g_note = assessment.note()

        return {
            "source": canonical_book(sportsbook),
            "tx_hash": f"{canonical_book(sportsbook)}_{ticket_id}_settle",
            "timestamp": timestamp,
            "asset_class": ASSET_CLASS,
            "symbol": bet_symbol(sportsbook, sport, selection, ticket_id),
            "side": side,
            "quantity": fraction,
            "price": unit_price,
            "fee": float(fee),
            "total_value": payout,
            "notes": _notes(strategy, [
                ("sportsbook", sportsbook),
                ("result", res),
                ("ticket", ticket_id),
                ("payout", f"{payout:.2f}"),
                ("stake_fraction", f"{fraction:.4f}" if fraction < 1.0 else None),
                # Read back by tax_calculator to credit the federal prepayment.
                ("w2g_withholding", f"{float(withholding):.2f}" if withholding > 0 else None),
                ("odds_check", f"payout_off_by_{mismatch * 100:.1f}pct" if mismatch else None),
            ], ";".join(part for part in (w2g_note, notes) if part)),
        }

    @classmethod
    def create_dead_heat_settlement(
        cls,
        ticket_id: str,
        sportsbook: str,
        sport: str,
        selection: str,
        wager: float,
        payout: float,
        timestamp: str,
        win_fraction: float = 0.5,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Dead heat: `win_fraction` of the stake is settled as a WINNER at the full
        price, the remainder as a LOSER. This is NOT a push - the losing half is
        a real 165(d) loss, and books it as one.

        A 2-way dead heat on a $100 ticket at +200 returns $150: $50 stake wins
        $100, $50 stake loses. `payout` is that $150, as printed.
        """
        wager = float(wager)
        win_fraction = float(win_fraction)
        if not (0.0 < win_fraction < 1.0):
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: dead-heat win_fraction must be strictly between 0 "
                f"and 1; got {win_fraction!r}. A full win or loss is an ordinary settlement."
            )
        # WITHHOLDING GOES ON ONE LEG ONLY. `w2g_withholding:` is summed per ROW
        # by the escrow calculator, so tagging both halves of one ticket credits
        # the bettor twice for money the book sent to the Treasury once. There is
        # only ever one W-2G per ticket, and it belongs to the leg that paid.
        withholding = float(kwargs.pop("withholding", 0.0) or 0.0)
        common = dict(ticket_id=ticket_id, sportsbook=sportsbook, sport=sport,
                      selection=selection, timestamp=timestamp, wager=wager, **kwargs)
        return [
            cls.create_bet_settled(result="WIN", payout=payout, withholding=withholding,
                                   stake_fraction=win_fraction, **common),
            cls.create_bet_settled(result="LOSS", payout=0.0,
                                   stake_fraction=1.0 - win_fraction, **common),
        ]

    @classmethod
    def create_partial_void_settlement(
        cls,
        ticket_id: str,
        sportsbook: str,
        sport: str,
        selection: str,
        wager: float,
        payout: float,
        timestamp: str,
        void_fraction: float,
        result: str = "WIN",
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        A postponed or voided leg that the book refunds pro rata rather than
        repricing the ticket: `void_fraction` of the stake comes back as a push,
        the remainder settles per `result`.

        Note that most books instead RECOMPUTE a parlay at the reduced odds and
        settle the whole ticket once - that is an ordinary WIN/LOSS at the new
        payout and needs nothing special. Use this only when the export shows a
        partial refund line.
        """
        void_fraction = float(void_fraction)
        if not (0.0 < void_fraction < 1.0):
            raise BetSettlementError(
                f"Ticket {ticket_id!r}: void_fraction must be strictly between 0 and 1; "
                f"got {void_fraction!r}. A fully voided ticket is a plain push."
            )
        # One leg only - see `create_dead_heat_settlement`. A refunded stake has
        # nothing withheld against it, so the tag belongs to the settled leg.
        withholding = float(kwargs.pop("withholding", 0.0) or 0.0)
        common = dict(ticket_id=ticket_id, sportsbook=sportsbook, sport=sport,
                      selection=selection, timestamp=timestamp, wager=float(wager), **kwargs)
        return [
            cls.create_bet_settled(result="PUSH", payout=float(wager) * void_fraction,
                                   stake_fraction=void_fraction, **common),
            cls.create_bet_settled(result=result, payout=payout, withholding=withholding,
                                   stake_fraction=1.0 - void_fraction, **common),
        ]

    @classmethod
    def load_from_csv(cls, csv_path: Path,
                      default_odds_format: Optional[str] = None,
                      tolerance_pct: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Reads a sportsbook export.

        Handles both shapes books actually emit: a two-row log (a placement row
        and a settlement row) and the far more common single-row "settled bets"
        export, where one row carries stake, price and outcome together and both
        legs have to be synthesised.

        Rows that cannot be read are SKIPPED WITH A WARNING rather than dropped
        silently or allowed to abort the file - a tax import that quietly loses
        rows is the failure this whole agent exists to prevent.

        `default_odds_format` ("american" / "decimal") settles the one price zone
        `parse_odds` refuses to guess - a bare `150.0`, which is 2.50 or 150.0
        depending on who wrote the file. It applies only where the row does not
        already carry an `odds_format` column of its own.

        `tolerance_pct` is how far a settled payout may sit from the payout its own
        odds imply before the row is tagged. Cashouts and dead heats legitimately
        drift; a $1,910 payout typed as $191 does not, and nothing else here would
        catch it.
        """
        trades: List[Dict[str, Any]] = []
        if not csv_path.exists():
            return trades

        skipped = 0
        # ONE TICKET, ONE OPENING LOT. Some books print a parlay as one row PER
        # LEG, each carrying the ticket-level stake. Every leg then minted its own
        # opening lot and the ticket's cost basis was multiplied by its leg count
        # - a 4-leg $100 parlay booked $400 of basis and understated the winnings
        # by $300. Keyed on (source, tx_hash, side), which already encodes
        # book + ticket + role, so a genuine two-row placement/settlement log is
        # untouched and only a repeated ROLE collapses.
        #
        # The first row wins, which also keeps the symbol stable: legs differ in
        # `selection`, and letting the settlement pick a later leg's spelling
        # would point it at a lot family that does not exist.
        seen: Dict[tuple, Dict[str, Any]] = {}
        collapsed = 0
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            for line_no, row in enumerate(csv.DictReader(f), start=2):
                clean = {str(k).strip().lower(): str(v).strip()
                         for k, v in row.items() if k}
                try:
                    produced = cls._rows_from_record(clean, default_odds_format,
                                                     tolerance_pct)
                except (BetSettlementError, OddsFormatError, ValueError) as e:
                    skipped += 1
                    print(f"[WARN] {csv_path.name}:{line_no} skipped - {e}")
                    continue

                for trade in produced:
                    key = (trade["source"], trade["tx_hash"], trade["side"])
                    previous = seen.get(key)
                    if previous is None:
                        seen[key] = trade
                        trades.append(trade)
                        continue
                    collapsed += 1
                    # ONLY A DIFFERING AMOUNT IS WORTH A WARNING.
                    #
                    # A differing SYMBOL on the same ticket is the parlay-leg
                    # shape this collapse exists for - the legs are LEG_A, LEG_B,
                    # LEG_C against one stake - so warning on it fired on every
                    # correctly-handled parlay, and printed "a DIFFERENT amount
                    # ($100.00 vs $100.00)" while doing so. An alert that cries
                    # wolf on the normal case trains the operator to skip the one
                    # that matters. The collapse is already reported in the
                    # [INFO] summary below; only a real money mismatch escalates.
                    if abs(float(previous["total_value"])
                           - float(trade["total_value"])) > 0.005:
                        print(f"[WARN] {csv_path.name}:{line_no} repeats ticket "
                              f"{trade['tx_hash']!r} ({trade['side']}) with a DIFFERENT "
                              f"amount (${float(previous['total_value']):,.2f} vs "
                              f"${float(trade['total_value']):,.2f}). Keeping the first. "
                              f"If these are two separate wagers they need distinct "
                              f"ticket ids, or one of them is now missing from the ledger.")

        if collapsed:
            print(f"[INFO] {csv_path.name}: collapsed {collapsed} repeated ticket row(s) "
                  f"(a parlay printed one line per leg books ONE stake, not one per leg).")
        if skipped:
            print(f"[WARN] {csv_path.name}: {skipped} row(s) skipped. Those wagers are NOT "
                  f"in the ledger and the escrow below is understated until they are.")
        return trades

    @classmethod
    def _rows_from_record(cls, clean: Dict[str, str],
                          default_odds_format: Optional[str] = None,
                          tolerance_pct: Optional[float] = None) -> List[Dict[str, Any]]:
        """One CSV record -> zero, one or two transactions."""
        ticket_id = _first(clean, "ticket_id", "ticket", "bet_id", "betid", "wager_id", "id")
        sportsbook = _first(clean, "sportsbook", "book", "source", "site") or "sportsbook"
        sport = _first(clean, "sport", "league") or "SPORTS"
        selection = _first(clean, "selection", "pick", "bet", "market", "event", "description")
        strategy = _first(clean, "strategy") or DEFAULT_STRATEGY
        extra_notes = _first(clean, "notes", "comment") or ""

        # Books that log placement and settlement separately date them separately,
        # and collapsing both onto one timestamp destroys the ordering the FIFO
        # engine relies on when several tickets share a day.
        placed_at = _first(clean, "placed_date", "placed_at", "date_placed",
                           "timestamp", "date")
        settled_at = _first(clean, "settled_date", "settled_at", "date_settled",
                            "settlement_date") or placed_at

        if not placed_at or not selection:
            raise BetSettlementError("row has no timestamp or no selection")

        # A book that funds a ticket from a bonus balance splits the stake across
        # two columns. Read BOTH: the cash half is basis, the promotional half is
        # not, and the total is what the ticket was actually placed for.
        #
        # THE HARD PART IS THAT `stake` MEANS TWO DIFFERENT THINGS. Some books
        # print it as the CASH side beside a separate bonus column; others print
        # it as the TOTAL of which the bonus is a part. Reading a total as a cash
        # side inflates the ticket and hands it a basis it never had - a `Stake:
        # 100, Free Bet Stake: 25` row booked $100 of basis instead of $75, so
        # $25 of winnings went untaxed.
        #
        # An explicit CASH column settles it, and its mere presence is the signal
        # - `cash_wager: 0.00` is a real answer, so the check is presence, not a
        # positive value.
        has_cash_column = any(clean.get(column) not in (None, "")
                              for column in CASH_STAKE_COLUMNS)
        cash_stake = _to_float(_first(clean, *CASH_STAKE_COLUMNS))
        promo_stake = _to_float(_first(clean, *PROMO_AMOUNT_COLUMNS))
        wager = _to_float(_first(clean, "wager", "stake", "risk", "amount", "bet_amount"))
        stake_note = ""
        if promo_stake > 0:
            if has_cash_column:
                # The book split them itself. Disjoint by construction.
                wager = cash_stake + promo_stake
            elif wager <= 0:
                # Wholly promotional - DraftKings `Stake: 0.00, Free Bet: 50.00`.
                wager = promo_stake
            elif wager < promo_stake:
                # A total cannot be smaller than one of its own parts, so this
                # `stake` must be the cash side.
                wager = wager + promo_stake
            elif canonical_book(sportsbook) in BOOK_STAKE_IS_CASH:
                # This book is known to report `stake` as the cash side.
                wager = wager + promo_stake
                stake_note = "stake_basis:book_reports_cash"
            else:
                # GENUINELY AMBIGUOUS: `stake` >= the promo amount reads equally
                # well as the total or as the cash side, and the numbers cannot
                # separate them. Taken as the TOTAL, which gives the LOWER basis
                # and the higher taxable winnings - the safe direction for a
                # reserve. Tagged so the row can be reconciled against the export.
                stake_note = "stake_basis:assumed_total_not_cash"
        payout = _to_float(_first(clean, "payout", "return", "returns", "collected",
                                  "win", "settled_amount", "to_win_total"))
        withholding = _to_float(_first(clean, "withholding", "tax_withheld",
                                       "federal_withholding", "w2g"))
        # NOT `price`: several exports use that column for the stake, and reading
        # a stake as odds silently produces a nonsense consistency check.
        raw_odds = _first(clean, "odds", "american_odds", "decimal_odds", "line", "price_odds")
        # Most specific wins: the row's own column, then the column the price came
        # from, then the operator's configured default.
        odds_format = _first(clean, "odds_format")
        if not odds_format:
            if "american_odds" in clean and clean["american_odds"]:
                odds_format = "american"
            elif "decimal_odds" in clean and clean["decimal_odds"]:
                odds_format = "decimal"
            else:
                odds_format = default_odds_format or ""

        if not ticket_id:
            ticket_id = _row_fingerprint(clean, sportsbook)

        side = (_first(clean, "side") or "").upper()
        result = (_first(clean, "result", "status", "outcome", "settlement") or "").upper()

        # A promo marker is what separates a genuine free bet from a stake column
        # the export forgot to fill in. Without one, a zero stake is refused.
        promo = promo_stake > 0
        for column in PROMO_COLUMNS:
            token = str(clean.get(column, "")).strip().upper().replace(" ", "_")
            if token and (token in PROMO_WORDS
                          or any(word in token for word in ("FREE", "PROMO", "BONUS"))):
                promo = True
                break

        if stake_note:
            extra_notes = f"{extra_notes};{stake_note}".strip(";") if extra_notes else stake_note

        common = dict(ticket_id=ticket_id, sportsbook=sportsbook, sport=sport,
                      selection=selection, strategy=strategy, notes=extra_notes)
        settle_extra = ({} if tolerance_pct is None
                        else {"tolerance_pct": float(tolerance_pct)})

        # 1. Explicit side column - the ledger's own export shape.
        if side == "BET":
            return [cls.create_bet_placed(wager=wager, odds=raw_odds, timestamp=placed_at,
                                          odds_format=odds_format, promo=promo,
                                          promo_stake=promo_stake, **common)]
        if side.startswith("BET_") or side in WIN_WORDS | LOSS_WORDS | PUSH_WORDS | CASHOUT_WORDS:
            token = side[4:] if side.startswith("BET_") else side
            return [cls.create_bet_settled(result=token, payout=payout, timestamp=settled_at,
                                           withholding=withholding,
                                           wager=wager or None, odds=raw_odds,
                                           odds_format=odds_format,
                                           **settle_extra, **common)]

        # 2. Single-row completed bet: synthesise the placement and the settlement.
        if result and result not in OPEN_WORDS:
            if wager <= 0 and not promo:
                raise BetSettlementError(
                    f"ticket {ticket_id!r} is settled ({result}) but has no stake column; "
                    f"cost basis would be zero and the whole payout taxed as winnings")
            rows = [cls.create_bet_placed(wager=wager, odds=raw_odds, timestamp=placed_at,
                                          odds_format=odds_format, promo=promo,
                                          promo_stake=promo_stake, **common)]
            if result in HALF_WIN_WORDS:
                rows.extend(cls.create_dead_heat_settlement(
                    wager=wager, payout=payout, timestamp=settled_at, win_fraction=0.5,
                    withholding=withholding, odds=raw_odds, odds_format=odds_format, **common))
            elif result in HALF_LOSS_WORDS:
                rows.extend(cls.create_partial_void_settlement(
                    wager=wager, payout=payout or wager * 0.5, timestamp=settled_at,
                    void_fraction=0.5, result="LOSS", withholding=withholding,
                    odds=raw_odds, odds_format=odds_format, **common))
            else:
                rows.append(cls.create_bet_settled(
                    result=result, payout=payout, timestamp=settled_at,
                    withholding=withholding, wager=wager, odds=raw_odds,
                    odds_format=odds_format, promo_stake=promo_stake,
                    **settle_extra, **common))
            return rows

        # 3. Pending ticket. An opening lot and nothing more - see module docstring.
        if wager > 0 or promo:
            return [cls.create_bet_placed(wager=wager, odds=raw_odds, timestamp=placed_at,
                                          odds_format=odds_format, promo=promo,
                                          promo_stake=promo_stake, **common)]
        return []


def _safe_quote(odds: Any, odds_format: Optional[str], ticket_id: str) -> Optional[OddsQuote]:
    """
    Odds are metadata, not tax. An unreadable price must never cost us the wager:
    warn, record nothing, and let the dollars through.
    """
    if odds in (None, "", 0, 0.0):
        return None
    try:
        return parse_odds(odds, fmt=odds_format or None)
    except OddsFormatError as e:
        print(f"[WARN] Ticket {ticket_id!r}: {e} Wager recorded without a price.")
        return None


def _first(row: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return ""


def _to_float(value: Any) -> float:
    """Books print `$1,250.00` and `(50.00)`. None of those are floats."""
    if value in (None, ""):
        return 0.0
    text = str(value).strip().replace("$", "").replace(",", "").replace("+", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        result = float(text)
    except (TypeError, ValueError):
        return 0.0
    return -result if negative else result
