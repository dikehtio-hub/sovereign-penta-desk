"""
Paper Trading Simulation Engine for HL_Monarch.
Simulates wallet balance, margin management, order execution (Market, Limit, Stop-Loss),
and real-time PnL tracking without risking real capital.
"""
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import (
    FADE_ORDER_TTL_SECONDS,
    PAPER_STATE_PATH,
    MAKER_FEE_PCT,
    HURDLE_MIN_TRADES,
    HURDLE_PASS_WIN_RATE,
    HURDLE_PASS_PROFIT_FACTOR,
    HURDLE_RETUNE_WIN_RATE,
)

logger = logging.getLogger("PaperTrader")

class PaperTrader:
    def __init__(self, initial_balance_usd: float = 100_000.0,
                 receipts_enabled: bool = False,
                 receipts_dir: Optional[Path] = None,
                 default_strategy: Optional[str] = None):
        """
        `receipts_enabled` is OFF by default, and deliberately so.

        A receipt is a real CSV written into the Tax Agent's shared drop folder,
        where a watcher will ingest it into the tax ledger. Emitting them from
        every PaperTrader would mean 561 unit tests, every backtest and every
        research run writing fabricated fills into a book that Q1 reads as truth.
        Attribution has to be opt-in at the point something is actually trading.
        """
        self.initial_balance = initial_balance_usd
        self.cash_balance = initial_balance_usd
        self.receipts_enabled = bool(receipts_enabled)
        self.receipts_dir = Path(receipts_dir) if receipts_dir else None
        self.default_strategy = default_strategy
        self.receipts_written: List[Path] = []
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.open_orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        # Realised PnL is tracked explicitly rather than inferred from
        # cash_balance - the two diverge as soon as the starting balance is
        # configurable, and "how much has this strategy actually made" is the
        # number anyone reading a paper account actually wants.
        self.realized_pnl = 0.0
        self.closed_trades = 0
        self.expired_orders = 0
        # Fee accounting. Kept separate from PnL so the gross edge and the cost of
        # capturing it can be read independently - a strategy that is profitable
        # gross and unprofitable net is a different problem from one that is
        # simply wrong.
        self.fees_paid = 0.0
        self.wins = 0
        self.losses = 0
        self.gross_profit = 0.0    # sum of winning trades, net of their fees
        self.gross_loss = 0.0      # absolute sum of losing trades, net of their fees

    def get_account_summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Compute current equity, margin utilization, and unrealized PnL."""
        current_prices = current_prices or {}
        total_unrealized_pnl = 0.0
        total_margin_used = 0.0

        for coin, pos in self.positions.items():
            mark = current_prices.get(coin, pos["entry_price"])
            size = pos["size"]
            entry = pos["entry_price"]
            lev = pos["leverage"]

            if size > 0:  # Long
                pnl = (mark - entry) * size
            else:         # Short
                pnl = (entry - mark) * abs(size)

            margin = (abs(size) * entry) / lev
            total_unrealized_pnl += pnl
            total_margin_used += margin

        equity = self.cash_balance + total_unrealized_pnl
        margin_free = max(0.0, equity - total_margin_used)

        return {
            "cash_balance": self.cash_balance,
            "equity": equity,
            "total_unrealized_pnl": total_unrealized_pnl,
            "margin_used": total_margin_used,
            "margin_free": margin_free,
            "open_positions_count": len(self.positions),
            "open_orders_count": len(self.open_orders),
            "realized_pnl": self.realized_pnl,
            "closed_trades": self.closed_trades,
            "expired_orders": self.expired_orders,
            "fees_paid": self.fees_paid,
            "gross_pnl": self.realized_pnl + self.fees_paid,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate_pct": self.win_rate_pct(),
            "profit_factor": self.profit_factor(),
            "hurdle": self.hurdle_verdict(),
            "return_pct": (
                (equity - self.initial_balance) / self.initial_balance * 100.0
                if self.initial_balance else 0.0
            ),
        }

    def place_limit_order(
        self,
        coin: str,
        side: str,
        size: float,
        limit_price: float,
        leverage: int = 10,
        stop_loss_px: Optional[float] = None,
        take_profit_px: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Rest a limit order. It sits in `open_orders` until price crosses it.

        A mean-reversion fade wants to be *paid* to take the other side of a
        cascade, not to cross the spread into it - so the strategy rests an order
        deeper into the move and lets the cascade come to it. An order that never
        fills is the correct outcome when the move does not overshoot.
        """
        if limit_price <= 0 or size <= 0:
            return {"status": "REJECTED", "reason": "Invalid price or size"}

        order = {
            "order_id": f"paper-lim-{uuid.uuid4().hex[:8]}",
            "coin": coin,
            "side": "BUY" if side.upper() in ("B", "BUY") else "SELL",
            "size": size,
            "limit_price": limit_price,
            "leverage": leverage,
            "stop_loss": stop_loss_px,
            "take_profit": take_profit_px,
            "placed_at": int(time.time() * 1000),
            "status": "OPEN",
        }
        self.open_orders.append(order)
        return order

    def expire_stale_orders(self, ttl_seconds: float = FADE_ORDER_TTL_SECONDS,
                            now_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Cancel resting orders older than `ttl_seconds`.

        A fade is a bet on *this* cascade mean-reverting. Left resting, an order
        placed during a cascade hours ago will eventually fill on unrelated price
        action and book a position the strategy never intended - which silently
        flatters the paper PnL with trades it did not really take.
        """
        if not self.open_orders or ttl_seconds is None or ttl_seconds <= 0:
            return []
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        cutoff = now_ms - int(ttl_seconds * 1000)

        expired, live = [], []
        for order in self.open_orders:
            if order.get("placed_at", 0) < cutoff:
                order["status"] = "EXPIRED"
                order["expired_at"] = now_ms
                self.expired_orders += 1
                expired.append(order)
            else:
                live.append(order)
        self.open_orders = live
        return expired

    def check_open_orders(self, current_prices: Dict[str, float],
                          ttl_seconds: float = FADE_ORDER_TTL_SECONDS,
                          now_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Expire stale orders, then fill any whose limit price has been crossed.

        Expiry runs FIRST: an order that has outlived its thesis must not be
        allowed to fill on the same tick that retires it.

        A buy fills when the mark trades at or below its limit; a sell fills at or
        above. Fills execute at the limit price, not the mark: a resting order does
        not get price improvement it never asked for, and assuming it would is how
        a paper backtest flatters itself.
        """
        self.expire_stale_orders(ttl_seconds, now_ms=now_ms)
        if not self.open_orders:
            return []

        filled = []
        still_open = []
        for order in self.open_orders:
            mark = current_prices.get(order["coin"])
            if mark is None or mark <= 0:
                still_open.append(order)
                continue

            crossed = (
                (order["side"] == "BUY" and mark <= order["limit_price"])
                or (order["side"] == "SELL" and mark >= order["limit_price"])
            )
            if not crossed:
                still_open.append(order)
                continue

            result = self.place_market_order(
                coin=order["coin"],
                side=order["side"],
                size=order["size"],
                current_price=order["limit_price"],
                leverage=order["leverage"],
                stop_loss_px=order.get("stop_loss"),
                take_profit_px=order.get("take_profit"),
                fee_pct=MAKER_FEE_PCT,   # a resting limit is always maker
            )
            if result.get("status") == "FILLED":
                order["status"] = "FILLED"
                order["filled_at"] = result["timestamp"]
                filled.append(order)
            else:
                # Rejected (usually insufficient margin): leave it resting.
                still_open.append(order)

        self.open_orders = still_open
        return filled

    def cancel_orders(self, coin: Optional[str] = None) -> int:
        """Cancel resting orders, optionally only for one coin."""
        before = len(self.open_orders)
        if coin is None:
            self.open_orders = []
        else:
            self.open_orders = [o for o in self.open_orders if o["coin"] != coin]
        return before - len(self.open_orders)

    def place_market_order(
        self,
        coin: str,
        side: str,           # 'B' (Buy) or 'A' (Sell)
        size: float,
        current_price: float,
        leverage: int = 10,
        stop_loss_px: Optional[float] = None,
        take_profit_px: Optional[float] = None,
        fee_pct: float = 0.0,
        strategy: Optional[str] = None,
        exit_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute instant paper market order at current mark price.

        `strategy` and `exit_reason` are carried only for attribution - they do
        not affect execution. `exit_reason` distinguishes a TAKE_PROFIT from a
        STOP_LOSS or TIME_STOP in the receipt, which is what lets per-strategy
        performance be read back out of the ledger later.
        """
        if current_price <= 0 or size <= 0:
            return {"status": "REJECTED", "reason": "Invalid price or size"}

        notional = size * current_price
        margin_required = notional / leverage

        summary = self.get_account_summary({coin: current_price})
        if summary["margin_free"] < margin_required:
            return {"status": "REJECTED", "reason": f"Insufficient margin (Required: ${margin_required:,.2f}, Available: ${summary['margin_free']:,.2f})"}

        order_id = f"paper-{uuid.uuid4().hex[:8]}"
        is_buy = (side.upper() == "B" or side.upper() == "BUY")
        signed_size = size if is_buy else -size

        # Update existing position or create new
        if coin in self.positions:
            existing = self.positions[coin]
            old_size = existing["size"]
            new_size = old_size + signed_size
            
            if new_size == 0:
                # Closed position. Net of BOTH legs' fees: the entry fee was paid
                # out of cash when the position opened, and attributing it to the
                # trade here is what makes realized_pnl the true net result.
                pnl = (current_price - existing["entry_price"]) * old_size if old_size > 0 else (existing["entry_price"] - current_price) * abs(old_size)
                exit_fee = notional * float(fee_pct)
                entry_fee = float(existing.get("entry_fee") or 0.0)
                net = pnl - exit_fee - entry_fee

                self.cash_balance += pnl
                self.realized_pnl += net
                self.closed_trades += 1
                if net >= 0:
                    self.wins += 1
                    self.gross_profit += net
                else:
                    self.losses += 1
                    self.gross_loss += abs(net)
                del self.positions[coin]
            elif (old_size > 0 and new_size > 0) or (old_size < 0 and new_size < 0):
                # Increased position
                total_cost = (abs(old_size) * existing["entry_price"]) + (size * current_price)
                avg_entry = total_cost / abs(new_size)
                existing["size"] = new_size
                existing["entry_price"] = avg_entry
            else:
                # Flipped position
                pnl = (current_price - existing["entry_price"]) * old_size if old_size > 0 else (existing["entry_price"] - current_price) * abs(old_size)
                self.cash_balance += pnl
                self.realized_pnl += pnl
                self.closed_trades += 1
                self.positions[coin] = {
                    "coin": coin,
                    "size": new_size,
                    "entry_price": current_price,
                    "leverage": leverage,
                    "stop_loss": stop_loss_px,
                    "take_profit": take_profit_px,
                    "opened_at": time.time()
                }
        else:
            self.positions[coin] = {
                "coin": coin,
                "size": signed_size,
                "entry_price": current_price,
                "leverage": leverage,
                "stop_loss": stop_loss_px,
                "take_profit": take_profit_px,
                "opened_at": time.time(),
                "entry_fee": None,   # filled in below, once the fee is computed
            }

        # Charge the fee on every fill, whichever side of the book it took.
        fee = notional * float(fee_pct)
        if fee:
            self.cash_balance -= fee
            self.fees_paid += fee
            if coin in self.positions and self.positions[coin].get("entry_fee") is None:
                self.positions[coin]["entry_fee"] = fee

        fill_record = {
            "order_id": order_id,
            "fee": fee,
            "timestamp": int(time.time() * 1000),
            "coin": coin,
            "side": "BUY" if is_buy else "SELL",
            "size": size,
            "price": current_price,
            "notional": notional,
            "leverage": leverage,
            "status": "FILLED"
        }
        self.trade_history.append(fill_record)
        self._emit_receipt(fill_record, strategy=strategy, exit_reason=exit_reason)
        return fill_record

    def _emit_receipt(self, fill: Dict[str, Any], strategy: Optional[str] = None,
                      exit_reason: Optional[str] = None) -> Optional[Path]:
        """
        Writes one fill to the Tax Agent drop folder, if receipts are enabled.

        EVERY fill gets its own receipt - entries and exits alike - because the
        ledger runs its own FIFO lot matching. Trying to net an entry against an
        exit here would duplicate that logic in a second place and get it wrong;
        the ledger only needs to be told what happened.

        Never raises: a bookkeeping failure must not break an execution path.
        """
        if not self.receipts_enabled:
            return None
        name = strategy or self.default_strategy
        if not name:
            print("[WARN] Receipts are enabled but this fill has no strategy; it would "
                  "reach the ledger unattributed, so it was NOT written.")
            return None
        try:
            from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt
        except Exception as e:
            print(f"[WARN] Tax Reserve Agent receipts unavailable ({type(e).__name__}: {e}); "
                  f"this fill will not be attributed.")
            return None

        path = log_execution_receipt(
            symbol=fill["coin"], side=fill["side"], quantity=fill["size"],
            price=fill["price"], strategy=name, venue="hyperliquid",
            fee=fill.get("fee", 0.0), exit_reason=exit_reason,
            tx_hash=fill.get("order_id"), imports_dir=self.receipts_dir,
            extra_notes=f"perp {fill.get('leverage', 1)}x")
        if path:
            self.receipts_written.append(path)
        return path

    # --- performance ---------------------------------------------------------

    def win_rate_pct(self) -> float:
        total = self.wins + self.losses
        return (self.wins / total * 100.0) if total else 0.0

    def profit_factor(self) -> Optional[float]:
        """
        Gross profit / gross loss, both net of fees.

        None when nothing has lost yet - an undefined ratio is honest, where
        reporting infinity would read as a spectacular result off two trades.
        """
        if self.gross_loss <= 0:
            return None
        return self.gross_profit / self.gross_loss

    def hurdle_verdict(self) -> Dict[str, Any]:
        """
        Apply the pre-registered 50-trade hurdle. No discretion.

        Agreed 2026-08-31 before any trade closed:
          PASS   : win rate >= 54.0% AND profit factor >= 1.25 (net of fees)
          RETUNE : 48.0% <= win rate < 54.0%
          FAIL   : win rate < 48.0%
        """
        total = self.wins + self.losses
        wr = self.win_rate_pct()
        pf = self.profit_factor()

        if total < HURDLE_MIN_TRADES:
            verdict = "PENDING"
        elif wr >= HURDLE_PASS_WIN_RATE:
            # A high win rate with a poor payoff ratio is not a pass; the matrix
            # requires both, and the gap is reported rather than resolved.
            verdict = "PASS" if (pf is not None and pf >= HURDLE_PASS_PROFIT_FACTOR) else "INCONCLUSIVE"
        elif wr >= HURDLE_RETUNE_WIN_RATE:
            verdict = "RETUNE"
        else:
            verdict = "FAIL"

        return {
            "verdict": verdict,
            "closed_trades": total,
            "trades_required": HURDLE_MIN_TRADES,
            "win_rate_pct": round(wr, 2),
            "profit_factor": round(pf, 3) if pf is not None else None,
        }

    # --- persistence ---------------------------------------------------------
    #
    # The paper account is written by the collector (which reacts to live
    # liquidations) and read by `main.py paper`, which is a different process.
    # Without persistence the CLI constructs an empty trader every invocation and
    # always reports a flat account, no matter what the strategy did.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_balance": self.initial_balance,
            "cash_balance": self.cash_balance,
            "realized_pnl": self.realized_pnl,
            "closed_trades": self.closed_trades,
            "expired_orders": self.expired_orders,
            "fees_paid": self.fees_paid,
            "wins": self.wins,
            "losses": self.losses,
            # The raw running totals, not the derived ratios: win rate, profit
            # factor and the hurdle verdict are all recomputed on load, so a
            # stored copy could only ever go stale against them.
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "positions": self.positions,
            "open_orders": self.open_orders,
            # Bounded: this file is rewritten on every flush, and unbounded
            # history would make each write slower than the last.
            "trade_history": self.trade_history[-200:],
            "saved_at": int(time.time() * 1000),
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        self.initial_balance = float(data.get("initial_balance", self.initial_balance))
        self.cash_balance = float(data.get("cash_balance", self.cash_balance))
        self.realized_pnl = float(data.get("realized_pnl", 0.0))
        self.closed_trades = int(data.get("closed_trades", 0))
        self.expired_orders = int(data.get("expired_orders", 0))
        self.fees_paid = float(data.get("fees_paid", 0.0))
        self.wins = int(data.get("wins", 0))
        self.losses = int(data.get("losses", 0))
        self.gross_profit = float(data.get("gross_profit", 0.0))
        self.gross_loss = float(data.get("gross_loss", 0.0))
        self.positions = dict(data.get("positions") or {})
        self.open_orders = list(data.get("open_orders") or [])
        self.trade_history = list(data.get("trade_history") or [])

    def save(self, path: Optional[Path] = None) -> Path:
        """Write state atomically, so a crash mid-write cannot corrupt the file."""
        target = Path(path or PAPER_STATE_PATH)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(target)
        return target

    @classmethod
    def load(cls, path: Optional[Path] = None,
             initial_balance_usd: float = 100_000.0) -> "PaperTrader":
        """
        Restore a saved account, or start a fresh one.

        A missing or unreadable file yields a clean account rather than an error:
        this is a simulator, and refusing to start because the state file is
        corrupt would be worse than beginning again.
        """
        trader = cls(initial_balance_usd=initial_balance_usd)
        target = Path(path or PAPER_STATE_PATH)
        if not target.exists():
            return trader
        try:
            trader.load_dict(json.loads(target.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"Could not read paper state at {target}: {e}")
        return trader
