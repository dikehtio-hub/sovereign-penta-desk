"""
Dexter CLI
Entry point for process control (agents/bots) and second-brain task tracking.

Usage (from Dexter/):
    python -m core.cli list
    python -m core.cli start <id>
    python -m core.cli stop <id>
    python -m core.cli status [<id>]
    python -m core.cli task add "<title>" [--priority p]
    python -m core.cli task list [--status s]
    python -m core.cli task done <task_id>
    python -m core.cli role list
    python -m core.cli role run <role_id>
"""

from __future__ import annotations
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .memory_sync import MemorySync
from .process_manager import ProcessManager, ProcessManagerError
from .registry import Registry, RegistryError
from .roles import list_roles, run_role
from .vault_bridge import VaultBridge

console = Console()
app = typer.Typer(help="Dexter: process control + second-brain task tracking")
task_app = typer.Typer(help="Task tracking in the Obsidian vault")
role_app = typer.Typer(help="Run or list extensible roles")
app.add_typer(task_app, name="task")
app.add_typer(role_app, name="role")


def _ctx() -> dict:
    """Build the shared context every role/command runs against."""
    vault = VaultBridge()
    registry = Registry()
    return {
        "vault": vault,
        "registry": registry,
        "process_manager": ProcessManager(registry=registry, vault=vault),
        "memory": MemorySync(vault),
    }


# -------------------------------------------------------------------------
# Process control
# -------------------------------------------------------------------------
@app.command("list")
def list_entries():
    """List every registry entry with its live state."""
    ctx = _ctx()
    table = Table(title="Dexter Registry")
    table.add_column("id")
    table.add_column("name")
    table.add_column("category")
    table.add_column("enabled")
    table.add_column("state")

    for entry in ctx["registry"].list_entries():
        st = ctx["process_manager"].status(entry["id"])
        state_text = f"[green]{st['state']}[/]" if st["state"] == "running" else f"[yellow]{st['state']}[/]"
        enabled_text = "[green]yes[/]" if entry["enabled"] else "[red]no[/]"
        table.add_row(entry["id"], entry["name"], entry["category"], enabled_text, state_text)

    console.print(table)


@app.command()
def start(entry_id: str):
    """Start a registered agent/bot (must have enabled: true in registry.yaml)."""
    ctx = _ctx()
    try:
        result = ctx["process_manager"].start(entry_id)
        console.print(f"[green]started[/] '{entry_id}' — pid {result['pid']}, log: {result['log_path']}")
    except (ProcessManagerError, RegistryError) as e:
        console.print(f"[red]error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def stop(entry_id: str):
    """Stop a running agent/bot."""
    ctx = _ctx()
    try:
        result = ctx["process_manager"].stop(entry_id)
        status_word = "green" if result["confirmed_stopped"] else "red"
        console.print(f"[{status_word}]stopped[/] '{entry_id}' (pid {result['pid']}) via {result['method']}")
    except ProcessManagerError as e:
        console.print(f"[red]error:[/] {e}")
        raise typer.Exit(1)


@app.command("start-all")
def start_all():
    """Start all enabled agents and bots in the registry."""
    ctx = _ctx()
    entries = ctx["registry"].list_entries()
    for entry in entries:
        if not entry.get("enabled"):
            continue
        eid = entry["id"]
        try:
            cur = ctx["process_manager"].status(eid)
            if cur["state"] == "running":
                console.print(f"[yellow]already running[/] '{eid}' (pid {cur['pid']})")
                continue
            res = ctx["process_manager"].start(eid)
            console.print(f"[green]started[/] '{eid}' — pid {res['pid']}")
        except Exception as e:
            console.print(f"[red]failed to start '{eid}':[/] {e}")


@app.command("stop-all")
def stop_all():
    """Stop all running agents and bots."""
    ctx = _ctx()
    entries = ctx["registry"].list_entries()
    for entry in entries:
        eid = entry["id"]
        try:
            cur = ctx["process_manager"].status(eid)
            if cur["state"] == "running":
                res = ctx["process_manager"].stop(eid)
                console.print(f"[green]stopped[/] '{eid}' (pid {res['pid']})")
        except Exception as e:
            console.print(f"[red]failed to stop '{eid}':[/] {e}")


@app.command()
def status(entry_id: Optional[str] = typer.Argument(None)):
    """Show health-checked status for one entry, or every entry if omitted."""
    ctx = _ctx()
    ids = [entry_id] if entry_id else [e["id"] for e in ctx["registry"].list_entries()]
    for eid in ids:
        st = ctx["process_manager"].status(eid)
        if st["state"] == "running":
            console.print(f"[green]{eid}: running[/] (pid {st['pid']}, up {st['uptime_seconds']:.0f}s)")
        else:
            reason = f" — {st['reason']}" if st.get("reason") else ""
            console.print(f"[yellow]{eid}: stopped[/]{reason}")


# -------------------------------------------------------------------------
# Tasks
# -------------------------------------------------------------------------
@task_app.command("add")
def task_add(
    title: str,
    priority: str = typer.Option("medium", help="low | medium | high"),
    assigned_agent: str = typer.Option("unassigned"),
):
    vault = VaultBridge()
    path = vault.create_task(title=title, description="", priority=priority, assigned_agent=assigned_agent)
    meta, _ = vault.read_note(path)
    console.print(f"[green]created[/] {meta['id']} — {path.name}")


@task_app.command("list")
def task_list(status: Optional[str] = typer.Option(None, help="filter: pending | in-progress | blocked | completed")):
    vault = VaultBridge()
    from .config import settings

    folder = settings.completed_tasks_dir if status == "completed" else settings.active_tasks_dir
    tasks = vault.list_tasks(folder)

    table = Table(title="Tasks")
    table.add_column("id")
    table.add_column("title")
    table.add_column("status")
    table.add_column("priority")
    for t in tasks:
        meta = t["metadata"]
        if status and meta.get("status") != status:
            continue
        table.add_row(meta.get("id", "?"), meta.get("title", t["file_name"]), meta.get("status", "?"), meta.get("priority", "?"))
    console.print(table)


@task_app.command("done")
def task_done(task_id: str, summary: str = typer.Option("", help="optional completion summary")):
    vault = VaultBridge()
    try:
        path = vault.complete_task_by_id(task_id, agent_summary=summary)
        console.print(f"[green]completed[/] {task_id} -> {path}")
    except FileNotFoundError as e:
        console.print(f"[red]error:[/] {e}")
        raise typer.Exit(1)


@task_app.command("status")
def task_status(task_id: str, new_status: str):
    """Update a task's status without completing/moving it (pending | in-progress | blocked)."""
    vault = VaultBridge()
    try:
        path = vault.update_task_status(task_id, new_status)
        console.print(f"[green]updated[/] {task_id} -> {new_status} ({path.name})")
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]error:[/] {e}")
        raise typer.Exit(1)


# -------------------------------------------------------------------------
# Roles
# -------------------------------------------------------------------------
@role_app.command("list")
def role_list():
    table = Table(title="Roles")
    table.add_column("id")
    table.add_column("description")
    for r in list_roles():
        table.add_row(r["id"], r["description"])
    console.print(table)


@role_app.command("run")
def role_run(role_id: str):
    ctx = _ctx()
    try:
        run_role(role_id, ctx)
    except ValueError as e:
        console.print(f"[red]error:[/] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
