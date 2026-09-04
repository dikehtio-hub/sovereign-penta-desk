"""
Round 24 audit: reconciler lifecycle hygiene.

Three defects, all of which only show up in a process that runs for weeks:

  1. A "filled" status booked `requested_sz` rather than what actually filled.
     A receipt is a TAX RECORD, so over-stating it puts inventory in the ledger
     that the account does not hold.
  2. An `unknownOid` reply matched no branch, so the order stayed RESTING and was
     re-queried on every cycle forever - a permanent drain on the rate-limit
     budget and a phantom entry in `open_orders()`.
  3. Nothing was ever evicted. Every order ever placed stayed in memory.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.reconciliation import OrderReconciler, TrackedOrder


class _Client:
    def __init__(self, open_orders=None, statuses=None):
        self._open = open_orders or []
        self._statuses = statuses or {}
        self.status_calls = 0

    def get_open_orders(self, user_address):
        return self._open

    def get_order_status(self, user_address, oid):
        self.status_calls += 1
        return self._statuses.get(oid, {"status": "unknownOid"})


def _order(oid=1, cloid="0x01", sz=2.0, **kwargs):
    return TrackedOrder(cloid=cloid, coin="SOL", side="BUY", requested_sz=sz,
                        limit_px=150.0, strategy="hl_basis_harvest", oid=oid, **kwargs)


def _filled(orig, remaining):
    return {"status": "order",
            "order": {"status": "filled", "oid": 1, "origSz": orig, "sz": remaining}}


# ------------------------------------------------- what actually filled

def test_a_full_fill_books_the_full_size():
    client = _Client(statuses={1: _filled("2.0", "0.0")})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order()
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.filled_sz == pytest.approx(2.0)


def test_a_partial_fill_books_only_what_filled():
    """
    The regression. `origSz - sz` is what the exchange says filled; booking
    `requested_sz` would put 2.0 in the tax ledger for a 1.5 fill.
    """
    client = _Client(statuses={1: _filled("2.0", "0.5")})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order(sz=2.0)
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.filled_sz == pytest.approx(1.5)
    assert order.unfilled_sz == pytest.approx(0.5)


def test_an_explicit_filled_size_is_used_when_given():
    client = _Client(statuses={1: {"status": "order",
                                   "order": {"status": "filled", "filledSz": "0.75"}}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order(sz=2.0)
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.filled_sz == pytest.approx(0.75)


def test_it_falls_back_to_the_requested_size_when_the_exchange_says_nothing():
    """Backwards compatible: no size fields means we cannot do better."""
    client = _Client(statuses={1: {"status": "order", "order": {"status": "filled"}}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order(sz=2.0)
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.filled_sz == pytest.approx(2.0)


def test_a_cancel_after_a_partial_fill_keeps_the_filled_part():
    """Booking zero on a cancel would lose real inventory from the ledger."""
    client = _Client(statuses={1: {"status": "order",
                                   "order": {"status": "canceled", "origSz": "2.0",
                                             "sz": "1.2"}}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order(sz=2.0)
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.filled_sz == pytest.approx(0.8)
    # CANCELED, not PARTIAL - see TERMINAL_STATUSES. `filled_sz` carries the
    # partial fill; the status carries the fact that the order is over.
    assert order.status == "CANCELED"
    assert order not in reconciler.resting_orders


def test_a_clean_cancel_books_nothing():
    client = _Client(statuses={1: {"status": "order",
                                   "order": {"status": "canceled", "origSz": "2.0",
                                             "sz": "2.0"}}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order(sz=2.0)
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.filled_sz == 0.0
    assert order.status == "CANCELED"


# ------------------------------------------------------------- unknownOid

def test_an_unknown_oid_becomes_terminal_rather_than_resting_forever():
    client = _Client(statuses={1: {"status": "unknownOid"}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order()
    reconciler.track(order)
    reconciler.reconcile_once("0xuser")
    assert order.status == "UNKNOWN"
    assert order not in reconciler.resting_orders


def test_an_unknown_oid_is_not_re_queried_on_the_next_cycle():
    """It used to be polled every cycle forever, burning rate-limit weight."""
    client = _Client(statuses={1: {"status": "unknownOid"}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    reconciler.track(_order())
    reconciler.reconcile_once("0xuser")
    after_first = client.status_calls
    reconciler.reconcile_once("0xuser")
    assert client.status_calls == after_first


def test_an_unknown_oid_is_never_treated_as_a_fill():
    """It is not confirmed filled, so it must not write a tax receipt."""
    client = _Client(statuses={1: {"status": "unknownOid"}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    order = _order()
    reconciler.track(order)
    summary = reconciler.reconcile_once("0xuser")
    assert summary["newly_filled"] == 0
    assert order.filled_sz == 0.0
    assert order.receipt_path is None


# ------------------------------------------------------------- pruning

def test_settled_orders_are_eventually_released():
    reconciler = OrderReconciler(rest_client=None, receipts_enabled=False)
    old = _order(oid=1, cloid="0x01")
    old.status = "FILLED"
    old.created_at = time.time() - 7200
    reconciler.track(old)
    assert reconciler.tracked_count == 1
    assert reconciler.prune(max_age_seconds=3600.0) == 1
    assert reconciler.tracked_count == 0


def test_a_resting_order_is_never_pruned_however_old():
    """An unsettled order is exactly the one worth remembering."""
    reconciler = OrderReconciler(rest_client=None, receipts_enabled=False)
    stale = _order(oid=2, cloid="0x02")
    stale.created_at = time.time() - 999_999
    reconciler.track(stale)
    assert reconciler.prune(max_age_seconds=1.0) == 0
    assert reconciler.tracked_count == 1


def test_a_recently_settled_order_is_kept_for_reconciliation():
    reconciler = OrderReconciler(rest_client=None, receipts_enabled=False)
    fresh = _order(oid=3, cloid="0x03")
    fresh.status = "FILLED"
    reconciler.track(fresh)
    assert reconciler.prune(max_age_seconds=3600.0) == 0


def test_pruning_releases_the_oid_index_too():
    """Otherwise the leak just moves to the other dict."""
    reconciler = OrderReconciler(rest_client=None, receipts_enabled=False)
    old = _order(oid=9, cloid="0x09")
    old.status = "CANCELED"
    old.created_at = time.time() - 7200
    reconciler.track(old)
    reconciler.prune(max_age_seconds=3600.0)
    assert reconciler._orders_by_oid == {}


def test_a_long_running_reconciler_does_not_grow_without_bound():
    """The leak, at the scale it actually mattered: weeks of settled orders."""
    reconciler = OrderReconciler(rest_client=None, receipts_enabled=False)
    for i in range(500):
        order = _order(oid=i, cloid=f"0x{i:04x}")
        order.status = "FILLED"
        order.created_at = time.time() - 7200
        reconciler.track(order)
    assert reconciler.tracked_count == 500
    reconciler.prune(max_age_seconds=3600.0)
    assert reconciler.tracked_count == 0


def test_reconcile_once_prunes_as_it_goes():
    client = _Client(statuses={})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    old = _order(oid=77, cloid="0x77")
    old.status = "FILLED"
    old.created_at = time.time() - 7200
    reconciler.track(old)
    summary = reconciler.reconcile_once("0xuser")
    assert summary["pruned"] == 1
    assert summary["tracked_count"] == 0


# ============================================================================
# Round 25: a cancelled order is not a resting order.
#
# Marking a partially-filled cancel as PARTIAL put it back into `resting_orders`
# (which matches RESTING and PARTIAL), so `reconcile_once` re-queried a DEAD
# order every cycle - 360 times at a 10s cadence - until prune() evicted it an
# hour later. PARTIAL was also listed in TERMINAL_STATUSES at the same time,
# which contradicted prune()'s own docstring and would have evicted a genuinely
# resting partial fill.
# ============================================================================

def test_a_cancelled_partial_is_polled_exactly_once():
    """The leak, stated as the API traffic it caused."""
    client = _Client(statuses={1: {"status": "order",
                                   "order": {"status": "canceled", "origSz": "2.0",
                                             "sz": "1.2"}}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    reconciler.track(_order(sz=2.0))

    reconciler.reconcile_once("0xuser")
    assert client.status_calls == 1

    reconciler.reconcile_once("0xuser")
    assert client.status_calls == 1          # zero further polls


def test_a_cancelled_partial_leaves_the_resting_set_immediately():
    client = _Client(statuses={1: {"status": "order",
                                   "order": {"status": "canceled", "origSz": "2.0",
                                             "sz": "1.2"}}})
    reconciler = OrderReconciler(rest_client=client, receipts_enabled=False)
    reconciler.track(_order(sz=2.0))
    reconciler.reconcile_once("0xuser")
    assert reconciler.resting_orders == []


def test_partial_is_not_a_terminal_status():
    """
    PARTIAL means STILL RESTING and part-filled - the order most worth keeping.
    Listing it as terminal would have pruned a live order after an hour.
    """
    assert "PARTIAL" not in OrderReconciler.TERMINAL_STATUSES


def test_a_resting_partial_fill_is_never_pruned():
    reconciler = OrderReconciler(rest_client=None, receipts_enabled=False)
    order = _order(oid=5, cloid="0x05")
    order.status = "PARTIAL"
    order.filled_sz = 0.4
    order.created_at = time.time() - 999_999
    reconciler.track(order)
    assert reconciler.prune(max_age_seconds=1.0) == 0
    assert reconciler.tracked_count == 1


def test_a_resting_partial_fill_is_still_polled():
    """It is genuinely live, so it must stay in the reconciliation loop."""
    reconciler = OrderReconciler(rest_client=_Client(), receipts_enabled=False)
    order = _order(oid=6, cloid="0x06")
    order.status = "PARTIAL"
    reconciler.track(order)
    assert order in reconciler.resting_orders
