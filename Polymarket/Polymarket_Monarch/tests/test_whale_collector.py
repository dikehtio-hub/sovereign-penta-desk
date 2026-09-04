"""
Tests for whale_collector.py: the replay fixture, the offline replay path, and
the Cloudflare keepalive loop.
"""

import asyncio
import json
import sqlite3

import pytest

import whale_collector as wc


# ---------------------------------------------------------------------------
# Fixture integrity
# ---------------------------------------------------------------------------

def test_sample_fixture_exists_and_is_valid_json():
    assert wc.SAMPLE_TRADES_PATH.exists(), "data/fixtures/sample_trades.json is missing"
    doc = json.loads(wc.SAMPLE_TRADES_PATH.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert doc["frames"], "fixture contains no frames"
    assert doc["_frame_count"] == len(doc["frames"])


def test_sample_fixture_frames_match_live_rtds_shape():
    """Recorded frames must match the live socket envelope exactly."""
    doc = json.loads(wc.SAMPLE_TRADES_PATH.read_text(encoding="utf-8"))
    for frame in doc["frames"]:
        assert frame["topic"] == "activity"
        assert frame["type"] == "trades"
        payload = frame["payload"]
        # Antigravity verified fills carry both price and size in payload.
        assert "price" in payload and "size" in payload
        for field in ("proxyWallet", "side", "timestamp", "title", "outcome"):
            assert field in payload, f"payload missing {field}"


def test_sample_fixture_covers_whale_and_sub_threshold_trades():
    """The fixture must exercise both sides of the $1k filter."""
    payloads = wc.load_fixture_frames()
    notionals = [float(p["price"]) * float(p["size"]) for p in payloads]
    assert any(n >= 1000 for n in notionals), "no whale trades in fixture"
    assert any(n < 1000 for n in notionals), "no sub-threshold trades in fixture"
    assert max(notionals) >= 50_000, "fixture should include a MEGA whale tier trade"


# ---------------------------------------------------------------------------
# load_fixture_frames
# ---------------------------------------------------------------------------

def test_load_fixture_frames_accepts_bare_list(tmp_path):
    path = tmp_path / "bare.json"
    path.write_text(json.dumps([
        {"topic": "activity", "type": "trades", "payload": {"price": 0.5, "size": 10}}
    ]), encoding="utf-8")
    assert wc.load_fixture_frames(path) == [{"price": 0.5, "size": 10}]


def test_load_fixture_frames_accepts_unwrapped_payloads(tmp_path):
    """Entries that are raw payloads (no envelope) are still usable."""
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"frames": [{"price": 0.4, "size": 5000}]}), encoding="utf-8")
    assert wc.load_fixture_frames(path) == [{"price": 0.4, "size": 5000}]


def test_load_fixture_frames_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        wc.load_fixture_frames(tmp_path / "does_not_exist.json")


# ---------------------------------------------------------------------------
# save_trade
# ---------------------------------------------------------------------------

def _trade(**overrides):
    base = {
        "transactionHash": "0xabc",
        "proxyWallet": "0xwallet",
        "pseudonym": "Test-Whale",
        "title": "Test Market",
        "outcome": "Yes",
        "side": "BUY",
        "price": 0.5,
        "size": 4000,          # $2,000 notional
        "timestamp": 1788054510,
    }
    base.update(overrides)
    return base


def test_save_trade_stores_trade_above_threshold(temp_db):
    wc.init_database(temp_db)
    assert wc.save_trade(_trade(), min_usd=1000.0, db_path=temp_db) is True

    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT usd_notional, side, wallet FROM whale_trades").fetchone()
    conn.close()
    assert row == (2000.0, "BUY", "0xwallet")


def test_save_trade_rejects_trade_below_threshold(temp_db):
    wc.init_database(temp_db)
    assert wc.save_trade(_trade(size=100), min_usd=1000.0, db_path=temp_db) is False

    conn = sqlite3.connect(temp_db)
    assert conn.execute("SELECT COUNT(*) FROM whale_trades").fetchone()[0] == 0
    # ... but the wallet is still tracked for the PnL scanner pool.
    assert conn.execute("SELECT COUNT(*) FROM tracked_wallets").fetchone()[0] == 1
    conn.close()


def test_save_trade_is_idempotent_on_tx_hash(temp_db):
    wc.init_database(temp_db)
    assert wc.save_trade(_trade(), min_usd=1000.0, db_path=temp_db) is True
    assert wc.save_trade(_trade(), min_usd=1000.0, db_path=temp_db) is False

    conn = sqlite3.connect(temp_db)
    assert conn.execute("SELECT COUNT(*) FROM whale_trades").fetchone()[0] == 1
    conn.close()


