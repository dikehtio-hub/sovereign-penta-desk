"""
Dexter Role Contract (duck-typed — no base class to inherit from)

A role is any .py file in this folder (other than base.py/__init__.py) that
defines, at module level:

    ROLE_ID: str            unique slug, e.g. "bot-status-summarizer"
    DESCRIPTION: str        one line, shown by `role list`
    def run(ctx: dict) -> None

`ctx` hands the role the same already-constructed objects the CLI uses, so a
role has full access without wiring anything itself:

    ctx["registry"]          core.registry.Registry
    ctx["process_manager"]   core.process_manager.ProcessManager
    ctx["vault"]              core.vault_bridge.VaultBridge
    ctx["memory"]             core.memory_sync.MemorySync
    ctx["config"]             core.config.settings

Bad or incomplete modules are skipped with a warning by the loader below
rather than crashing role discovery.
"""

from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

_REQUIRED_ATTRS = ("ROLE_ID", "DESCRIPTION", "run")
_SKIP_MODULES = {"base", "__init__"}


def discover_roles() -> Dict[str, ModuleType]:
    """Import every valid role module in this package. Returns {role_id: module}."""
    roles: Dict[str, ModuleType] = {}
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name in _SKIP_MODULES:
            continue
        try:
            module = importlib.import_module(f"{__package__}.{module_name}")
        except Exception as e:
            print(f"[roles] skipping '{module_name}': import failed ({e})")
            continue

        missing = [a for a in _REQUIRED_ATTRS if not hasattr(module, a)]
        if missing:
            print(f"[roles] skipping '{module_name}': missing {missing}")
            continue

        roles[module.ROLE_ID] = module
    return roles


def list_roles() -> List[Dict[str, str]]:
    return [{"id": m.ROLE_ID, "description": m.DESCRIPTION} for m in discover_roles().values()]


def run_role(role_id: str, ctx: Dict[str, Any]) -> None:
    roles = discover_roles()
    if role_id not in roles:
        raise ValueError(f"no such role '{role_id}'. Known roles: {sorted(roles.keys())}")
    roles[role_id].run(ctx)
