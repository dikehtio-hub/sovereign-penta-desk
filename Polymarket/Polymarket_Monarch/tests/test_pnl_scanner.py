"""
Tests for pnl_scanner.py: the realized/unrealized PnL engine and the Cloudflare
rate limiter.
"""

import time

import pytest

import pnl_scanner as ps


NOW = 1_788_054_510
DAY = 24 * 3600


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The 200ms floor is process-global; reset it between tests."""
    ps._last_request_at = 0.0
    yield
    ps._last_request_at = 0.0


# ---------------------------------------------------------------------------
# compute_pnl_metrics -- realized side (/closed-positions)
# ---------------------------------------------------------------------------

def test_realized_pnl_sums_closed_positions_in_window():
    closed = [
        {"realizedPnl": 500.0, "totalBought": 1000.0, "timestamp": NOW - DAY},
        {"realizedPnl": 250.0, "totalBought": 800.0, "timestamp": NOW - 3 * DAY},
    ]
    m = ps.compute_pnl_metrics("0xw", closed, [], [], now=NOW)
    assert m["realized_pnl_7d"] == 750.0


def test_realized_pnl_excludes_positions_older_than_7_days():
    closed = [
        {"realizedPnl": 100.0, "timestamp": NOW - 2 * DAY},
        {"realizedPnl": 9999.0, "timestamp": NOW - 30 * DAY},   # outside window
    ]
    m = ps.compute_pnl_metrics("0xw", closed, [], [], now=NOW)
    assert m["realized_pnl_7d"] == 100.0
    assert m["closed_positions_7d"] == 1


def test_win_rate_counts_only_profitable_closed_positions():
    closed = [
        {"realizedPnl": 100.0, "timestamp": NOW},
        {"realizedPnl": -50.0, "timestamp": NOW},
        {"realizedPnl": 25.0, "timestamp": NOW},
        {"realizedPnl": -10.0, "timestamp": NOW},
    ]
    m = ps.compute_pnl_metrics("0xw", closed, [], [], now=NOW)
    assert m["win_rate"] == 50.0


# ---------------------------------------------------------------------------
# compute_pnl_metrics -- unrealized side (/positions)
# ---------------------------------------------------------------------------

def test_unrealized_pnl_uses_cash_pnl():
    open_pos = [
        {"cashPnl": -22745.83, "currentValue": 107089.32, "initialValue": 129835.14},
    ]
    m = ps.compute_pnl_metrics("0xw", [], open_pos, [], now=NOW)
    assert m["unrealized_pnl"] == pytest.approx(-22745.83)
    assert m["open_exposure"] == pytest.approx(107089.32)
    assert m["open_positions"] == 1


def test_unrealized_pnl_falls_back_to_value_difference():
    """Older rows omit cashPnl; derive it from currentValue - initialValue."""
    open_pos = [{"currentValue": 1500.0, "initialValue": 1000.0}]
    m = ps.compute_pnl_metrics("0xw", [], open_pos, [], now=NOW)
    assert m["unrealized_pnl"] == pytest.approx(500.0)


def test_headline_pnl_is_realized_plus_unrealized():
    closed = [{"realizedPnl": 1000.0, "timestamp": NOW}]
    open_pos = [{"cashPnl": -400.0, "currentValue": 100.0}]
    m = ps.compute_pnl_metrics("0xw", closed, open_pos, [], now=NOW)
    assert m["pnl_7d"] == pytest.approx(600.0)
    assert m["realized_pnl_7d"] == 1000.0
    assert m["unrealized_pnl"] == -400.0


# ---------------------------------------------------------------------------
# compute_pnl_metrics -- volume and trade count (/activity)
# ---------------------------------------------------------------------------

def test_volume_sums_usdc_size_of_trades_in_window():
    activity = [
        {"type": "TRADE", "usdcSize": 1547.07, "timestamp": NOW - 1000},
        {"type": "TRADE", "usdcSize": 452.93, "timestamp": NOW - 2000},
    ]
    m = ps.compute_pnl_metrics("0xw", [], [], activity, now=NOW)
    assert m["volume_7d"] == pytest.approx(2000.0)
    assert m["trades_7d"] == 2


def test_non_trade_activity_is_not_counted_as_volume():
    """REDEEM / SPLIT / MERGE / REWARD are not fills."""
    activity = [
        {"type": "TRADE", "usdcSize": 100.0, "timestamp": NOW},
        {"type": "REDEEM", "usdcSize": 5000.0, "timestamp": NOW},
        {"type": "SPLIT", "usdcSize": 2000.0, "timestamp": NOW},
        {"type": "MERGE", "usdcSize": 3000.0, "timestamp": NOW},
    ]
    m = ps.compute_pnl_metrics("0xw", [], [], activity, now=NOW)
    assert m["volume_7d"] == pytest.approx(100.0)
    assert m["trades_7d"] == 1


def test_activity_outside_window_is_ignored():
    activity = [
        {"type": "TRADE", "usdcSize": 100.0, "timestamp": NOW - 2 * DAY},
        {"type": "TRADE", "usdcSize": 999.0, "timestamp": NOW - 10 * DAY},
    ]
    m = ps.compute_pnl_metrics("0xw", [], [], activity, now=NOW)
    assert m["volume_7d"] == pytest.approx(100.0)
    assert m["trades_7d"] == 1


def test_volume_falls_back_to_total_bought_when_activity_missing():
    closed = [{"realizedPnl": 10.0, "totalBought": 2500.0, "timestamp": NOW}]
    m = ps.compute_pnl_metrics("0xw", closed, [], [], now=NOW)
    assert m["volume_7d"] == pytest.approx(2500.0)
    assert m["trades_7d"] == 1  # falls back to closed position count


# ---------------------------------------------------------------------------
# compute_pnl_metrics -- edge cases
# ---------------------------------------------------------------------------

def test_returns_none_when_wallet_has_no_data():
    assert ps.compute_pnl_metrics("0xw", [], [], [], now=NOW) is None


def test_malformed_numeric_fields_do_not_crash():
    closed = [{"realizedPnl": None, "timestamp": NOW}]
    open_pos = [{"cashPnl": "", "currentValue": "not-a-number"}]
    activity = [{"type": "TRADE", "usdcSize": None, "timestamp": NOW}]
    m = ps.compute_pnl_metrics("0xw", closed, open_pos, activity, now=NOW)
    assert m["pnl_7d"] == 0.0


def test_pseudonym_prefers_activity_handle_over_address():
    activity = [{"type": "TRADE", "timestamp": NOW, "pseudonym": "Large-Peach"}]
    m = ps.compute_pnl_metrics("0xw", [], [], activity, now=NOW)
    assert m["pseudonym"] == "Large-Peach"


def test_pseudonym_ignores_raw_address_names():
    activity = [{"type": "TRADE", "timestamp": NOW, "name": "0xabc123", "pseudonym": "Anonymous"}]
    m = ps.compute_pnl_metrics("0xw", [], [], activity, now=NOW)
    assert m["pseudonym"] == "Anonymous"


# ---------------------------------------------------------------------------
# _rate_limited_get -- Cloudflare protection
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_request_interval_is_200ms():
    assert ps.REQUEST_INTERVAL_SECONDS == 0.2


def test_rate_limiter_enforces_200ms_between_requests(monkeypatch):
    stamps = []

    def fake_get(url, **kwargs):
        stamps.append(time.time())
        return FakeResponse()

    monkeypatch.setattr(ps.requests, "get", fake_get)

    for _ in range(3):
        ps._rate_limited_get("https://example.test/x")

    assert len(stamps) == 3
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    for gap in gaps:
        assert gap >= 0.19, f"requests fired {gap:.3f}s apart, below the 200ms floor"


def test_rate_limiter_retries_after_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(status_code=429, headers={"Retry-After": "0"})
        return FakeResponse(status_code=200, payload=[{"ok": True}])

    monkeypatch.setattr(ps.requests, "get", fake_get)

    resp = ps._rate_limited_get("https://example.test/x")
    assert resp is not None
    assert resp.json() == [{"ok": True}]
    assert calls["n"] == 2


def test_rate_limiter_gives_up_after_persistent_429(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        return FakeResponse(status_code=429, headers={"Retry-After": "0"})

    monkeypatch.setattr(ps.requests, "get", fake_get)

    assert ps._rate_limited_get("https://example.test/x") is None
    assert calls["n"] == ps.MAX_RETRIES


def test_rate_limiter_does_not_retry_client_errors(monkeypatch):
    """A 404 is not a throttle -- retrying just burns the rate budget."""
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        return FakeResponse(status_code=404)

    monkeypatch.setattr(ps.requests, "get", fake_get)

    assert ps._rate_limited_get("https://example.test/x") is None
    assert calls["n"] == 1


def test_rate_limiter_survives_connection_errors(monkeypatch):
    def fake_get(url, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(ps.requests, "get", fake_get)
    assert ps._rate_limited_get("https://example.test/x") is None


# ---------------------------------------------------------------------------
# Fetchers hit the endpoints Antigravity verified
# ---------------------------------------------------------------------------

def test_fetchers_target_the_documented_endpoints(monkeypatch):
    seen = []

    def fake_get(url, **kwargs):
        seen.append((url, kwargs.get("params", {})))
        return FakeResponse(payload=[])

    monkeypatch.setattr(ps.requests, "get", fake_get)

    ps.fetch_wallet_closed_positions("0xdead")
    ps.fetch_wallet_open_positions("0xdead")
    ps.fetch_wallet_activity("0xdead")

    urls = [u for u, _ in seen]
    assert "https://data-api.polymarket.com/closed-positions" in urls
    assert "https://data-api.polymarket.com/positions" in urls
    assert "https://data-api.polymarket.com/activity" in urls
    for _, params in seen:
        assert params.get("user") == "0xdead"


def test_activity_fetcher_pages_until_exhausted(monkeypatch):
    """An active whale exceeds one page well inside 7 days."""
    pages = [
        [{"type": "TRADE", "usdcSize": 1.0}] * 100,   # full page -> keep going
        [{"type": "TRADE", "usdcSize": 1.0}] * 20,    # short page -> stop
    ]
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        idx = calls["n"]
        calls["n"] += 1
        return FakeResponse(payload=pages[idx] if idx < len(pages) else [])

    monkeypatch.setattr(ps.requests, "get", fake_get)

    records = ps.fetch_wallet_activity("0xdead", limit=100)
    assert len(records) == 120
    assert calls["n"] == 2


def test_data_api_wrapper_shape_is_tolerated(monkeypatch):
    monkeypatch.setattr(ps.requests, "get", lambda url, **kw: FakeResponse(payload={"data": [{"a": 1}]}))
    assert ps.fetch_wallet_open_positions("0xdead") == [{"a": 1}]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_sharp_trader_row_persists_realized_and_unrealized(tmp_path, monkeypatch):
    db = tmp_path / "pnl.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)

    metrics = ps.compute_pnl_metrics(
        "0xw",
        [{"realizedPnl": 800.0, "timestamp": NOW}],
        [{"cashPnl": 150.0, "currentValue": 900.0}],
        [{"type": "TRADE", "usdcSize": 1200.0, "timestamp": NOW}],
        now=NOW,
    )
    ps.save_sharp_trader(metrics, min_sharp_pnl=300.0)

    conn = ps.get_db_connection(db)
    row = conn.execute("SELECT * FROM sharp_traders WHERE wallet='0xw'").fetchone()
    conn.close()

    assert row["realized_pnl_7d"] == 800.0
    assert row["unrealized_pnl"] == 150.0
    assert row["pnl_7d"] == 950.0
    assert row["is_sharp"] == 1


def _header_row(rendered: str) -> str:
    """
    The table's column-header line.

    Assertions must not run against the whole capture: the caption describes the
    columns in prose ("ROI% = 7D Realized / 7D Volume"), so a naive substring
    check would pass even when the column is absent.
    """
    for line in rendered.splitlines():
        if "Trader" in line:
            return line
    return ""


def test_pnl_basis_note_states_ranking_and_mixed_period():
    """The note must say what the board is ranked by AND why Est. PnL is mixed."""
    note = ps.PNL_BASIS_NOTE.lower()
    assert "ranked by 7d realized" in note
    assert "unrealized" in note
    assert "lifetime-to-date" in note


def test_leaderboard_headline_is_labelled_estimate(tmp_path, monkeypatch, capsys):
    """
    Regression guard: the column must not claim to be a clean "7D Net PnL" when
    half of it is lifetime-to-date on open positions.
    """
    from rich.console import Console

    db = tmp_path / "label.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)
    ps.save_sharp_trader(
        ps.compute_pnl_metrics(
            "0xw",
            [{"realizedPnl": 800.0, "timestamp": NOW}],
            [{"cashPnl": 150.0, "currentValue": 900.0}],
            [{"type": "TRADE", "usdcSize": 1200.0, "timestamp": NOW}],
            now=NOW,
        ),
        db_path=db,
    )

    monkeypatch.setattr(ps, "console", Console(width=80, force_terminal=False))
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0)
    out = cap.get()

    assert "Est. PnL" in out
    assert "7D Realized" in out
    assert "7D Net PnL" not in out


def test_leaderboard_splits_realized_and_unrealized_on_wide_terminals(tmp_path, monkeypatch):
    from rich.console import Console

    db = tmp_path / "wide.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)
    ps.save_sharp_trader(
        ps.compute_pnl_metrics(
            "0xw",
            [{"realizedPnl": 800.0, "timestamp": NOW}],
            [{"cashPnl": 150.0, "currentValue": 900.0}],
            [{"type": "TRADE", "usdcSize": 1200.0, "timestamp": NOW}],
            now=NOW,
        ),
        db_path=db,
    )

    monkeypatch.setattr(ps, "console", Console(width=140, force_terminal=False))
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0)
    wide_out = cap.get()

    monkeypatch.setattr(ps, "console", Console(width=80, force_terminal=False))
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0)
    narrow_out = cap.get()

    # Check the HEADER ROW, not the whole render: the caption explains the
    # columns in prose and would otherwise satisfy every substring check.
    wide_header = _header_row(wide_out)
    narrow_header = _header_row(narrow_out)

    assert "7D Realized" in wide_header and "Open Unreal" in wide_header
    # 7D Realized is the ranking key and Open Unreal. its context, so both
    # survive at 80 columns. What yields is everything derivable or optional:
    # the wallet address, 7d volume, the profile URL, and Est. PnL -- which is
    # just the sum of the two columns already on screen.
    assert "7D Realized" in narrow_header
    assert "Open Unreal" in narrow_header
    assert "Wallet" in wide_header and "Wallet" not in narrow_header
    assert "7D Volume" in wide_header and "7D Volume" not in narrow_header
    assert "Est. PnL" in wide_header and "Est. PnL" not in narrow_header


# ---------------------------------------------------------------------------
# Leaderboard ranks on 7d REALIZED, not the blended figure
# ---------------------------------------------------------------------------

def _seed(db, monkeypatch, wallets):
    """wallets: (name, realized, unrealized) -> rows in sharp_traders."""
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)
    for name, realized, unrealized in wallets:
        ps.save_sharp_trader({
            "wallet": name,
            "pseudonym": name,
            "pnl_7d": round(realized + unrealized, 2),
            "realized_pnl_7d": realized,
            "unrealized_pnl": unrealized,
            "volume_7d": 1000.0,
            "trades_7d": 10,
            "open_positions": 1,
            "win_rate": 50.0,
            "polymarket_link": f"https://polymarket.com/profile/{name}",
        }, db_path=db)


def _board(monkeypatch, width=140):
    from rich.console import Console
    monkeypatch.setattr(ps, "console", Console(width=width, force_terminal=False))
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0)
    return cap.get()


def test_dormant_wallet_cannot_outrank_an_active_winner(tmp_path, monkeypatch):
    """
    The core accounting flaw: a wallet with no realized profit this week but a
    big paper gain on an old open bet used to sit at #1.
    """
    db = tmp_path / "rank.db"
    _seed(db, monkeypatch, [
        ("dormant", 0.0, 500_000.0),      # blended $500k, banked nothing
        ("active", 25_000.0, -38_000.0),  # banked $25k, open book underwater
    ])
    out = _board(monkeypatch)
    assert "active" in out
    # It does not merely rank below the active winner -- with zero realized it
    # fails the sharp filter outright.
    assert "dormant" not in out


def test_dormant_wallet_is_filtered_out_entirely(tmp_path, monkeypatch):
    """Zero realized means it never qualifies as sharp, however big the paper gain."""
    db = tmp_path / "filter.db"
    _seed(db, monkeypatch, [("dormant", 0.0, 500_000.0)])
    assert "dormant" not in _board(monkeypatch)


def test_profitable_wallet_with_underwater_open_book_is_included(tmp_path, monkeypatch):
    """
    Regression guard: filtering on the blended figure hid real 7d winners whose
    open positions happened to be marked down.
    """
    db = tmp_path / "included.db"
    _seed(db, monkeypatch, [("winner", 25_000.0, -38_000.0)])  # blended is NEGATIVE
    out = _board(monkeypatch)
    assert "winner" in out


def test_board_is_ordered_by_realized_descending(tmp_path, monkeypatch):
    db = tmp_path / "order.db"
    _seed(db, monkeypatch, [
        ("alpha", 5_000.0, 0.0),
        ("bravo", 50_000.0, -900_000.0),   # worst blended, best realized
        ("charlie", 500.0, 900_000.0),     # best blended, worst realized
    ])
    out = _board(monkeypatch)
    assert out.index("bravo") < out.index("alpha") < out.index("charlie")


def test_is_sharp_flag_tracks_realized_not_blended(tmp_path, monkeypatch):
    db = tmp_path / "sharp.db"
    _seed(db, monkeypatch, [
        ("banked", 1_000.0, -50_000.0),    # blended deeply negative
        ("paper", 10.0, 50_000.0),         # blended large positive
    ])
    conn = ps.get_db_connection(db)
    flags = dict(conn.execute("SELECT wallet, is_sharp FROM sharp_traders").fetchall())
    conn.close()
    assert flags["banked"] == 1
    assert flags["paper"] == 0


def test_unrealized_stays_visible_for_context(tmp_path, monkeypatch):
    """Ranking on realized must not hide the open book behind it."""
    db = tmp_path / "context.db"
    _seed(db, monkeypatch, [("winner", 25_000.0, -38_000.0)])
    for width in (80, 140):
        out = _board(monkeypatch, width=width)
        assert "Open Unreal" in out
        assert "-$38.0K" in out


# ---------------------------------------------------------------------------
# Win rate: "no settled positions" is not a 0% record
# ---------------------------------------------------------------------------

def test_win_rate_dashed_when_nothing_resolved_in_window():
    """
    Regression guard: a wallet holding only open positions resolves nothing, so
    win_rate falls out as 0.0. Printing "0%" reads as "lost every trade".
    """
    assert ps.format_win_rate(0.0, 0) == ps.NO_DATA_DASH
    assert ps.format_win_rate(0.0, None) == ps.NO_DATA_DASH


def test_win_rate_zero_is_shown_when_positions_did_resolve():
    """A genuine 0% record must still read as 0%, not a dash."""
    assert ps.format_win_rate(0.0, 4) == "0%"


def test_win_rate_renders_normally_with_closed_positions():
    assert ps.format_win_rate(100.0, 3) == "100%"
    assert ps.format_win_rate(66.6, 3) == "67%"


def test_win_rate_dash_survives_a_legacy_console():
    ps.NO_DATA_DASH.encode("cp1252")


def test_win_rate_dashes_on_malformed_input():
    assert ps.format_win_rate(None, 3) == ps.NO_DATA_DASH
    assert ps.format_win_rate("n/a", 3) == ps.NO_DATA_DASH


def test_metrics_expose_closed_position_count_for_the_dash_decision():
    open_only = ps.compute_pnl_metrics(
        "0xw", [], [{"cashPnl": 100.0, "currentValue": 500.0}],
        [{"type": "TRADE", "usdcSize": 50.0, "timestamp": NOW}], now=NOW)
    assert open_only["closed_positions_7d"] == 0
    assert open_only["win_rate"] == 0.0  # raw metric stays numeric...
    assert ps.format_win_rate(open_only["win_rate"],
                              open_only["closed_positions_7d"]) == ps.NO_DATA_DASH


def test_closed_position_count_is_persisted(tmp_path, monkeypatch):
    """The display cannot make the dash decision unless the count is stored."""
    db = tmp_path / "closed.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)
    ps.save_sharp_trader(ps.compute_pnl_metrics(
        "0xw", [{"realizedPnl": 500.0, "timestamp": NOW}], [], [], now=NOW), db_path=db)

    conn = ps.get_db_connection(db)
    row = conn.execute("SELECT closed_positions_7d FROM sharp_traders").fetchone()
    conn.close()
    assert row["closed_positions_7d"] == 1


# ---------------------------------------------------------------------------
# ROI%
# ---------------------------------------------------------------------------

def test_roi_is_realized_over_volume():
    assert ps.compute_roi(5_000.0, 10_000.0) == pytest.approx(50.0)
    assert ps.compute_roi(5_000.0, 500_000.0) == pytest.approx(1.0)


def test_roi_is_zero_without_volume():
    assert ps.compute_roi(5_000.0, 0.0) == 0.0
    assert ps.compute_roi(5_000.0, None) == 0.0


def test_roi_handles_losses():
    assert ps.compute_roi(-250.0, 1_000.0) == pytest.approx(-25.0)


def test_roi_separates_edge_from_bankroll():
    """The whole point: same profit, very different traders."""
    sharp = ps.compute_roi(5_000.0, 10_000.0)
    grinder = ps.compute_roi(5_000.0, 5_000_000.0)
    assert sharp > grinder * 100


def test_roi_withheld_when_activity_was_truncated():
    """
    Regression guard: a wallet at the /activity paging cap has a PARTIAL volume
    sum. Live data produced +2,576,423% from a $5 denominator against $132k
    realized -- the denominator was truncated, not the trader superhuman.
    """
    metrics = ps.compute_pnl_metrics(
        "0xw",
        [{"realizedPnl": 132_686.0, "timestamp": NOW}],
        [],
        [{"type": "TRADE", "usdcSize": 5.0, "timestamp": NOW}],
        now=NOW,
        activity_truncated=True,
    )
    assert metrics["volume_is_partial"] is True
    assert metrics["roi_7d"] is None
    assert ps.format_roi(metrics["roi_7d"]) == ps.NO_DATA_DASH


def test_roi_reported_when_activity_was_complete():
    metrics = ps.compute_pnl_metrics(
        "0xw",
        [{"realizedPnl": 500.0, "timestamp": NOW}],
        [],
        [{"type": "TRADE", "usdcSize": 1_000.0, "timestamp": NOW}],
        now=NOW,
        activity_truncated=False,
    )
    assert metrics["volume_is_partial"] is False
    assert metrics["roi_7d"] == pytest.approx(50.0)


def test_large_roi_is_abbreviated_so_it_cannot_overflow_its_column():
    assert ps.format_roi(2_576_423.0).count("k%") == 1
    # Rendered width must stay inside the 8-wide column.
    import re
    plain = re.sub(r"\[/?[^\]]+\]", "", ps.format_roi(2_576_423.0))
    assert len(plain) <= 8


def test_format_roi_dashes_on_missing_or_bad_values():
    assert ps.format_roi(None) == ps.NO_DATA_DASH
    assert ps.format_roi("n/a") == ps.NO_DATA_DASH


# ---------------------------------------------------------------------------
# --sort modes
# ---------------------------------------------------------------------------

def test_sort_modes_cover_the_documented_choices():
    assert set(ps.SORT_MODES) == {"realized", "roi", "volume"}


def test_sort_by_roi_orders_by_return_not_size(tmp_path, monkeypatch):
    db = tmp_path / "roisort.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)
    # big: huge profit on huge turnover (low ROI). small: modest profit, tiny turnover.
    for name, realized, volume in [("big", 100_000.0, 10_000_000.0), ("small", 1_000.0, 2_000.0)]:
        ps.save_sharp_trader({
            "wallet": name, "pseudonym": name, "pnl_7d": realized,
            "realized_pnl_7d": realized, "unrealized_pnl": 0.0, "volume_7d": volume,
            "trades_7d": 10, "open_positions": 0, "closed_positions_7d": 5,
            "volume_is_partial": False, "win_rate": 50.0,
            "polymarket_link": f"https://polymarket.com/profile/{name}",
        }, db_path=db)

    from rich.console import Console
    monkeypatch.setattr(ps, "console", Console(width=150, force_terminal=False))

    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0, sort_by="realized")
    by_realized = cap.get()
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0, sort_by="roi")
    by_roi = cap.get()

    assert by_realized.index("big") < by_realized.index("small")
    assert by_roi.index("small") < by_roi.index("big")


def test_sort_by_roi_demotes_partial_volume_rows(tmp_path, monkeypatch):
    """An inflated ratio from a truncated divisor must not lead the board."""
    db = tmp_path / "partial.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)
    for name, realized, volume, partial in [
        ("truncated", 132_000.0, 5.0, True),     # absurd ratio, bad denominator
        ("genuine", 18_000.0, 1_800.0, False),   # real 1000% ROI
    ]:
        ps.save_sharp_trader({
            "wallet": name, "pseudonym": name, "pnl_7d": realized,
            "realized_pnl_7d": realized, "unrealized_pnl": 0.0, "volume_7d": volume,
            "trades_7d": 500, "open_positions": 0, "closed_positions_7d": 5,
            "volume_is_partial": partial, "win_rate": 50.0,
            "polymarket_link": f"https://polymarket.com/profile/{name}",
        }, db_path=db)

    from rich.console import Console
    monkeypatch.setattr(ps, "console", Console(width=150, force_terminal=False))
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0, sort_by="roi")
    out = cap.get()
    assert out.index("genuine") < out.index("truncated")


def test_unknown_sort_mode_falls_back_to_realized(tmp_path, monkeypatch):
    """An unrecognised mode must not reach the SQL or blank the board."""
    db = tmp_path / "badsort.db"
    _seed(db, monkeypatch, [("alpha", 5_000.0, 0.0), ("bravo", 9_000.0, 0.0)])

    from rich.console import Console
    monkeypatch.setattr(ps, "console", Console(width=150, force_terminal=False))
    with ps.console.capture() as cap:
        ps.display_sharp_traders_table(min_pnl=300.0, sort_by="not-a-mode")
    out = cap.get()

    assert "sorted by 7D Realized" in out
    assert out.index("bravo") < out.index("alpha")


def test_roi_column_appears_only_on_wide_terminals(tmp_path, monkeypatch):
    db = tmp_path / "roiwidth.db"
    _seed(db, monkeypatch, [("winner", 5_000.0, 0.0)])
    assert "ROI%" not in _header_row(_board(monkeypatch, width=120))
    assert "ROI%" in _header_row(_board(monkeypatch, width=136))


# ---------------------------------------------------------------------------
# Wallet address normalisation
# ---------------------------------------------------------------------------

def test_normalize_wallet_lowercases():
    assert ps.normalize_wallet("0xC69Bd5567B40") == "0xc69bd5567b40"


def test_scanner_persists_wallet_lowercased(tmp_path, monkeypatch):
    db = tmp_path / "norm.db"
    monkeypatch.setattr(ps, "DB_PATH", db)
    ps.init_pnl_tables(db)

    metrics = ps.compute_pnl_metrics(
        "0xC69Bd5567b40ef4d11922Eaa57E1F9BE1c642076",
        [{"realizedPnl": 500.0, "timestamp": NOW}], [], [], now=NOW,
    )
    ps.save_sharp_trader(metrics, db_path=db)

    conn = ps.get_db_connection(db)
    wallet = conn.execute("SELECT wallet FROM sharp_traders").fetchone()[0]
    conn.close()
    assert wallet == "0xc69bd5567b40ef4d11922eaa57e1f9be1c642076"


def test_migration_merges_duplicate_wallet_casings(tmp_path):
    """One trader stored under two casings must collapse into a single row."""
    import sqlite3

    db = tmp_path / "dupes.db"
    lower = "0xc69bd5567b40ef4d11922eaa57e1f9be1c642076"
    upper = "0xC69Bd5567b40ef4d11922Eaa57E1F9BE1c642076"

    ps.init_pnl_tables(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO sharp_traders (wallet, pseudonym, pnl_7d, last_scanned) "
        "VALUES (?, 'Ultimate-Underpass', 132683.42, '2026-08-29 01:00:00')", (lower,))
    conn.execute(
        "INSERT INTO sharp_traders (wallet, pseudonym, pnl_7d, last_scanned) "
        "VALUES (?, 'Ultimate-Underpass', 132683.42, '2026-08-29 02:00:00')", (upper,))
    conn.execute(
        "INSERT INTO tracked_wallets (wallet, pseudonym, first_seen, last_seen, "
        "trade_count, total_volume_usd) VALUES (?, 'Ultimate-Underpass', 100, 200, 3, 500.0)",
        (lower,))
    conn.execute(
        "INSERT INTO tracked_wallets (wallet, pseudonym, first_seen, last_seen, "
        "trade_count, total_volume_usd) VALUES (?, 'Ultimate-Underpass', 150, 300, 4, 700.0)",
        (upper,))
    conn.commit()
    conn.close()

    ps.init_pnl_tables(db)  # runs the merge

    conn = sqlite3.connect(db)
    sharp = conn.execute("SELECT wallet FROM sharp_traders").fetchall()
    tracked = conn.execute(
        "SELECT wallet, first_seen, last_seen, trade_count, total_volume_usd FROM tracked_wallets"
    ).fetchall()
    conn.close()

    assert sharp == [(lower,)]
    # Counters are additive, and the seen-window spans both rows.
    assert tracked == [(lower, 100, 300, 7, 1200.0)]


def test_migration_is_idempotent_and_leaves_clean_data_alone(tmp_path):
    import sqlite3

    db = tmp_path / "clean.db"
    ps.init_pnl_tables(db)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO sharp_traders (wallet, pnl_7d) VALUES ('0xaaa', 1.0)")
    conn.execute("INSERT INTO sharp_traders (wallet, pnl_7d) VALUES ('0xbbb', 2.0)")
    conn.commit()
    conn.close()

    ps.init_pnl_tables(db)
    ps.init_pnl_tables(db)

    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT wallet FROM sharp_traders ORDER BY wallet").fetchall()
    conn.close()
    assert rows == [("0xaaa",), ("0xbbb",)]


def test_schema_migration_adds_columns_to_legacy_database(tmp_path):
    """An existing pre-upgrade DB must gain the new columns in place."""
    import sqlite3

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE sharp_traders (
            wallet TEXT PRIMARY KEY, pseudonym TEXT, pnl_7d REAL, volume_7d REAL,
            trades_7d INTEGER, win_rate REAL, is_sharp BOOLEAN DEFAULT 1,
            polymarket_link TEXT, last_scanned TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO sharp_traders (wallet, pnl_7d) VALUES ('0xold', 42.0)")
    conn.commit()
    conn.close()

    ps.init_pnl_tables(db)

    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sharp_traders)")}
    preserved = conn.execute("SELECT pnl_7d FROM sharp_traders WHERE wallet='0xold'").fetchone()[0]
    conn.close()

    assert {"realized_pnl_7d", "unrealized_pnl", "open_positions"} <= cols
    assert preserved == 42.0  # migration must not drop existing rows
