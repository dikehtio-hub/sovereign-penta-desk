"""
Unit Tests for Obsidian Bot Control, Telemetry, and Trading Terminal Exporters.
"""

import json
import pytest
from pathlib import Path
from analytics.obsidian_exporter import (
    generate_bot_control_note,
    generate_trading_terminal_note,
    export_hyperliquid_to_obsidian,
    get_service_telemetry,
)
from analytics.obsidian_links import (
    BOT_CONTROL_NOTE,
    BOT_CONFIG_NOTE,
    TRADING_TERMINAL_NOTE,
    HL_DASHBOARD_NOTE,
    HUB_NOTE,
    make_progress_bar,
)


def test_make_progress_bar():
    bar = make_progress_bar(25, 50, length=10)
    assert "50.0%" in bar
    assert "25/50" in bar
    assert "█" in bar
    assert "░" in bar


def test_service_telemetry_detection():
    telem = get_service_telemetry()
    assert "collector_running" in telem
    assert "collector_pid" in telem
    assert "db_freshness" in telem


def test_generate_bot_control_note(tmp_path):
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    path, written = generate_bot_control_note(vault_dir, "2026-09-01 14:00:00 UTC")
    assert path.exists()
    assert written is True

    content = path.read_text(encoding="utf-8")
    assert "# 🎮 Monarch Bot Control & Activation Deck" in content
    assert "start_collector.bat" in content
    assert "emergency_killswitch.bat" in content
    assert "Trading_Terminal" in content


def test_generate_trading_terminal_note(tmp_path):
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    path, written = generate_trading_terminal_note(vault_dir, "2026-09-01 14:00:00 UTC")
    assert path.exists()
    assert written is True

    content = path.read_text(encoding="utf-8")
    assert "# 📈 Monarch Trading Terminal & 50-Trade Hurdle Tracker" in content
    assert "50-Trade Hurdle Validation Deck" in content
    assert "Win Rate" in content
    assert "Profit Factor" in content


def test_export_hyperliquid_full_suite(tmp_path):
    from storage.db import DatabaseManager
    from storage.repository import MarketRepository

    vault_dir = tmp_path / "obsidian_vault"
    db_file = tmp_path / "test_export.db"
    DatabaseManager._instance = None
    db = DatabaseManager(db_file)
    repo = MarketRepository(db)

    try:
        master_file = export_hyperliquid_to_obsidian(str(vault_dir), repo=repo)

        assert master_file.exists()
        assert (vault_dir / f"{BOT_CONTROL_NOTE}.md").exists()
        assert (vault_dir / f"{BOT_CONFIG_NOTE}.md").exists()
        assert (vault_dir / f"{TRADING_TERMINAL_NOTE}.md").exists()
        assert (vault_dir / f"{HUB_NOTE}.md").exists()

        hub_content = (vault_dir / f"{HUB_NOTE}.md").read_text(encoding="utf-8")
        assert "Bot Control" in hub_content
        assert "Bot Configuration" in hub_content
        assert "Trading Terminal" in hub_content
    finally:
        db.close()
        DatabaseManager._instance = None
