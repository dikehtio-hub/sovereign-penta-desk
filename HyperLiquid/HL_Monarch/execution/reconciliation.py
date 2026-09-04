"""
================================================================================
HL Monarch: Resting Order Reconciliation Engine
================================================================================
Tracks open resting orders and reconciles their lifecycle state against Hyperliquid
exchange responses. When a resting limit order executes asynchronously on L1,
the reconciler detects the fill and writes the strategy-attributed receipt to
`Tax_Reserve_Agent/data/imports/`.
================================================================================
"""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from execution.order_executor import ExecutionResult


@dataclass
class TrackedOrder:
    """An order placed on exchange whose lifecycle is being monitored."""
    cloid: str
    coin: str
    side: str
    requested_sz: float
    limit_px: float
    strategy: str
    oid: Optional[int] = None
    filled_sz: float = 0.0
    fee: float = 0.0
    status: str = "RESTING"  # RESTING, FILLED, PARTIAL, CANCELED, UNKNOWN
    created_at: float = field(default_factory=time.time)
    receipt_path: Optional[str] = None

    @property
    def unfilled_sz(self) -> float:
        return max(0.0, self.requested_sz - self.filled_sz)


class OrderReconciler:
    """
    Monitors resting limit orders and closes the loop between exchange fills
    and the tax reserve ledger.
    """

    def __init__(self,
                 rest_client: Any = None,
                 receipts_enabled: bool = True,
                 receipts_dir: Optional[Path] = None):
        self.rest_client = rest_client
        self.receipts_enabled = bool(receipts_enabled)
        self.receipts_dir = Path(receipts_dir) if receipts_dir else None
        self._orders_by_cloid: Dict[str, TrackedOrder] = {}
        self._orders_by_oid: Dict[int, TrackedOrder] = {}

    def track(self, order: Any) -> TrackedOrder:
        """Register an order for reconciliation."""
        if isinstance(order, ExecutionResult):
            tracked = TrackedOrder(
                cloid=order.cloid,
                oid=order.oid,
                coin=order.coin,
                side=order.side,
                requested_sz=order.requested_sz,
                limit_px=order.avg_price,
                strategy=order.strategy,
                filled_sz=order.filled_sz,
                fee=order.fee,
                status="FILLED" if order.status == "FILLED" else "RESTING"
            )
        elif isinstance(order, TrackedOrder):
            tracked = order
        elif isinstance(order, dict):
            tracked = TrackedOrder(
                cloid=order.get("cloid", ""),
                oid=order.get("oid"),
                coin=order.get("coin", ""),
                side=order.get("side", ""),
                requested_sz=float(order.get("requested_sz", 0.0)),
                limit_px=float(order.get("limit_px", 0.0)),
                strategy=order.get("strategy", ""),
                filled_sz=float(order.get("filled_sz", 0.0)),
                fee=float(order.get("fee", 0.0)),
                status=order.get("status", "RESTING")
            )
        else:
            raise TypeError(f"Cannot track object of type {type(order).__name__}")

        if tracked.cloid:
            self._orders_by_cloid[tracked.cloid] = tracked
        if tracked.oid is not None:
            self._orders_by_oid[tracked.oid] = tracked
        return tracked

    def get_order(self, cloid: Optional[str] = None, oid: Optional[int] = None) -> Optional[TrackedOrder]:
        if cloid and cloid in self._orders_by_cloid:
            return self._orders_by_cloid[cloid]
        if oid is not None and oid in self._orders_by_oid:
            return self._orders_by_oid[oid]
        return None

    @property
    def resting_orders(self) -> List[TrackedOrder]:
        return [o for o in self._orders_by_cloid.values() if o.status in ("RESTING", "PARTIAL")]

    def _write_receipt(self, order: TrackedOrder) -> Optional[str]:
        if not self.receipts_enabled or order.filled_sz <= 0:
            return None
        try:
            from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt
        except Exception as exc:
            print(f"[WARN] Receipts unavailable ({type(exc).__name__}: {exc}); fill unattributed.")
            return None

        path = log_execution_receipt(
            symbol=order.coin,
            side=order.side,
            quantity=order.filled_sz,
            price=order.limit_px,
            strategy=order.strategy,
            venue="hyperliquid",
            fee=order.fee,
            tx_hash=str(order.oid or order.cloid),
            imports_dir=self.receipts_dir,
            extra_notes=f"cloid={order.cloid}; reconciled_fill={order.filled_sz:g}"
        )
        return str(path) if path else None

    @staticmethod
    def _filled_size(order: "TrackedOrder", order_data: Dict[str, Any],
                     default: Optional[float] = None) -> float:
        """
        What ACTUALLY filled, from the exchange's own numbers.

        Hyperliquid reports `sz` as the size still resting and `origSz` as the
        size originally submitted, so the fill is the difference. This previously
        booked `requested_sz` on any "filled" status, which over-states a partial
        fill - and a receipt is a tax record, so an over-stated size puts
        inventory in the ledger that the account does not hold and every
        downstream number (cost basis, open exposure, the bucket ceiling) is
        wrong in the same direction.

        Falls back to `default` (or the requested size) only when the exchange
        did not give us the numbers to do better.
        """
        try:
            orig = order_data.get("origSz")
            remaining = order_data.get("sz")
            if orig is not None and remaining is not None:
                filled = float(orig) - float(remaining)
                if filled >= 0:
                    return filled
            if order_data.get("filledSz") is not None:
                return float(order_data["filledSz"])
        except (TypeError, ValueError):
            pass
        return order.requested_sz if default is None else default

    # PARTIAL is deliberately absent: it means an order that is STILL RESTING and
    # has filled part of the way, which is exactly the order worth keeping. It was
    # listed here once, which contradicted `prune`'s own docstring and would have
    # evicted a live order after an hour.
    TERMINAL_STATUSES = ("FILLED", "CANCELED", "REJECTED", "UNKNOWN")

    def prune(self, max_age_seconds: float = 3600.0) -> int:
        """
        Drops settled orders older than `max_age_seconds`. Returns how many went.

        Without this the tracking dicts only ever grew: a supervised process
        placing orders continuously for weeks accumulated every order it had ever
        made, all of them terminal, none of them ever released. Resting and
        partial orders are NEVER pruned regardless of age - an unsettled order is
        exactly the one worth remembering.
        """
        cutoff = time.time() - max_age_seconds
        doomed = [cloid for cloid, order in self._orders_by_cloid.items()
                  if order.status in self.TERMINAL_STATUSES and order.created_at < cutoff]
        for cloid in doomed:
            order = self._orders_by_cloid.pop(cloid, None)
            if order is not None and order.oid is not None:
                self._orders_by_oid.pop(order.oid, None)
        return len(doomed)

    @property
    def tracked_count(self) -> int:
        return len(self._orders_by_cloid)

    def reconcile_once(self, user_address: str) -> Dict[str, Any]:
        """
        Polls exchange state once, matches resting orders, and emits receipts
        for newly filled orders.
        """
        if self.rest_client is None:
            return {"status": "NO_CLIENT", "checked": 0, "filled": 0, "canceled": 0}

        try:
            open_orders_raw = self.rest_client.get_open_orders(user_address) or []
        except Exception as exc:
            return {"status": "ERROR", "reason": f"get_open_orders failed: {exc}", "checked": 0}

        open_oids = set()
        for ro in open_orders_raw:
            oid = ro.get("oid")
            if oid is not None:
                open_oids.add(int(oid))

        newly_filled = 0
        newly_canceled = 0
        checked = 0

        for order in self.resting_orders:
            checked += 1
            if order.oid is None:
                continue

            if order.oid in open_oids:
                # Still resting on exchange
                continue

            # No longer in openOrders: query orderStatus
            try:
                status_raw = self.rest_client.get_order_status(user_address, order.oid) or {}
            except Exception as exc:
                print(f"[WARN] Failed to query orderStatus for oid {order.oid}: {exc}")
                continue

            order_data = status_raw.get("order", {})
            # Hyperliquid nests the real lifecycle state: the OUTER `status` is
            # "order" (meaning "this oid is known"), the INNER one is
            # filled/open/canceled. `unknownOid` appears only on the outer.
            inner_status = str(order_data.get("status") or "").lower()
            outer_status = str(status_raw.get("status") or "").lower()
            status_str = inner_status if inner_status and inner_status != "order" else outer_status

            if "unknownoid" in status_str.replace("_", ""):
                # The exchange has never heard of this oid, or has aged it out.
                # It was previously left RESTING, which meant it was re-queried on
                # every cycle forever - a permanent drain on the rate-limit budget
                # and a phantom entry in `open_orders()`. Terminal and honest.
                order.status = "UNKNOWN"
                print(f"[WARN] oid {order.oid} (cloid {order.cloid}) is unknown to the "
                      f"exchange. Marking UNKNOWN - it is NOT resting, and it is not "
                      f"confirmed filled. Reconcile manually before assuming either.")
                continue

            if "filled" in status_str:
                order.status = "FILLED"
                order.filled_sz = self._filled_size(order, order_data)
                order.receipt_path = self._write_receipt(order)
                newly_filled += 1
            elif "canceled" in status_str or "cancelled" in status_str:
                # A cancel can still have filled part of the way first. Booking
                # zero there would lose real inventory from the ledger.
                order.filled_sz = self._filled_size(order, order_data, default=0.0)
                # CANCELED even when part of it filled. A cancelled order is not
                # resting, and marking it PARTIAL put it back in `resting_orders`
                # - so a dead order was re-polled every cycle for a full hour
                # until prune() caught it, burning rate-limit weight the whole
                # time. `filled_sz > 0` is what records the partial fill; the
                # status records that it is over.
                order.status = "CANCELED"
                if order.filled_sz > 0 and order.receipt_path is None:
                    order.receipt_path = self._write_receipt(order)
                newly_canceled += 1
            elif "rejected" in status_str:
                order.status = "REJECTED"

        pruned = self.prune()

        return {
            "status": "OK",
            "checked": checked,
            "newly_filled": newly_filled,
            "newly_canceled": newly_canceled,
            "resting_count": len(self.resting_orders),
            "pruned": pruned,
            "tracked_count": self.tracked_count,
        }
