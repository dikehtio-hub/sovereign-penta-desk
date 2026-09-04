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


def snap(coin, rate, oi=1_000_000.0, vol=1_000_000.0):
    return {"coin": coin, "funding_rate": rate, "notional_oi": oi, "day_ntl_vlm": vol}


def test_top_funding_candidates_rank_positive_funding_deterministically():
    snapshots = [
        snap("BTC", 0.0001),
        snap("ETH", -0.0002),           # negative: the spot-backed harvester cannot collect it
        snap("xyz:TSLA", 0.001),        # no universe given: the prefix fallback excludes it
        snap("PUMP", 0.0005),
        snap("AAA", 0.0005),            # ties break on the name
        snap("WIF", None),
        snap("ZERO", 0.0),
        snap("", 0.9),
        "junk",
    ]
    assert top_funding_candidates(snapshots, n=3) == ["AAA", "PUMP", "BTC"]
    assert top_funding_candidates(snapshots, n=2, spot_backed_only=False) == ["xyz:TSLA", "AAA"]
    assert top_funding_candidates([], n=5) == []
    assert top_funding_candidates(snapshots, n=0) == []


def test_candidates_are_grounded_on_the_spot_universe_not_the_prefix():
    """
    Round 38 (cross-check 3.2): the live sample under the prefix rule was CHIP,
    PONS, XMR, FARTCOIN, STABLE - four of them with no spot token - while
    para:ANSEM, which the harvester holds against spot ANSEM, was excluded.
    """
    snapshots = [snap("CHIP", 0.009), snap("PONS", 0.008), snap("XMR", 0.007), snap("FARTCOIN", 0.006),
                 snap("STABLE", 0.005), snap("para:ANSEM", 0.004), snap("XPL", 0.003), snap("BTC", 0.002)]
    universe = {"STABLE", "ANSEM", "UXPL", "UBTC", "UFART"}  # wrapped large caps and Round 40 aliases count
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe) == ["FARTCOIN", "STABLE", "para:ANSEM", "XPL", "BTC"]
    # Round 40: FARTCOIN's spot is UFART, an alias rather than "U" + name, and it IS spot-backed in fact ($570k/day).
    # Volumes only pick WHICH spot name would hedge; they never change membership or rank.
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe,
                                  spot_volumes={"UFART": 1.0}) == ["FARTCOIN", "STABLE", "para:ANSEM", "XPL", "BTC"]
    # An EMPTY universe is a failed lookup: nothing can be called spot-backed, so nothing is sampled as a candidate.
    assert top_funding_candidates(snapshots, n=5, spot_universe=set()) == []
    # The prefix rule survives only as the no-universe fallback.
    assert top_funding_candidates(snapshots, n=5)[:4] == ["CHIP", "PONS", "XMR", "FARTCOIN"]


def test_measured_candidates_rank_on_net_apr_and_unmeasured_on_gross():
    """
    Round 39 (cross-check 3.4). Over a 7-day hold a 40% quote at 40 bps nets
    40 - 0.4 x 2 x 365/7 = -1.7% and sinks; 30% at 1 bp nets 28.96% and leads
    the measured coins. A coin with no spread on record ranks on its gross - an
    upper bound that buys it one sample - so a new hot market is not starved
    behind measured ones.
    """
    universe = {"WIDE", "TIGHT", "NEW", "MID"}

    def rate(apr):
        return apr / 100.0 / 8760.0

    snapshots = [snap("WIDE", rate(40.0)), snap("TIGHT", rate(30.0)), snap("NEW", rate(29.5)), snap("MID", rate(35.0))]
    spreads = {"WIDE": 40.0, "TIGHT": 1.0, "MID": 8.0}        # MID nets 35 - 0.08 x 2 x 365/7 = 26.66%
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe, spreads=spreads) == ["NEW", "TIGHT", "MID", "WIDE"]
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe) == ["WIDE", "MID", "TIGHT", "NEW"]
    # A longer hold amortises the same spread further: WIDE at 30 days nets 30.3% and moves up.
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe, spreads=spreads,
                                  holding_days=30.0) == ["MID", "WIDE", "TIGHT", "NEW"]


def test_the_latest_spread_per_coin_within_a_day_feeds_candidate_ranking(repo):
    """Round 39: the repository hands the sampler each coin's NEWEST reading, and only a recent one."""
    sample_orderbooks(FakeClient({"BTC": book(100.0, 6.0), "ETH": book(100.0, 2.0)}), repo, ["BTC", "ETH"], now_ms=T0)
    sample_orderbooks(FakeClient({"BTC": book(100.0, 3.0)}), repo, ["BTC"], now_ms=T0 + 60_000)
    spreads = repo.get_latest_orderbook_spreads(within_hours=24.0, now_ms=T0 + 120_000)
    assert spreads == pytest.approx({"BTC": 3.0, "ETH": 2.0}, abs=0.01)      # the newest reading, not the first
    assert repo.get_latest_orderbook_spreads(within_hours=90 / 3600.0, now_ms=T0 + 120_000) == pytest.approx({"BTC": 3.0}, abs=0.01)
    assert repo.get_latest_orderbook_spreads(within_hours=24.0, now_ms=T0 + 25 * H) == {}   # a day old is history


