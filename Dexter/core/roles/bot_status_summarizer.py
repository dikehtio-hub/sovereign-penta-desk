"""
Dexter Role: bot-status-summarizer

Health-checks every registry entry and folds current state into
Shared_Context.md via the existing MemorySync.append_shared_fact — this is
the concrete mechanism that keeps the "second brain" current on what's
actually running, built entirely on methods that already existed in this
scaffold. Copy this file's shape for any future role.
"""

from __future__ import annotations
from typing import Any, Dict

ROLE_ID = "bot-status-summarizer"
DESCRIPTION = "Health-checks every registered agent/bot and logs current state into Shared_Context.md"


def run(ctx: Dict[str, Any]) -> None:
    registry = ctx["registry"]
    process_manager = ctx["process_manager"]
    memory = ctx["memory"]

    entries = registry.list_entries()
    lines = []
    for entry in entries:
        st = process_manager.status(entry["id"])
        if st["state"] == "running":
            lines.append(f"{entry['id']}: running (pid {st['pid']}, up {st['uptime_seconds']:.0f}s)")
        else:
            reason = f" ({st['reason']})" if st.get("reason") else ""
            lines.append(f"{entry['id']}: stopped{reason}")

    summary = "; ".join(lines) if lines else "no registry entries"
    memory.append_shared_fact("bot-status", summary)
    print(f"[bot-status-summarizer] {summary}")
