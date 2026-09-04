"""
👑 HL_Monarch Dynamic Risk & Parameter Configuration Manager
Loads, validates, and hot-reloads trading parameters directly from Obsidian's `Bot_Config.md`
YAML frontmatter (or local fallback `data/bot_config.json`) without restarting running daemons.
"""

import os
import re
import sys
import json
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("DynamicConfig")

from config.settings import (  # noqa: E402 - settings imports nothing from here
    ALLOW_SYNTHETIC_TRADFI_BASIS as _SETTINGS_ALLOW_SYNTHETIC_TRADFI_BASIS,
    SPOT_MIN_DAY_VOLUME as _SETTINGS_SPOT_MIN_DAY_VOLUME,
    SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE as _SETTINGS_SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE,
)

MONARCH_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = MONARCH_DIR / "data"
DEFAULT_JSON_PATH = DEFAULT_DATA_DIR / "bot_config.json"
DEFAULT_VAULT_PATH = Path("C:/Users/ixis1/Desktop/DEV/obsidian_vault") if Path("C:/Users/ixis1/Desktop/DEV/obsidian_vault").exists() else (MONARCH_DIR / "obsidian_vault")
PM_DASHBOARD_NOTE = "Polymarket_Monarch"
QL_DASHBOARD_NOTE = "Quant_Trading_Lab"

USER_RUNBOOK_HEADER = "## 📝 Strategy Notes & Runbook"
DEFAULT_USER_RUNBOOK = """
*Add your custom trading notes, risk checklists, parameter justifications, and strategy runbooks below:*
- **Risk Checklist**: Verified spot liquidity, checked funding persistence (>4h), confirmed maker fees.
- **Notes**: 
"""

PRESETS: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "basis_notional_usd": 5000.0,
        "max_concurrent_positions": 1,
        "max_drawdown_limit_pct": 5.0,
        "basis_min_funding_apr": 35.0,
        "basis_min_net_apr": 25.0,
        "basis_holding_days": 7.0,
        "max_spread_bps": 15.0,
        "whale_danger_zone_pct": 3.0,
        "alert_cooldown_seconds": 120.0,
        "emergency_killswitch": False,
        "pause_new_entries": False,
        "active_preset": "conservative",
    },
    "balanced": {
        "basis_notional_usd": 10000.0,
        "max_concurrent_positions": 2,
        "max_drawdown_limit_pct": 10.0,
        "basis_min_funding_apr": 25.0,
        "basis_min_net_apr": 20.0,
        "basis_holding_days": 7.0,
        "max_spread_bps": 25.0,
        "whale_danger_zone_pct": 5.0,
        "alert_cooldown_seconds": 60.0,
        "emergency_killswitch": False,
        "pause_new_entries": False,
        "active_preset": "balanced",
    },
    "aggressive": {
        "basis_notional_usd": 25000.0,
        "max_concurrent_positions": 4,
        "max_drawdown_limit_pct": 15.0,
        "basis_min_funding_apr": 18.0,
        "basis_min_net_apr": 14.0,
        "basis_holding_days": 5.0,
        "max_spread_bps": 35.0,
        "whale_danger_zone_pct": 8.0,
        "alert_cooldown_seconds": 30.0,
        "emergency_killswitch": False,
        "pause_new_entries": False,
        "active_preset": "aggressive",
    },
}

# Bounds for safety clamping
BOUNDS = {
    "basis_notional_usd": (1000.0, 100000.0),
    "max_concurrent_positions": (1, 10),
    "max_drawdown_limit_pct": (1.0, 50.0),
    "basis_min_funding_apr": (5.0, 300.0),
    "basis_min_net_apr": (1.0, 250.0),
    "basis_holding_days": (1.0, 60.0),
    "max_spread_bps": (2.0, 100.0),
    "whale_danger_zone_pct": (1.0, 30.0),
    "alert_cooldown_seconds": (5.0, 600.0),
    # Round 43 (Ruling 43-6): spot-leg liquidity thresholds, hot-reloadable.
    "spot_min_volume_notional_multiple": (1.0, 100.0),
    "spot_min_day_volume": (10_000.0, 10_000_000.0),      # Round 44: $1k was too low a floor
}


