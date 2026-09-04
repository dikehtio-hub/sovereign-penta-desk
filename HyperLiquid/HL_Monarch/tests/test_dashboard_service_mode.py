"""
Round 36 Ruling 3.A: one ingester. The dashboard is a read-only viewer while a
service collector is alive, and a standalone ingester only when none is.

The decision and the badge are pure functions so they can be pinned without a
terminal: which mode a start-up lands in, and what the header says when the
world changes underneath a running dashboard.
"""
import io
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.market_collector import read_service_pid
from ui.components import build_header_panel, ingestion_badge


def test_read_service_pid_is_none_when_absent_or_junk(tmp_path):
    assert read_service_pid(tmp_path / "nope.pid") is None
    junk = tmp_path / "junk.pid"
    junk.write_text("abc", encoding="utf-8")
    assert read_service_pid(junk) is None
    good = tmp_path / "collector.pid"
    good.write_text(" 4242\n", encoding="utf-8")
    assert read_service_pid(good) == 4242


def test_start_up_lands_in_read_only_when_a_service_is_alive():
    mode, badge = ingestion_badge(alive=True, pid=4242, started_read_only=None)
    assert mode == "read_only"
    assert badge == "[dim]Service: RUNNING (PID 4242) · Read-Only Mode[/dim]"


def test_start_up_falls_back_to_standalone_when_no_service():
    mode, badge = ingestion_badge(alive=False, pid=None, started_read_only=None)
    assert mode == "standalone"
    assert badge == "[bold yellow]Service: STOPPED · Standalone Ingestion Active[/bold yellow]"


def test_a_read_only_dashboard_whose_service_died_says_so_loudly():
    """Its tables are going stale and nothing is ingesting - the one state that must not look calm."""
    mode, badge = ingestion_badge(alive=False, pid=4242, started_read_only=True)
    assert mode == "orphaned"
    assert "STOPPED" in badge and "No ingestion" in badge and "start_collector.bat" in badge
    assert badge.startswith("[bold red]")


def test_a_standalone_dashboard_joined_by_a_service_asks_for_a_restart():
    """Its embedded collector yields maintenance but still polls: two REST budgets until restarted."""
    mode, badge = ingestion_badge(alive=True, pid=99, started_read_only=False)
    assert mode == "dual"
    assert "PID 99" in badge and "restart" in badge.lower()


def test_the_header_panel_carries_the_badge():
    panel = build_header_panel(1_000_000.0, 2_000_000.0, {"main": 1_000_000.0}, active_tab="ALL",
                               status="[dim]Service: RUNNING (PID 4242) · Read-Only Mode[/dim]")
    buffer = io.StringIO()
    Console(file=buffer, width=200, force_terminal=False, color_system=None).print(panel)
    text = buffer.getvalue()
    assert "Service: RUNNING (PID 4242)" in text and "Read-Only Mode" in text
    # And the header still renders without one.
    build_header_panel(1_000_000.0, 2_000_000.0, {"main": 1_000_000.0}, active_tab="ALL")