def test_save_trade_accumulates_wallet_volume(temp_db):
    wc.init_database(temp_db)
    wc.save_trade(_trade(transactionHash="0x1"), min_usd=1000.0, db_path=temp_db)
    wc.save_trade(_trade(transactionHash="0x2"), min_usd=1000.0, db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    count, volume = conn.execute(
        "SELECT trade_count, total_volume_usd FROM tracked_wallets WHERE wallet='0xwallet'"
    ).fetchone()
    conn.close()
    assert count == 2
    assert volume == pytest.approx(4000.0)


# ---------------------------------------------------------------------------
# Market-relative whale rule
# ---------------------------------------------------------------------------

def test_relative_whale_fraction_is_one_percent():
    assert wc.RELATIVE_WHALE_FRACTION == 0.01


def test_absolute_rule_still_flags_large_fills():
    assert wc.is_whale_trade(1000.0, min_usd=1000.0) is True
    assert wc.is_whale_trade(999.99, min_usd=1000.0) is False


def test_relative_rule_flags_significant_fill_in_thin_market():
    """$400 is under the absolute bar, but 2% of a $20k/day book."""
    assert wc.is_whale_trade(400.0, min_usd=1000.0, market_volume_24h=20_000.0) is True


def test_relative_rule_ignores_small_fill_in_deep_market():
    """The same $400 in a $2.3M Fed market is noise."""
    assert wc.is_whale_trade(400.0, min_usd=1000.0, market_volume_24h=2_300_000.0) is False


def test_relative_rule_boundary_is_inclusive():
    # 1% of $40,000 is exactly $400, which also clears the $250 floor.
    assert wc.is_whale_trade(400.0, min_usd=1_000_000.0, market_volume_24h=40_000.0) is True
    assert wc.is_whale_trade(399.99, min_usd=1_000_000.0, market_volume_24h=40_000.0) is False


# --- the $250 absolute floor on relative whales ---------------------------

def test_relative_whale_floor_is_250():
    assert wc.RELATIVE_WHALE_MIN_USD == 250.0


def test_floor_blocks_dust_fills_in_dead_markets():
    """
    Regression guard: without a floor, 1% of a dead $50/day market is 50 cents,
    so every dust trade would raise a whale alert.
    """
    assert wc.is_whale_trade(0.50, min_usd=1000.0, market_volume_24h=50.0) is False
    assert wc.is_whale_trade(5.0, min_usd=1000.0, market_volume_24h=50.0) is False
    assert wc.is_whale_trade(249.99, min_usd=1000.0, market_volume_24h=50.0) is False


def test_floor_is_inclusive_and_lets_real_fills_through():
    assert wc.is_whale_trade(250.0, min_usd=1000.0, market_volume_24h=50.0) is True


def test_floor_never_blocks_an_absolute_whale():
    """Rule 1 is independent of the floor."""
    assert wc.is_whale_trade(1000.0, min_usd=1000.0, market_volume_24h=50.0) is True


def test_floor_is_configurable():
    assert wc.is_whale_trade(100.0, min_usd=1000.0, market_volume_24h=5_000.0,
                             relative_min_usd=50.0) is True


def test_relative_rule_can_only_add_whales():
    """A fill over the absolute bar stays a whale whatever the market volume."""
    assert wc.is_whale_trade(5_000.0, min_usd=1000.0, market_volume_24h=10_000_000.0) is True


def test_falls_back_to_absolute_rule_without_volume_data():
    for missing in (None, 0.0):
        assert wc.is_whale_trade(500.0, min_usd=1000.0, market_volume_24h=missing) is False
        assert wc.is_whale_trade(2000.0, min_usd=1000.0, market_volume_24h=missing) is True


@pytest.mark.parametrize("key", list(wc.MARKET_VOLUME_KEYS))
def test_market_volume_read_from_any_accepted_key(key):
    assert wc.extract_market_volume_24h({key: 12_345.0}) == pytest.approx(12_345.0)


def test_market_volume_absent_from_raw_rtds_frames():
    """Raw recorded frames carry no volume, so the relative rule stays inert."""
    for payload in wc.load_fixture_frames():
        assert wc.extract_market_volume_24h(payload) is None


def test_market_volume_ignores_unusable_values():
    assert wc.extract_market_volume_24h({"volume24hr": None}) is None
    assert wc.extract_market_volume_24h({"volume24hr": "not-a-number"}) is None
    assert wc.extract_market_volume_24h({"volume24hr": 0}) is None


def test_save_trade_stores_relative_whale_below_absolute_threshold(temp_db):
    wc.init_database(temp_db)
    # $400 fill: under the $1,000 bar, over the $250 floor, and 2% of a
    # $20,000/day market.
    trade = _trade(size=800, price=0.5, market_volume_24h=20_000.0)
    assert wc.save_trade(trade, min_usd=1000.0, db_path=temp_db) is True

    conn = sqlite3.connect(temp_db)
    assert conn.execute("SELECT usd_notional FROM whale_trades").fetchone()[0] == 400.0
    conn.close()


def test_save_trade_rejects_dust_in_dead_market(temp_db):
    wc.init_database(temp_db)
    # $5 fill in a $50/day market: 10% of volume, but far below the floor.
    trade = _trade(size=10, price=0.5, market_volume_24h=50.0)
    assert wc.save_trade(trade, min_usd=1000.0, db_path=temp_db) is False

    conn = sqlite3.connect(temp_db)
    assert conn.execute("SELECT COUNT(*) FROM whale_trades").fetchone()[0] == 0
    conn.close()


def test_save_trade_explicit_volume_overrides_payload(temp_db):
    wc.init_database(temp_db)
    trade = _trade(size=800, price=0.5, market_volume_24h=20_000.0)
    # Caller-supplied deep-market volume must win over the payload's thin one.
    assert wc.save_trade(
        trade, min_usd=1000.0, db_path=temp_db, market_volume_24h=100_000_000.0
    ) is False


def test_save_trade_relative_rule_disabled_by_zero_fraction(temp_db):
    wc.init_database(temp_db)
    trade = _trade(size=800, price=0.5, market_volume_24h=20_000.0)
    assert wc.save_trade(
        trade, min_usd=1000.0, db_path=temp_db, relative_fraction=0.0
    ) is False


# ---------------------------------------------------------------------------
# GammaVolumeCache
# ---------------------------------------------------------------------------

class _CacheResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _market_page(n, start=0, volume=1000.0):
    return [{"conditionId": f"0xCOND{start + i}", "volume24hr": volume} for i in range(n)]


def test_volume_cache_defaults():
    assert wc.VOLUME_CACHE_REFRESH_SECONDS == 60
    assert wc.VOLUME_CACHE_MARKET_LIMIT == 500
    assert wc.GAMMA_MARKETS_URL == "https://gamma-api.polymarket.com/markets"


def test_volume_cache_paginates_because_gamma_caps_pages_at_100(monkeypatch):
    """
    Regression guard: Gamma silently caps /markets at 100 rows whatever `limit`
    says, so asking for 500 in one call quietly yields 100.
    """
    calls = []

    def fake_get(url, **kwargs):
        params = kwargs.get("params", {})
        calls.append(params.get("offset"))
        return _CacheResponse(_market_page(100, start=params.get("offset", 0)))

    monkeypatch.setattr(wc.requests, "get", fake_get)

    cache = wc.GammaVolumeCache(limit=250, page_size=100)
    assert cache.refresh() >= 250
    assert calls == [0, 100, 200]


def test_volume_cache_requests_busiest_markets_first(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs.get("params", {}))
        return _CacheResponse([])

    monkeypatch.setattr(wc.requests, "get", fake_get)
    wc.GammaVolumeCache(limit=100).refresh()

    assert captured["order"] == "volume24hr"
    assert captured["ascending"] == "false"
    assert captured["active"] == "true"
    assert captured["closed"] == "false"


def test_volume_cache_stops_on_short_page(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        return _CacheResponse(_market_page(7))

    monkeypatch.setattr(wc.requests, "get", fake_get)
    cache = wc.GammaVolumeCache(limit=500, page_size=100)
    cache.refresh()
    assert calls["n"] == 1


def test_volume_cache_lookup_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse([{"conditionId": "0xAbCdEf", "volume24hr": 4242.0}]))
    cache = wc.GammaVolumeCache(limit=1)
    cache.refresh()
    assert cache.get("0xabcdef") == pytest.approx(4242.0)
    assert cache.get("0xABCDEF") == pytest.approx(4242.0)
    assert cache.get("0xmissing") is None
    assert cache.get(None) is None


def test_volume_cache_skips_rows_without_usable_volume(monkeypatch):
    payload = [
        {"conditionId": "0x1", "volume24hr": 100.0},
        {"conditionId": "0x2", "volume24hr": None},     # resolved market
        {"conditionId": "0x3", "volume24hr": 0},        # no flow
        {"conditionId": None, "volume24hr": 500.0},     # unusable key
        {"conditionId": "0x5", "volume24hr": "abc"},    # unparseable
    ]
    monkeypatch.setattr(wc.requests, "get", lambda url, **kw: _CacheResponse(payload))
    cache = wc.GammaVolumeCache(limit=10)
    assert cache.refresh() == 1
    assert cache.get("0x1") == pytest.approx(100.0)


def test_volume_cache_survives_http_error_without_wiping(monkeypatch):
    """A failed refresh must never blank a good cache."""
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse([{"conditionId": "0x1", "volume24hr": 9.0}]))
    cache = wc.GammaVolumeCache(limit=10)
    cache.refresh()

    monkeypatch.setattr(wc.requests, "get", lambda url, **kw: _CacheResponse([], status_code=503))
    cache.refresh()

    assert cache.get("0x1") == pytest.approx(9.0)
    assert cache.last_error == "HTTP 503"


