"""
Quarterly Estimated Tax Schedule.

Turns the realised P&L in the ledger into "how much is due, and when", and says
how much of the tax escrow should be released at each deadline. Drives
`python -m Tax_Reserve_Agent.main calendar`.

THE QUARTERS ARE NOT QUARTERS. This is the detail the name hides and everyone
gets wrong:

    Q1   Jan 1 - Mar 31   (3 months)  due Apr 15
    Q2   Apr 1 - May 31   (2 months)  due Jun 15
    Q3   Jun 1 - Aug 31   (3 months)  due Sep 15
    Q4   Sep 1 - Dec 31   (4 months)  due Jan 15 of the FOLLOWING year

A trader who books a large gain on June 1 owes it in the Q3 payment, not Q2, and
one who books it on May 31 owes it two weeks later. Splitting the year into even
three-month blocks produces the right annual total and the wrong deadline on
every one of them, which is precisely what triggers an underpayment penalty even
when the year is paid in full.

The gain is attributed to the period it was REALISED in, which is the annualised
income installment method - the right one for lumpy trading income, where the
even-quarters default would demand tax in April on a gain not made until
November.

Deadlines falling at a weekend roll to the following Monday. Federal holidays are
NOT modelled: the one that matters in practice is Emancipation Day in DC, which
pushes the April deadline to the 17th in some years. Treat a due date within a day
or two of a weekend as needing a check against the IRS calendar.

Not modelled either: the safe-harbour rules (paying 90% of this year, or 100% /
110% of last year's liability, avoids a penalty regardless of how the income
actually fell). This schedule shows what the year's realised gains imply, which
is the number you need to have set aside either way.
"""
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import load_config
from ..database.db import get_connection

# (label, start month/day, end month/day, due month/day, due-year offset)
QUARTER_DEFINITIONS = (
    ("Q1", (1, 1), (3, 31), (4, 15), 0),
    ("Q2", (4, 1), (5, 31), (6, 15), 0),
    ("Q3", (6, 1), (8, 31), (9, 15), 0),
    ("Q4", (9, 1), (12, 31), (1, 15), 1),
)


def next_business_day(day: date) -> date:
    """Saturday and Sunday roll forward to Monday. Federal holidays are not modelled."""
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


@dataclass
class QuarterSchedule:
    label: str
    period_start: str
    period_end: str
    due_date: str
    short_term_net: float = 0.0
    long_term_net: float = 0.0
    net_gain: float = 0.0
    tax_due: float = 0.0
    cumulative_tax_due: float = 0.0
    trade_count: int = 0
    status: str = "UPCOMING"          # CLOSED_UNPAID | UPCOMING | IN_PROGRESS | FUTURE
    days_until_due: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaxCalendar:
    tax_year: int
    quarters: List[QuarterSchedule] = field(default_factory=list)
    total_tax_due: float = 0.0
    escrow_held: float = 0.0
    escrow_releasable: float = 0.0    # already past its deadline
    escrow_reserved: float = 0.0      # still owed at a future deadline
    shortfall: float = 0.0            # owed but not covered by the escrow

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["quarters"] = [q.to_dict() for q in self.quarters]
        return data

    def render(self) -> str:
        lines = ["=" * 76, f"  QUARTERLY ESTIMATED TAX SCHEDULE - {self.tax_year}", "=" * 76,
                 f"  {'':<4}{'PERIOD':<26}{'DUE':<13}{'NET GAIN':>13}{'TAX DUE':>12}  STATUS",
                 "-" * 76]
        for q in self.quarters:
            period = f"{q.period_start[5:]} to {q.period_end[5:]}"
            lines.append(f"  {q.label:<4}{period:<26}{q.due_date:<13}"
                         f"{q.net_gain:>13,.2f}{q.tax_due:>12,.2f}  {q.status}")
        lines.append("-" * 76)
        lines.append(f"  Total estimated tax on {self.tax_year} realised gains: "
                     f"${self.total_tax_due:,.2f}")
        lines.append(f"  Tax escrow currently held:                    ${self.escrow_held:,.2f}")
        lines.append("-" * 76)
        lines.append(f"  >>> PAST DUE / PAYABLE NOW:   ${self.escrow_releasable:>12,.2f}  "
                     f"<-- release from escrow and pay")
        lines.append(f"  >>> KEEP RESERVED:            ${self.escrow_reserved:>12,.2f}  "
                     f"(owed at a later deadline)")
        if self.shortfall > 0:
            lines.append(f"  [!] SHORTFALL:                ${self.shortfall:>12,.2f}  "
                         f"escrow does not cover what is owed")
        lines.append("=" * 76)
        lines.append("  [i] Periods are IRS estimated-tax periods, not even quarters: Q2 is two")
        lines.append("      months and Q4 is four. Weekend deadlines roll to Monday; federal")
        lines.append("      holidays are not modelled. Safe-harbour rules are not modelled.")
        lines.append("=" * 76)
        return "\n".join(lines)


