"""
🌙 Moon Dev's chart-control tools.

Covers symbol, timeframe, current state, and screenshots. Uses a mix of
URL navigation (for symbol/interval — most robust) and keyboard shortcuts
(for timeframe-on-existing-chart — slick when it works).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import quote

from ..cdp_client import CDPClient
from ._helpers import focus_chart, press_escape, with_cdp


def _current_chart_state(cdp: CDPClient) -> dict[str, str]:
    """Scrape symbol + interval from the page title and URL. TV encodes both.

    2026-09-14: on tradingview.com/chart/ the title is just the ticker ("AAPL")
    and the URL carries no query, so both original sources come back empty.
    Added DOM fallbacks: the header symbol button (ticker) and the main-series
    legend row (interval / exchange / description). The header interval bar is
    NOT used first: its aria-checked button disagreed with the legend on a live
    chart (toolbar said 15m, legend and candles said 1D).
    """
    js = """
    (() => {
      const txt = (el) => el ? (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim() : '';
      const q = (s) => document.querySelector(s);
      const series = q('[class*="legend-"] [class*="item-"][class*="series-"]');
      const sub = (s) => series ? series.querySelector(s) : null;
      const hb = q('#header-toolbar-intervals [aria-checked="true"]');
      return {
        title: document.title || '',
        href: location.href || '',
        symbol_button: txt(q('#header-toolbar-symbol-search')),
        interval_legend: txt(sub('[class*="intervalTitle"]')),
        interval_header: hb ? (hb.getAttribute('data-value') || txt(hb)) : '',
        exchange: txt(sub('[class*="exchangeTitle"]')),
        description: txt(sub('[class*="mainTitle"] [class*="title-"]')) || txt(sub('[class*="mainTitle"]')),
        series_title: txt(sub('[class*="titlesWrapper"]')),
      };
    })()
    """
    data = cdp.eval_js(js) or {}
    title = str(data.get("title", ""))
    href = str(data.get("href", ""))
    symbol, interval = "", ""
    # "NVDA, 5 — TradingView" or "BTCUSD · 1H Chart" — many variants. Best-effort.
    if " — " in title:
        head = title.split(" — ", 1)[0]
        parts = [p.strip() for p in head.replace("·", ",").split(",")]
        if parts:
            symbol = parts[0]
            if len(parts) >= 2:
                interval = parts[1]
    # Fallback 1: header symbol button + main-series legend row (current TV DOM).
    # The legend row has two display modes: full ("Apple Inc 1D NASDAQ", separate
    # intervalTitle/exchangeTitle spans) and compact ("BATS:AAPL · 15", one title).
    # Parse the compact form before trusting the header bar, which has disagreed
    # with the chart on a live session.
    import re
    series_title = str(data.get("series_title", ""))
    exchange = str(data.get("exchange", ""))
    m_iv = re.search(r"(?<![\w:])(\d+[smhHDWM]?)(?![\w:!])", series_title)
    m_ex = re.search(r"(?<![\w:])([A-Z0-9_]+):([A-Z0-9_.!&-]+)", series_title)
    symbol = symbol or str(data.get("symbol_button", "")) or (m_ex.group(2) if m_ex else "")
    interval = (
        interval
        or str(data.get("interval_legend", ""))
        or (m_iv.group(1) if m_iv else "")
        or str(data.get("interval_header", ""))
    )
    exchange = exchange or (m_ex.group(1) if m_ex else "")
    # Fallback 2: parse ?symbol=&interval= from URL.
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(href).query)
    symbol = symbol or (qs.get("symbol", [""])[0])
    interval = interval or (qs.get("interval", [""])[0])
    return {
        "symbol": symbol,
        "interval": interval,
        "url": href,
        "exchange": exchange,
        "description": str(data.get("description", "")),
    }


def register(mcp) -> None:
    """Register chart tools on the given FastMCP instance."""

    @mcp.tool()
    @with_cdp("tv_set_symbol")
    def tv_set_symbol(cdp: CDPClient, symbol: str) -> dict:
        """
        🌙 Switch the active chart to a symbol. Supports exchange-prefixed
        symbols like COINBASE:BTCUSD or NASDAQ:NVDA (recommended — unambiguous).

        Strategy: navigate to the chart URL with ?symbol= query param. This
        is the most reliable method and survives TV UI changes.
        """
        if not symbol or not isinstance(symbol, str):
            return {"status": "error", "error": "symbol must be a non-empty string"}

        # Navigate via JS so we keep the same tab. Page.navigate also works.
        js = f"""
        (() => {{
          const s = {json.dumps(symbol)};
          const base = 'https://www.tradingview.com/chart/';
          const url = new URL(location.href.startsWith(base) ? location.href : base);
          url.pathname = '/chart/';
          url.searchParams.set('symbol', s);
          location.href = url.toString();
          return true;
        }})()
        """
        cdp.eval_js(js)
        # Give TV a moment to load.
        time.sleep(1.2)
        state = _current_chart_state(cdp)
        return {"status": "ok", "symbol": symbol, "state": state}

    @mcp.tool()
    @with_cdp("tv_set_timeframe")
    def tv_set_timeframe(cdp: CDPClient, timeframe: str) -> dict:
        """
        🌙 Set the chart timeframe. Accepts TV-native codes: "1","5","15","60",
        "240" (minutes) or "D","W","M" (daily/weekly/monthly).

        Strategy: TV's "type-to-change-interval" shortcut. Focus the chart,
        type the code, press Enter. Fallback: header toolbar click.
        """
        tf = (timeframe or "").strip()
        if not tf:
            return {"status": "error", "error": "timeframe required"}

        focus_chart(cdp)
        time.sleep(0.2)
        # Clear any open overlay first.
        press_escape(cdp)
        time.sleep(0.15)
        # Type the timeframe code.
        cdp.type_text(tf)
        time.sleep(0.25)
        cdp.press_key("Enter")
        time.sleep(0.8)

        state = _current_chart_state(cdp)
        return {"status": "ok", "timeframe": tf, "state": state}

    @mcp.tool()
    @with_cdp("tv_get_current_symbol")
    def tv_get_current_symbol(cdp: CDPClient) -> dict:
        """🌙 Return the symbol, timeframe, and URL of the currently displayed chart."""
        state = _current_chart_state(cdp)
        return {"status": "ok", **state}

    @mcp.tool()
    @with_cdp("tv_screenshot")
    def tv_screenshot(cdp: CDPClient, path: str = "") -> dict:
        """
        🌙 Capture a PNG of the current chart. Default save dir lives next to the
        dedicated Chrome profile so screenshots are easy to find.
        """
        if not path:
            default_dir = Path(os.path.expanduser("~/.tradingview_mcp_chrome/screenshots"))
            default_dir.mkdir(parents=True, exist_ok=True)
            path = str(default_dir / f"tv_{int(time.time())}.png")
        saved = cdp.screenshot(path)
        return {"status": "ok", "path": saved}
