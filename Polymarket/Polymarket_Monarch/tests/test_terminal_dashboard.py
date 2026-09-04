"""
Tests for terminal_dashboard.py: tag-driven Gamma macro fetching and
Windows-safe console output.
"""

import json

import pytest

import terminal_dashboard as td


# ---------------------------------------------------------------------------
# Gamma tag querying
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload


def test_macro_categories_cover_the_three_required_tags():
    keys = [c[0] for c in td.MACRO_CATEGORIES]
    assert keys == ["crypto", "politics", "economics"]


def test_gamma_query_uses_tag_slug_not_tag(monkeypatch):
    """
    Regression guard: Gamma's /events silently ignores `tag=`, returning the
    same unfiltered feed for every category. Only `tag_slug=` actually filters.
    """
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params", {})
        return FakeResponse(payload=[])

    monkeypatch.setattr(td.requests, "get", fake_get)
    td.fetch_top_markets_by_tag("crypto")

    assert captured["url"] == "https://gamma-api.polymarket.com/events"
    assert captured["params"]["tag_slug"] == "crypto"
    assert "tag" not in captured["params"]


def test_gamma_query_requests_top_24h_volume_first(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs.get("params", {}))
        return FakeResponse(payload=[])

    monkeypatch.setattr(td.requests, "get", fake_get)
    td.fetch_top_markets_by_tag("politics")

    assert captured["order"] == "volume24hr"
    assert captured["ascending"] == "false"
    assert captured["active"] == "true"
    assert captured["closed"] == "false"


def test_gamma_failure_degrades_to_empty_list(monkeypatch):
    monkeypatch.setattr(td.requests, "get", lambda *a, **k: FakeResponse(status_code=503))
    assert td.fetch_top_markets_by_tag("crypto") == []


