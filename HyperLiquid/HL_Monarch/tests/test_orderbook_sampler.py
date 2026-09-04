"""
Round 35 Target 2: the caller orderbook_snapshots never had.

Pins that a sampling pass writes one spread row per coin from a real-shaped
l2Book payload, that one failing coin does not cost the others, that the coin
list is prioritised and capped, and - the point of the target - that a persisted
basis window whose entry has a measured spread carries a MEASURED net rate.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.orderbook_sampler import sample_orderbooks, select_sample_coins
from storage import incremental_persistence as ip
from storage.db import DatabaseManager
from storage.repository import MarketRepository

H = 3_600_000
T0 = 1_788_000_000_000 // (3 * H) * (3 * H)


def book(mid=100.0, spread_bps=6.0, size=10.0):
    half = mid * spread_bps / 10_000.0 / 2.0
    return {"levels": [[{"px": str(mid - half), "sz": str(size)},
                        {"px": str(mid * 0.985), "sz": str(size)}],
                       [{"px": str(mid + half), "sz": str(size)},
                        {"px": str(mid * 1.015), "sz": str(size)}]]}


class FakeClient:
    def __init__(self, books, failing=()):
        self.books, self.failing, self.calls = books, set(failing), []

    def get_l2_book(self, coin):
        self.calls.append(coin)
        if coin in self.failing:
            raise RuntimeError("HTTP 429")
        return self.books.get(coin, {"levels": [[], []]})


@pytest.fixture
def repo(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager(tmp_path / "ob.db")
    r = MarketRepository(db)
    yield r
    db.close()
    DatabaseManager._instance = None


def test_coin_selection_is_prioritised_deduplicated_and_capped():
    picked = select_sample_coins(core=["BTC", "ETH", "xyz:GOLD"], rotated={"PUMP", "ETH", "ABC"},
                                 cap=4, extra=["SOL"])
    assert picked == ["SOL", "ABC", "ETH", "PUMP"]            # extras, rotated (sorted), then core
    assert select_sample_coins(["BTC"], set(), cap=0) == []


def test_a_pass_writes_one_row_per_coin_and_isolates_failures(repo):
    client = FakeClient({"BTC": book(50_000.0, 1.0), "ETH": book(3_000.0, 4.0), "DEAD": {"levels": [[], []]}},
                        failing={"PUMP"})
    stats = sample_orderbooks(client, repo, ["BTC", "PUMP", "ETH", "DEAD"], now_ms=T0)
    assert stats["requested"] == 4 and stats["written"] == 2
    assert stats["failed"] == {"PUMP": "RuntimeError: HTTP 429", "DEAD": "empty book"}
    assert stats["median_spread_bps"] == pytest.approx(4.0, abs=0.01)
    rows = repo.db.connection.execute(
        "SELECT coin, timestamp, spread_bps, best_bid, best_ask FROM orderbook_snapshots ORDER BY coin").fetchall()
    assert [(r[0], r[1]) for r in rows] == [("BTC", T0), ("ETH", T0)]
    assert rows[0][2] == pytest.approx(1.0, abs=0.01)
    assert rows[0][3] < rows[0][4]


def test_a_measured_spread_reaches_the_persisted_window(repo):
    repo.upsert_assets([{"coin": "BTC", "dex": "main", "sz_decimals": 4, "max_leverage": 50,
                         "only_isolated": False}])
    rows = []
    t = T0
    while t <= T0 + 30 * H:
        rows.append({"timestamp": t, "coin": "BTC", "dex": "main", "mark_px": 100.0, "mid_px": 100.0,
                     "oracle_px": 100.0, "open_interest": 1.0, "notional_oi": 1000.0,
                     "funding_rate": 0.0001, "premium": 0.0, "day_ntl_vlm": 0.0})
        t += 5 * 60_000
    repo.insert_snapshots(rows)

    # A spread sampled a minute before the entry instant, 6 bps.
    sample_orderbooks(FakeClient({"BTC": book(100.0, 6.0)}), repo, ["BTC"], now_ms=T0 - 60_000)

    conn = repo.db.connection
    out = ip.persist_basis_windows(conn, T0 + 31 * H, 24.0, retention_hours=192, max_grid_points=100)
    assert out["fees_measured"] >= 1
    row = conn.execute("SELECT fee_basis, spread_bps_entry, realised_apr, net_apr_after_fees "
                       "FROM basis_realised_windows WHERE window_start_utc = ?", (T0,)).fetchone()
    assert row[0] == "measured" and row[1] == pytest.approx(6.0, abs=0.01)
    assert row[3] == pytest.approx(row[2] - ip.spread_drag_apr(6.0, 24.0), abs=0.01)
    # An entry more than the gap tolerance after the sample stays unmeasured - no default spread.
    later = conn.execute("SELECT fee_basis FROM basis_realised_windows WHERE window_start_utc = ?",
                         (T0 + 6 * H,)).fetchone()
    assert later[0] == "unmeasured"


def test_orderbook_rows_are_in_the_fail_closed_set(repo, monkeypatch):
    now = int(time.time() * 1000)
    sample_orderbooks(FakeClient({"BTC": book()}), repo, ["BTC"], now_ms=now - 300 * H)
    monkeypatch.setattr(ip, "persist_completed_measurements",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    deleted = repo.prune_old_data(snapshot_retention_hours=192)
    assert deleted["orderbook_snapshots"] == 0
    assert repo.db.connection.execute("SELECT COUNT(*) FROM orderbook_snapshots").fetchone()[0] == 1
    monkeypatch.undo()
    deleted = repo.prune_old_data(snapshot_retention_hours=192)
    assert deleted["orderbook_snapshots"] == 1
