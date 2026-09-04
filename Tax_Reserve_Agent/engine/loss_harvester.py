"""
Tax-Loss Harvesting Scanner.

Looks at open lots that are underwater, works out what selling them would save
against the gains already realised this year, and ranks them. Drives
`python -m Tax_Reserve_Agent.main harvest`.

THE HARD PART IS NOT THE ARITHMETIC, IT IS THE MARKS. The ledger knows what every
lot cost; it has no idea what any of it is worth today. Nothing here invents a
price. A position with no mark is listed as UNMARKED and excluded from every
total - because a made-up mark produces a made-up loss, which produces a
harvestable-saving figure someone might actually trade on. Marks come from:

  * `data/marks.csv`  - `symbol,price` written by hand or by a bot. Always
                        available, fully deterministic, works offline.
  * a live source      - `PolymarketMarkSource` prices open prediction-market
                        positions off the CLOB midpoint. Opt-in, and it degrades
                        to UNMARKED rather than guessing.

WHAT A HARVEST IS ACTUALLY WORTH. Not `loss * tax_rate`. A capital loss is only
worth the tax on the gain it can offset, and US netting has a specific order:
short-term losses net against short-term gains, long-term against long-term, then
whatever is left crosses over, then up to $3,000 of the remainder goes against
ordinary income and the rest carries forward at zero present value. Modelling
`loss * rate` overstates the benefit of harvesting into a year with no gains by
an order of magnitude, which is exactly when someone would be tempted to do it.
`estimate_benefit()` implements the real netting order.

This is an estimate from your own ledger, not tax advice, and it does not model
wash sales - see the note on `WASH_SALE_WARNING`.
"""
import csv
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import load_config
from ..database.db import get_connection
from .lot_engine import is_long_term, parse_iso_date

DEFAULT_MARKS_PATH = Path(__file__).parent.parent / "data" / "marks.csv"
ORDINARY_INCOME_OFFSET_CAP = 3000.0   # IRC 1211(b): net capital loss against ordinary income
LONG_TERM_DAYS = 365   # reported only; `is_long_term` decides the term

WASH_SALE_WARNING = (
    "Wash-sale rules (IRC 1091) are NOT modelled. They apply to stock and "
    "securities; crypto and prediction-market positions are currently treated as "
    "property and fall outside them, but that treatment is a policy choice that "
    "can change and does not cover every asset you might import here. If you "
    "repurchase a harvested position within 30 days, check the treatment before "
    "relying on the loss."
)