def test_candidates_under_the_liquidity_floors_are_not_worth_a_sampling_slot():
    """Cross-check 3.3: the scan rejects them before reading a spread, so sampling them measures nothing tradeable."""
    universe = {"HOT", "THIN", "DEAD", "NOOI"}
    snapshots = [snap("THIN", 0.01, oi=1_000_000.0, vol=99_999.0),    # under the volume floor
                 snap("NOOI", 0.01, oi=249_999.0, vol=1_000_000.0),   # under the OI floor
                 snap("HOT", 0.001),
                 {"coin": "DEAD", "funding_rate": 0.02}]              # no liquidity fields at all: fail closed
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe) == ["HOT"]
    assert top_funding_candidates(snapshots, n=5, spot_universe=universe,
                                  min_notional_oi=0.0, min_day_volume=0.0) == ["DEAD", "NOOI", "THIN", "HOT"]


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
    collector._spot_universe, collector._spot_universe_at = {"HOT", "WARM", "ANSEM"}, time.time()
    snapshots = [snap("HOT", 0.002), snap("WARM", 0.001), snap("para:ANSEM", 0.0005),
                 snap("CHIP", 0.01)]                                # highest funding, no spot token: not a candidate
    picked = collector._sample_coins(snapshots)
    assert picked[:5] == ["FARTCOIN", "xyz:SILVER", "HOT", "WARM", "para:ANSEM"]   # held, then candidates, then PUMP
    assert picked[5] == "PUMP"
    assert "CHIP" not in picked
    assert picked.count("FARTCOIN") == 1
    assert len(picked) <= mc.ORDERBOOK_SAMPLE_MAX_COINS

    bare = mc.MarketCollector.__new__(mc.MarketCollector)
    bare._rotated_coins = set()
    assert bare._sample_coins()[0] == mc.ALL_CORE_WATCHLIST[0]      # no harvester, no snapshots: core first


def test_the_spot_universe_is_cached_refreshed_and_never_guessed(monkeypatch):
    """
    Round 38: a failed lookup yields NO candidates (an empty universe), not the
    prefix rule; a stale copy outlives a failed refresh; a good copy is reused
    until SPOT_UNIVERSE_REFRESH_SECONDS have passed.
    """
    import collectors.market_collector as mc

    class Engine:
        def __init__(self, answers):
            self.answers, self.calls = list(answers), 0

        def get_spot_universe(self, refresh=False):
            self.calls += 1
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        def get_spot_volumes(self, refresh=False):
            return {"ANSEM": 1_515.0, "UANSEM": 927_818.0}       # Round 40: cached alongside, for the liquid hedge

    collector = mc.MarketCollector.__new__(mc.MarketCollector)
    collector._spot_universe, collector._spot_universe_at, collector._spot_universe_warned = None, 0.0, False
    collector._spot_volumes_map = None
    collector._rotated_coins = set()
    collector._arb_engine = Engine([set(), {"ANSEM"}, RuntimeError("429"), {"ANSEM", "NEW"}])

    assert collector._spot_universe_cached() == set()                 # lookup failed: nothing is spot-backed
    assert collector._spot_universe_warned
    assert collector._spot_volumes_map is None
    assert collector._spot_universe_cached() == {"ANSEM"}             # retried on the next pass
    assert collector._spot_volumes_map == {"ANSEM": 1_515.0, "UANSEM": 927_818.0}
    assert collector._spot_universe_cached() == {"ANSEM"}             # fresh: served from the cache
    assert collector._arb_engine.calls == 2
    collector._spot_universe_at -= mc.SPOT_UNIVERSE_REFRESH_SECONDS + 1
    assert collector._spot_universe_cached() == {"ANSEM"}             # refresh failed: the stale copy stands
    assert collector._spot_universe_cached() == {"ANSEM", "NEW"}      # and the next attempt replaces it
    assert collector._arb_engine.calls == 4
    # The cached universe is what decides candidates: the highest funding on the
    # tape (CHIP) has no spot token and is not sampled ahead of the core list.
    picked = collector._sample_coins([snap("para:ANSEM", 0.01), snap("CHIP", 0.02)])
    assert picked[0] == "para:ANSEM" and "CHIP" not in picked
    assert collector._arb_engine.calls == 4                           # served from the cache, no fetch


def test_a_sampling_pass_reads_current_state_and_samples_the_candidates(repo):
    """_sample_pass runs on the hl-l2 thread: latest_snapshots -> coins -> sample_orderbooks."""
    import collectors.market_collector as mc

    class Repo:
        def __init__(self, inner):
            self.inner = inner
            self.rows = []

        def get_latest_snapshots(self, coins=None):
            return [snap("HOT", 0.002), snap("WARM", 0.0019), snap("COLD", -0.001)]

        def get_latest_orderbook_spreads(self, **kwargs):
            return {"HOT": 300.0}                           # Round 39: measured wide, so it nets negative

        def insert_orderbook_snapshots(self, rows):
            self.rows.extend(rows)

    collector = mc.MarketCollector.__new__(mc.MarketCollector)
    collector._rotated_coins = set()
    collector._spot_universe, collector._spot_universe_at = {"HOT", "WARM", "COLD"}, time.time()
    collector.repo = Repo(repo)
    collector.rest_client = FakeClient({"WARM": book(10.0, 3.0)})
    stats = collector._sample_pass()
    assert collector.rest_client.calls[:2] == ["WARM", "HOT"]     # unmeasured gross beats measured-wide net
    assert stats["written"] >= 1
    assert collector.repo.rows[0]["coin"] == "WARM"


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
