"""
Dexter Task Dispatcher & Model Router
Dispatches tasks from the Obsidian Vault or CLI to the optimal AI model engine.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import settings
from .gemini_bridge import GeminiBridge
from .claude_bridge import ClaudeBridge
from .memory_sync import MemorySync
from .vault_bridge import VaultBridge


class TaskDispatcher:
    """Intelligent task router and orchestrator across Gemini, Claude, Claude Code, and Antigravity."""

    def __init__(self):
        self.vault = VaultBridge()
        self.memory = MemorySync(self.vault)
        self.gemini = GeminiBridge()
        self.claude = ClaudeBridge()

    def route_model(self, task_description: str, forced_target: Optional[str] = None) -> str:
        """Determine the best model engine for a given task if not explicitly specified."""
        if forced_target:
            return forced_target.lower()

        desc_lower = task_description.lower()

        # Code execution / refactor in terminal -> Claude Code
        if any(k in desc_lower for k in ["refactor files", "git commit", "run tests", "terminal", "claude code", "build repo"]):
            return "claude-code"

        # Large context / multimodal / broad analysis -> Gemini
        if any(k in desc_lower for k in ["analyze notes", "large context", "multimodal", "video", "audio", "pdf", "gemini", "summarize vault"]):
            return "gemini"

        # Deep logic / math / architectural reasoning -> Claude API
        if any(k in desc_lower for k in ["design pattern", "architecture", "complex reasoning", "claude", "proof"]):
            return "claude"

        # Default to fast multimodal model (Gemini)
        return "gemini"

    def execute_task(
        self,
        task_input: str | Path,
        target_engine: Optional[str] = None,
        complete_note: bool = True,
    ) -> str:
        """
        Execute a task from a prompt string or task file path.
        Returns the agent response text.
        """
        task_path: Optional[Path] = None
        task_meta = {}
        prompt = ""
        task_title = "Ad-hoc Task"

        # Check if task_input points to a file in the vault
        potential_path = Path(task_input)
        if not potential_path.is_absolute():
            potential_path = settings.vault_path / potential_path

        if potential_path.exists() and potential_path.suffix == ".md":
            task_path = potential_path
            task_meta, body = self.vault.read_note(task_path)
            prompt = body
            task_title = task_meta.get("title", task_path.stem)
            if not target_engine:
                target_engine = task_meta.get("assigned_agent")
        else:
            prompt = str(task_input)
            task_title = prompt[:30].replace("\n", " ")

        engine = self.route_model(prompt, target_engine)
        system_prompt = self.memory.build_unified_system_prompt(agent_role=f"Dexter {engine.upper()} Agent")

        print(f"[*] Dispatching task '{task_title}' to [{engine.upper()}]...")

        output = ""
        if engine == "gemini":
            output = self.gemini.generate(
                prompt=prompt,
                system_instruction=system_prompt,
                task_name=task_title,
            )
        elif engine == "claude":
            output = self.claude.generate(
                prompt=prompt,
                system_instruction=system_prompt,
                task_name=task_title,
            )
        elif engine == "claude-code":
            res = self.claude.run_claude_code(prompt=prompt, task_name=task_title)
            output = res.get("stdout") or res.get("stderr") or "No output returned."
        elif engine == "antigravity":
            output = (
                f"### Antigravity Task Directive\n\n"
                f"This task is formatted for Google Antigravity autonomous execution:\n\n"
                f"```yaml\n"
                f"task: {task_title}\n"
                f"target_workspace: {settings.dev_root}\n"
                f"```\n\n"
                f"**Instructions:**\n{prompt}\n"
            )
            self.vault.log_agent_run("Antigravity", task_title, prompt, output)
        else:
            output = f"Unknown engine: {engine}"

        # If it was an existing task note and complete_note is True, mark completed
        if task_path and complete_note:
            self.vault.complete_task(task_path, agent_summary=output)
            print(f"[+] Task marked completed and moved to {settings.completed_tasks_dir.name}/")

        return output


def main():
    """CLI entrypoint for Dexter Task Dispatcher."""
    parser = argparse.ArgumentParser(description="Dexter Task Dispatcher & Model Router")
    parser.add_argument("task", help="Task prompt string or path to an Obsidian task note")
    parser.add_argument(
        "--engine",
        "-e",
        choices=["gemini", "claude", "claude-code", "antigravity", "auto"],
        default="auto",
        help="Target AI engine to run the task (default: auto-route)",
    )
    parser.add_argument(
        "--no-complete",
        action="store_true",
        help="Do not mark task as completed in Obsidian",
    )

    args = parser.parse_args()
    dispatcher = TaskDispatcher()
    target = None if args.engine == "auto" else args.engine

    result = dispatcher.execute_task(
        task_input=args.task,
        target_engine=target,
        complete_note=not args.no_complete,
    )
    print("\n--- AGENT RESULT ---")
    print(result)


if __name__ == "__main__":
    main()