@dataclass
class HarvestCandidate:
    """One open lot that is currently worth less than it cost."""
    lot_id: int
    symbol: str
    asset_class: str
    acquired_at: str
    quantity: float
    unit_cost_basis: float
    cost_basis: float
    mark: float
    market_value: float
    unrealised_loss: float          # negative
    holding_days: int
    term: str                       # SHORT_TERM | LONG_TERM
    mark_source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HarvestReport:
    tax_year: int
    candidates: List[HarvestCandidate] = field(default_factory=list)
    unmarked: List[Dict[str, Any]] = field(default_factory=list)
    unrealised_gains: float = 0.0            # open lots that are UP (not harvestable)
    short_term_loss: float = 0.0
    long_term_loss: float = 0.0
    total_loss: float = 0.0
    realised_short_term: float = 0.0
    realised_long_term: float = 0.0
    offsettable_loss: float = 0.0            # loss that finds a gain to cancel
    carryforward_loss: float = 0.0           # loss with no present-year use
    ordinary_offset: float = 0.0             # up to $3,000
    estimated_tax_saving: float = 0.0
    escrow_before: float = 0.0
    escrow_after: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["candidates"] = [c.to_dict() for c in self.candidates]
        return data

    def render(self) -> str:
        # ASCII only: the HUD is read in a cp1252 Windows console, where a
        # middle dot renders as a question mark.
        lines = ["=" * 72, "  TAX-LOSS HARVESTING SCAN", "=" * 72,
                 f"  Tax year {self.tax_year}   |   realised so far: "
                 f"ST {self.realised_short_term:+,.2f} / LT {self.realised_long_term:+,.2f}",
                 "-" * 72]
        if self.candidates:
            lines.append(f"  {'SYMBOL':<28}{'QTY':>10}{'BASIS':>12}{'MARK':>9}{'LOSS':>13}  TERM")
            for c in self.candidates:
                lines.append(f"  {c.symbol[:27]:<28}{c.quantity:>10,.2f}"
                             f"{c.cost_basis:>12,.2f}{c.mark:>9,.4f}{c.unrealised_loss:>13,.2f}"
                             f"  {'LT' if c.term == 'LONG_TERM' else 'ST'}")
        else:
            lines.append("  No marked open position is underwater.")

        lines.append("-" * 72)
        lines.append(f"  Harvestable loss:          {self.total_loss:>14,.2f}   "
                     f"(ST {self.short_term_loss:,.2f} / LT {self.long_term_loss:,.2f})")
        lines.append(f"  Offsets realised gains:    {self.offsettable_loss:>14,.2f}")
        lines.append(f"  Against ordinary income:   {self.ordinary_offset:>14,.2f}   "
                     f"(capped at ${ORDINARY_INCOME_OFFSET_CAP:,.0f})")
        lines.append(f"  Carries forward:           {self.carryforward_loss:>14,.2f}   "
                     f"(no value this tax year)")
        lines.append("-" * 72)
        lines.append(f"  >>> ESTIMATED TAX SAVING:  {self.estimated_tax_saving:>14,.2f}")
        lines.append(f"  Tax escrow {self.escrow_before:,.2f} -> {self.escrow_after:,.2f} "
                     f"(frees {max(0.0, self.escrow_before - self.escrow_after):,.2f} of bankroll)")
        if self.unmarked:
            lines.append("-" * 72)
            lines.append(f"  UNMARKED - excluded from every figure above ({len(self.unmarked)}):")
            for row in self.unmarked[:12]:
                lines.append(f"    * {row['symbol']}  ({row['quantity']:,.2f} sh, "
                             f"basis ${row['cost_basis']:,.2f})")
            if len(self.unmarked) > 12:
                lines.append(f"    ... and {len(self.unmarked) - 12} more")
            lines.append("    Add them to data/marks.csv (symbol,price) to include them.")
        lines.append("=" * 72)
        wrapped = textwrap.wrap(WASH_SALE_WARNING, 66)
        lines.append("  [!] " + (wrapped[0] if wrapped else ""))
        lines.extend("      " + line for line in wrapped[1:])
        lines.append("=" * 72)
        return "\n".join(lines)


def load_marks(marks_path: Optional[Path] = None) -> Dict[str, float]:
    """
    `data/marks.csv` -> {symbol: price}.

    Columns: `symbol,price` (a `mark` column is accepted too). Missing file is not
    an error - it just means nothing is marked from disk.
    """
    path = Path(marks_path) if marks_path else DEFAULT_MARKS_PATH
    marks: Dict[str, float] = {}
    if not path.exists():
        return marks
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                clean = {str(k).strip().lower(): v for k, v in row.items() if k}
                symbol = str(clean.get("symbol") or "").strip()
                raw = clean.get("price", clean.get("mark"))
                if not symbol or raw in (None, ""):
                    continue
                try:
                    marks[symbol] = float(raw)
                except (TypeError, ValueError):
                    print(f"[WARN] Unparseable mark for {symbol!r} in {path.name}; skipping.")
    except OSError as e:
        print(f"[WARN] Could not read {path}: {e}")
    return marks


