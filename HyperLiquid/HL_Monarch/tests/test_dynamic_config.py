"""
Unit Tests for Monarch Dynamic Risk & Parameter Configuration Manager.
"""

import json
import pytest
from pathlib import Path
from config.dynamic_config import (
    DynamicConfigManager,
    BotConfig,
    parse_yaml_frontmatter,
    PRESETS,
    BOUNDS,
)


def test_parse_yaml_frontmatter_standard():
    sample = """---
title: Test Config
basis_notional_usd: 15000.0
max_concurrent_positions: 3
emergency_killswitch: true
pause_new_entries: false
active_preset: "custom"
---
# Body content
"""
    parsed = parse_yaml_frontmatter(sample)
    assert parsed.get("basis_notional_usd") == 15000.0
    assert parsed.get("max_concurrent_positions") == 3
    assert parsed.get("emergency_killswitch") is True
    assert parsed.get("pause_new_entries") is False
    assert parsed.get("active_preset") == "custom"


def test_bot_config_validation_and_clamping():
    # Test out of bounds values
    cfg = BotConfig(
        basis_notional_usd=500_000.0,  # exceeds 100k
        max_concurrent_positions=25,    # exceeds 10
        max_spread_bps=0.5,            # below 2.0
    ).validate_and_clamp()

    assert cfg.basis_notional_usd == 100_000.0
    assert cfg.max_concurrent_positions == 10
    assert cfg.max_spread_bps == 2.0


def test_dynamic_config_manager_file_sync(tmp_path):
    vault_dir = tmp_path / "obsidian_vault"
    json_path = tmp_path / "data" / "bot_config.json"

    mgr = DynamicConfigManager(vault_path=vault_dir, json_path=json_path)
    cfg = mgr.get_config()
    assert cfg.basis_notional_usd == 10000.0

    # Apply Conservative preset
    cons_cfg = mgr.apply_preset("conservative")
    assert cons_cfg.basis_notional_usd == 5000.0
    assert cons_cfg.max_concurrent_positions == 1
    assert cons_cfg.active_preset == "conservative"

    # Verify Bot_Config.md was written
    note_path = vault_dir / "Bot_Config.md"
    assert note_path.exists()
    content = note_path.read_text(encoding="utf-8")
    assert "basis_notional_usd: 5000.0" in content
    assert "active_preset: \"conservative\"" in content

    # Test Killswitch
    kill_cfg = mgr.set_killswitch(True)
    assert kill_cfg.emergency_killswitch is True
    assert kill_cfg.pause_new_entries is True

    # Test Resume
    resume_cfg = mgr.set_pause(False)
    assert resume_cfg.emergency_killswitch is False
    assert resume_cfg.pause_new_entries is False


def test_user_notes_preservation_in_bot_config(tmp_path):
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Bot_Config.md"

    # Write initial note with custom user research
    initial_text = """---
basis_notional_usd: 10000.0
---
# Title
## 📝 Strategy Notes & Runbook
- My custom risk note: Never trade FOMC days.
"""
    note_path.write_text(initial_text, encoding="utf-8")

    mgr = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json")
    mgr.apply_preset("aggressive")

    # Verify custom note is preserved
    new_text = note_path.read_text(encoding="utf-8")
    assert "My custom risk note: Never trade FOMC days." in new_text


def test_parser_corruptions_and_bom():
    # Leading blank line
    d1 = parse_yaml_frontmatter("\n---\nemergency_killswitch: true\n---\n")
    assert d1.get("emergency_killswitch") is True

    # UTF-8 BOM
    d2 = parse_yaml_frontmatter("\ufeff---\nemergency_killswitch: true\n---\n")
    assert d2.get("emergency_killswitch") is True

    # Missing closing fence
    d3 = parse_yaml_frontmatter("---\nemergency_killswitch: true\n")
    assert d3.get("emergency_killswitch") is True


def test_fail_closed_on_corrupt_config(tmp_path):
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Bot_Config.md"
    note_path.write_text("---\nemergency_killswitch: true\n---\n", encoding="utf-8")

    mgr = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json")
    assert mgr.get_config().emergency_killswitch is True

    # Corrupt the file completely
    note_path.write_text("CORRUPTED JUNK", encoding="utf-8")
    cfg = mgr.get_config()
    # Must fail closed: emergency_killswitch stays True!
    assert cfg.emergency_killswitch is True
    assert cfg.pause_new_entries is True


def test_halt_flag_sentinel(tmp_path):
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Bot_Config.md"
    note_path.write_text("---\nemergency_killswitch: false\n---\n", encoding="utf-8")

    mgr = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json")
    assert mgr.get_config().emergency_killswitch is False

    # Create HALT.flag
    (vault_dir / "HALT.flag").touch()
    assert mgr.get_config().emergency_killswitch is True
    assert mgr.get_config().pause_new_entries is True