def test_volume_cache_survives_connection_error(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("no route")

    monkeypatch.setattr(wc.requests, "get", boom)
    cache = wc.GammaVolumeCache(limit=10)
    assert cache.refresh() == 0
    assert "ConnectionError" in (cache.last_error or "")


def test_volume_cache_tolerates_wrapped_payload(monkeypatch):
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse({"data": [{"conditionId": "0x9", "volume24hr": 7.0}]}))
    cache = wc.GammaVolumeCache(limit=10)
    assert cache.refresh() == 1


def test_volume_for_trade_prefers_inline_payload_value(monkeypatch):
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse([{"conditionId": "0xc", "volume24hr": 1.0}]))
    cache = wc.GammaVolumeCache(limit=10)
    cache.refresh()
    trade = {"conditionId": "0xc", "market_volume_24h": 5000.0}
    assert cache.volume_for_trade(trade) == pytest.approx(5000.0)


def test_volume_for_trade_falls_back_to_condition_id_lookup(monkeypatch):
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse([{"conditionId": "0xc", "volume24hr": 1234.0}]))
    cache = wc.GammaVolumeCache(limit=10)
    cache.refresh()
    assert cache.volume_for_trade({"conditionId": "0xc"}) == pytest.approx(1234.0)
    assert cache.volume_for_trade({"conditionId": "0xunknown"}) is None


