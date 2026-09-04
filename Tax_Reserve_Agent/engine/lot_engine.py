"""
Lot Accounting and Cost Basis Engine (FIFO / HIFO).
Tracks purchases, sales, and option/prediction market lifecycles to calculate exact capital gains.

ACCOUNTING METHOD. Which open lot a sale consumes is a policy choice, set by
`config.yaml -> accounting.method`:

  FIFO  Oldest lot first. The conservative default, and the method the IRS assumes
        when no adequate identification was made.
  HIFO  Highest cost basis first - a form of specific identification that
        minimises the gain realised on each sale, and therefore the escrow.
        It is not free: consuming the expensive lot first tends to leave the
        CHEAP, OLD lots open, so it can convert what would have been long-term
        gains into short-term ones and simply defer tax rather than avoid it.
        Using it requires that you can actually identify the lots sold - keep
        this ledger as that record.

SWITCHING METHODS DOES NOT REWRITE HISTORY. Lots already consumed stay consumed,
so flipping the config mid-year leaves a ledger that is half one method and half
the other - which is both wrong and not a position any method permits. The method
the lots were built with is recorded in `agent_meta`, `calculate_tax_summary()`
warns when it no longer matches the config, and `rebuild_lots()` (exposed as
`python -m Tax_Reserve_Agent.main rebuild`) replays the whole ledger from the
`transactions` table, which is the immutable source of truth.
"""
from datetime import date, datetime, timezone
import sqlite3
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..database.db import get_connection, set_meta

FIFO = "FIFO"
HIFO = "HIFO"
SUPPORTED_METHODS = (FIFO, HIFO)
DEFAULT_METHOD = FIFO
ACCOUNTING_METHOD_KEY = "accounting_method"

# WHICH RULE THE STORED TERMS WERE CLASSIFIED UNDER.
#
# Round 26c replaced `holding_days >= 365` with the calendar test in
# `is_long_term`, because no day count can express "more than one year" across a
# leap year. Lots matched BEFORE that change keep the term they were given -
# `realized_pnl` is derived data and nothing rewrites it in place - so a ledger
# built earlier can hold boundary trades marked LONG_TERM that are legally
# SHORT_TERM, which UNDER-states the reserve.
#
# Versioned the same way the accounting method is: recorded on write, compared on
# read, surfaced rather than silently fixed. A rebuild re-matches everything.
TERM_RULE_KEY = "term_rule_version"
TERM_RULE_VERSION = "calendar-more-than-one-year"

# Sides that open a lot, and sides that close one. Named rather than inlined so
# the matcher and the rebuild path cannot drift apart.
OPENING_SIDES = ("BUY", "OPTION_BUY", "SPLIT_YES", "SPLIT_NO", "MINT", "BET")
CLOSING_SIDES = ("SELL", "REDEEM", "OPTION_SELL", "OPTION_EXPIRE", "OPTION_BUY_TO_CLOSE",
                 "BET_WIN", "BET_LOSS", "BET_PUSH", "BET_CASHOUT")

# Every wager side, opening and closing. A row with one of these is a gambling
# row no matter what `asset_class` the import happened to write, and it must not
# be allowed to land in a capital-gain term bucket.
WAGER_SIDES = ("BET", "BET_WIN", "BET_LOSS", "BET_PUSH", "BET_CASHOUT")
# Cash movements. Recorded in `transactions` so the ledger can state the liquid
# balance from evidence, but they are not positions: no lot opens, nothing is
# ever realised against them, and the tax summary never sums them into gains.
CASH_SIDES = ("DEPOSIT", "WITHDRAWAL")
GAMBLING_TERM = "GAMBLING"
GAMBLING_ASSET_CLASS = "sports_bet"

# Sides whose proceeds are ZERO by definition rather than by price. BET_CASHOUT
# is deliberately NOT here: cashing a $100 ticket out at $60 is a $40 loss, and
# booking it as BET_LOSS would record a $100 one.
WORTHLESS_SIDES = ("OPTION_EXPIRE", "BET_LOSS")


