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

from collectors.orderbook_sampler import (sample_orderbooks, select_sample_coins,
                                          top_funding_candidates)
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


def test_candidates_sit_between_held_positions_and_the_rotation():
    """Round 37: held > candidates > rotated > core, deduplicated, capped."""
    picked = select_sample_coins(core=["BTC", "ETH"], rotated={"PUMP"}, cap=5,
                                 extra=["SOL"], candidates=["FART", "ETH"])
    assert picked == ["SOL", "FART", "ETH", "PUMP", "BTC"]
    # A held coin that is also a candidate keeps its first place and appears once.
    picked = select_sample_coins(core=["BTC"], rotated=set(), cap=5, extra=["SOL"], candidates=["SOL", "WIF"])
    assert picked == ["SOL", "WIF", "BTC"]


def test_top_funding_candidates_rank_positive_main_dex_funding_deterministically():
    snapshots = [
        {"coin": "BTC", "funding_rate": 0.0001},
        {"coin": "ETH", "funding_rate": -0.0002},          # negative: the spot-backed harvester cannot collect it
        {"coin": "xyz:TSLA", "funding_rate": 0.001},        # HIP-3: no spot leg, excluded by default
        {"coin": "PUMP", "funding_rate": 0.0005},
        {"coin": "AAA", "funding_rate": 0.0005},            # ties break on the name
        {"coin": "WIF", "funding_rate": None},
        {"coin": "ZERO", "funding_rate": 0.0},
        {"coin": "", "funding_rate": 0.9},
    ]
    assert top_funding_candidates(snapshots, n=3) == ["AAA", "PUMP", "BTC"]
    assert top_funding_candidates(snapshots, n=2, spot_backed_only=False) == ["xyz:TSLA", "AAA"]
    assert top_funding_candidates([], n=5) == []
    assert top_funding_candidates(snapshots, n=0) == []


def test_open_positions_are_sampled_even_when_the_cap_is_tight():
    """
    Round 36: a held basis position must never lose its spread series because
    its volume rank slipped out of the rotation. Positions go in as `extra` and
    survive a cap that drops both the rotated set and the core watchlist.
    """
    held = ["FARTCOIN", "xyz:SILVER"]
    core = ["BTC", "ETH", "SOL", "xyz:GOLD"]
    rotated = {"PUMP", "WIF", "AAA"}
    picked = select_sample_coins(core, rotated, cap=3, extra=held)
    assert picked[:2] == held
    assert len(picked) == 3 and picked[2] == "AAA"             # then rotated, sorted; core never reached
    # A held coin that is also rotated or core is not listed twice.
    picked = select_sample_coins(core, {"BTC", "ETH"}, cap=10, extra=["ETH"])
    assert picked.count("ETH") == 1 and picked[0] == "ETH"


def test_the_collector_samples_held_positions_first_and_copes_without_a_harvester():
    """_sample_coins reads the harvester's open positions when one exists - the
    harvester is created lazily by the accrual loop, so a collector that has not
    accrued yet has none - and never lists a coin twice."""
    import collectors.market_collector as mc

    class Harvester:
        positions = {"FARTCOIN": {}, "xyz:SILVER": {}}

    collector = mc.MarketCollector.__new__(mc.MarketCollector)
    collector._rotated_coins = {"PUMP", "FARTCOIN"}
    collector.basis_harvester = Harvester()
    snapshots = [{"coin": "HOT", "funding_rate": 0.002}, {"coin": "WARM", "funding_rate": 0.001},
                 {"coin": "xyz:TSLA", "funding_rate": 0.01}]
    picked = collector._sample_coins(snapshots)
    assert picked[:4] == ["FARTCOIN", "xyz:SILVER", "HOT", "WARM"]   # held, then candidates, then PUMP...
    assert picked[4] == "PUMP"
    assert "xyz:TSLA" not in picked[:5]
    assert picked.count("FARTCOIN") == 1
    assert len(picked) <= mc.ORDERBOOK_SAMPLE_MAX_COINS

    bare = mc.MarketCollector.__new__(mc.MarketCollector)
    bare._rotated_coins = set()
    assert bare._sample_coins()[0] == mc.ALL_CORE_WATCHLIST[0]      # no harvester, no snapshots: core first


def test_a_sampling_pass_reads_current_state_and_samples_the_candidates(repo):
    """_sample_pass runs on the hl-l2 thread: latest_snapshots -> coins -> sample_orderbooks."""
    import collectors.market_collector as mc

    class Repo:
        def __init__(self, inner):
            self.inner = inner
            self.rows = []

        def get_latest_snapshots(self, coins=None):
            return [{"coin": "HOT", "funding_rate": 0.002}, {"coin": "COLD", "funding_rate": -0.001}]

        def insert_orderbook_snapshots(self, rows):
            self.rows.extend(rows)

    collector = mc.MarketCollector.__new__(mc.MarketCollector)
    collector._rotated_coins = set()
    collector.repo = Repo(repo)
    collector.rest_client = FakeClient({"HOT": book(10.0, 3.0)})
    stats = collector._sample_pass()
    assert collector.rest_client.calls[0] == "HOT"                 # the candidate is sampled first
    assert stats["written"] >= 1
    assert collector.repo.rows[0]["coin"] == "HOT"


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