def test_save_trade_uses_the_cache_to_flag_a_thin_market_whale(temp_db, monkeypatch):
    """End to end: RTDS frame carries no volume, the cache supplies it."""
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse([{"conditionId": "0xcond", "volume24hr": 20_000.0}]))
    cache = wc.GammaVolumeCache(limit=10)
    cache.refresh()

    wc.init_database(temp_db)
    frame = _trade(size=800, price=0.5, conditionId="0xcond")  # $400, no volume field
    assert wc.extract_market_volume_24h(frame) is None
    assert wc.save_trade(frame, min_usd=1000.0, db_path=temp_db, volume_cache=cache) is True


def test_cache_miss_falls_back_to_absolute_rule(temp_db, monkeypatch):
    monkeypatch.setattr(wc.requests, "get", lambda url, **kw: _CacheResponse([]))
    cache = wc.GammaVolumeCache(limit=10)
    cache.refresh()

    wc.init_database(temp_db)
    frame = _trade(size=800, price=0.5, conditionId="0xnotcached")
    assert wc.save_trade(frame, min_usd=1000.0, db_path=temp_db, volume_cache=cache) is False


def test_volume_cache_background_thread_starts_and_stops(monkeypatch):
    monkeypatch.setattr(wc.requests, "get",
                        lambda url, **kw: _CacheResponse([{"conditionId": "0x1", "volume24hr": 1.0}]))
    cache = wc.GammaVolumeCache(limit=10, refresh_seconds=0.01)
    cache.start()
    try:
        assert cache._thread is not None and cache._thread.is_alive()
        assert cache._thread.daemon, "must not block interpreter shutdown"
    finally:
        cache.stop()


# ---------------------------------------------------------------------------
# Wallet address normalisation
# ---------------------------------------------------------------------------

def test_wallet_address_casing_is_normalised():
    checksummed = "0xC69Bd5567b40ef4d11922Eaa57E1F9BE1c642076"
    assert wc.normalize_wallet(checksummed) == checksummed.lower()
    assert wc.normalize_wallet("  0xABC  ") == "0xabc"
    assert wc.normalize_wallet(None) == ""


