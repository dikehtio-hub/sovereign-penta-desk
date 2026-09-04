"""
Dexter Registry
Loads and validates the static list of controllable units (agents/bots) that
process_manager.py is allowed to start, stop, and health-check.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .config import settings

REGISTRY_PATH = settings.dexter_root / "registry.yaml"

REQUIRED_FIELDS = {"id", "name", "category", "cwd", "command", "enabled"}


class RegistryError(Exception):
    """Raised when registry.yaml is missing, malformed, or an entry is invalid."""


def _validate_entry(entry: Dict[str, Any], index: int) -> None:
    missing = REQUIRED_FIELDS - entry.keys()
    if missing:
        raise RegistryError(f"registry.yaml entry #{index} is missing required field(s): {sorted(missing)}")
    if not isinstance(entry["command"], list) or not entry["command"]:
        raise RegistryError(f"registry.yaml entry '{entry.get('id')}': 'command' must be a non-empty list")
    if not isinstance(entry["enabled"], bool):
        raise RegistryError(f"registry.yaml entry '{entry.get('id')}': 'enabled' must be true/false")


def load_registry(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load, parse, and validate registry.yaml. Raises RegistryError on any problem."""
    registry_path = path or REGISTRY_PATH
    if not registry_path.exists():
        raise RegistryError(f"registry.yaml not found at {registry_path}")

    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise RegistryError("registry.yaml must contain a top-level list of entries")

    seen_ids = set()
    for i, entry in enumerate(raw):
        _validate_entry(entry, i)
        if entry["id"] in seen_ids:
            raise RegistryError(f"duplicate registry id: '{entry['id']}'")
        seen_ids.add(entry["id"])

    return raw


class Registry:
    """Thin wrapper so callers don't have to pass a path around everywhere."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or REGISTRY_PATH
        self._entries = load_registry(self.path)

    def reload(self) -> None:
        self._entries = load_registry(self.path)

    def list_entries(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def get_entry(self, entry_id: str) -> Dict[str, Any]:
        for entry in self._entries:
            if entry["id"] == entry_id:
                return entry
        raise RegistryError(f"no registry entry with id '{entry_id}'")