def _config_number(config_dict: Dict[str, Any], key: str, default: float) -> float:
    """
    A numeric Bot_Config field, or `default` with a warning when it is absent or
    unparseable (Round 44, Ruling 44-4). One bad field must not take the whole
    config down with it - and must not silently become something else.
    """
    raw = config_dict.get(key)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(f"Bot_Config {key}={raw!r} is not a number; using the settings default {default}")
        return float(default)


def _config_int(config_dict: Dict[str, Any], key: str, default: int) -> int:
    """An integer Bot_Config field ("3", 3, 3.0 all read as 3); else `default` with a warning."""
    raw = config_dict.get(key)
    if raw is None:
        return int(default)
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        logger.warning(f"Bot_Config {key}={raw!r} is not an integer; using the default {default}")
        return int(default)


def _config_flag(config_dict: Dict[str, Any], key: str, default: bool) -> bool:
    """A boolean Bot_Config field; anything but true/false falls back with a warning."""
    raw = config_dict.get(key)
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in ("true", "yes", "1"):
        return True
    if text in ("false", "no", "0"):
        return False
    logger.warning(f"Bot_Config {key}={raw!r} is not true/false; using the settings default {default}")
    return bool(default)


@dataclass
class BotConfig:
    basis_notional_usd: float = 10000.0
    max_concurrent_positions: int = 2
    max_drawdown_limit_pct: float = 10.0
    basis_min_funding_apr: float = 25.0
    basis_min_net_apr: float = 20.0
    basis_holding_days: float = 7.0
    max_spread_bps: float = 25.0
    whale_danger_zone_pct: float = 5.0
    alert_cooldown_seconds: float = 60.0
    emergency_killswitch: bool = False
    pause_new_entries: bool = False
    active_preset: str = "balanced"
    # Round 43 (Ruling 43-6): the spot-leg rules that used to need a service
    # restart. Defaults are the settings constants; Bot_Config.md overrides live.
    allow_synthetic_tradfi_basis: bool = _SETTINGS_ALLOW_SYNTHETIC_TRADFI_BASIS
    spot_min_volume_notional_multiple: float = _SETTINGS_SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE
    spot_min_day_volume: float = _SETTINGS_SPOT_MIN_DAY_VOLUME

    def validate_and_clamp(self) -> 'BotConfig':
        """Clamp parameters to strictly safe operating boundaries."""
        for key, (low, high) in BOUNDS.items():
            val = getattr(self, key, None)
            if val is not None:
                if isinstance(val, int):
                    clamped = max(int(low), min(int(high), int(val)))
                else:
                    clamped = max(float(low), min(float(high), float(val)))
                setattr(self, key, clamped)
        if self.active_preset not in ("conservative", "balanced", "aggressive", "custom"):
            self.active_preset = "custom"
        return self


def parse_yaml_frontmatter(content: str) -> Dict[str, Any]:
    """Lightweight, robust YAML frontmatter parser handling BOM, whitespace, and fence variations."""
    if not content:
        return {}
    cleaned = content.lstrip("\ufeff \t\r\n")
    if not cleaned.startswith("---"):
        return {}
    parts = cleaned.split("---")
    if len(parts) < 2:
        return {}
    yaml_block = parts[1]
    result: Dict[str, Any] = {}
    for line in yaml_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val.lower() == "true":
            result[key] = True
        elif val.lower() == "false":
            result[key] = False
        elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            result[key] = val[1:-1]
        else:
            try:
                if "." in val:
                    result[key] = float(val)
                else:
                    result[key] = int(val)
            except ValueError:
                result[key] = val
    return result


