"""
Tax Escrow Calculator and Safe Bankroll Sizer.
Computes real-time tax liabilities, loss offsets, and available risk capital.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from ..database.db import get_connection, get_meta
from ..config import load_config, get_composite_tax_rate
from .lot_engine import (ACCOUNTING_METHOD_KEY, DEFAULT_METHOD, GAMBLING_ASSET_CLASS,
                        GAMBLING_TERM, TERM_RULE_KEY, TERM_RULE_VERSION,
                        normalise_method)
from .gambling_tax import (GamblingInputs, SESSION_NETTING, compute_gambling_tax,
                           resolve_policy, resolve_rates)

def calculate_tax_summary(tax_year: int = 2026, db_path: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Computes YTD Realized Gains, Losses, Net PnL by asset class, and Tax Escrow Reserve.
    """
    if config is None:
        config = load_config()
        
    rates = config.get("tax_rates", {})
    st_rate = rates.get("short_term_capital_gains", 0.28) + rates.get("state_tax_rate", 0.05) + rates.get("safety_buffer_pct", 0.02)
    lt_rate = rates.get("long_term_capital_gains", 0.15) + rates.get("state_tax_rate", 0.05)

    # IRC 1256(a)(3): a regulated futures contract is taxed 60% long-term / 40%
    # short-term REGARDLESS of how long it was held. Day-traded CME contracts
    # therefore do not book at the full short-term rate.
    #
    # NOTE, because this LOWERS the reserve: the blend uses the rates as they are
    # already defined above, and `lt_rate` carries no safety buffer while
    # `st_rate` does. That asymmetry predates 1256 and is left alone here rather
    # than silently re-rating every long-term gain in the ledger - but it is why
    # this comes out at 26.0% and not the 27.2% a buffered LT leg would give.
    futures_rate = 0.60 * lt_rate + 0.40 * st_rate

    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Query Realized PnL grouped by asset class and term
        cursor.execute("""
            SELECT 
                asset_class,
                term,
                SUM(CASE WHEN net_gain_loss > 0 THEN net_gain_loss ELSE 0 END) as gross_gains,
                SUM(CASE WHEN net_gain_loss < 0 THEN net_gain_loss ELSE 0 END) as gross_losses,
                SUM(net_gain_loss) as net_pnl,
                COUNT(*) as trade_count
            FROM realized_pnl
            WHERE tax_year = ?
            GROUP BY asset_class, term
        """, (tax_year,))
        
        rows = cursor.fetchall()
        
        breakdown_by_asset = {}
        st_net = 0.0
        lt_net = 0.0
        futures_net = 0.0
        gambling_gains = 0.0
        gambling_losses = 0.0
        gambling_net = 0.0
        total_gross_gains = 0.0
        total_gross_losses = 0.0
        # Capital-only mirrors. `total_gross_gains` has always included the 1256
        # futures bucket, and now the gambling bucket too, so the field named
        # `net_capital_gains` is not net capital gains. Kept as-is for every
        # existing caller; these are what the HUD and the exporter should read.
        capital_gross_gains = 0.0
        capital_gross_losses = 0.0
        
        for r in rows:
            asset = r["asset_class"]
            term = r["term"]
            gains = float(r["gross_gains"] or 0.0)
            losses = float(r["gross_losses"] or 0.0)
            net = float(r["net_pnl"] or 0.0)
            
            if asset not in breakdown_by_asset:
                breakdown_by_asset[asset] = {
                    "gross_gains": 0.0,
                    "gross_losses": 0.0,
                    "net_pnl": 0.0,
                    "trade_count": 0
                }
            breakdown_by_asset[asset]["gross_gains"] += gains
            breakdown_by_asset[asset]["gross_losses"] += losses
            breakdown_by_asset[asset]["net_pnl"] += net
            breakdown_by_asset[asset]["trade_count"] += int(r["trade_count"])
            
            total_gross_gains += gains
            total_gross_losses += losses
            
            # Section 1256 contracts and Sports Bets are carved out of capital gain term buckets.
            # Routed on EITHER key. A wager whose import mislabelled the asset
            # class would otherwise fall through to `else` and be reserved as a
            # LONG-TERM capital gain at 20% instead of ordinary income at 35%.
            if asset == GAMBLING_ASSET_CLASS or term == GAMBLING_TERM:
                gambling_gains += gains
                gambling_losses += losses
                gambling_net += net
            elif asset == "futures":
                futures_net += net
                capital_gross_gains += gains
                capital_gross_losses += losses
            elif term == "SHORT_TERM":
                st_net += net
                capital_gross_gains += gains
                capital_gross_losses += losses
            else:
                lt_net += net
                capital_gross_gains += gains
                capital_gross_losses += losses
                
        # Calculate Tax Escrow Reserve
        # Short-term gains are taxed at composite ST rate; losses offset gains
        st_tax = max(0.0, st_net * st_rate)
        lt_tax = max(0.0, lt_net * lt_rate)

        # A net 1256 LOSS reserves nothing. It does not offset the other buckets
        # either: 1256 losses carry back three years against prior 1256 gains,
        # which is a filing election and not a reason to release cash today.
        futures_tax = max(0.0, futures_net) * futures_rate

        # --------------------------------------------------------------------
        # SPORTS BETTING & WAGERING TAX (IRC 61, 165(d), 1402; OBBBA 70114)
        #
        # The rules themselves live in `engine/gambling_tax.py` - they are pure
        # arithmetic over dollars and are unit-tested there without a database.
        # What happens here is only the MEASUREMENT: turning the ledger into the
        # five numbers that module needs.
        # --------------------------------------------------------------------
        gambling_cfg = config.get("gambling", {}) or {}
        gambling_policy = resolve_policy(gambling_cfg)
        gambling_rates = resolve_rates(rates, gambling_cfg)

        # Sessions (IRS AM 2008-011). Grouped by day AND by book, not by day
        # alone: a session is one kind of wagering at ONE establishment, and
        # netting a DraftKings loss against a FanDuel win on the same afternoon
        # is a deduction dressed up as a measurement. `session_grouping: "day"`
        # restores the looser reading for anyone who wants it.
        session_winnings = 0.0
        session_losses = 0.0
        session_count = 0
        if gambling_policy.treatment == SESSION_NETTING:
            group_by_book = str(gambling_cfg.get("session_grouping", "day_book")) != "day"
            book_key = "t.source" if group_by_book else "''"
            # Both sides in one pass: winning sessions are the taxable base,
            # losing sessions are the Schedule A deduction when itemising.
            cursor.execute(f"""
                SELECT
                    SUM(CASE WHEN session_net > 0 THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN session_net > 0 THEN session_net ELSE 0 END) AS won,
                    SUM(CASE WHEN session_net < 0 THEN -session_net ELSE 0 END) AS lost
                FROM (
                    SELECT SUBSTR(p.closed_at, 1, 10) AS session_date,
                           {book_key} AS book,
                           SUM(p.net_gain_loss) AS session_net
                    FROM realized_pnl p
                    LEFT JOIN transactions t ON t.id = p.close_transaction_id
                    WHERE p.tax_year = ? AND (p.asset_class = ? OR p.term = ?)
                    GROUP BY session_date, book
                )
            """, (tax_year, GAMBLING_ASSET_CLASS, GAMBLING_TERM))
            srow = cursor.fetchone()
            if srow:
                session_count = int(srow["wins"] or 0)
                session_winnings = float(srow["won"] or 0.0)
                session_losses = float(srow["lost"] or 0.0)

        # Schedule C expenses, professional mode only. Deliberately EXCLUDED from
        # the ordinary-income bucket below so the same dollar is not deducted
        # twice - once against funding income and once against wagering profit.
        cursor.execute("""
            SELECT SUM(total_value) AS spend FROM transactions
            WHERE asset_class = ? AND side = 'EXPENSE' AND timestamp LIKE ?
        """, (GAMBLING_ASSET_CLASS, f"{tax_year}%"))
        exp_row = cursor.fetchone()
        gambling_expenses = float(exp_row["spend"] or 0.0) if exp_row else 0.0

        # Form W-2G federal withholding, tagged onto the settlement row at
        # ingestion. Read from the SETTLEMENT sides only: a `w2g_withholding:`
        # tag can only describe money the book already sent to the Treasury, and
        # scanning every wager row would double-count a note copied onto both.
        total_w2g_withheld = 0.0
        total_w2g_predicted = 0.0
        if gambling_policy.track_w2g_withholdings:
            cursor.execute("""
                SELECT id, source, notes FROM transactions
                WHERE asset_class = ?
                  AND side IN ('BET_WIN', 'BET_PUSH', 'BET_CASHOUT', 'BET_LOSS')
                  AND timestamp LIKE ?
                  AND (notes LIKE '%w2g_withholding:%'
                       OR notes LIKE '%w2g_withholding_predicted:%')
            """, (GAMBLING_ASSET_CLASS, f"{tax_year}%"))

            # ONE W-2G PER TICKET, STRUCTURALLY. The ingestor already tags a
            # single leg, but this sums a free-text note across rows and a
            # multi-leg settlement (dead heat, partial void) is two rows for one
            # ticket. Trusting the writer is how the tag ended up on both legs in
            # the first place, and a double credit SHRINKS the reserve silently.
            # Deduped here on (book, ticket) so no future import shape can
            # reintroduce it. A row with no `ticket:` tag cannot be deduped and
            # is counted on its own id - dropping it would lose a real payment.
            per_ticket: Dict[Any, float] = {}
            predicted_per_ticket: Dict[Any, float] = {}
            for wrow in cursor.fetchall():
                notes = wrow["notes"] or ""
                amount = None
                predicted = None
                ticket = None
                for part in notes.split(";"):
                    part = part.strip()
                    if part.startswith("w2g_withholding:"):
                        try:
                            amount = float(part.split(":", 1)[1])
                        except (ValueError, IndexError):
                            print(f"[WARN] Unparseable W-2G tag {part!r}; withholding "
                                  f"credit ignored for that row.")
                    elif part.startswith("w2g_withholding_predicted:"):
                        try:
                            predicted = float(part.split(":", 1)[1])
                        except (ValueError, IndexError):
                            pass
                    elif part.startswith("ticket:"):
                        ticket = part.split(":", 1)[1].strip().upper()
                key = (wrow["source"], ticket) if ticket else ("#row", wrow["id"])
                if amount is not None:
                    previous = per_ticket.get(key)
                    if previous is not None and abs(previous - amount) > 0.005:
                        print(f"[WARN] Ticket {ticket!r} carries two different W-2G "
                              f"amounts (${previous:,.2f} and ${amount:,.2f}); crediting "
                              f"the larger. One ticket has one W-2G - check the import.")
                    per_ticket[key] = max(previous or 0.0, amount)
                if predicted is not None:
                    predicted_per_ticket[key] = max(predicted_per_ticket.get(key, 0.0),
                                                    predicted)
            total_w2g_withheld = sum(per_ticket.values())
            # A ticket the book WAS REQUIRED to withhold on but whose import
            # carries no withholding tag. Counted once, and only where nothing was
            # actually recorded - a book that withheld and a book that must
            # withhold cannot both be credited for the same wager.
            total_w2g_predicted = sum(value for key, value in predicted_per_ticket.items()
                                      if key not in per_ticket)

        gambling = compute_gambling_tax(
            GamblingInputs(
                gross_winnings=gambling_gains,
                gross_losses=abs(gambling_losses),
                net_cash_pnl=gambling_net,
                session_winnings=session_winnings,
                session_losses=session_losses,
                session_count=session_count,
                expenses=gambling_expenses,
                w2g_withheld=total_w2g_withheld,
                w2g_predicted=total_w2g_predicted,
            ),
            gambling_rates, gambling_policy, tax_year,
        )
        gambling_escrow = gambling.escrow
        
        # Which method the lots were actually matched under, versus what the config
        # asks for now. They diverge the moment someone edits config.yaml without
        # rebuilding, and every number below would then be a blend of two methods -
        # a position no accounting standard permits. Surfaced, never silently fixed.
        configured_method = normalise_method((config.get("accounting", {}) or {}).get("method"))
        ledger_method = get_meta(ACCOUNTING_METHOD_KEY, DEFAULT_METHOD, db_path=db_path)

        # Which term rule the stored classifications were made under. Only
        # meaningful once there ARE capital terms to misclassify - an empty or
        # gambling-only ledger has nothing at stake here.
        ledger_term_rule = get_meta(TERM_RULE_KEY, None, db_path=db_path)
        has_capital_terms = bool(st_net or lt_net or capital_gross_gains
                                 or capital_gross_losses)
        term_rule_stale = bool(has_capital_terms
                               and ledger_term_rule != TERM_RULE_VERSION)

        # Query ordinary income (funding payments, etc.) under IRC §61
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN side = 'INCOME' THEN total_value ELSE 0 END) as ordinary_income,
                SUM(CASE WHEN side = 'EXPENSE' THEN total_value ELSE 0 END) as ordinary_expense
            FROM transactions
            WHERE timestamp LIKE ? AND asset_class != ?
        """, (f"{tax_year}%", GAMBLING_ASSET_CLASS))
        inc_row = cursor.fetchone()
        ord_income = float(inc_row["ordinary_income"] or 0.0) if inc_row else 0.0
        ord_expense = float(inc_row["ordinary_expense"] or 0.0) if inc_row else 0.0
        net_ord_income = ord_income - ord_expense

        # ORDINARY INCOME IS ESCROWED TOO.
        #
        # Funding accruals are IRC 61 ordinary income, taxed at ordinary rates -
        # the same rates `st_rate` already composites (federal + state + buffer).
        # Reporting the income without reserving against it was the whole failure
        # mode this ledger exists to prevent: a basis harvester earning funding all
        # year would show the income on the card and still report 100% of it as
        # safe to deploy.
        #
        # Floored at zero. A net ordinary LOSS does not hand back escrow that
        # capital gains are responsible for - those are separate buckets, and
        # crediting one against the other moves the reserve DOWN, which is the one
        # direction a tax reserve must never move on an assumption.
        #
        # Capital losses likewise do NOT reduce this. IRC 1211 caps an individual's
        # capital-loss offset against ordinary income at $3,000/yr, and applying
        # even that would shrink the reserve. Conservative and deliberate: see
        # "DEFAULTS THAT LOOK CONSERVATIVE BY ACCIDENT AND ARE NOT" in VERSION.
        ord_tax = max(0.0, net_ord_income) * st_rate

        total_tax_escrow = st_tax + lt_tax + futures_tax + ord_tax + gambling_escrow

        liquid_cash = float(config.get("portfolio", {}).get("default_cash_balance_usdc", 10000.0))
        safe_deployable_bankroll = max(0.0, liquid_cash - total_tax_escrow)
        reserve_ratio = (total_tax_escrow / liquid_cash * 100.0) if liquid_cash > 0 else 0.0

        return {
            "tax_year": tax_year,
            "accounting_method": ledger_method,
            "configured_method": configured_method,
            "method_mismatch": ledger_method != configured_method,
            "term_rule": ledger_term_rule or "pre-calendar",
            "term_rule_stale": term_rule_stale,
            "liquid_cash_balance": liquid_cash,
            "total_gross_gains": total_gross_gains,
            "total_gross_losses": total_gross_losses,
            "net_capital_gains": total_gross_gains + total_gross_losses,
            "short_term_net": st_net,
            "long_term_net": lt_net,
            "ordinary_income": ord_income,
            "ordinary_expense": ord_expense,
            "net_ordinary_income": net_ord_income,
            "effective_tax_rate": st_rate,
            "escrow_short_term": st_tax,
            "escrow_long_term": lt_tax,
            "escrow_futures": futures_tax,
            "escrow_ordinary": ord_tax,
            "escrow_gambling": gambling_escrow,
            # Legacy field names, preserved so nothing downstream breaks. Signed
            # `gambling_losses` (negative) is what the HUD has always rendered.
            "gambling_gains": gambling_gains,
            "gambling_losses": gambling_losses,
            "gambling_net": gambling_net,
            "gambling_taxable_base": gambling.federal_taxable_base,
            "gambling_tax_gross": gambling.tax_gross,
            "gambling_w2g_withheld": gambling.w2g_withheld,
            "gambling_treatment": gambling.treatment,
            "state_allows_loss_deduction": gambling_policy.state_allows_loss_deduction,
            "gambling_expenses": gambling_expenses,
            "capital_gross_gains": capital_gross_gains,
            "capital_gross_losses": capital_gross_losses,
            "net_capital_gains_excl_gambling": capital_gross_gains + capital_gross_losses,
            "futures_net": futures_net,
            "futures_rate": futures_rate,
            "tax_escrow_reserve": total_tax_escrow,
            "safe_deployable_bankroll": safe_deployable_bankroll,
            "reserve_ratio_pct": reserve_ratio,
            "breakdown_by_asset": breakdown_by_asset,
            # Federal/state split, the 165(d) disallowance, the OBBBA haircut,
            # the W-2G credit actually applied and any overwithheld surplus.
            # `as_summary_fields` owns these names so the rules engine and the
            # HUD cannot drift apart.
            **{k: v for k, v in gambling.as_summary_fields().items()
               if k not in ("escrow_gambling", "gambling_treatment", "gambling_expenses")},
        }
    finally:
        conn.close()
