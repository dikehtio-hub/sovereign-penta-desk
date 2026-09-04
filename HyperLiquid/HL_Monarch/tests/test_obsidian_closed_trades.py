"""
Round 43 (Ruling 43-4): the Trading Terminal note's closed-trades table read
keys the harvester never writes (realized_pnl, hold_duration_hours), so every
swept trade rendered as $0.00 over 0.0h. The harvester writes net_pnl and
hours_held; the old keys stay as fallbacks. Offline: temp state files, temp vault.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analytics.obsidian_exporter as ox


def _state(closed, positions=None):
    return {"starting_cash": 100_000.0, "cash": 60_308.98, "positions": positions or {},
            "closed": closed, "realized_pnl": 308.92, "funding_collected": 349.91,
            "fees_paid": 41.0, "accruals": 51}


def test_swept_trades_render_their_net_pnl_and_hours(tmp_path, monkeypatch):
    closed = [
        {"coin": "xyz:HOOD", "spot_symbol": "HOOD", "net_pnl": 4.09, "hours_held": 51.0,
         "exit_reason": "ILLIQUID_SPOT_LEG: HOOD is synthetic TradFi (quarantined)"},
        {"coin": "xyz:AVGO", "spot_symbol": "AVGO", "net_pnl": -7.28, "hours_held": 16.0,
         "exit_reason": "ILLIQUID_SPOT_LEG: AVGO is synthetic TradFi (quarantined)"},
        {"coin": "OLD", "realized_pnl": 12.5, "hold_duration_hours": 3.0},          # legacy keys still read
        {"coin": "ZERO", "net_pnl": 0.0, "hours_held": 0.0},                         # zero is red, not a crash
    ]
    state = tmp_path / "basis.json"
    state.write_text(json.dumps(_state(closed)), encoding="utf-8")
    monkeypatch.setattr(ox, "BASIS_PAPER_STATE_PATH", str(state))
    monkeypatch.setattr(ox, "PAPER_STATE_PATH", str(tmp_path / "absent_paper.json"))

    path, _ = ox.generate_trading_terminal_note(tmp_path, "2026-09-04T20:00:00+00:00")
    text = Path(path).read_text(encoding="utf-8")
    rows = {line.split("|")[1].strip(): line for line in text.splitlines() if line.startswith("| **`")}

    assert "4.09" in rows["**`xyz:HOOD`**"] and "51.0h" in rows["**`xyz:HOOD`**"]
    assert rows["**`xyz:HOOD`**"].count("🟢") == 1 and "ILLIQUID_SPOT_LEG" in rows["**`xyz:HOOD`**"]
    assert "7.28" in rows["**`xyz:AVGO`**"] and "16.0h" in rows["**`xyz:AVGO`**"] and "🔴" in rows["**`xyz:AVGO`**"]
    assert "12.50" in rows["**`OLD`**"] and "3.0h" in rows["**`OLD`**"]
    assert "0.0h" in rows["**`ZERO`**"] and "🔴" in rows["**`ZERO`**"]
    assert "No closed basis pairs" not in text


def test_an_empty_book_still_renders(tmp_path, monkeypatch):
    state = tmp_path / "basis.json"
    state.write_text(json.dumps(_state([])), encoding="utf-8")
    monkeypatch.setattr(ox, "BASIS_PAPER_STATE_PATH", str(state))
    monkeypatch.setattr(ox, "PAPER_STATE_PATH", str(tmp_path / "absent_paper.json"))
    path, _ = ox.generate_trading_terminal_note(tmp_path, "2026-09-04T20:00:00+00:00")
    assert "No closed basis pairs" in Path(path).read_text(encoding="utf-8")
