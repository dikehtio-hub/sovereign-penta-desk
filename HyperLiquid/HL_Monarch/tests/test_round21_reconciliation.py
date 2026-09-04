"""
Tests for Round 21: Resting Order Lifecycle Reconciliation Loop
"""
import pytest
from pathlib import Path
from execution.reconciliation import OrderReconciler, TrackedOrder
from execution.order_executor import ExecutionResult
from execution.supervisor import EcosystemSupervisor


class _MockRestClient:
    def __init__(self, open_orders=None, order_statuses=None):
        self._open_orders = open_orders or []
        self._order_statuses = order_statuses or {}

    def get_open_orders(self, user):
        return self._open_orders

    def get_order_status(self, user, oid):
        return self._order_statuses.get(oid, {"status": "unknown"})


def test_tracked_order_initialization():
    order = TrackedOrder(
        cloid="0xabc",
        coin="BTC",
        side="BUY",
        requested_sz=0.5,
        limit_px=60000.0,
        strategy="hl_basis_harvest",
        oid=12345
    )
    assert order.unfilled_sz == 0.5
    assert order.status == "RESTING"


def test_reconciler_tracks_execution_result():
    reconciler = OrderReconciler(receipts_enabled=False)
    exec_res = ExecutionResult(
        cloid="0x123",
        oid=999,
        coin="ETH",
        side="SELL",
        requested_sz=1.0,
        filled_sz=0.0,
        avg_price=3000.0,
        status="SUBMITTED",
        strategy="hl_basis_harvest"
    )
    tracked = reconciler.track(exec_res)
    assert tracked.cloid == "0x123"
    assert tracked.oid == 999
    assert tracked.status == "RESTING"
    assert reconciler.get_order(cloid="0x123") is tracked
    assert reconciler.get_order(oid=999) is tracked


def test_reconcile_once_resting_remains_resting():
    client = _MockRestClient(open_orders=[{"oid": 101, "coin": "BTC"}])
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = TrackedOrder(
        cloid="0x01",
        coin="BTC",
        side="BUY",
        requested_sz=0.1,
        limit_px=60000.0,
        strategy="hl_basis_harvest",
        oid=101
    )
    reconciler.track(order)

    summary = reconciler.reconcile_once("0xuser")
    assert summary["status"] == "OK"
    assert summary["newly_filled"] == 0
    assert summary["resting_count"] == 1
    assert order.status == "RESTING"


def test_reconcile_once_detects_fill_and_emits_receipt(tmp_path: Path):
    client = _MockRestClient(
        open_orders=[],  # Order no longer in openOrders
        order_statuses={
            202: {
                "status": "order",
                "order": {"status": "filled", "oid": 202}
            }
        }
    )
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=True, receipts_dir=tmp_path)
    order = TrackedOrder(
        cloid="0x02",
        coin="SOL",
        side="BUY",
        requested_sz=2.0,
        limit_px=150.0,
        strategy="hl_basis_harvest",
        oid=202
    )
    reconciler.track(order)

    summary = reconciler.reconcile_once("0xuser")
    assert summary["status"] == "OK"
    assert summary["newly_filled"] == 1
    assert summary["resting_count"] == 0
    assert order.status == "FILLED"
    assert order.filled_sz == 2.0
    assert order.receipt_path is not None
    assert Path(order.receipt_path).exists()


def test_reconcile_once_detects_canceled_order():
    client = _MockRestClient(
        open_orders=[],
        order_statuses={
            303: {
                "status": "order",
                "order": {"status": "canceled", "oid": 303}
            }
        }
    )
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=True)
    order = TrackedOrder(
        cloid="0x03",
        coin="BTC",
        side="SELL",
        requested_sz=0.05,
        limit_px=65000.0,
        strategy="hl_basis_harvest",
        oid=303
    )
    reconciler.track(order)

    summary = reconciler.reconcile_once("0xuser")
    assert summary["status"] == "OK"
    assert summary["newly_canceled"] == 1
    assert summary["newly_filled"] == 0
    assert order.status == "CANCELED"
    assert order.receipt_path is None


def test_supervisor_drives_reconciler():
    client = _MockRestClient(open_orders=[])
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    supervisor = EcosystemSupervisor(
        executor=None,
        reconciler=reconciler,
        user_address="0xuser123",
        reconcile_interval_seconds=5.0
    )

    tick_res = supervisor.tick()
    # Reconciler was due and ran
    assert any("reconciled" in a for a in tick_res["actions"])
