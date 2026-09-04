"""
Dexter Configuration Module
Loads environment settings, paths, and model defaults.

Dexter is split across two locations by design:
  - This code (DEV/Dexter/) is the engine.
  - The actual Obsidian vault — the second brain itself — lives at
    Desktop/Dexter/, a sibling of DEV/, not nested inside this project.
    DEFAULT_VAULT_PATH points there so the code and the vault stay in sync
    without duplicating vault content inside DEV/Dexter/.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

# Base Directories
DEXTER_ROOT = Path(__file__).resolve().parent.parent
DEV_ROOT = DEXTER_ROOT.parent
DEFAULT_VAULT_PATH = DEV_ROOT.parent / "Dexter"

# Try loading .env if python-dotenv is installed, or read directly
try:
    from dotenv import load_dotenv
    # Check Dexter/configs/.env first, then Dexter/.env, then DEV/.env
    env_paths = [
        DEXTER_ROOT / "configs" / ".env",
        DEXTER_ROOT / ".env",
        DEV_ROOT / ".env"
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            break
except ImportError:
    pass


class Settings:
    """Dexter engine settings and environment parameters."""

    # Paths
    dexter_root: Path = DEXTER_ROOT
    dev_root: Path = DEV_ROOT
    vault_path: Path = Path(os.getenv("OBSIDIAN_VAULT_PATH", str(DEFAULT_VAULT_PATH))).resolve()

    # API Keys
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # Vault Subdirectories
    @property
    def inbox_dir(self) -> Path:
        return self.vault_path / "00_Inbox"

    @property
    def agents_dir(self) -> Path:
        return self.vault_path / "01_Agents"

    @property
    def tasks_dir(self) -> Path:
        return self.vault_path / "02_Tasks_&_Workflows"

    @property
    def active_tasks_dir(self) -> Path:
        return self.tasks_dir / "Active"

    @property
    def completed_tasks_dir(self) -> Path:
        return self.tasks_dir / "Completed"

    @property
    def kb_dir(self) -> Path:
        return self.vault_path / "03_Knowledge_Base"

    @property
    def memory_dir(self) -> Path:
        return self.vault_path / "04_Memory_&_Context"

    @property
    def logs_dir(self) -> Path:
        return self.vault_path / "05_Logs_&_Telemetry"

    @property
    def templates_dir(self) -> Path:
        return self.vault_path / "Templates"

    # Default Models
    default_fast_model: str = os.getenv("DEFAULT_FAST_MODEL", "gemini-2.0-flash")
    default_reasoning_model: str = os.getenv("DEFAULT_REASONING_MODEL", "claude-3-7-sonnet")
    default_multimodal_model: str = os.getenv("DEFAULT_MULTIMODAL_MODEL", "gemini-1.5-pro")

    def ensure_directories(self) -> None:
        """Create all standard vault directories if they don't exist."""
        dirs = [
            self.vault_path,
            self.inbox_dir,
            self.agents_dir,
            self.tasks_dir,
            self.active_tasks_dir,
            self.completed_tasks_dir,
            self.kb_dir,
            self.memory_dir,
            self.logs_dir,
            self.templates_dir,
            self.logs_dir / "Antigravity_Runs",
            self.logs_dir / "Claude_Runs",
            self.logs_dir / "Gemini_Runs",
            self.kb_dir / "Prompts_Library",
            self.kb_dir / "Tech_Stack",
            self.kb_dir / "Research",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