class DynamicConfigManager:
    """Thread-safe, high-performance hot-reloader for Bot Configuration."""
    _instance: Optional['DynamicConfigManager'] = None

    def __init__(self, vault_path: Optional[Path] = None, json_path: Optional[Path] = None):
        self.vault_path = Path(vault_path) if vault_path else self._resolve_vault_path()
        self.json_path = Path(json_path) if json_path else DEFAULT_JSON_PATH
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_note_path = self.vault_path / "Bot_Config.md"
        self._last_mtime: float = -1.0
        self._cached_config: BotConfig = BotConfig().validate_and_clamp()
        self.reload()

    @classmethod
    def get_instance(cls, vault_path: Optional[Path] = None) -> 'DynamicConfigManager':
        target_path = Path(vault_path).expanduser().resolve() if vault_path else cls._resolve_vault_path()
        if cls._instance is None or cls._instance.vault_path != target_path:
            cls._instance = DynamicConfigManager(vault_path=target_path)
        return cls._instance

    @staticmethod
    def _resolve_vault_path() -> Path:
        if os.environ.get("OBSIDIAN_VAULT_PATH"):
            p = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
        else:
            p = DEFAULT_VAULT_PATH
        p.mkdir(parents=True, exist_ok=True)
        return p

    def is_halt_flag_present(self) -> bool:
        """Check if a hard HALT.flag sentinel exists in vault or DEV directory."""
        halt_paths = [
            self.vault_path / "HALT.flag",
            self.vault_path / "EMERGENCY_HALT.flag",
            MONARCH_DIR / "HALT.flag",
            MONARCH_DIR.parent / "HALT.flag",
            Path("C:/Users/ixis1/Desktop/DEV/HALT.flag"),
        ]
        return any(p.exists() for p in halt_paths)

    def get_config(self) -> BotConfig:
        """Fetch current config, hot-reloading if the file modified on disk."""
        target_file = self.config_note_path if self.config_note_path.exists() else self.json_path
        if target_file.exists():
            try:
                mtime = target_file.stat().st_mtime
                if mtime != self._last_mtime:
                    self.reload()
            except Exception as e:
                logger.warning(f"Error checking config mtime: {e}")

        if self.is_halt_flag_present():
            self._cached_config.emergency_killswitch = True
            self._cached_config.pause_new_entries = True
        return self._cached_config

    def reload(self) -> BotConfig:
        """Force a reload from Bot_Config.md or JSON fallback with fail-closed safety."""
        config_dict: Dict[str, Any] = {}
        read_success = False
        mtime = -1.0

        if self.config_note_path.exists():
            for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
                try:
                    content = self.config_note_path.read_text(encoding=enc)
                    config_dict = parse_yaml_frontmatter(content)
                    if config_dict:
                        read_success = True
                        mtime = self.config_note_path.stat().st_mtime
                        break
                except Exception:
                    continue

        if not read_success and self.json_path.exists():
            try:
                content = self.json_path.read_text(encoding="utf-8")
                config_dict = json.loads(content)
                if config_dict:
                    read_success = True
                    mtime = self.json_path.stat().st_mtime
            except Exception as e:
                logger.warning(f"Failed to read {self.json_path}: {e}")

        if read_success and config_dict:
            self._last_mtime = mtime
            # Round 45 (Ruling 45-1): every field parses on its own. A corrupt,
            # missing or unparseable value logs a warning and takes that field's
            # default; the other fields load normally. The whole-file fail-closed
            # path below is reached only when the note cannot be read or its
            # frontmatter yields nothing at all. The two SAFETY flags are the one
            # deliberate asymmetry: a kill-switch that reads "maybe" is armed, not
            # off - a malformed safety value must stop trading, never enable it.
            # Round 46 (Ruling 46-2): the fallback is PRESET-AWARE. active_preset is
            # read first; a corrupt field then takes the value that preset gives it
            # (a "conservative" operator whose notional line is mistyped gets $5k,
            # not the dataclass's $10k). "custom", an unknown preset, or a field the
            # preset does not carry falls back to the dataclass / settings default.
            d = BotConfig()
            preset_name = str(config_dict.get("active_preset", "custom")).strip().lower()
            preset_defaults = PRESETS.get(preset_name, {})

            def dflt(field: str):
                return preset_defaults.get(field, getattr(d, field))

            cfg = BotConfig(
                basis_notional_usd=_config_number(config_dict, "basis_notional_usd", dflt("basis_notional_usd")),
                max_concurrent_positions=_config_int(config_dict, "max_concurrent_positions", dflt("max_concurrent_positions")),
                max_drawdown_limit_pct=_config_number(config_dict, "max_drawdown_limit_pct", dflt("max_drawdown_limit_pct")),
                basis_min_funding_apr=_config_number(config_dict, "basis_min_funding_apr", dflt("basis_min_funding_apr")),
                basis_min_net_apr=_config_number(config_dict, "basis_min_net_apr", dflt("basis_min_net_apr")),
                basis_holding_days=_config_number(config_dict, "basis_holding_days", dflt("basis_holding_days")),
                max_spread_bps=_config_number(config_dict, "max_spread_bps", dflt("max_spread_bps")),
                whale_danger_zone_pct=_config_number(config_dict, "whale_danger_zone_pct", dflt("whale_danger_zone_pct")),
                alert_cooldown_seconds=_config_number(config_dict, "alert_cooldown_seconds", dflt("alert_cooldown_seconds")),
                emergency_killswitch=_config_flag(config_dict, "emergency_killswitch", True)
                if "emergency_killswitch" in config_dict else bool(dflt("emergency_killswitch")),
                pause_new_entries=_config_flag(config_dict, "pause_new_entries", True)
                if "pause_new_entries" in config_dict else bool(dflt("pause_new_entries")),
                active_preset=preset_name,
                allow_synthetic_tradfi_basis=_config_flag(
                    config_dict, "allow_synthetic_tradfi_basis", _SETTINGS_ALLOW_SYNTHETIC_TRADFI_BASIS),
                spot_min_volume_notional_multiple=_config_number(
                    config_dict, "spot_min_volume_notional_multiple", _SETTINGS_SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE),
                spot_min_day_volume=_config_number(
                    config_dict, "spot_min_day_volume", _SETTINGS_SPOT_MIN_DAY_VOLUME),
            )
            self._cached_config = cfg.validate_and_clamp()
        else:
            # FAIL-CLOSED ON RISK: Keep last known parameters, but force emergency killswitch = True!
            logger.error(f"Failed to parse valid config from {self.config_note_path} -> FAILING CLOSED (KILLSWITCH ARMED)")
            self._cached_config.emergency_killswitch = True
            self._cached_config.pause_new_entries = True
            # Do NOT update _last_mtime so next read will re-attempt parsing

        if self.is_halt_flag_present():
            self._cached_config.emergency_killswitch = True
            self._cached_config.pause_new_entries = True

        return self._cached_config

    def apply_preset(self, preset_name: str) -> BotConfig:
        """Apply a predefined risk preset and write it out to Bot_Config.md and JSON."""
        name = preset_name.lower().strip()
        if name not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_name}. Valid: {list(PRESETS.keys())}")
        preset_data = PRESETS[name]
        cfg = BotConfig(**preset_data).validate_and_clamp()
        self.save_config(cfg)
        return cfg

    def set_killswitch(self, active: bool = True) -> BotConfig:
        """Activate or deactivate emergency killswitch."""
        cfg = self.get_config()
        cfg.emergency_killswitch = active
        if active:
            cfg.pause_new_entries = True
        self.save_config(cfg)
        return cfg

    def set_pause(self, paused: bool = True) -> BotConfig:
        """Pause or resume new trade entries."""
        cfg = self.get_config()
        cfg.pause_new_entries = paused
        if not paused and cfg.emergency_killswitch:
            cfg.emergency_killswitch = False
        self.save_config(cfg)
        return cfg

    def save_config(self, cfg: BotConfig) -> None:
        """Persist config to both JSON and Bot_Config.md while preserving notes."""
        cfg.validate_and_clamp()
        self._cached_config = cfg

        # 1. Save JSON
        try:
            self.json_path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save {self.json_path}: {e}")

        # 2. Save Bot_Config.md
        self._write_config_note(cfg)

    def _write_config_note(self, cfg: BotConfig) -> None:
        self.vault_path.mkdir(parents=True, exist_ok=True)
        user_notes = DEFAULT_USER_RUNBOOK
        if self.config_note_path.exists():
            try:
                old_content = self.config_note_path.read_text(encoding="utf-8")
                if USER_RUNBOOK_HEADER in old_content:
                    user_notes = old_content.split(USER_RUNBOOK_HEADER, 1)[1]
            except Exception:
                pass

        kill_status = "🚨 **ENGAGED (HALTED)**" if cfg.emergency_killswitch else "🟢 **ARMED / READY (NORMAL)**"
        pause_status = "⏸️ **PAUSED (NO NEW ENTRIES)**" if cfg.pause_new_entries else "🟢 **ACTIVE**"
        preset_badge = f"`{cfg.active_preset.upper()}`"

        yaml_header = f"""---
title: Monarch Bot Configuration & Dynamic Risk Controller
basis_notional_usd: {cfg.basis_notional_usd}
max_concurrent_positions: {cfg.max_concurrent_positions}
max_drawdown_limit_pct: {cfg.max_drawdown_limit_pct}
basis_min_funding_apr: {cfg.basis_min_funding_apr}
basis_min_net_apr: {cfg.basis_min_net_apr}
basis_holding_days: {cfg.basis_holding_days}
max_spread_bps: {cfg.max_spread_bps}
whale_danger_zone_pct: {cfg.whale_danger_zone_pct}
alert_cooldown_seconds: {cfg.alert_cooldown_seconds}
emergency_killswitch: {str(cfg.emergency_killswitch).lower()}
pause_new_entries: {str(cfg.pause_new_entries).lower()}
active_preset: "{cfg.active_preset}"
allow_synthetic_tradfi_basis: {str(cfg.allow_synthetic_tradfi_basis).lower()}
spot_min_volume_notional_multiple: {cfg.spot_min_volume_notional_multiple}
spot_min_day_volume: {cfg.spot_min_day_volume}
tags:
  - monarch
  - bot-config
  - risk-management
---"""

        pm_link_row = f"- [[{PM_DASHBOARD_NOTE}|🌐 Polymarket Intelligence]]\n" if (self.vault_path / f"{PM_DASHBOARD_NOTE}.md").exists() else ""
        ql_link_row = f"- [[{QL_DASHBOARD_NOTE}|⚡ Quant Trading Lab]]\n" if (self.vault_path / f"{QL_DASHBOARD_NOTE}.md").exists() else ""

        content = f"""{yaml_header}

# ⚙️ Monarch Bot Configuration & Dynamic Risk Controller

> [!INFO] **Live Parameter Hot-Reload Controller**
> Edit any field in the YAML frontmatter above and save. Running daemons automatically detect changes in `< 1s` without dropping WebSocket feeds.
> - **Active Risk Preset**: {preset_badge}
> - **Execution Status**: {pause_status}
> - **Emergency Kill-Switch**: {kill_status}

---

## 🎛️ 1-Click Quick Presets & Safety Actions

| Preset / Action | Notional / Leg | Max Slots | Min Gross APR | Min Net APR | Action Trigger |
| :--- | :---: | :---: | :---: | :---: | :--- |
| 🛡️ **Conservative** | `$5,000` | `1` | `35.0%` | `25.0%` | [[Bot_Control#Presets|Run Conservative Preset]] |
| ⚖️ **Balanced (Default)** | `$10,000` | `2` | `25.0%` | `20.0%` | [[Bot_Control#Presets|Run Balanced Preset]] |
| ⚔️ **Aggressive** | `$25,000` | `4` | `18.0%` | `14.0%` | [[Bot_Control#Presets|Run Aggressive Preset]] |
| 🚨 **EMERGENCY STOP** | — | `0` | — | — | [[Bot_Control#Safety|Trigger Emergency Halt]] |
| ⏸️ **Pause / Resume** | — | — | — | — | [[Bot_Control#Safety|Toggle Entry Gating]] |

---

## 📊 Active Strategy Parameter Deck

| Parameter Key | Current Value | Safe Operating Bounds | Parameter Description |
| :--- | :---: | :---: | :--- |
| **`basis_notional_usd`** | **`${cfg.basis_notional_usd:,.2f}`** | `$1,000 - $100,000` | Capital allocation per leg ($10k notional = $20k total commitment per position) |
| **`max_concurrent_positions`** | **`{cfg.max_concurrent_positions}`** | `1 - 10 slots` | Maximum simultaneous delta-neutral basis pairs open |
| **`max_drawdown_limit_pct`** | **`{cfg.max_drawdown_limit_pct:.1f}%`** | `1.0% - 50.0%` | Maximum portfolio drawdown threshold before automated gating |
| **`basis_min_funding_apr`** | **`{cfg.basis_min_funding_apr:.1f}%`** | `5.0% - 300.0%` | Gross annualized funding rate threshold required for entry |
| **`basis_min_net_apr`** | **`{cfg.basis_min_net_apr:.1f}%`** | `1.0% - 250.0%` | Net annualized funding rate required after both legs' spread & fees |
| **`basis_holding_days`** | **`{cfg.basis_holding_days:.1f} days`** | `1.0 - 60.0 days` | Holding period used to amortize entry/exit spread frictions |
| **`max_spread_bps`** | **`{cfg.max_spread_bps:.1f} bps`** | `2.0 - 100.0 bps` | Maximum allowable top-of-book bid/ask spread on spot & perp |
| **`whale_danger_zone_pct`** | **`{cfg.whale_danger_zone_pct:.1f}%`** | `1.0% - 30.0%` | Liquidation distance threshold for high-risk whale account alerts |
| **`alert_cooldown_seconds`** | **`{cfg.alert_cooldown_seconds:.0f}s`** | `5 - 600 seconds` | Minimum seconds between duplicate liquidation cascade webhooks |
| **`allow_synthetic_tradfi_basis`** | **`{str(cfg.allow_synthetic_tradfi_basis).lower()}`** | `true / false` | Allow basis hedges on stock, index, commodity, bond and FX perps (weekend-gap risk; keep false) |
| **`spot_min_volume_notional_multiple`** | **`{cfg.spot_min_volume_notional_multiple:.1f}x`** | `1 - 100x` | Spot pair must turn over this many times the per-leg notional per day (10x = one fill is 10% of ADV) |
| **`spot_min_day_volume`** | **`${cfg.spot_min_day_volume:,.0f}`** | `$10,000 - $10,000,000` | Absolute floor on the spot pair's 24h notional, whatever the notional multiple gives |

---

## 🔗 Quick Navigation

- [[Monarch_Hub|👑 Monarch Intelligence Hub]]
- [[Bot_Control|🎮 Bot Control & Activation Deck]]
- [[Trading_Terminal|📈 Live Trading Terminal & 50-Trade Hurdle]]
- [[HyperLiquid_Monarch|🏛 HyperLiquid Market Dashboard]]
{pm_link_row}{ql_link_row}---

{USER_RUNBOOK_HEADER}
{user_notes.strip()}
"""
        self.config_note_path.write_text(content.strip() + "\n", encoding="utf-8")
        try:
            self._last_mtime = self.config_note_path.stat().st_mtime
        except Exception:
            pass