def normalise_method(method: Optional[str]) -> str:
    """Accepts None/any case; falls back to FIFO on anything unrecognised."""
    candidate = str(method or DEFAULT_METHOD).strip().upper()
    if candidate not in SUPPORTED_METHODS:
        print(f"[WARN] Unknown accounting method {method!r}; using {DEFAULT_METHOD}.")
        return DEFAULT_METHOD
    return candidate


def resolve_method(method: Optional[str] = None) -> str:
    """Explicit argument wins, then `config.yaml -> accounting.method`, then FIFO."""
    if method is not None:
        return normalise_method(method)
    try:
        from ..config import load_config
        return normalise_method((load_config().get("accounting", {}) or {}).get("method"))
    except Exception:
        return DEFAULT_METHOD


def lot_ordering(method: str) -> str:
    """
    The ORDER BY that defines the accounting method.

    Both orderings end in `id ASC` so that lots identical on the leading key are
    still consumed in a fixed, reproducible order - without it a rebuild could
    match a different lot than the original run and quietly change the holding
    period on a boundary trade.
    """
    if method == HIFO:
        return "ORDER BY unit_cost_basis DESC, acquired_at ASC, id ASC"
    return "ORDER BY acquired_at ASC, id ASC"

# Formats `datetime.fromisoformat` will not take, tried in order after it fails.
_FALLBACK_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d/%m/%Y %H:%M:%S",
)


def parse_iso_date(dt_str: str) -> datetime:
    """
    Parse the timestamp shapes that actually reach this ledger.

    The old implementation took exactly two: an ISO string containing `T`, and
    `%Y-%m-%d %H:%M:%S`. Everything else raised - including a BARE DATE
    (`2026-01-10`), MICROSECONDS (`13:00:00.123456`) and a SPACE-SEPARATED OFFSET
    (`2026-01-10 13:00:00-05:00`), all three of which real exports emit. That was
    not merely an import failure: `sortable_timestamp` catches the ValueError and
    sorts the row to `datetime.max`, which pushes an OPENING lot to the end of
    the batch. Its settlement then finds no lot, the zero-basis fallback books the
    full payout as winnings, and the stake stays open forever - the exact bug the
    ordering fix was meant to close, reached by a different door.

    `fromisoformat` on 3.11+ handles nearly all of it; the ladder below covers the
    slash-separated shapes it will not. A bare date is midnight, which is what
    every consumer here already assumes for a date-only row.

    Still deliberately REFUSED: bare epoch seconds. `1767013200` is a plausible
    quantity, price or ticket id, and reading it as a timestamp is a guess this
    module does not get to make.
    """
    text = str(dt_str).strip()
    if not text:
        raise ValueError("empty timestamp")

    # `Z` is valid ISO-8601 but only `fromisoformat` on 3.11+ accepts it, and the
    # strptime ladder never will.
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass

    for fmt in _FALLBACK_TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Unrecognised timestamp {dt_str!r}. Expected ISO-8601 "
        f"(2026-01-10, 2026-01-10 13:00:00, 2026-01-10T13:00:00Z, with optional "
        f"fractional seconds or UTC offset) or a slash-separated US date."
    )


def one_year_after(day: date) -> date:
    """
    The anniversary. 29 February has none in a common year, and the settled
    convention is that the holding period turns on 1 March.
    """
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return date(day.year + 1, 3, 1)


