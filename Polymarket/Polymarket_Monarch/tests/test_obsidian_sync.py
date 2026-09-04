"""
Unit tests for obsidian_sync.py in Polymarket Monarch.
Tests Markdown generation, Obsidian callout blocks, table structure,
individual wallet profiling notes, and user notes preservation.
"""

from pathlib import Path
import sqlite3
import pytest

import obsidian_sync as obs


NOW = 1_788_054_510


@pytest.fixture
def mock_db(tmp_path):
    """Create a temporary mock SQLite database with sharp traders and whale trades."""
    db_file = tmp_path / "test_polymarket.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE sharp_traders (
            wallet TEXT PRIMARY KEY,
            pseudonym TEXT,
            pnl_7d REAL,
            realized_pnl_7d REAL,
            unrealized_pnl REAL,
            volume_7d REAL,
            trades_7d INTEGER,
            open_positions INTEGER,
            closed_positions_7d INTEGER,
            win_rate REAL,
            volume_is_partial INTEGER DEFAULT 0,
            is_sharp INTEGER DEFAULT 1,
            polymarket_link TEXT,
            last_updated INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE whale_trades (
            tx_hash TEXT PRIMARY KEY,
            timestamp INTEGER,
            title TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            size_usd REAL,
            price REAL,
            shares REAL,
            trader_address TEXT,
            trader_name TEXT,
            outcome TEXT
        )
    """)

    # Seed sharp trader
    cur.execute("""
        INSERT INTO sharp_traders VALUES (
            '0x1234567890abcdef1234567890abcdef12345678',
            'Whale-King',
            25000.0,
            20000.0,
            5000.0,
            50000.0,
            120,
            4,
            10,
            80.0,
            0,
            1,
            'https://polymarket.com/profile/0x1234567890abcdef1234567890abcdef12345678',
            ?
        )
    """, (NOW,))

    # Seed whale trade
    cur.execute("""
        INSERT INTO whale_trades VALUES (
            'tx_001',
            ?,
            'Will Fed Cut Rates in Sept?',
            'cond_1',
            'tok_1',
            'BUY',
            15000.0,
            0.65,
            23000.0,
            '0x1234567890abcdef1234567890abcdef12345678',
            'Whale-King',
            'Yes'
        )
    """, (NOW,))
    conn.commit()
    conn.close()
    return db_file


def test_get_vault_path_creates_directory(tmp_path):
    target = tmp_path / "custom_vault"
    resolved = obs.get_vault_path(str(target))
    assert resolved.exists()
    assert resolved.is_dir()


def test_generate_wallet_note_creates_markdown_file(tmp_path):
    vault = tmp_path / "vault"
    trader = {
        "wallet": "0x1234567890abcdef1234567890abcdef12345678",
        "pseudonym": "Alpha-Trader",
        "realized_pnl_7d": 15000.0,
        "unrealized_pnl": -2000.0,
        "pnl_7d": 13000.0,
        "volume_7d": 45000.0,
        "trades_7d": 85,
        "win_rate": 75.0,
        "closed_positions_7d": 8,
        "volume_is_partial": 0,
    }
    file_path = obs.generate_wallet_note(trader, vault)
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "# 👑 Sharp Trader: Alpha-Trader" in content
    assert "0x1234567890abcdef1234567890abcdef12345678" in content
    assert "+$15.0K" in content
    assert "75%" in content
    assert "## 📝 My Research & Notes" in content


def test_preserve_user_notes_across_sync_cycles(tmp_path):
    vault = tmp_path / "vault"
    trader = {
        "wallet": "0x1234567890abcdef1234567890abcdef12345678",
        "pseudonym": "Alpha-Trader",
        "realized_pnl_7d": 15000.0,
        "unrealized_pnl": 0.0,
        "pnl_7d": 15000.0,
        "volume_7d": 30000.0,
        "trades_7d": 40,
        "win_rate": 100.0,
        "closed_positions_7d": 5,
        "volume_is_partial": 0,
    }
    file_path = obs.generate_wallet_note(trader, vault)
    
    # User edits the note and writes their custom alpha notes
    custom_text = "\n- **My Thesis**: Only trades election markets with tight spreads.\n- **Copy Trading**: Yes, sizing 0.5x"
    file_path.write_text(file_path.read_text(encoding="utf-8") + custom_text, encoding="utf-8")

    # Simulate next sync cycle with updated PnL
    trader["realized_pnl_7d"] = 28000.0
    trader["pnl_7d"] = 28000.0
    updated_file = obs.generate_wallet_note(trader, vault)

    updated_content = updated_file.read_text(encoding="utf-8")
    assert "+$28.0K" in updated_content
    # Crucial: User's custom thesis and copy trading notes must be preserved!
    assert "Only trades election markets with tight spreads" in updated_content
    assert "Copy Trading" in updated_content


def test_master_dashboard_generation(mock_db, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setattr(obs, "fetch_macro_sentiment", lambda: [
        {"category": "🪙 Crypto", "title": "BTC > 100k", "volume_24h": 1_500_000.0, "prob": 65.4}
    ])

    master_file, count = obs.sync_to_obsidian(str(vault), db_path=mock_db)
    assert master_file.exists()
    assert count == 1

    content = master_file.read_text(encoding="utf-8")
    assert "# 👑 Polymarket Monarch • Real-Time Intelligence" in content
    assert "Whale-King" in content
    assert "[[Wallets/0x1234567890abcdef1234567890abcdef12345678|Whale-King]]" in content
    assert "Will Fed Cut Rates in Sept?" in content
    assert "BTC > 100k" in content
    assert "`███████░░░` **65.4%**" in content