def test_gamma_exception_degrades_to_empty_list(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(td.requests, "get", boom)
    assert td.fetch_top_markets_by_tag("crypto") == []


# ---------------------------------------------------------------------------
# Probability extraction
# ---------------------------------------------------------------------------

def _market(question, prices, volume24hr=100.0, closed=False, outcomes=None):
    return {
        "question": question,
        "outcomes": json.dumps(outcomes or ["Yes", "No"]),
        "outcomePrices": json.dumps(prices),
        "volume24hr": volume24hr,
        "closed": closed,
        "active": True,
    }


def test_extracts_yes_probability_from_json_encoded_strings():
    """Gamma serialises outcomes/outcomePrices as JSON strings, not arrays."""
    event = {"title": "Fed", "volume24hr": 2_327_295.0,
             "markets": [_market("Will the Fed hold?", ["0.525", "0.475"])]}
    row = td.extract_event_probability(event)
    assert row["prob"] == 52.5
    assert row["volume"] == pytest.approx(2_327_295.0)


def test_skips_already_resolved_markets():
    """
    Regression guard: settled legs report price 1/0 with volume24hr=None. They
    used to win the ranking via lifetime volume and rendered as a useless 100%.
    """
    event = {
        "title": "What price will Bitcoin hit in August?",
        "volume24hr": 862_000.0,
        "markets": [
            _market("Will Bitcoin reach $80,000?", ["1", "0"], volume24hr=None, closed=True),
            _market("Will Bitcoin reach $82,500?", ["0.045", "0.955"], volume24hr=93_791.0),
        ],
    }
    row = td.extract_event_probability(event)
    assert row["title"] == "Will Bitcoin reach $82,500?"
    assert row["prob"] == 4.5


def test_keeps_high_volume_near_certain_market():
    """
    A 99% market that is the primary traded leg IS the sentiment -- it must not
    be discarded in favour of a thinly-traded coin flip elsewhere in the event.
    """
    event = {
        "title": "Crypto",
        "volume24hr": 1000.0,
        "markets": [
            _market("Near certain, heavily traded", ["0.99", "0.01"], volume24hr=999_999.0),
            _market("Coin flip, barely traded", ["0.44", "0.56"], volume24hr=10.0),
        ],
    }
    row = td.extract_event_probability(event)
    assert row["title"] == "Near certain, heavily traded"
    assert row["prob"] == 99.0


def test_keeps_high_volume_long_shot_market():
    """The 1% mirror of the above -- a heavily traded long shot is still signal."""
    event = {
        "title": "Crypto",
        "volume24hr": 1000.0,
        "markets": [
            _market("Long shot, heavily traded", ["0.01", "0.99"], volume24hr=500_000.0),
            _market("Coin flip, barely traded", ["0.50", "0.50"], volume24hr=3.0),
        ],
    }
    assert td.extract_event_probability(event)["title"] == "Long shot, heavily traded"


def test_ranks_by_volume_when_scores_are_comparable():
    event = {
        "title": "Crypto",
        "volume24hr": 1000.0,
        "markets": [
            _market("Third", ["0.30", "0.70"], volume24hr=5.0),
            _market("First", ["0.60", "0.40"], volume24hr=900.0),
            _market("Second", ["0.45", "0.55"], volume24hr=100.0),
        ],
    }
    assert td.extract_event_probability(event)["title"] == "First"


# ---------------------------------------------------------------------------
# Multi-strike ladders: contested-ness weighting
# ---------------------------------------------------------------------------

def test_contested_score_peaks_at_a_coin_flip():
    assert td.contested_score(1000.0, 50.0) == pytest.approx(1000.0)
    assert td.contested_score(1000.0, 25.0) == pytest.approx(500.0)
    assert td.contested_score(1000.0, 75.0) == pytest.approx(500.0)


def test_contested_score_is_symmetric_about_50():
    for offset in (5.0, 20.0, 45.0):
        assert td.contested_score(1000.0, 50.0 - offset) == pytest.approx(
            td.contested_score(1000.0, 50.0 + offset))


def test_contested_score_never_falls_below_the_floor():
    """Weighting, not filtering: an extreme leg keeps 10% of its volume."""
    assert td.contested_score(1000.0, 0.0) == pytest.approx(100.0)
    assert td.contested_score(1000.0, 100.0) == pytest.approx(100.0)
    assert td.contested_score(1000.0, 1.0) >= 1000.0 * td.CONTESTED_WEIGHT_FLOOR


def test_multi_strike_ladder_picks_the_live_strike_over_a_lottery_ticket():
    """
    Regression guard: cheap far-out strikes accumulate huge SHARE volume
    precisely because they are lottery tickets. Raw volume ranking surfaced
    "BTC to $1M @ 0.6%" as the crypto sentiment.
    """
    event = {
        "title": "What price will Bitcoin hit in August?",
        "volume24hr": 880_000.0,
        "markets": [
            _market("Will Bitcoin reach $1,000,000?", ["0.006", "0.994"], volume24hr=500_000.0),
            _market("Will Bitcoin reach $80,000?", ["0.275", "0.725"], volume24hr=200_000.0),
            _market("Will Bitcoin reach $90,000?", ["0.002", "0.998"], volume24hr=300_000.0),
        ],
    }
    row = td.extract_event_probability(event)
    assert row["title"] == "Will Bitcoin reach $80,000?"
    assert row["prob"] == 27.5


def test_two_outcome_event_is_not_reweighted():
    """
    A plain two-sided market's headline IS its most-traded leg, even at 99% --
    the ladder weighting must not drag it toward a thin 50% sibling.
    """
    event = {
        "title": "Fed Decision",
        "volume24hr": 2_300_000.0,
        "markets": [
            _market("Will the Fed hold?", ["0.99", "0.01"], volume24hr=1_000_000.0),
            _market("Coin flip sibling", ["0.50", "0.50"], volume24hr=200_000.0),
        ],
    }
    assert td.extract_event_probability(event)["title"] == "Will the Fed hold?"


def test_ladder_weighting_still_respects_overwhelming_volume():
    """The 0.1 floor keeps a dominant extreme leg in contention."""
    event = {
        "title": "Ladder",
        "volume24hr": 1000.0,
        "markets": [
            _market("Extreme but dominant", ["0.01", "0.99"], volume24hr=1_000_000.0),
            _market("Contested but tiny", ["0.50", "0.50"], volume24hr=1_000.0),
            _market("Filler", ["0.40", "0.60"], volume24hr=10.0),
        ],
    }
    # 1,000,000 * 0.1 = 100,000 still beats 1,000 * 1.0.
    assert td.extract_event_probability(event)["title"] == "Extreme but dominant"


def test_score_is_exposed_on_the_returned_row():
    event = {
        "title": "Ladder",
        "volume24hr": 1.0,
        "markets": [
            _market("A", ["0.50", "0.50"], volume24hr=100.0),
            _market("B", ["0.10", "0.90"], volume24hr=100.0),
            _market("C", ["0.20", "0.80"], volume24hr=1.0),
        ],
    }
    row = td.extract_event_probability(event)
    assert row["score"] == pytest.approx(100.0)  # A: full weight at 50%


def test_skips_markets_pinned_at_exact_certainty():
    """Exactly 100.0% / 0.0% is decided in all but settlement -- no signal."""
    event = {
        "title": "Crypto",
        "volume24hr": 1000.0,
        "markets": [
            _market("Pinned at 100", ["1", "0"], volume24hr=999_999.0),
            _market("Pinned at 0", ["0", "1"], volume24hr=888_888.0),
            _market("Still live", ["0.97", "0.03"], volume24hr=10.0),
        ],
    }
    row = td.extract_event_probability(event)
    assert row["title"] == "Still live"
    assert row["prob"] == 97.0


def test_skips_markets_with_no_24h_volume_reported():
    """Gamma stops reporting volume24hr once a market resolves."""
    event = {
        "title": "Crypto",
        "volume24hr": 1000.0,
        "markets": [
            _market("Resolved, no 24h volume", ["0.5", "0.5"], volume24hr=None),
            _market("Live", ["0.62", "0.38"], volume24hr=1.0),
        ],
    }
    assert td.extract_event_probability(event)["title"] == "Live"


def test_event_where_every_leg_is_pinned_yields_nothing():
    event = {
        "title": "Crypto",
        "volume24hr": 1000.0,
        "markets": [
            _market("A", ["1", "0"], volume24hr=100.0),
            _market("B", ["0", "1"], volume24hr=50.0),
        ],
    }
    assert td.extract_event_probability(event) is None


def test_handles_up_down_outcome_naming():
    event = {"title": "BTC", "volume24hr": 1.0,
             "markets": [_market("BTC 5m", ["0.52", "0.48"], outcomes=["Up", "Down"])]}
    assert td.extract_event_probability(event)["prob"] == 52.0


def test_event_without_markets_yields_nothing():
    assert td.extract_event_probability({"title": "Empty", "markets": []}) is None


def test_event_with_only_closed_markets_yields_nothing():
    event = {"title": "Done", "volume24hr": 1.0,
             "markets": [_market("Settled", ["1", "0"], closed=True)]}
    assert td.extract_event_probability(event) is None


def test_resolved_market_volume_does_not_fall_back_to_lifetime():
    assert td._market_24h_volume({"volume24hr": None, "volumeNum": 1_516_226.86}) == 0.0
    assert td._market_24h_volume({"volume24hr": 51_947.55}) == pytest.approx(51_947.55)


# ---------------------------------------------------------------------------
# Macro panel assembly
# ---------------------------------------------------------------------------

def test_macro_sentiment_builds_all_three_categories(monkeypatch):
    def fake_fetch(tag_slug, limit=4, timeout=8):
        return [{
            "title": f"{tag_slug} event",
            "volume24hr": 1000.0,
            "markets": [_market(f"{tag_slug} question", ["0.5", "0.5"])],
        }]

    monkeypatch.setattr(td, "fetch_top_markets_by_tag", fake_fetch)
    data = td.fetch_macro_sentiment_data(per_category=1)

    assert [c["key"] for c in data["categories"]] == ["crypto", "politics", "economics"]
    for cat in data["categories"]:
        assert len(cat["rows"]) == 1
    assert data["last_updated"]


def test_macro_sentiment_dedupes_markets_across_categories(monkeypatch):
    """The Fed decision is tagged both politics and economics; show it once."""
    def fake_fetch(tag_slug, limit=4, timeout=8):
        return [{
            "title": "Fed Decision",
            "volume24hr": 2_327_295.0,
            "markets": [_market("Will the Fed hold?", ["0.525", "0.475"])],
        }]

    monkeypatch.setattr(td, "fetch_top_markets_by_tag", fake_fetch)
    data = td.fetch_macro_sentiment_data(per_category=1)

    titles = [r["title"] for c in data["categories"] for r in c["rows"]]
    assert len(titles) == len(set(titles)) == 1


def test_macro_sentiment_uses_fallback_slug_for_thin_tags(monkeypatch):
    """`economics` often has a single active event; top up from the next slug."""
    def fake_fetch(tag_slug, limit=4, timeout=8):
        if tag_slug == "economics":
            return [{"title": "Argentina", "volume24hr": 45.0,
                     "markets": [_market("Will Argentina dollarize?", ["0.065", "0.935"])]}]
        if tag_slug == "economy":
            return [{"title": "Fed cuts", "volume24hr": 96_202.0,
                     "markets": [_market("Will no Fed rate cuts happen?", ["0.876", "0.124"])]}]
        return []

    monkeypatch.setattr(td, "fetch_top_markets_by_tag", fake_fetch)
    data = td.fetch_macro_sentiment_data(per_category=2)

    economics = next(c for c in data["categories"] if c["key"] == "economics")
    assert len(economics["rows"]) == 2


def test_macro_sentiment_survives_total_api_outage(monkeypatch):
    monkeypatch.setattr(td, "fetch_top_markets_by_tag", lambda *a, **k: [])
    data = td.fetch_macro_sentiment_data()

    assert len(data["categories"]) == 3
    for cat in data["categories"]:
        assert cat["rows"] == []


def test_macro_panel_renders_without_data(monkeypatch):
    """An empty panel must render, not raise, so the Live loop keeps running."""
    monkeypatch.setattr(td, "shared_macro_sentiment", {"categories": []})
    assert td.make_macro_panel() is not None


def test_macro_panel_renders_with_data(monkeypatch):
    monkeypatch.setattr(td, "shared_macro_sentiment", {
        "last_updated": "12:00:00 UTC",
        "categories": [
            {"key": "crypto", "glyph": "coin", "label": "Crypto", "tag_slug": "crypto",
             "rows": [{"title": "BTC up?", "prob": 52.5, "volume": 1_000_000.0}]},
            {"key": "politics", "glyph": "globe", "label": "Politics", "tag_slug": "politics",
             "rows": []},
        ],
    })
    assert td.make_macro_panel() is not None


@pytest.mark.parametrize("prob", [0.0, 0.1, 50.0, 99.9, 100.0])
def test_probability_bar_never_overflows(monkeypatch, prob):
    """int(prob/10) must stay clamped to 0..10 or the bar breaks the layout."""
    monkeypatch.setattr(td, "shared_macro_sentiment", {
        "last_updated": "12:00:00 UTC",
        "categories": [{"key": "crypto", "glyph": "coin", "label": "Crypto",
                        "tag_slug": "crypto",
                        "rows": [{"title": "T", "prob": prob, "volume": 1.0}]}],
    })
    assert td.make_macro_panel() is not None


# ---------------------------------------------------------------------------
# Traders panel: PnL labelling
# ---------------------------------------------------------------------------

class _FakeRow(dict):
    """sqlite3.Row stand-in: subscript by column name, KeyError when absent."""


def _trader_row(**overrides):
    row = _FakeRow({
        "wallet": "0xc69bd5567b40ef4d11922eaa57e1f9be1c642076",
        "pseudonym": "Ultimate-Underpass",
        "pnl_7d": 132683.42,
        "realized_pnl_7d": 132685.0,
        "unrealized_pnl": -2.0,
        "volume_7d": 5.0,
        "trades_7d": 500,
        "win_rate": 100.0,
    })
    row.update(overrides)
    return row


def _render_traders_panel(monkeypatch, width, rows=None):
    from rich.console import Console

    monkeypatch.setattr(td, "fetch_top_sharp_traders",
                        lambda limit=10: rows if rows is not None else [_trader_row()])
    monkeypatch.setattr(td, "console", Console(width=width, force_terminal=False))
    with td.console.capture() as cap:
        td.console.print(td.make_traders_panel())
    return cap.get()


def test_traders_panel_headline_is_realized_not_blended(monkeypatch):
    """
    The panel ranks on banked profit, so 7D Real. leads and the blended figure
    is not shown here at all -- it is derivable from the two columns present,
    and this panel only gets half the console.
    """
    out = _render_traders_panel(monkeypatch, 200)
    assert "7D Real" in out
    assert "Open Unr" in out
    assert "7D Net PnL" not in out


def test_traders_panel_title_states_the_ranking_basis(monkeypatch):
    """The title must say the board ranks on realized, not the blended figure."""
    out = _render_traders_panel(monkeypatch, 200)
    assert "7D Realized" in out
    assert "open unrealized" in out


def test_traders_panel_splits_pnl_on_wide_console(monkeypatch):
    out = _render_traders_panel(monkeypatch, 200)
    assert "7D Real." in out
    assert "Open Unr." in out


def test_traders_panel_keeps_ranking_columns_on_narrow_console(monkeypatch):
    """
    The panel gets only half the console, so something must yield at 80 cols --
    but never the ranking key or the open-book context beside it.
    """
    out = _render_traders_panel(monkeypatch, 80)
    assert "7D Real." in out
    assert "Open Unr." in out
    # The blended total and volume are the ones that go.
    assert "Est. PnL" not in out
    assert "7D Volume" not in out


def test_traders_panel_tolerates_pre_migration_rows(monkeypatch):
    """Rows written before the realized/unrealized split must still render."""
    legacy = _trader_row()
    del legacy["realized_pnl_7d"]
    del legacy["unrealized_pnl"]
    out = _render_traders_panel(monkeypatch, 200, rows=[legacy])
    assert "7D Real" in out


def test_traders_panel_empty_state_renders(monkeypatch):
    out = _render_traders_panel(monkeypatch, 200, rows=[])
    assert "No sharp traders" in out


def test_traders_panel_dashes_win_rate_with_no_closed_positions(monkeypatch):
    """A wallet holding only open positions has no record to score, not a 0% one."""
    row = _trader_row(win_rate=0.0, closed_positions_7d=0)
    out = _render_traders_panel(monkeypatch, 200, rows=[row])
    assert "—" in out
    assert " 0%" not in out


def test_traders_panel_shows_a_real_zero_percent_record(monkeypatch):
    row = _trader_row(win_rate=0.0, closed_positions_7d=5)
    out = _render_traders_panel(monkeypatch, 200, rows=[row])
    assert "0%" in out


def test_traders_panel_shows_roi_on_wide_console(monkeypatch):
    row = _trader_row(realized_pnl_7d=5_000.0, volume_7d=10_000.0)
    out = _render_traders_panel(monkeypatch, 200, rows=[row])
    assert "ROI%" in out
    assert "+50.0%" in out


def test_traders_panel_hides_roi_on_narrow_console(monkeypatch):
    """The panel gets half the console; below 136 there is no room for ROI."""
    out = _render_traders_panel(monkeypatch, 80)
    assert "ROI%" not in out


def test_traders_panel_withholds_roi_on_partial_volume(monkeypatch):
    row = _trader_row(realized_pnl_7d=132_000.0, volume_7d=5.0, volume_is_partial=1)
    out = _render_traders_panel(monkeypatch, 200, rows=[row])
    assert "ROI%" in out
    assert "k%" not in out  # no absurd ratio from a truncated denominator
    assert "—" in out


def test_traders_panel_dash_degrades_to_ascii(monkeypatch):
    """The dash must survive a console that cannot render an em dash."""
    monkeypatch.setattr(td, "UNICODE_OK", False)
    assert td.safe_glyph("dash") == "-"
    row = _trader_row(win_rate=0.0, closed_positions_7d=0)
    out = _render_traders_panel(monkeypatch, 200, rows=[row])
    out.encode("cp1252")


def test_dashboard_reuses_the_scanner_formatters():
    """One definition of the dash rule, shared by both surfaces."""
    import pnl_scanner as ps
    assert td.format_win_rate is ps.format_win_rate
    assert td.format_roi is ps.format_roi
    assert td.compute_roi is ps.compute_roi


# ---------------------------------------------------------------------------
# Windows console safety
# ---------------------------------------------------------------------------

def test_glyph_table_provides_ascii_fallback_for_every_entry():
    for name, (preferred, fallback) in td._GLYPHS.items():
        assert fallback, f"{name} has no ASCII fallback"
        fallback.encode("cp1252")  # must survive a legacy Windows console


def test_safe_glyph_returns_ascii_when_console_lacks_unicode(monkeypatch):
    monkeypatch.setattr(td, "UNICODE_OK", False)
    assert td.safe_glyph("crown") == "[M]"
    assert td.safe_glyph("bar_full") == "#"
    assert td.safe_glyph("bar_empty") == "-"


def test_safe_glyph_returns_emoji_when_console_supports_unicode(monkeypatch):
    monkeypatch.setattr(td, "UNICODE_OK", True)
    assert td.safe_glyph("crown") == "\U0001f451"


def test_safe_glyph_tolerates_unknown_names():
    assert td.safe_glyph("no_such_glyph") == ""


def test_ascii_panels_are_cp1252_encodable(monkeypatch):
    """The whole macro panel must survive a cp1252 console end to end."""
    from rich.console import Console

    monkeypatch.setattr(td, "UNICODE_OK", False)
    monkeypatch.setattr(td, "shared_macro_sentiment", {
        "last_updated": "12:00:00 UTC",
        "categories": [{"key": "crypto", "glyph": "coin", "label": "Crypto",
                        "tag_slug": "crypto",
                        "rows": [{"title": "BTC up?", "prob": 52.5, "volume": 1_000_000.0}]}],
    })

    console = Console(width=100, safe_box=True, legacy_windows=True)
    with console.capture() as capture:
        console.print(td.make_macro_panel())

    capture.get().encode("cp1252")  # raises UnicodeEncodeError on regression


def test_unicode_detection_handles_missing_stdout_encoding(monkeypatch):
    class Dummy:
        encoding = None

    monkeypatch.setattr(td.sys, "stdout", Dummy())
    assert td._console_supports_unicode() is False