def is_long_term(acquired: datetime, disposed: datetime) -> bool:
    """
    IRC 1222(3): long-term needs the asset held for MORE THAN one year, and
    Rev. Rul. 66-7 starts the count the day after acquisition. Buy on 1 January
    and you must sell on 2 January of the following year at the earliest.

    COUNTING DAYS CANNOT EXPRESS THIS. The old test was `holding_days >= 365`,
    which called an exact one-year hold long-term - wrong by one day. Changing it
    to `> 365` fixes the common year and BREAKS THE LEAP YEAR: 2024-01-01 to
    2025-01-01 is 366 days and still exactly one year, so it is short-term, and
    `> 365` would call it long. Same for a 29 February purchase. There is no
    day-count threshold that is right in both, because "one year" is a calendar
    span and not a number of days. So this asks the calendar.

    The correction only ever moves a boundary trade from long-term to short-term,
    which RAISES the reserve - the safe direction for a ledger whose whole job is
    to not under-reserve.
    """
    return as_naive_utc(disposed).date() > one_year_after(as_naive_utc(acquired).date())

def as_naive_utc(moment: datetime) -> datetime:
    """
    Offset-aware -> UTC, then naive. Naive is returned untouched.

    The ledger holds both kinds: `2026-01-10T13:00:00Z` from a chain ingestor and
    `2026-01-10 16:30:00` from a CSV. Subtracting one from the other raises
    `TypeError: can't subtract offset-naive and offset-aware datetimes` - a latent
    crash in the holding-period calculation that predates the wagering module and
    only surfaced once the settlement started finding its own opening lot.
    Comparing the raw strings, as the ledger used to, hid it by never matching.
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def sortable_timestamp(raw: Any) -> datetime:
    """
    A timestamp that can be ORDERED, not just compared as text.

    The ledger was sorting `str(timestamp)` and the ingestors do not agree on a
    format: `"2026-01-10 16:30:00"` sorts BEFORE `"2026-01-10T13:00:00Z"` because
    a space is 0x20 and `T` is 0x54. A wager placed at 13:00 therefore arrived
    AFTER its own 16:30 settlement, the settlement found no open lot, and the
    zero-basis fallback booked the full payout as winnings while leaving the
    stake open forever. Same trap for any BUY/SELL pair whose rows came from two
    different importers.

    Offset-aware values are normalised to UTC and made naive so they compare
    against the naive majority; a naive value is taken as UTC, which is what
    comparing the raw strings already assumed. An unparseable timestamp sorts
    last and warns - `apply_to_lots` will raise on it a moment later anyway, and
    the warning names the row.
    """
    try:
        parsed = parse_iso_date(str(raw))
    except (ValueError, TypeError):
        print(f"[WARN] Unparseable timestamp {raw!r}; ordering it last.")
        return datetime.max
    return as_naive_utc(parsed)


def _side_rank(side: Any) -> int:
    """
    Tie-break for rows sharing one timestamp: a ticket must be placed before it
    settles, so a wager settlement sorts after everything else at that instant.

    DELIBERATELY LIMITED TO WAGER SIDES. Books export single-row "settled bets"
    where the placement and the settlement carry one timestamp, which is what
    this exists for. Applying the same rule to spot would force a BUY ahead of a
    same-second SELL and silently re-point a sell-then-rebuy at the new lot -
    a change to cost basis on the frozen paths, for no reported problem. Every
    other side keeps pure insertion order, exactly as before.
    """
    return 1 if str(side or "").upper() in ("BET_WIN", "BET_LOSS", "BET_PUSH",
                                            "BET_CASHOUT") else 0


def ledger_ordering_key(tx: Dict[str, Any], sequence: int) -> tuple:
    """`(when, settlements-after-placements, original order)`. Used by both the
    live import path and `rebuild_lots`, so a rebuild cannot re-order history."""
    return (sortable_timestamp(tx.get("timestamp")), _side_rank(tx.get("side")), sequence)


def process_transaction(tx: Dict[str, Any], conn: sqlite3.Connection,
                       method: Optional[str] = None) -> None:
    """
    Process a single transaction through the lot engine.
    Records it in `transactions`, then updates `tax_lots` and `realized_pnl`.
    """
    method = normalise_method(method) if method else resolve_method()
    cursor = conn.cursor()
    
    # 1. Insert transaction into ledger
    cursor.execute("""
        INSERT OR IGNORE INTO transactions 
        (source, tx_hash, timestamp, asset_class, symbol, side, quantity, price, fee, total_value, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tx["source"],
        tx.get("tx_hash"),
        tx["timestamp"],
        tx["asset_class"],
        tx["symbol"],
        tx["side"].upper(),
        float(tx["quantity"]),
        float(tx["price"]),
        float(tx.get("fee", 0.0)),
        float(tx.get("total_value", float(tx["quantity"]) * float(tx["price"]))),
        tx.get("notes", "")
    ))
    
    # rowcount, NOT lastrowid, is what tells us whether the INSERT OR IGNORE
    # actually wrote. After an ignored insert sqlite3 leaves lastrowid holding the
    # id of the PREVIOUS successful insert, which is truthy - so the old
    # `if not tx_id` check never fired and a re-imported file was replayed through
    # the lot engine, minting a duplicate tax lot and a duplicate realized_pnl row
    # for every line. Re-dropping one CSV export doubled the year's gains.
    already_recorded = cursor.rowcount == 0
    tx_id = cursor.lastrowid

    if already_recorded:
        # This exact (source, tx_hash, symbol, side) has been through the engine
        # before; its lots and P&L already exist. Re-imports are a no-op.
        return

    if not tx_id:
        cursor.execute("SELECT id FROM transactions WHERE source=? AND tx_hash=? AND symbol=? AND side=?",
                       (tx["source"], tx.get("tx_hash"), tx["symbol"], tx["side"].upper()))
        row = cursor.fetchone()
        if row:
            tx_id = row["id"]
        else:
            return

    apply_to_lots(tx, tx_id, conn, method)