class PolymarketMarkSource:
    """
    Live marks for open prediction-market positions from the CLOB midpoint.

    Opt-in and best-effort: a symbol it cannot price is left UNMARKED rather than
    defaulted, so a network failure shrinks the report instead of corrupting it.
    """

    def __init__(self, resolver=None, timeout: int = 10):
        from ..ingestors.polymarket import PolymarketMarketResolver
        self.resolver = resolver or PolymarketMarketResolver()
        self.timeout = timeout
        self._cache: Dict[str, Optional[float]] = {}

    def __call__(self, symbol: str, asset_class: str) -> Optional[float]:
        if asset_class != "prediction_market":
            return None
        if symbol in self._cache:
            return self._cache[symbol]
        price = self._fetch(symbol)
        self._cache[symbol] = price
        return price

    def _fetch(self, symbol: str) -> Optional[float]:
        import json
        import urllib.request

        token_id = self._token_for_symbol(symbol)
        if not token_id:
            return None
        try:
            req = urllib.request.Request(
                f"https://clob.polymarket.com/midpoint?token_id={token_id}",
                headers={"User-Agent": "TaxReserveAgent/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
            mid = payload.get("mid")
            return float(mid) if mid is not None else None
        except Exception as e:
            print(f"[INFO] No live mark for {symbol}: {e}")
            return None

    def _token_for_symbol(self, symbol: str) -> Optional[str]:
        """
        Symbol -> CLOB token id, resolving from Gamma when the cache is cold.

        REGRESSION FIXED: this used to scan `resolver._cache` and nothing else, so
        on a fresh run - new checkout, CSV-built ledger, cleared cache - it
        returned None for every position and `harvest --live-marks` silently
        priced NOTHING. Nothing errored; the report was just empty.
        """
        resolved = self.resolver.resolve_symbol(symbol)
        return (resolved or {}).get("token_id") or None


class LossHarvester:
    """
    Ranks open underwater lots by the tax they would actually save.

    `price_source` is any callable `(symbol, asset_class) -> Optional[float]`,
    checked before `data/marks.csv`, so a caller can plug in live prices without
    this module knowing anything about where they come from.
    """

    def __init__(self,
                 db_path: Optional[Path] = None,
                 config: Optional[Dict[str, Any]] = None,
                 marks_path: Optional[Path] = None,
                 price_source: Optional[Callable[[str, str], Optional[float]]] = None):
        self.db_path = db_path
        self.config = config if config is not None else load_config()
        self.marks_path = marks_path
        self.price_source = price_source

    # -- inputs -------------------------------------------------------------

    def open_lots(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, symbol, asset_class, acquired_at, remaining_qty, unit_cost_basis
                FROM tax_lots
                WHERE is_closed = 0 AND remaining_qty > 0
                ORDER BY symbol ASC, acquired_at ASC, id ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def realised_by_term(self, tax_year: int) -> Dict[str, float]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT term, SUM(net_gain_loss) AS net
                FROM realized_pnl WHERE tax_year = ? GROUP BY term
            """, (tax_year,))
            rows = {row["term"]: float(row["net"] or 0.0) for row in cursor.fetchall()}
        finally:
            conn.close()
        return {"SHORT_TERM": rows.get("SHORT_TERM", 0.0), "LONG_TERM": rows.get("LONG_TERM", 0.0)}

    def mark_for(self, symbol: str, asset_class: str, marks: Dict[str, float]) -> Optional[float]:
        if self.price_source is not None:
            live = self.price_source(symbol, asset_class)
            if live is not None:
                return float(live)
        return marks.get(symbol)

    # -- the benefit calculation -------------------------------------------

    def estimate_benefit(self, short_term_loss: float, long_term_loss: float,
                         realised_short: float, realised_long: float) -> Dict[str, float]:
        """
        Applies the US capital-loss netting order to a proposed harvest.

        Losses are passed in as POSITIVE magnitudes. Order: same-term netting
        first, then the cross-over, then the ordinary-income allowance, then
        carryforward. The carried-forward part is deliberately valued at zero -
        it is worth something in a future year, but nothing this April, and
        conflating the two is what makes naive harvest tools overstate the
        benefit of selling into a flat year.
        """
        rates = self.config.get("tax_rates", {})
        st_rate = (rates.get("short_term_capital_gains", 0.28)
                   + rates.get("state_tax_rate", 0.05)
                   + rates.get("safety_buffer_pct", 0.02))
        lt_rate = rates.get("long_term_capital_gains", 0.15) + rates.get("state_tax_rate", 0.05)

        st_loss, lt_loss = max(0.0, short_term_loss), max(0.0, long_term_loss)
        st_gain, lt_gain = max(0.0, realised_short), max(0.0, realised_long)

        # 1. Same-term netting.
        st_used = min(st_loss, st_gain)
        lt_used = min(lt_loss, lt_gain)
        saving = st_used * st_rate + lt_used * lt_rate
        st_loss -= st_used
        lt_loss -= lt_used
        st_gain -= st_used
        lt_gain -= lt_used

        # 2. Cross-over: whatever is left of one term offsets the other.
        st_cross = min(st_loss, lt_gain)      # ST loss killing a LT gain saves the LT rate
        saving += st_cross * lt_rate
        st_loss -= st_cross
        lt_gain -= st_cross

        lt_cross = min(lt_loss, st_gain)      # LT loss killing a ST gain saves the ST rate
        saving += lt_cross * st_rate
        lt_loss -= lt_cross
        st_gain -= lt_cross

        offsettable = st_used + lt_used + st_cross + lt_cross

        # 3. Up to $3,000 of what remains goes against ordinary income.
        remaining = st_loss + lt_loss
        ordinary = min(remaining, ORDINARY_INCOME_OFFSET_CAP)
        saving += ordinary * st_rate          # ordinary income taxed at the ST composite rate

        return {
            "offsettable_loss": offsettable,
            "ordinary_offset": ordinary,
            "carryforward_loss": max(0.0, remaining - ordinary),
            "estimated_tax_saving": saving,
        }

    # -- the scan -----------------------------------------------------------

    def analyze(self, tax_year: int = 2026, as_of: Optional[str] = None) -> HarvestReport:
        """
        Builds the report. `as_of` (default: now) sets the holding-period cutoff
        that decides short versus long term.
        """
        as_of_dt = parse_iso_date(as_of) if as_of else datetime.now()
        marks = load_marks(self.marks_path)
        realised = self.realised_by_term(tax_year)
        report = HarvestReport(tax_year=tax_year,
                               realised_short_term=realised["SHORT_TERM"],
                               realised_long_term=realised["LONG_TERM"])

        for lot in self.open_lots():
            quantity = float(lot["remaining_qty"])
            unit_cost = float(lot["unit_cost_basis"])
            cost_basis = quantity * unit_cost
            mark = self.mark_for(lot["symbol"], lot["asset_class"], marks)

            if mark is None:
                report.unmarked.append({"symbol": lot["symbol"], "asset_class": lot["asset_class"],
                                        "quantity": quantity, "cost_basis": cost_basis})
                continue

            market_value = quantity * float(mark)
            unrealised = market_value - cost_basis
            if unrealised >= 0:
                report.unrealised_gains += unrealised
                continue

            try:
                holding_days = max(0, (as_of_dt - parse_iso_date(lot["acquired_at"])).days)
            except (ValueError, TypeError):
                holding_days = 0
            # Same calendar test the lot engine books with - see `is_long_term`.
            # A day count cannot express "more than one year" across a leap year.
            term = ("LONG_TERM" if is_long_term(parse_iso_date(lot["acquired_at"]), as_of_dt)
                    else "SHORT_TERM")

            report.candidates.append(HarvestCandidate(
                lot_id=int(lot["id"]), symbol=lot["symbol"], asset_class=lot["asset_class"],
                acquired_at=lot["acquired_at"], quantity=quantity, unit_cost_basis=unit_cost,
                cost_basis=cost_basis, mark=float(mark), market_value=market_value,
                unrealised_loss=unrealised, holding_days=holding_days, term=term,
                mark_source="live" if self.price_source else "marks.csv"))

            if term == "SHORT_TERM":
                report.short_term_loss += -unrealised
            else:
                report.long_term_loss += -unrealised

        # Biggest loss first - that is the order someone would work down the list.
        report.candidates.sort(key=lambda c: c.unrealised_loss)
        report.total_loss = report.short_term_loss + report.long_term_loss

        benefit = self.estimate_benefit(report.short_term_loss, report.long_term_loss,
                                        realised["SHORT_TERM"], realised["LONG_TERM"])
        report.offsettable_loss = benefit["offsettable_loss"]
        report.ordinary_offset = benefit["ordinary_offset"]
        report.carryforward_loss = benefit["carryforward_loss"]
        report.estimated_tax_saving = benefit["estimated_tax_saving"]

        from .tax_calculator import calculate_tax_summary
        summary = calculate_tax_summary(tax_year=tax_year, db_path=self.db_path, config=self.config)
        report.escrow_before = summary["tax_escrow_reserve"]
        report.escrow_after = max(0.0, report.escrow_before - report.estimated_tax_saving)
        return report