def quarter_bounds(tax_year: int) -> List[Dict[str, Any]]:
    """The four estimated-tax periods with their (business-day adjusted) deadlines."""
    bounds = []
    for label, start, end, due, year_offset in QUARTER_DEFINITIONS:
        bounds.append({
            "label": label,
            "start": date(tax_year, *start),
            "end": date(tax_year, *end),
            "due": next_business_day(date(tax_year + year_offset, *due)),
        })
    return bounds


def build_calendar(tax_year: int = 2026,
                   db_path: Optional[Path] = None,
                   config: Optional[Dict[str, Any]] = None,
                   today: Optional[date] = None) -> TaxCalendar:
    """
    Buckets the year's realised gains into estimated-tax periods and prices each.

    `today` is injectable so the status column is testable rather than dependent
    on the clock.
    """
    if config is None:
        config = load_config()
    today = today or date.today()

    rates = config.get("tax_rates", {})
    st_rate = (rates.get("short_term_capital_gains", 0.28)
               + rates.get("state_tax_rate", 0.05)
               + rates.get("safety_buffer_pct", 0.02))
    lt_rate = rates.get("long_term_capital_gains", 0.15) + rates.get("state_tax_rate", 0.05)

    calendar = TaxCalendar(tax_year=tax_year)
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        for bounds in quarter_bounds(tax_year):
            # closed_at is 'YYYY-MM-DD HH:MM:SS', so a lexical date range works and
            # keeps the bucketing inside SQLite.
            cursor.execute("""
                SELECT term,
                       SUM(net_gain_loss) AS net,
                       COUNT(*) AS trades
                FROM realized_pnl
                WHERE tax_year = ? AND date(closed_at) BETWEEN ? AND ?
                GROUP BY term
            """, (tax_year, bounds["start"].isoformat(), bounds["end"].isoformat()))
            rows = cursor.fetchall()

            quarter = QuarterSchedule(
                label=bounds["label"],
                period_start=bounds["start"].isoformat(),
                period_end=bounds["end"].isoformat(),
                due_date=bounds["due"].isoformat(),
            )
            for row in rows:
                net = float(row["net"] or 0.0)
                quarter.trade_count += int(row["trades"] or 0)
                if row["term"] == "SHORT_TERM":
                    quarter.short_term_net += net
                else:
                    quarter.long_term_net += net

            quarter.net_gain = quarter.short_term_net + quarter.long_term_net
            # Each period is priced on its own gains. A loss in one period does not
            # produce a refund from an earlier payment; it reduces the ANNUAL
            # liability, which the escrow figure already reflects. Clamping at zero
            # here keeps a losing quarter from cancelling tax genuinely owed on an
            # earlier one.
            quarter.tax_due = (max(0.0, quarter.short_term_net) * st_rate
                               + max(0.0, quarter.long_term_net) * lt_rate)
            quarter.days_until_due = (bounds["due"] - today).days

            if today > bounds["due"]:
                quarter.status = "CLOSED_UNPAID" if quarter.tax_due > 0 else "CLOSED"
            elif today > bounds["end"]:
                quarter.status = "UPCOMING"
            elif today >= bounds["start"]:
                quarter.status = "IN_PROGRESS"
            else:
                quarter.status = "FUTURE"

            calendar.quarters.append(quarter)
    finally:
        conn.close()

    running = 0.0
    for quarter in calendar.quarters:
        running += quarter.tax_due
        quarter.cumulative_tax_due = running
    calendar.total_tax_due = running

    from ..engine.tax_calculator import calculate_tax_summary
    summary = calculate_tax_summary(tax_year=tax_year, db_path=db_path, config=config)
    calendar.escrow_held = summary["tax_escrow_reserve"]

    past_due = sum(q.tax_due for q in calendar.quarters if q.status == "CLOSED_UNPAID")
    calendar.escrow_releasable = min(past_due, calendar.escrow_held)
    calendar.escrow_reserved = max(0.0, calendar.escrow_held - calendar.escrow_releasable)
    calendar.shortfall = max(0.0, past_due - calendar.escrow_held)
    return calendar
