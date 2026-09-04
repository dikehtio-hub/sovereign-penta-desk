"""
Dexter State Store
Small stdlib-only lock + atomic-write helpers shared by process_manager.py
(processes.json) and vault_bridge.py's task id counter (task_counter.json).

Built lock-safe now so a future background daemon can call the same
process_manager/vault functions in a loop without a redesign — see the Dexter
implementation plan for why this matters even though nothing runs a loop yet.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Dict


class LockTimeoutError(Exception):
    """Raised when a state file lock can't be acquired within the timeout."""


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def acquire_lock(path: Path, timeout: float = 5.0, poll_interval: float = 0.05) -> Path:
    """Acquire an exclusive lock for `path` via an O_CREAT|O_EXCL sentinel file.
    Works identically on Windows and POSIX, no extra dependency."""
    lock_path = _lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lock_path
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockTimeoutError(f"could not acquire lock on {path} within {timeout}s")
            time.sleep(poll_interval)


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json_atomic(path: Path, data: Any) -> None:
    """Write via temp-file + os.replace() — atomic on the same NTFS volume."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def update_json_locked(path: Path, mutate_fn, default: Any) -> Any:
    """Read-modify-write `path` under a lock. `mutate_fn(data) -> data` returns
    the new value to persist. Returns the new value."""
    lock_path = acquire_lock(path)
    try:
        data = read_json(path, default)
        data = mutate_fn(data)
        write_json_atomic(path, data)
        return data
    finally:
        release_lock(lock_path)


def next_counter(path: Path, key: str = "next") -> int:
    """Atomically increment and return an integer counter stored at `path`."""
    result = {}

    def _bump(data: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal result
        current = data.get(key, 0)
        data[key] = current + 1
        result = data
        return data

    update_json_locked(path, _bump, default={key: 0})
    return result[key]