def test_same_wallet_in_two_casings_is_one_tracked_row(temp_db):
    """
    Regression guard: REST returns lowercase addresses and the RTDS socket
    returns EIP-55 checksummed ones. Un-normalised, one trader became two rows
    and was counted twice on the leaderboard.
    """
    wc.init_database(temp_db)
    lower = "0xc69bd5567b40ef4d11922eaa57e1f9be1c642076"
    checksummed = "0xC69Bd5567b40ef4d11922Eaa57E1F9BE1c642076"

    wc.save_trade(_trade(transactionHash="0x1", proxyWallet=lower), db_path=temp_db)
    wc.save_trade(_trade(transactionHash="0x2", proxyWallet=checksummed), db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    rows = conn.execute("SELECT wallet, trade_count FROM tracked_wallets").fetchall()
    conn.close()

    assert rows == [(lower, 2)]


# ---------------------------------------------------------------------------
# replay_fixture (--replay)
# ---------------------------------------------------------------------------

def test_replay_fixture_runs_offline_and_reports_counts(temp_db):
    summary = wc.replay_fixture(min_usd=1000.0, db_path=temp_db, quiet=True)

    assert summary["frames"] > 0
    assert summary["whales"] > 0
    assert summary["frames"] == summary["whales"] + summary["skipped"]
    # First run into an empty DB: every whale is newly stored.
    assert summary["stored"] == summary["whales"]

    conn = sqlite3.connect(temp_db)
    stored = conn.execute("SELECT COUNT(*) FROM whale_trades").fetchone()[0]
    conn.close()
    assert stored == summary["whales"]


def test_replay_fixture_respects_min_usd_threshold(temp_db):
    low = wc.replay_fixture(min_usd=1.0, db_path=temp_db, quiet=True)
    high = wc.replay_fixture(min_usd=100_000.0, db_path=temp_db, quiet=True)
    assert low["whales"] > high["whales"]


def test_replay_fixture_is_repeatable(temp_db):
    """Replaying twice must not duplicate rows -- tx_hash is unique."""
    first = wc.replay_fixture(min_usd=1000.0, db_path=temp_db, quiet=True)
    wc.replay_fixture(min_usd=1000.0, db_path=temp_db, quiet=True)

    conn = sqlite3.connect(temp_db)
    stored = conn.execute("SELECT COUNT(*) FROM whale_trades").fetchone()[0]
    conn.close()
    assert stored == first["whales"]


def test_replay_reports_whales_even_when_already_stored(temp_db):
    """
    Regression guard: a second replay stores nothing new, but must still report
    how many whales the fixture holds -- otherwise it reads as "0 whales found".
    """
    first = wc.replay_fixture(min_usd=1000.0, db_path=temp_db, quiet=True)
    second = wc.replay_fixture(min_usd=1000.0, db_path=temp_db, quiet=True)

    assert second["whales"] == first["whales"] > 0
    assert second["stored"] == 0


def test_replay_defaults_to_separate_db_from_live_collection():
    """Replay must not pollute the live collector's database."""
    assert wc.REPLAY_DB_PATH != wc.DB_PATH


# ---------------------------------------------------------------------------
# Cloudflare keepalive
# ---------------------------------------------------------------------------

class FakeWebSocket:
    """Minimal stand-in that records what the keepalive sends."""

    def __init__(self, fail_after=None):
        self.sent = []
        self.fail_after = fail_after

    async def send(self, message):
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise ConnectionError("socket closed")
        self.sent.append(message)


def test_keepalive_interval_is_20_seconds():
    """Cloudflare drops idle sockets; the agreed cadence is 20s."""
    assert wc.PING_INTERVAL_SECONDS == 20


def test_ws_keepalive_sends_ping_frames_on_interval():
    async def scenario():
        ws = FakeWebSocket()
        task = asyncio.create_task(wc.ws_keepalive(ws, interval=0.01))
        await asyncio.sleep(0.055)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return ws.sent

    sent = asyncio.run(scenario())
    assert len(sent) >= 3, f"expected repeated pings, got {sent}"
    assert set(sent) == {"PING"}


def test_ws_keepalive_exits_quietly_when_socket_dies():
    """A dead socket must not raise out of the keepalive task."""
    async def scenario():
        ws = FakeWebSocket(fail_after=1)
        await asyncio.wait_for(wc.ws_keepalive(ws, interval=0.01), timeout=2.0)
        return ws.sent

    sent = asyncio.run(scenario())
    assert sent == ["PING"]


def test_ws_keepalive_waits_before_first_ping():
    """It must sleep first, so it never races the subscribe frame."""
    async def scenario():
        ws = FakeWebSocket()
        task = asyncio.create_task(wc.ws_keepalive(ws, interval=5.0))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return ws.sent

    assert asyncio.run(scenario()) == []
