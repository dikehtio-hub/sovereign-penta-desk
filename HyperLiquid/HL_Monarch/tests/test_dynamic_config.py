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


def test_malformed_spot_fields_fall_back_to_settings_defaults(tmp_path, caplog):
    """Round 44 (Ruling 44-4): one bad field falls back with a warning; the rest of the config still loads."""
    from config.settings import SPOT_MIN_DAY_VOLUME, SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir()
    (vault_dir / "Bot_Config.md").write_text(
        "---\nbasis_notional_usd: 12000.0\nmax_concurrent_positions: 3\n"
        "spot_min_day_volume: abc\nspot_min_volume_notional_multiple: lots\n"
        "allow_synthetic_tradfi_basis: maybe\n---\n# Bot Config\n", encoding="utf-8")
    mgr = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json")
    cfg = mgr.get_config()
    assert cfg.basis_notional_usd == 12000.0 and cfg.max_concurrent_positions == 3
    assert cfg.spot_min_day_volume == SPOT_MIN_DAY_VOLUME
    assert cfg.spot_min_volume_notional_multiple == SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE
    assert cfg.allow_synthetic_tradfi_basis is False
    assert cfg.emergency_killswitch is False                     # a bad field is not a corrupt config
    assert sum("settings default" in r.message for r in caplog.records) == 3
    # A floor under $10k clamps up rather than passing through (Ruling 44-4).
    (vault_dir / "Bot_Config.md").write_text("---\nspot_min_day_volume: 1\n---\n", encoding="utf-8")
    assert mgr.reload().spot_min_day_volume == 10_000.0


NUMERIC_FIELDS = ("basis_notional_usd", "max_drawdown_limit_pct", "basis_min_funding_apr",
                  "basis_min_net_apr", "basis_holding_days", "max_spread_bps", "whale_danger_zone_pct",
                  "alert_cooldown_seconds", "spot_min_volume_notional_multiple", "spot_min_day_volume")
INT_FIELDS = ("max_concurrent_positions",)
FLAG_FIELDS = ("emergency_killswitch", "pause_new_entries", "allow_synthetic_tradfi_basis")


def _write(vault_dir, body):
    vault_dir.mkdir(exist_ok=True)
    (vault_dir / "Bot_Config.md").write_text("---\n" + body + "---\n# Bot Config\n", encoding="utf-8")


def test_every_field_falls_back_on_its_own_and_the_others_still_load(tmp_path, caplog):
    """
    Round 45 (Ruling 45-1). One corrupt field used to abort the whole reload,
    which get_config() swallowed by keeping the last cached config - silently.
    Now each field warns and takes its own default while its neighbours load.
    """
    from config.dynamic_config import BotConfig
    d = BotConfig()
    vault_dir = tmp_path / "obsidian_vault"
    for field in NUMERIC_FIELDS + INT_FIELDS:
        caplog.clear()
        _write(vault_dir, f"basis_min_net_apr: 33.0\nmax_spread_bps: 9.0\n{field}: garbage\n")
        cfg = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config()
        assert getattr(cfg, field) == getattr(d, field), field                 # its own default
        if field != "basis_min_net_apr":
            assert cfg.basis_min_net_apr == 33.0, field                          # the neighbours loaded
        if field != "max_spread_bps":
            assert cfg.max_spread_bps == 9.0, field
        assert cfg.emergency_killswitch is False, field                          # a bad field is not a corrupt file
        assert sum("using the" in r.message for r in caplog.records) == 1, field
    # An integer field accepts 3.0 and "3" and rejects 2.5-as-text? No: int(float("2.5")) is 2, by design.
    _write(vault_dir, "max_concurrent_positions: 3.0\n")
    assert DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config().max_concurrent_positions == 3


def test_a_corrupt_field_falls_back_to_the_active_presets_value(tmp_path, caplog):
    """
    Round 46 (Ruling 46-2). A "conservative" operator who mistypes the notional
    line must land on the conservative $5,000, not be scaled up to the
    dataclass's $10,000. "custom", an unknown preset, or a field the preset does
    not carry take the dataclass / settings default.
    """
    from config.dynamic_config import BotConfig, PRESETS
    from config.settings import SPOT_MIN_DAY_VOLUME
    vault_dir = tmp_path / "obsidian_vault"
    cases = (("conservative", 5000.0, 1, 35.0), ("aggressive", 25000.0, 4, 18.0),
             ("custom", 10000.0, 2, 25.0), ("weird", 10000.0, 2, 25.0))
    for preset, notional, slots, gross_bar in cases:
        caplog.clear()
        _write(vault_dir, f'active_preset: "{preset}"\nbasis_notional_usd: garbage\n'
                          f"max_concurrent_positions: nope\nbasis_min_funding_apr: ???\n"
                          f"spot_min_day_volume: bad\nmax_spread_bps: 9.0\n")
        cfg = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config()
        assert cfg.basis_notional_usd == notional, preset
        assert cfg.max_concurrent_positions == slots, preset
        assert cfg.basis_min_funding_apr == gross_bar, preset
        assert cfg.spot_min_day_volume == SPOT_MIN_DAY_VOLUME, preset          # presets carry no spot fields
        assert cfg.max_spread_bps == 9.0, preset                                # a good line still wins
        assert cfg.emergency_killswitch is False, preset
        assert cfg.active_preset == (preset if preset in PRESETS or preset == "custom" else "custom")
        assert sum("using the" in r.message for r in caplog.records) == 4, preset
    # The preset only supplies FALLBACKS: a well-formed line under "conservative" is honoured as written.
    _write(vault_dir, 'active_preset: "conservative"\nbasis_notional_usd: 7500.0\n')
    assert DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config().basis_notional_usd == 7500.0
    assert BotConfig().basis_notional_usd == 10000.0


def test_malformed_safety_flags_fail_armed_not_off(tmp_path, caplog):
    """A kill-switch that reads "maybe" stops trading; a spot policy flag that reads "maybe" stays at its default."""
    vault_dir = tmp_path / "obsidian_vault"
    _write(vault_dir, "emergency_killswitch: maybe\npause_new_entries: 7\nallow_synthetic_tradfi_basis: perhaps\n")
    cfg = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config()
    assert cfg.emergency_killswitch is True
    assert cfg.pause_new_entries is True
    assert cfg.allow_synthetic_tradfi_basis is False
    assert sum("using the" in r.message for r in caplog.records) == 3
    # Absent safety flags are simply off - absence is not corruption.
    _write(vault_dir, "basis_notional_usd: 5000.0\n")
    cfg = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config()
    assert cfg.emergency_killswitch is False and cfg.pause_new_entries is False
    # And a well-formed "false" is honoured.
    _write(vault_dir, "emergency_killswitch: false\npause_new_entries: FALSE\n")
    cfg = DynamicConfigManager(vault_path=vault_dir, json_path=tmp_path / "cfg.json").get_config()
    assert cfg.emergency_killswitch is False and cfg.pause_new_entries is False


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
