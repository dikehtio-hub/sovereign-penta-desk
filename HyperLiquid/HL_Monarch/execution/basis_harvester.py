"""
Delta-neutral basis harvester: the paper engine that replaced the retired fade.

WHAT IT TRADES. Positive funding means longs pay shorts. The harvester shorts the
perp to collect that and buys the same notional of spot so the price exposure
cancels. Net delta zero, 1:1 by construction: the funding IS the return.

WHY THIS IS STRUCTURALLY DIFFERENT FROM WHAT IT REPLACED.
The liquidation fade was retired because its entry signal was measured wrong-sided
(MFE/MAE 0.513 against a 1.092 control). That was a DIRECTIONAL bet dressed up as a
mean-reversion edge. This is not a directional bet at all - the two legs cancel, and
the return does not depend on predicting anything. The risk moves from "was the
forecast right" to "does the rate persist and do both legs stay hedged".

HOW FUNDING ACCRUES. Funding is paid hourly on the PERP notional. The spot leg is
unlevered inventory and pays nothing. So:

    hourly_pnl = perp_notional x funding_rate_1h

`accrue()` takes the CURRENT rate each hour rather than extrapolating the entry
rate. That distinction is the entire risk of the strategy: an entry APR is an
instantaneous quote, and a position opened at 56% APR earns whatever the rate
actually turns out to be - which may be zero, or negative, within hours. A
harvester that projected its entry rate forward would report a fantasy.

WHAT IS STILL NOT MODELLED. Spot/perp basis drift between the legs (the hedge is
exact in notional at entry, not thereafter), liquidation of the perp leg if margin
is not shared with the spot leg, transfer frictions between spot and perp wallets,
and the borrow that would be needed to run this in reverse (which is why only
positive-funding markets are ever opened - see basis_strategy.build_position).
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from execution.sizing import matched_leg_size
from config.dynamic_config import get_dynamic_config
from execution.risk_manager import STRATEGY_BASIS_HARVEST
from config.settings import (
    BASIS_EXIT_APR_FLOOR,
    BASIS_EXIT_STALE_APR,
    BASIS_EXIT_STALE_DAYS,
    BASIS_MAX_CONCURRENT,
    BASIS_MIN_HOLD_DAYS,
    BASIS_NOTIONAL_USD,
    BASIS_PAPER_STARTING_CASH,
    BASIS_PAPER_STATE_PATH,
    MAKER_FEE_PCT,
    TAKER_FEE_PCT,
)

HOURS_PER_YEAR = 24.0 * 365.0
# Both legs, in and out: taker in, maker out, per leg. Charged as a percent of one
# leg's notional, matching basis_strategy.round_trip_fee_pct().
ROUND_TRIP_FEE_PCT = (TAKER_FEE_PCT + MAKER_FEE_PCT) * 100.0 * 2


class BasisHarvester:
    """
    Paper book for cash-and-carry positions.

    Cash accounting mirrors the perp paper trader so the two are comparable: both
    legs' notional is deducted on open, entry fees are charged immediately, and
    funding lands in cash as it accrues. Once flat, cash minus starting cash must
    equal realised PnL.
    """

    def __init__(self, starting_cash: float = BASIS_PAPER_STARTING_CASH,
                 state_path: Optional[str] = None,
                 receipts_enabled: bool = False,
                 receipts_dir: Optional[Path] = None,
                 executor: Optional[Any] = None):
        # Receipts OFF by default, same reasoning as PaperTrader: they write real
        # CSVs into the tax ledger's drop folder, and every backtest and unit test
        # would otherwise be filing fabricated fills into a live book.
        self.receipts_enabled = bool(receipts_enabled)
        self.receipts_dir = Path(receipts_dir) if receipts_dir else None
        self.executor = executor
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed: List[Dict[str, Any]] = []
        self.realized_pnl = 0.0
        self.funding_collected = 0.0
        self.fees_paid = 0.0
        self.accruals = 0
        # Round 38: why the last open_position() returned None, for the log.
        self.last_refusal: Optional[str] = None
        self.state_path = Path(state_path or BASIS_PAPER_STATE_PATH)

    # ---------------------------------------------------------------- open

    def capital_required(self, notional_per_leg: float) -> float:
        """Both legs tie up capital - the headline APR is quoted against one."""
        return notional_per_leg * 2.0

    @staticmethod
    def effective_max_positions(cfg: Optional[Any] = None) -> int:
        """The slot cap in force: the hot-reloaded config's, else the code default."""
        cfg = cfg if cfg is not None else get_dynamic_config()
        configured = getattr(cfg, "max_concurrent_positions", None)
        return int(configured) if configured else BASIS_MAX_CONCURRENT

    def holds_spot(self, spot_symbol: Optional[str]) -> Optional[str]:
        """The coin already hedged against `spot_symbol`, or None."""
        if not spot_symbol:
            return None
        for coin, pos in self.positions.items():
            if pos.get("spot_symbol") == spot_symbol:
                return coin
        return None

    def can_open(self, coin: str, notional_per_leg: Optional[float] = None,
                 spot_symbol: Optional[str] = None) -> bool:
        """
        Round 38 adds the underlying to the gate. Two perps against the SAME spot
        token (para:AVGO and xyz:AVGO, both hedged with AVGO) are two positions
        by coin and one concentration by risk: the spot leg is the same asset
        twice, and both perps' funding tends to move with the same flow. One
        position per spot symbol.
        """
        cfg = get_dynamic_config()
        if cfg.emergency_killswitch or cfg.pause_new_entries:
            return False
        effective_notional = notional_per_leg if notional_per_leg is not None else cfg.basis_notional_usd
        if coin in self.positions or len(self.positions) >= self.effective_max_positions(cfg):
            return False
        if self.holds_spot(spot_symbol) is not None:
            return False
        return self.capital_required(effective_notional) <= self.cash

    def _refuse(self, reason: str) -> None:
        self.last_refusal = reason
        return None

    def open_position(self, opportunity: Dict[str, Any],
                      notional_per_leg: Optional[float] = None,
                      min_hold_days: Optional[float] = None,
                      now: Optional[float] = None,
                      max_spread_bps: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Open a 1:1 cash-and-carry, or None if it fails a gate (`last_refusal`
        says which).

        Requires a MEASURED spread. `net_apr_after_spread` returns the gross APR
        untouched when no book was fetched, so an uncosted row would clear the net
        bar it was never tested against - the same trap basis_strategy refuses.

        Round 38: the measured spread must also sit under the configured ceiling
        (`max_spread_bps`, else the hot-reloaded config's). The scan enforces the
        same ceiling; this is the last gate before capital moves and must not
        rely on the caller having applied it. And the opportunity's spot symbol
        must not already be hedging an open position - see `can_open`.
        """
        self.last_refusal = None
        cfg = get_dynamic_config()
        if cfg.emergency_killswitch or cfg.pause_new_entries:
            return self._refuse("entries paused or kill-switch active")
        notional_per_leg = notional_per_leg if notional_per_leg is not None else cfg.basis_notional_usd
        effective_min_hold = min_hold_days if min_hold_days is not None else cfg.basis_holding_days

        coin = opportunity.get("coin")
        if not coin:
            return self._refuse("no coin")
        spot_symbol = opportunity.get("spot_symbol")
        held_by = self.holds_spot(spot_symbol)
        if held_by is not None:
            return self._refuse(f"spot {spot_symbol} already hedges {held_by}")
        if not self.can_open(coin, notional_per_leg, spot_symbol=spot_symbol):
            return self._refuse("gate: held, slots full, or insufficient cash")
        spread = opportunity.get("spread_bps")
        if spread is None:
            return self._refuse("spread unmeasured")
        ceiling = max_spread_bps if max_spread_bps is not None else cfg.max_spread_bps
        if ceiling is not None and float(spread) > float(ceiling):
            return self._refuse(f"spread {float(spread):.1f}bps > {float(ceiling):.1f}bps max")
        if float(opportunity.get("funding_apr") or 0.0) <= 0:
            return self._refuse("funding not positive")
        if float(opportunity.get("holding_days") or 0.0) < effective_min_hold:
            return self._refuse("holding period below minimum")
        mark = float(opportunity.get("mark_px") or 0.0)
        if mark <= 0:
            return self._refuse("no mark price")

        # Both legs must carry the SAME size, floored to the coarser szDecimals.
        # MON is the live case: perp is whole-units-only while spot takes 2dp, so
        # an unrounded size would be rejected by the perp and fill on spot alone -
        # a naked leg in a position whose whole premise is zero delta.
        sizing = matched_leg_size(
            notional_per_leg, mark,
            perp_decimals=opportunity.get("perp_sz_decimals"),
            spot_decimals=opportunity.get("spot_sz_decimals"),
        )
        if sizing["decimals"] is not None and not sizing["tradeable"]:
            return self._refuse("size not expressible at both legs' precision")
        if sizing["tradeable"]:
            # Deploy what the instruments can actually express, never more.
            notional_per_leg = sizing["notional_usd"]

        now = now if now is not None else time.time()
        capital = self.capital_required(notional_per_leg)
        entry_fee = TAKER_FEE_PCT * notional_per_leg * 2      # taker on both legs in

        if self.executor is not None:
            sz_val = sizing["size"] if sizing["tradeable"] else (notional_per_leg / mark)
            sz_str = f"{sz_val:.8f}"
            spot_px_str = str(opportunity.get("spot_price") or mark)
            perp_px_str = str(opportunity.get("perp_price") or mark)
            try:
                exec_result = self.executor.execute_basis_pair(
                    coin=coin, sz=sz_str, spot_px=spot_px_str, perp_px=perp_px_str
                )
                if exec_result.get("aborted"):
                    return self._refuse("executor aborted the pair")
            except Exception as exc:
                return self._refuse(f"executor failed: {type(exc).__name__}")

        self.cash -= capital + entry_fee
        self.fees_paid += entry_fee
        # Book the entry fee as realised immediately. It is spent the moment the
        # legs are opened, and leaving it out is what breaks the flat-state
        # invariant (cash - starting == realised_pnl) at close.
        self.realized_pnl -= entry_fee

        pos = {
            "coin": coin,
            "spot_symbol": opportunity.get("spot_symbol"),
            "structure": "LONG_SPOT_SHORT_PERP",
            "entry_mark": mark,
            "size": sizing["size"] if sizing["tradeable"] else notional_per_leg / mark,
            "sz_decimals": sizing["decimals"],
            "size_residual": sizing["residual"],
            "notional_per_leg": notional_per_leg,
            "capital": capital,
            "entry_funding_apr": float(opportunity.get("funding_apr") or 0.0),
            "entry_net_apr": float(opportunity.get("net_apr")
                                   or opportunity.get("funding_apr") or 0.0),
            "spread_bps": opportunity.get("spread_bps"),
            "entry_fee": entry_fee,
            "funding_accrued": 0.0,
            "hours_held": 0.0,
            "accruals": 0,
            "opened_at": now,
        }
        self.positions[coin] = pos
        return pos

    # ---------------------------------------------------------------- accrue

    def accrue(self, funding_rates_1h: Dict[str, float],
               hours: float = 1.0, now: Optional[float] = None) -> Dict[str, float]:
        """
        Credit one funding period using the CURRENT rate, not the entry rate.

        A market with no current rate accrues NOTHING rather than repeating its
        last known value: a stale rate carried forward would manufacture yield
        during exactly the outage where we can least justify claiming it.
        """
        now = now if now is not None else time.time()
        credited: Dict[str, float] = {}
        for coin, pos in self.positions.items():
            rate = funding_rates_1h.get(coin)
            if rate is None:
                continue
            # Positive funding pays the short. The perp leg is short, so a positive
            # rate is income and a negative rate is a cost we genuinely bear.
            pnl = pos["notional_per_leg"] * float(rate) * hours
            pos["funding_accrued"] += pnl
            pos["hours_held"] += hours
            pos["accruals"] += 1
            self.cash += pnl
            self.funding_collected += pnl
            self.realized_pnl += pnl
            credited[coin] = pnl
            if self.receipts_enabled and abs(pnl) >= 1e-9:
                self._emit_funding_receipt(coin, pnl, float(rate), hours, now)
        if credited:
            self.accruals += 1
        return credited

    def _emit_funding_receipt(self, coin: str, pnl: float, rate: float,
                              hours: float, now: float) -> Optional[Any]:
        """
        IRC §61: Funding is ordinary income (or expense if negative),
        not a capital asset sale. Emits an INCOME receipt to Tax Reserve Agent.
        """
        if not self.receipts_enabled or abs(pnl) < 1e-9:
            return None
        try:
            from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt
        except Exception as exc:
            print(f"[WARN] Receipts unavailable ({type(exc).__name__}: {exc}); funding unattributed.")
            return None

        dt_str = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
        side = "INCOME" if pnl >= 0 else "EXPENSE"
        return log_execution_receipt(
            symbol=f"{coin}-FUNDING",
            side=side,
            quantity=abs(pnl),
            price=1.0,
            strategy=STRATEGY_BASIS_HARVEST,
            venue="hyperliquid",
            timestamp=dt_str,
            imports_dir=self.receipts_dir,
            extra_notes=f"funding_rate_1h={rate:g}; hours={hours:g}; pnl={pnl:g}"
        )

    def should_exit(self, coin: str, current_apr: Optional[float],
                    floor_apr: float = BASIS_EXIT_APR_FLOOR,
                    stale_days: float = BASIS_EXIT_STALE_DAYS,
                    stale_apr: float = BASIS_EXIT_STALE_APR) -> Optional[str]:
        """
        Why this position should close, or None to hold.

        Holds through yield DECAY and exits only on yield REVERSAL. Measured on
        live funding history, exiting early destroys value: a 6h hold nets
        -0.0612% after the 0.0900% round trip and is profitable only 16% of the
        time, while a 48h hold nets +0.1185% and is profitable 78% of the time.
        A boring position still pays; an exit always costs.

        An unknown rate is NOT an exit signal - a data gap is not a reversal.

        ROUND 31 ADDS THE SECOND EXIT, AND ONLY THE SECOND. Reversal alone left a
        position earning 2% APR held indefinitely: never a loss, so nothing ever
        fired, and the capital sat there. The stale leg closes it once the hold
        has run long enough to have paid its own round trip AND the rate has
        fallen well below the entry bar.

        THE TWO THRESHOLDS ARE DELIBERATELY NOT THE ENTRY BAR. Exiting the moment
        funding dips under the 20% entry threshold would make the strategy thrash
        - a rate oscillating around 20% reopens the same position repeatedly and
        pays the full round trip each time to buy back what it just sold. Entry
        at 20%, exit at 10%-after-7-days, is hysteresis, not inconsistency.
        """
        if coin not in self.positions:
            return None
        if current_apr is None:
            return None
        if current_apr < floor_apr:
            return f"funding turned adverse ({current_apr:.1f}% < {floor_apr:.1f}%)"
        position = self.positions[coin]
        held_days = float(position.get("hours_held", 0.0) or 0.0) / 24.0
        if held_days >= stale_days and current_apr < stale_apr:
            return (f"stale: held {held_days:.1f}d at {current_apr:.1f}% "
                    f"(< {stale_apr:.1f}% after {stale_days:.0f}d)")
        return None

    def sweep_exits(self, funding_aprs: Dict[str, float],
                    floor_apr: float = BASIS_EXIT_APR_FLOOR,
                    stale_days: float = BASIS_EXIT_STALE_DAYS,
                    stale_apr: float = BASIS_EXIT_STALE_APR) -> List[Dict[str, Any]]:
        """Close every position that has reversed or gone stale."""
        out = []
        for coin in list(self.positions):
            reason = self.should_exit(coin, funding_aprs.get(coin), floor_apr,
                                      stale_days, stale_apr)
            if reason:
                closed = self.close_position(coin, reason=reason)
                if closed:
                    out.append(closed)
        return out

    # ---------------------------------------------------------------- close

    def close_position(self, coin: str, now: Optional[float] = None,
                       reason: str = "MANUAL") -> Optional[Dict[str, Any]]:
        pos = self.positions.pop(coin, None)
        if pos is None:
            return None
        now = now if now is not None else time.time()
        exit_fee = MAKER_FEE_PCT * pos["notional_per_leg"] * 2   # maker on both legs out

        if self.executor is not None:
            sz_str = f"{pos['size']:.8f}"
            mark_str = str(pos.get("entry_mark", 0.0))
            try:
                self.executor.close_basis_pair(
                    coin=coin, sz=sz_str, spot_px=mark_str, perp_px=mark_str
                )
            except Exception:
                pass

        self.cash += pos["capital"] - exit_fee
        self.fees_paid += exit_fee
        self.realized_pnl -= exit_fee

        closed = {
            **pos,
            "exit_fee": exit_fee,
            "closed_at": now,
            "exit_reason": reason,
            "net_pnl": pos["funding_accrued"] - pos["entry_fee"] - exit_fee,
            "realised_apr": (
                pos["funding_accrued"] / pos["notional_per_leg"]
                * (HOURS_PER_YEAR / pos["hours_held"]) * 100.0
                if pos["hours_held"] > 0 else None
            ),
        }
        self.closed.append(closed)
        self._emit_receipts(closed, opening=False, reason=reason)
        return closed

    def _emit_receipts(self, position: Dict[str, Any], opening: bool,
                       reason: Optional[str] = None) -> List[Any]:
        """
        Writes receipts for a basis position's TWO LEGS.

        THE BRIEF ONLY ASKED FOR paper_trader, BUT THIS BOOK NEVER GOES THROUGH
        IT. `BasisHarvester` keeps its own cash and positions, so hooking the
        paper trader alone would have instrumented the RETIRED liquidation fade
        and missed the delta-neutral strategy that is actually live.

        A basis position is long spot and short perp at the same notional. Both
        legs are written, because the ledger needs both to compute a cost basis -
        booking only one would leave a permanently open phantom position.

        FUNDING IS DELIBERATELY NOT BOOKED HERE. Funding accrual is periodic
        income, not a capital gain, and the tax ledger models capital gains only.
        Pushing it through the FIFO engine would misclassify ordinary income as
        price appreciation - wrong in a way that is invisible on the HUD and wrong
        on a filing. It is recorded in the receipt's notes as a memo so the number
        is not lost, and it needs separate treatment before any real filing.
        """
        if not getattr(self, "receipts_enabled", False):
            return []
        try:
            from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt
        except Exception as e:
            print(f"[WARN] Basis receipts unavailable ({type(e).__name__}: {e}).")
            return []

        coin = position.get("coin", "?")
        notional = float(position.get("notional_per_leg") or 0.0)
        spot_px = float(position.get("spot_price") or position.get("entry_spot") or 0.0)
        perp_px = float(position.get("perp_price") or position.get("entry_perp") or spot_px)
        if notional <= 0 or spot_px <= 0:
            return []

        funding = float(position.get("funding_accrued") or 0.0)
        memo = (f"basis leg; funding_accrued={funding:.6f} NOT booked as capital "
                f"(ordinary income)")
        written = []
        legs = [(f"{coin}-SPOT", "BUY" if opening else "SELL", spot_px),
                (f"{coin}-PERP", "SELL" if opening else "BUY", perp_px)]
        for symbol, side, price in legs:
            if price <= 0:
                continue
            path = log_execution_receipt(
                symbol=symbol, side=side, quantity=notional / price, price=price,
                strategy=STRATEGY_BASIS_HARVEST, venue="hyperliquid",
                fee=float(position.get("exit_fee" if not opening else "entry_fee") or 0.0) / 2.0,
                exit_reason=reason, imports_dir=getattr(self, "receipts_dir", None),
                extra_notes=memo)
            if path:
                written.append(path)
        return written

    # ---------------------------------------------------------------- report

    def summary(self) -> Dict[str, Any]:
        open_funding = sum(p["funding_accrued"] for p in self.positions.values())
        return {
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "equity": self.cash + sum(p["capital"] for p in self.positions.values()),
            "open_positions": len(self.positions),
            "closed_positions": len(self.closed),
            "deployed_capital": sum(p["capital"] for p in self.positions.values()),
            "funding_collected": self.funding_collected,
            "fees_paid": self.fees_paid,
            "realized_pnl": self.realized_pnl,
            "unrealized_funding": open_funding,
            "accrual_cycles": self.accruals,
        }

    # ---------------------------------------------------------------- persist

    def to_dict(self) -> Dict[str, Any]:
        return {
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "positions": self.positions,
            "closed": self.closed[-200:],
            "realized_pnl": self.realized_pnl,
            "funding_collected": self.funding_collected,
            "fees_paid": self.fees_paid,
            "accruals": self.accruals,
            "saved_at": time.time(),
        }

    def save(self) -> None:
        """Atomic: a crash mid-write must not leave a truncated book."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    def load(self) -> bool:
        if not self.state_path.exists():
            return False
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        self.starting_cash = d.get("starting_cash", self.starting_cash)
        self.cash = d.get("cash", self.starting_cash)
        self.positions = d.get("positions", {})
        self.closed = d.get("closed", [])
        self.realized_pnl = d.get("realized_pnl", 0.0)
        self.funding_collected = d.get("funding_collected", 0.0)
        self.fees_paid = d.get("fees_paid", 0.0)
        self.accruals = d.get("accruals", 0)
        return True


def format_report(h: BasisHarvester) -> str:
    s = h.summary()
    lines = [
        "",
        "DELTA-NEUTRAL BASIS HARVESTER (paper)",
        f"  Equity ${s['equity']:,.2f}   cash ${s['cash']:,.2f}   "
        f"deployed ${s['deployed_capital']:,.2f}",
        f"  Funding collected ${s['funding_collected']:,.2f}   "
        f"fees ${s['fees_paid']:,.2f}   net ${s['realized_pnl']:,.2f}",
        f"  Open {s['open_positions']}/{h.effective_max_positions()}   "
        f"closed {s['closed_positions']}   accrual cycles {s['accrual_cycles']}",
        "",
    ]
    if h.positions:
        lines.append(f"  {'COIN':<12}{'SPOT':<10}{'entry APR':>11}{'held':>8}"
                     f"{'funding':>11}{'realised APR':>14}")
        for p in h.positions.values():
            realised = (p["funding_accrued"] / p["notional_per_leg"]
                        * (HOURS_PER_YEAR / p["hours_held"]) * 100.0
                        if p["hours_held"] > 0 else None)
            lines.append(
                f"  {p['coin']:<12}{str(p['spot_symbol'] or '-'):<10}"
                f"{p['entry_funding_apr']:>10.1f}%{p['hours_held']:>7.0f}h"
                f"{p['funding_accrued']:>11,.2f}"
                f"{(f'{realised:.1f}%' if realised is not None else 'n/a'):>14}"
            )
        lines.append("")
        lines.append("  [realised APR is what the rate ACTUALLY paid; entry APR was only a quote]")
    else:
        lines.append("  No open positions.")
    lines.append("")
    return "\n".join(lines)
