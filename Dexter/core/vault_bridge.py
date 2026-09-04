"""
Dexter Vault Bridge
High-level interface for reading, writing, and querying the Obsidian Vault.
"""

from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None

from . import state_store
from .config import settings

TASK_COUNTER_PATH = settings.dexter_root / "state" / "task_counter.json"
VALID_TASK_STATUSES = {"pending", "in-progress", "blocked", "completed"}


class VaultBridge:
    """Interface to read, write, parse, and organize Obsidian Markdown files."""

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or settings.vault_path
        settings.ensure_directories()

    # -------------------------------------------------------------------------
    # Frontmatter Parsing & Serialization
    # -------------------------------------------------------------------------
    @staticmethod
    def parse_markdown(content: str) -> Tuple[Dict[str, Any], str]:
        """
        Extract YAML frontmatter and markdown body from file content.
        Returns: (frontmatter_dict, body_markdown)
        """
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}, content

        raw_yaml, body = match.group(1), match.group(2)
        metadata: Dict[str, Any] = {}

        if yaml:
            try:
                parsed = yaml.safe_load(raw_yaml)
                if isinstance(parsed, dict):
                    metadata = parsed
            except Exception:
                metadata = {}
        else:
            # Fallback simple key-value parser if PyYAML is absent
            for line in raw_yaml.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip().strip('"').strip("'")

        return metadata, body

    @staticmethod
    def serialize_markdown(metadata: Dict[str, Any], body: str) -> str:
        """Combine metadata dict and body into standard Obsidian frontmatter format."""
        if not metadata:
            return body

        if yaml:
            yaml_str = yaml.dump(metadata, sort_keys=False, default_flow_style=False).strip()
        else:
            lines = [f"{k}: {v}" for k, v in metadata.items()]
            yaml_str = "\n".join(lines)

        return f"---\n{yaml_str}\n---\n\n{body.lstrip()}"

    # -------------------------------------------------------------------------
    # File Operations
    # -------------------------------------------------------------------------
    def read_note(self, relative_or_abs_path: str | Path) -> Tuple[Dict[str, Any], str]:
        """Read a note and return its frontmatter and body."""
        p = Path(relative_or_abs_path)
        if not p.is_absolute():
            p = self.vault_path / p

        if not p.exists():
            raise FileNotFoundError(f"Note not found: {p}")

        content = p.read_text(encoding="utf-8")
        return self.parse_markdown(content)

    def write_note(
        self,
        relative_or_abs_path: str | Path,
        metadata: Dict[str, Any],
        body: str,
        overwrite: bool = True,
    ) -> Path:
        """Write a note with frontmatter and body to the vault."""
        p = Path(relative_or_abs_path)
        if not p.is_absolute():
            p = self.vault_path / p

        if p.exists() and not overwrite:
            raise FileExistsError(f"Note already exists: {p}")

        p.parent.mkdir(parents=True, exist_ok=True)
        content = self.serialize_markdown(metadata, body)
        p.write_text(content, encoding="utf-8")
        return p

    # -------------------------------------------------------------------------
    # Task Management
    # -------------------------------------------------------------------------
    def create_task(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        assigned_agent: str = "unassigned",
        tags: Optional[List[str]] = None,
        destination_folder: Optional[Path] = None,
    ) -> Path:
        """Create a new standardized task note in the vault."""
        dest = destination_folder or settings.active_tasks_dir
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title).replace(" ", "_")
        filename = f"TASK_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title}.md"
        target_path = dest / filename
        task_id = f"T-{state_store.next_counter(TASK_COUNTER_PATH):04d}"

        metadata = {
            "id": task_id,
            "title": title,
            "type": "task",
            "status": "pending",
            "priority": priority,
            "assigned_agent": assigned_agent,
            "created_at": timestamp,
            "updated_at": timestamp,
            "tags": tags or ["task", "dexter"],
        }

        body = f"""# {title}

## Objective
{description}

## Context & Requirements
- **Target Systems:** (e.g. Gemini, Antigravity, Claude Code, Obsidian)
- **Desired Output:**

## Execution Log
- [ ] Task initialized: `{timestamp}`

## Agent Results
*(Results and artifacts will be posted here)*
"""
        return self.write_note(target_path, metadata, body)

    def list_tasks(self, folder: Optional[Path] = None) -> List[Dict[str, Any]]:
        """List tasks with their metadata from a given folder or Active tasks directory."""
        search_dir = folder or settings.active_tasks_dir
        tasks = []
        if not search_dir.exists():
            return tasks

        for md_file in search_dir.glob("*.md"):
            try:
                meta, body = self.read_note(md_file)
                tasks.append({
                    "file_name": md_file.name,
                    "file_path": str(md_file),
                    "metadata": meta,
                    "preview": body[:200].replace("\n", " ").strip()
                })
            except Exception:
                continue
        return tasks

    def complete_task(self, task_file: Path | str, agent_summary: str) -> Path:
        """Mark a task as completed, append agent summary, and move to Completed folder."""
        p = Path(task_file)
        if not p.is_absolute():
            p = self.vault_path / p

        meta, body = self.read_note(p)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta["status"] = "completed"
        meta["completed_at"] = now_str
        meta["updated_at"] = now_str

        completed_body = f"""{body}

---
## Completion Summary ({now_str})
**Completed by:** `{meta.get('assigned_agent', 'Dexter Agent')}`

{agent_summary}
"""
        dest_path = settings.completed_tasks_dir / p.name
        self.write_note(dest_path, meta, completed_body, overwrite=True)
        if p.exists() and p != dest_path:
            p.unlink()

        return dest_path

    # -------------------------------------------------------------------------
    # Task lookup / status by short id (e.g. "T-0001")
    # -------------------------------------------------------------------------
    def find_task_path_by_id(self, task_id: str) -> Path:
        """Search Active/ then Completed/ for a task note with metadata id == task_id."""
        for folder in (settings.active_tasks_dir, settings.completed_tasks_dir):
            if not folder.exists():
                continue
            for md_file in folder.glob("*.md"):
                try:
                    meta, _ = self.read_note(md_file)
                except Exception:
                    continue
                if meta.get("id") == task_id:
                    return md_file
        raise FileNotFoundError(f"No task found with id '{task_id}'")

    def update_task_status(self, task_id: str, status: str) -> Path:
        """Set a task's status in place (does not move it between folders —
        use complete_task_by_id for the pending/in-progress/blocked -> completed
        transition, which does move it to Completed/)."""
        if status not in VALID_TASK_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_TASK_STATUSES)}, got '{status}'")

        path = self.find_task_path_by_id(task_id)
        meta, body = self.read_note(path)
        meta["status"] = status
        meta["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.write_note(path, meta, body, overwrite=True)
        return path

    def complete_task_by_id(self, task_id: str, agent_summary: str = "") -> Path:
        """Look up a task by its short id and complete it (moves to Completed/)."""
        path = self.find_task_path_by_id(task_id)
        return self.complete_task(path, agent_summary=agent_summary)

    # -------------------------------------------------------------------------
    # Log & Telemetry Output
    # -------------------------------------------------------------------------
    def log_agent_run(
        self,
        agent_name: str,
        task_name: str,
        input_prompt: str,
        output_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Save a full transcript log to the 05_Logs_&_Telemetry directory."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        safe_agent = agent_name.replace(" ", "_")
        safe_task = re.sub(r'[\\/*?:"<>|]', "", task_name).replace(" ", "_")[:30]

        agent_log_dir = settings.logs_dir / f"{safe_agent}_Runs"
        agent_log_dir.mkdir(parents=True, exist_ok=True)
        log_file = agent_log_dir / f"{date_str}_{time_str}_{safe_task}.md"

        log_meta = {
            "agent": agent_name,
            "task": task_name,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "success",
            **(metadata or {}),
        }

        body = f"""# Run Log: {task_name}

**Agent:** `{agent_name}`
**Timestamp:** `{log_meta['timestamp']}`

## Input / Prompt
```markdown
{input_prompt}
```

## Output / Artifacts
{output_response}
"""
        return self.write_note(log_file, log_meta, body)
