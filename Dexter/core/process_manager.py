"""
Dexter Process Manager
Starts, stops, and health-checks the agents/bots listed in registry.yaml, as
plain Windows subprocesses. No daemon here — see state_store.py's docstring for
why the state layer is still built lock/atomic-safe.
"""

from __future__ import annotations
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from . import state_store
from .config import settings
from .registry import Registry, RegistryError
from .vault_bridge import VaultBridge

STATE_DIR = settings.dexter_root / "state"
PROCESSES_STATE_PATH = STATE_DIR / "processes.json"
LOGS_DIR = settings.dexter_root / "logs"

STOP_GRACE_SECONDS = 10.0


class ProcessManagerError(Exception):
    """Raised for start/stop errors that are the caller's fault (not-enabled,
    unknown id, already running, etc.) — distinct from health-check results,
    which are always a normal dict, never an exception."""


class ProcessManager:
    def __init__(self, registry: Optional[Registry] = None, vault: Optional[VaultBridge] = None):
        self.registry = registry or Registry()
        self.vault = vault or VaultBridge()

    # -------------------------------------------------------------------
    # State helpers
    # -------------------------------------------------------------------
    def _read_state(self) -> Dict[str, Any]:
        return state_store.read_json(PROCESSES_STATE_PATH, default={})

    def _write_entry(self, entry_id: str, record: Optional[Dict[str, Any]]) -> None:
        def _mutate(data: Dict[str, Any]) -> Dict[str, Any]:
            if record is None:
                data.pop(entry_id, None)
            else:
                data[entry_id] = record
            return data

        state_store.update_json_locked(PROCESSES_STATE_PATH, _mutate, default={})

    # -------------------------------------------------------------------
    # Health check — never trust cached state alone
    # -------------------------------------------------------------------
    def status(self, entry_id: str) -> Dict[str, Any]:
        state = self._read_state()
        record = state.get(entry_id)

        if not record:
            return {"id": entry_id, "state": "stopped", "pid": None}

        pid = record["pid"]
        stored_create_time = record.get("create_time")

        if not psutil.pid_exists(pid):
            return {"id": entry_id, "state": "stopped", "pid": pid, "reason": "process not found"}

        try:
            proc = psutil.Process(pid)
            live_create_time = proc.create_time()
        except psutil.NoSuchProcess:
            return {"id": entry_id, "state": "stopped", "pid": pid, "reason": "process not found"}

        if stored_create_time is not None and abs(live_create_time - stored_create_time) > 1.0:
            # PID was recycled by the OS for an unrelated process since we started ours.
            return {"id": entry_id, "state": "stopped", "pid": pid, "reason": "pid reused by another process"}

        uptime_seconds = time.time() - live_create_time
        return {
            "id": entry_id,
            "state": "running",
            "pid": pid,
            "uptime_seconds": round(uptime_seconds, 1),
            "log_path": record.get("log_path"),
            "started_at": record.get("started_at"),
        }

    def status_all(self) -> list[Dict[str, Any]]:
        return [self.status(e["id"]) for e in self.registry.list_entries()]

    # -------------------------------------------------------------------
    # Start
    # -------------------------------------------------------------------
    def start(self, entry_id: str) -> Dict[str, Any]:
        try:
            entry = self.registry.get_entry(entry_id)
        except RegistryError as e:
            raise ProcessManagerError(str(e)) from e

        if not entry["enabled"]:
            raise ProcessManagerError(
                f"'{entry_id}' is disabled in registry.yaml (enabled: false) — "
                f"no bypass. Review it and flip enabled: true first."
            )

        current = self.status(entry_id)
        if current["state"] == "running":
            raise ProcessManagerError(f"'{entry_id}' is already running (pid {current['pid']})")

        # Preflight checks: cwd must exist, command[0] must be executable/resolved
        cwd_path = Path(entry["cwd"])
        if not cwd_path.is_dir():
            raise ProcessManagerError(f"Cannot start '{entry_id}': cwd directory does not exist: {entry['cwd']}")

        cmd0 = entry["command"][0]
        if os.path.sep in cmd0 or (os.path.altsep and os.path.altsep in cmd0):
            exe_path = Path(cmd0)
            if not exe_path.is_absolute():
                exe_path = cwd_path / exe_path
            if not exe_path.is_file():
                raise ProcessManagerError(f"Cannot start '{entry_id}': executable not found at {exe_path}")
        else:
            import shutil
            if not shutil.which(cmd0, path=os.environ.get("PATH", "") + os.pathsep + str(cwd_path)):
                raise ProcessManagerError(f"Cannot start '{entry_id}': executable '{cmd0}' not found on PATH or in {cwd_path}")

        log_dir = LOGS_DIR / entry_id
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"run_{timestamp}.log"

        cmd = list(entry["command"])
        if cmd and cmd[0].lower() in ("python", "python.exe"):
            cmd[0] = sys.executable

        flags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            flags |= subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags |= subprocess.CREATE_NO_WINDOW

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=entry["cwd"],
                stdout=fd,
                stderr=fd,
                env=env,
                creationflags=flags,
            )
        except Exception as e:
            os.close(fd)
            raise ProcessManagerError(f"Failed to spawn process for '{entry_id}': {e}") from e
        os.close(fd)

        # Check if process immediately crashed
        time.sleep(0.15)
        if proc.poll() is not None:
            err_msg = ""
            try:
                err_msg = log_path.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                pass
            raise ProcessManagerError(f"'{entry_id}' failed immediately on startup (exit code {proc.returncode}). Output: {err_msg or log_path}")

        psutil_proc = psutil.Process(proc.pid)
        record = {
            "pid": proc.pid,
            "create_time": psutil_proc.create_time(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "log_path": str(log_path),
            "command": entry["command"],
            "cwd": entry["cwd"],
        }
        self._write_entry(entry_id, record)

        self.vault.log_agent_run(
            agent_name=entry_id,
            task_name="process-start",
            input_prompt=" ".join(entry["command"]),
            output_response=f"Started pid {proc.pid}. Log: {log_path}",
            metadata={"category": entry["category"], "cwd": entry["cwd"]},
        )

        return {"id": entry_id, "pid": proc.pid, "log_path": str(log_path)}

    # -------------------------------------------------------------------
    # Stop — graceful CTRL_BREAK_EVENT, then taskkill /T /F fallback
    # -------------------------------------------------------------------
    def stop(self, entry_id: str, grace_seconds: float = STOP_GRACE_SECONDS) -> Dict[str, Any]:
        current = self.status(entry_id)
        if current["state"] != "running":
            self._write_entry(entry_id, None)
            raise ProcessManagerError(f"'{entry_id}' is not running")

        pid = current["pid"]
        stopped_via = None

        # Tier 1: graceful attempt. NOTE: the AGENTS/*/agent.py scripts only
        # handle KeyboardInterrupt (SIGINT), not SIGBREAK, and install no
        # SIGBREAK handler — so in practice this will very likely just
        # terminate them without running their own cleanup/summary print,
        # and Tier 2 will fire almost immediately below. This is a real
        # Windows/target-script limitation, not something this silently
        # papers over: fixing it means adding a shutdown handler to those
        # scripts, which is out of scope here (see the Dexter plan).
        try:
            os.kill(pid, signal.CTRL_BREAK_EVENT)
            deadline = time.monotonic() + grace_seconds
            while time.monotonic() < deadline:
                if self.status(entry_id)["state"] == "stopped":
                    stopped_via = "graceful (CTRL_BREAK_EVENT)"
                    break
                time.sleep(0.25)
        except (OSError, ProcessLookupError):
            pass

        # Tier 2: forced fallback — kills the whole process tree.
        if stopped_via is None:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
            # Give the OS a brief moment to actually reap it before checking.
            time.sleep(0.5)
            stopped_via = "forced (taskkill /T /F)"

        self._write_entry(entry_id, None)

        self.vault.log_agent_run(
            agent_name=entry_id,
            task_name="process-stop",
            input_prompt="",
            output_response=f"Stopped pid {pid} via {stopped_via}.",
            metadata={"pid": pid, "method": stopped_via},
        )

        final_status = self.status(entry_id)
        return {"id": entry_id, "pid": pid, "method": stopped_via, "confirmed_stopped": final_status["state"] == "stopped"}