def apply_to_lots(tx: Dict[str, Any], tx_id: int, conn: sqlite3.Connection,
                  method: str = DEFAULT_METHOD) -> None:
    """
    Opens or closes lots for one already-recorded transaction.

    Split out of `process_transaction` so `rebuild_lots()` can replay the ledger
    without re-inserting the transactions - the insert path early-returns on the
    UNIQUE constraint, which would make every replayed row a no-op.
    """
    cursor = conn.cursor()
    side = tx["side"].upper()
    if side in CASH_SIDES:
        return          # a deposit is money, not a position - see CASH_SIDES
    quantity = float(tx["quantity"])
    price = float(tx["price"])
    fee = float(tx.get("fee", 0.0))
    timestamp = tx["timestamp"]
    symbol = tx["symbol"]
    asset_class = tx["asset_class"]
    
    # 2. Handle BUY / ACQUISITION / OPENING LOTS
    if side in OPENING_SIDES:
        unit_cost = price + (fee / quantity if quantity > 0 else 0.0)
        total_cost = unit_cost * quantity
        cursor.execute("""
            INSERT INTO tax_lots (transaction_id, asset_class, symbol, acquired_at, original_qty, remaining_qty, unit_cost_basis, total_cost_basis, is_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (tx_id, asset_class, symbol, timestamp, quantity, quantity, unit_cost, total_cost))
        
    # 3. Handle SHORT OPTION OPEN (Collected Premium)
    elif side == "OPTION_SELL_TO_OPEN":
        # When selling to open, we create a short lot with negative quantity or liability tracking
        unit_basis = price - (fee / quantity if quantity > 0 else 0.0)
        cursor.execute("""
            INSERT INTO tax_lots (transaction_id, asset_class, symbol, acquired_at, original_qty, remaining_qty, unit_cost_basis, total_cost_basis, is_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (tx_id, "short_option", symbol, timestamp, quantity, quantity, unit_basis, unit_basis * quantity))

    # 4. Handle SELLS / CLOSURES / REDEMPTIONS / EXPIRATIONS / BET SETTLEMENTS
    elif side in CLOSING_SIDES:
        # Find open lots FIFO
        cursor.execute(f"""
            SELECT id, acquired_at, remaining_qty, unit_cost_basis 
            FROM tax_lots 
            WHERE symbol = ? AND is_closed = 0 
            {lot_ordering(method)}
        """, (symbol,))
        open_lots = cursor.fetchall()
        
        remaining_to_sell = quantity
        sell_dt = parse_iso_date(timestamp)
        tax_year = sell_dt.year
        
        for lot in open_lots:
            if remaining_to_sell <= 0.0000001:
                break
                
            lot_id = lot["id"]
            lot_acquired = lot["acquired_at"]
            lot_remaining = float(lot["remaining_qty"])
            lot_unit_basis = float(lot["unit_cost_basis"])
            
            matched_qty = min(remaining_to_sell, lot_remaining)
            allocated_fee = (matched_qty / quantity) * fee if quantity > 0 else 0.0
            
            # Gain calculation
            if side in WORTHLESS_SIDES:
                # Expired worthless or bet lost
                exit_price = 0.0
                proceeds = 0.0
            elif side == "REDEEM":
                # Redeemed winning prediction token at $1.00
                exit_price = 1.0
                proceeds = (matched_qty * exit_price) - allocated_fee
            else:
                exit_price = price
                proceeds = (matched_qty * exit_price) - allocated_fee
                
            cost_basis = matched_qty * lot_unit_basis
            gain_loss = proceeds - cost_basis
            
            # Holding period. Normalised to naive UTC for the subtraction ONLY -
            # `tax_year` above still comes from the timestamp as written, so an
            # offset-aware row filed on New Year's Eve keeps the local tax year
            # its taxpayer would report rather than being shifted by conversion.
            buy_dt = parse_iso_date(lot_acquired)
            holding_days = max(0, (as_naive_utc(sell_dt) - as_naive_utc(buy_dt)).days)
            if asset_class == GAMBLING_ASSET_CLASS or side in WAGER_SIDES:
                term = GAMBLING_TERM
            else:
                term = "LONG_TERM" if is_long_term(buy_dt, sell_dt) else "SHORT_TERM"
            
            # Insert realized PnL
            cursor.execute("""
                INSERT INTO realized_pnl 
                (close_transaction_id, open_lot_id, asset_class, symbol, opened_at, closed_at, quantity, cost_basis, proceeds, net_gain_loss, holding_period_days, term, tax_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_id, lot_id, asset_class, symbol, lot_acquired, timestamp, matched_qty, cost_basis, proceeds, gain_loss, holding_days, term, tax_year))
            
            # Update lot
            new_remaining = lot_remaining - matched_qty
            is_closed = 1 if new_remaining <= 0.000001 else 0
            cursor.execute("""
                UPDATE tax_lots SET remaining_qty = ?, is_closed = ? WHERE id = ?
            """, (new_remaining, is_closed, lot_id))
            
            remaining_to_sell -= matched_qty

        # UNMATCHED SETTLEMENT. A closing row that finds no open lot currently
        # falls off the end of that loop and books NOTHING - the win simply is
        # not in the ledger. For a wager that is the worst possible failure: a
        # settled-only sportsbook export (very common - books let you download
        # "settled bets" without the placements) silently drops every dollar of
        # taxable winnings and the escrow comes out at zero.
        #
        # Scoped to wager sides on purpose. The same fallback on SELL/REDEEM
        # would change how the frozen Polymarket and options paths behave, and
        # those have their own reconciliation. Here it is the safe direction:
        # with no recorded stake the whole payout is treated as winnings, which
        # OVER-states the base rather than losing it.
        if remaining_to_sell > 0.0000001 and side in WAGER_SIDES:
            unmatched = remaining_to_sell
            if side in WORTHLESS_SIDES:
                # A losing ticket with no recorded stake is no evidence of a
                # deductible loss. Booking one would invent a deduction.
                orphan_proceeds = 0.0
                orphan_basis = 0.0
            elif side == "BET_PUSH":
                # A push refunds the stake, so proceeds ARE the basis and the
                # row nets to zero without our having to know the wager.
                orphan_proceeds = unmatched * price
                orphan_basis = orphan_proceeds
            else:
                orphan_proceeds = (unmatched * price) - ((unmatched / quantity) * fee
                                                         if quantity > 0 else 0.0)
                orphan_basis = 0.0
            print(f"[WARN] {side} on {symbol!r} settled {unmatched:g} unit(s) with no open "
                  f"wager lot. Booked at ZERO cost basis (${orphan_proceeds:,.2f} of "
                  f"winnings). Import the matching placement row so the stake is "
                  f"deducted, or the taxable base stays overstated.")
            cursor.execute("""
                INSERT INTO realized_pnl
                (close_transaction_id, open_lot_id, asset_class, symbol, opened_at, closed_at, quantity, cost_basis, proceeds, net_gain_loss, holding_period_days, term, tax_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_id, None, asset_class, symbol, timestamp, timestamp, unmatched,
                  orphan_basis, orphan_proceeds, orphan_proceeds - orphan_basis, 0,
                  GAMBLING_TERM, tax_year))


def process_batch(transactions: List[Dict[str, Any]], db_path: Optional[Path] = None,
                  method: Optional[str] = None) -> None:
    """
    Sorts transactions chronologically and runs them through the lot engine.

    Chronological order is required under BOTH methods: HIFO changes which open
    lot a sale consumes, not the fact that a lot must exist before it is sold.
    """
    method = resolve_method(method)
    conn = get_connection(db_path)
    sorted_txs = [tx for _, tx in sorted(
        ((ledger_ordering_key(tx, i), tx) for i, tx in enumerate(transactions)),
        key=lambda pair: pair[0])]
    try:
        with conn:
            for tx in sorted_txs:
                process_transaction(tx, conn, method)
    finally:
        conn.close()
    if transactions:
        set_meta(ACCOUNTING_METHOD_KEY, method, db_path=db_path)
        set_meta(TERM_RULE_KEY, TERM_RULE_VERSION, db_path=db_path)


def rebuild_lots(db_path: Optional[Path] = None, method: Optional[str] = None) -> Dict[str, Any]:
    """
    Rebuilds every lot and realised gain from the `transactions` table.

    `transactions` is the immutable record of what happened; `tax_lots` and
    `realized_pnl` are derived from it and are safe to discard. This is what makes
    changing the accounting method a supported operation rather than a corruption:
    the whole history is re-matched under one consistent policy.

    Runs in a single transaction, so an interrupted rebuild rolls back to the
    previous lots rather than leaving the ledger half-matched.
    """
    method = resolve_method(method)
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS n FROM realized_pnl")
            previous_pnl = int(cursor.fetchone()["n"])
            cursor.execute("DELETE FROM realized_pnl")
            cursor.execute("DELETE FROM tax_lots")

            # Chronological, with id as the tie-break so same-timestamp rows keep
            # the order they were originally recorded in. Ordered in Python, NOT
            # in SQL: `ORDER BY timestamp` is a string sort and would re-order a
            # ledger holding two timestamp formats - so a rebuild would silently
            # produce different lots from the import that created them.
            cursor.execute("SELECT * FROM transactions")
            rows = sorted((dict(r) for r in cursor.fetchall()),
                          key=lambda r: ledger_ordering_key(r, int(r["id"])))
            for row in rows:
                apply_to_lots(row, int(row["id"]), conn, method)

            cursor.execute("SELECT COUNT(*) AS n FROM realized_pnl")
            rebuilt_pnl = int(cursor.fetchone()["n"])
    finally:
        conn.close()

    set_meta(ACCOUNTING_METHOD_KEY, method, db_path=db_path)
    set_meta(TERM_RULE_KEY, TERM_RULE_VERSION, db_path=db_path)
    return {"method": method, "transactions": len(rows),
            "realized_rows_before": previous_pnl, "realized_rows_after": rebuilt_pnl}
