"""
Dexter Memory Sync
Unifies and synchronizes shared memory, user profile, and system directives across all models.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import settings
from .vault_bridge import VaultBridge


class MemorySync:
    """Manages persistent context across Gemini, Antigravity, and Claude."""

    def __init__(self, vault: Optional[VaultBridge] = None):
        self.vault = vault or VaultBridge()
        self.memory_dir = settings.memory_dir

    def get_user_profile(self) -> str:
        """Read the User Profile note."""
        path = self.memory_dir / "User_Profile.md"
        if path.exists():
            _, body = self.vault.read_note(path)
            return body.strip()
        return "No User Profile defined."

    def get_system_directives(self) -> str:
        """Read Core System Directives."""
        path = self.memory_dir / "System_Directives.md"
        if path.exists():
            _, body = self.vault.read_note(path)
            return body.strip()
        return "No System Directives defined."

    def get_shared_context(self) -> str:
        """Read shared persistent facts and dynamic state."""
        path = self.memory_dir / "Shared_Context.md"
        if path.exists():
            _, body = self.vault.read_note(path)
            return body.strip()
        return "No Shared Context defined."

    def build_unified_system_prompt(self, agent_role: str = "General Assistant") -> str:
        """
        Assemble a complete system prompt including Directives, User Profile,
        and Shared Context to maintain seamless continuity between models.
        """
        directives = self.get_system_directives()
        profile = self.get_user_profile()
        context = self.get_shared_context()

        return f"""# Dexter Agent Directives ({agent_role})

You are an integrated AI agent inside the user's Dexter ecosystem.

## 1. System Directives & Operating Rules
{directives}

## 2. User Preferences & Profile
{profile}

## 3. Persistent Shared Context & Facts
{context}

---
Always format markdown outputs cleanly with GitHub Flavored Markdown and Obsidian-compatible wikilinks when referencing other notes.
"""

    def append_shared_fact(self, category: str, fact: str) -> None:
        """Append a new learned fact or state update to Shared_Context.md."""
        path = self.memory_dir / "Shared_Context.md"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        meta: Dict[str, Any] = {}
        body = ""
        if path.exists():
            meta, body = self.vault.read_note(path)

        addition = f"\n- **[{category.upper()}]** ({now_str}): {fact}"
        new_body = body + addition
        meta["updated_at"] = now_str
        self.vault.write_note(path, meta, new_body, overwrite=True)