def get_dynamic_config(vault_path: Optional[Path] = None) -> BotConfig:
    """Global accessor for hot-reloaded BotConfig."""
    return DynamicConfigManager.get_instance(vault_path=vault_path).get_config()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monarch Dynamic Risk & Parameter Controller")
    parser.add_argument("--preset", choices=["conservative", "balanced", "aggressive"], help="Apply risk preset")
    parser.add_argument("--killswitch", action="store_true", help="Activate emergency kill-switch")
    parser.add_argument("--pause", action="store_true", help="Pause new trade entries")
    parser.add_argument("--resume", action="store_true", help="Resume entries and clear killswitch")
    parser.add_argument("--show", action="store_true", help="Print current active configuration")
    parser.add_argument("--vault", type=str, default=None, help="Target Obsidian Vault path")

    args = parser.parse_args()
    mgr = DynamicConfigManager(vault_path=Path(args.vault) if args.vault else None)

    if args.preset:
        res = mgr.apply_preset(args.preset)
        print(f"✓ Applied '{args.preset.upper()}' preset: {res}")
    elif args.killswitch:
        res = mgr.set_killswitch(True)
        print(f"🚨 EMERGENCY KILL-SWITCH ENGAGED! All entries halted.")
    elif args.pause:
        res = mgr.set_pause(True)
        print(f"⏸️ Entries PAUSED.")
    elif args.resume:
        res = mgr.set_pause(False)
        print(f"🟢 Entries RESUMED. Kill-switch cleared.")
    elif args.show or len(sys.argv) == 1:
        cfg = mgr.get_config()
        print("\n👑 Monarch Bot Current Active Configuration:")
        print(json.dumps(asdict(cfg), indent=2))
