"""Master Module 23 (Round 96, Ratification R95-A..G): the knowledge layer.

WHAT THIS PACKAGE IS. The compiled, compounding wiki layer the Round 95
blueprint (LLM_WIKI_BLUEPRINT.md) found missing from DEV. The desk ``data/``
folders are the raw layer and stay exactly where the daemons write them;
``obsidian_vault/WIKI_SCHEMA.md`` is the constitution; this package is the
tooling that keeps ``obsidian_vault/{wiki,crm,journal,raw}/`` honest.

WHAT IT REFUSES, FAIL-CLOSED. Every command refuses when ``DEV/HALT.flag``
exists (exit 3, like the sniper, the AMM module and the C2 bot). Every write
goes through ``pages.write_page`` which refuses any path outside the four
owned folders and the three owned files; a page whose ``dev.window`` contains
now is refused too (registration files are never amended inside a window).
Nothing here opens a socket, imports an executor or writes to a dashboard,
an entity note, a drop folder, a stamp folder or a database.

FRONTMATTER. OKF v0.2 (GoogleCloudPlatform/knowledge-catalog, okf/SPEC.md):
``type`` is the only required field; ``generated``, ``verified``, ``status``,
``stale_after`` and ``sources`` are the optional families; ``index.md`` and
``log.md`` are reserved with fixed line formats. DEV extensions live under
one ``dev:`` key so an OKF consumer, which must tolerate unknown keys, reads
the vault untouched.
"""
from __future__ import annotations

from pathlib import Path

DEV_ROOT = Path(__file__).resolve().parents[1]
VAULT = DEV_ROOT / "obsidian_vault"

HALT_FLAG_NAME = "HALT.flag"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_HALT = 3

# The only places this package may write (Ratification R95-A).
OWNED_DIRS = ("wiki", "crm", "journal", "raw")
OWNED_FILES = ("WIKI_SCHEMA.md", "index.md", "log.md")
# OKF reserved filenames: no frontmatter, fixed line formats.
RESERVED_FILES = ("index.md", "log.md")

GENERATED_BY = "claude-code/fable-5.1"


def halt_flag(dev_root: Path | None = None) -> Path:
    return (dev_root or DEV_ROOT) / HALT_FLAG_NAME


def halted(dev_root: Path | None = None) -> bool:
    """True when the ecosystem kill-switch file exists. Every CLI checks first."""
    return halt_flag(dev_root).exists()
