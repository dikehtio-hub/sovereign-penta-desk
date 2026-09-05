"""
Single-instance lock for the Polymarket watcher (Round 55, Directive 55-1).

Two watchers on ONE drop folder write the same canonical files and duplicate
every stamped copy, so the lock is keyed to the folder: <folder>/polymarket_watcher.pid.
The semantics mirror HL_Monarch's CollectorSupervisor (Round 53, Ruling 53-5)
without importing across trees:

  * a pid file naming a dead process, a corrupt value, or a live process whose
    command line is not a watcher is STALE and swept;
  * a live watcher refuses the newcomer (`acquire` returns its pid);
  * the file is removed on orderly exit (atexit + signal handlers), and the
    sweep covers the exits that run neither (a closed console, a hard kill).

Liveness never uses os.kill(pid, 0): on Windows CPython maps that onto
TerminateProcess, so the "probe" would kill the watcher it was asked about.
"""
from __future__ import annotations

import atexit
import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

WATCHER_PID_NAME = "polymarket_watcher.pid"
WATCHER_MARK = "polymarket_fetcher"                 # what a watcher's command line must contain

DEFAULT_SIGNALS: Tuple[int, ...] = tuple(
    sig for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None),
                    getattr(signal, "SIGBREAK", None))
    if sig is not None)


def read_pid_file(path) -> Optional[int]:
    """The pid recorded in the file, or None when absent, corrupt or non-positive."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        pid = int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    return pid if pid > 0 else None


def pid_is_alive(pid: int) -> bool:
    """Whether a process with this id exists. Windows: OpenProcess + GetExitCodeProcess; POSIX: signal 0."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_cmdline(pid: int) -> Optional[str]:
    """The command line of `pid`; "" when it cannot be read; None when psutil is absent."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        return " ".join(psutil.Process(pid).cmdline())
    except Exception:                                       # noqa: BLE001 - access denied, zombie, gone
        return ""


def is_stale(path, probe: Optional[Callable[[int], Optional[str]]] = None, mark: str = WATCHER_MARK,
             alive: Optional[Callable[[int], bool]] = None) -> bool:
    """True when the file names a dead process, a corrupt value, or a live process that is not a watcher."""
    pid = read_pid_file(path)
    if pid is None:
        return True
    if not (alive or pid_is_alive)(pid):
        return True
    cmdline = (probe or process_cmdline)(pid)
    return cmdline is not None and mark.lower() not in cmdline.lower()


def remove_stale_pid_file(path, probe=None, mark: str = WATCHER_MARK, alive=None) -> bool:
    """Delete a stale pid file; True when a file was removed. Never raises."""
    p = Path(path)
    if not p.exists() or not is_stale(p, probe, mark, alive):
        return False
    try:
        p.unlink()
    except OSError:
        return False
    return True


def acquire(path, pid: Optional[int] = None, probe=None, mark: str = WATCHER_MARK, alive=None) -> Optional[int]:
    """
    Sweep a stale file, then claim the lock for `pid` (default: this process)
    with an EXCLUSIVE create. Returns None when claimed, the pid of the live
    watcher that holds it, or -1 when another starter holds it but its pid
    could not be read yet (treat as running). Sweep-then-write would let two
    starters that both saw a stale file both claim; O_EXCL leaves exactly one.
    """
    p = Path(path)
    own = int(pid or os.getpid())
    p.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        remove_stale_pid_file(p, probe, mark, alive)
        try:
            fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            holder = None
            for _ in range(5):                              # the winner writes right after creating
                holder = read_pid_file(p)
                if holder is not None:
                    break
                time.sleep(0.05)
            if holder == own:
                return None                                 # our own earlier claim
            if holder is not None and not is_stale(p, probe, mark, alive):
                return holder                               # a live watcher: refuse
            if attempt == 2:
                return holder if holder is not None else -1
            continue                                        # stale after all, or unreadable: sweep and retry
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("%d\n" % own)
        return None
    return -1


def release(path, pid: Optional[int] = None) -> bool:
    """Remove the file only while it still names `pid` (default: this process); True when removed."""
    p = Path(path)
    own = int(pid or os.getpid())
    if read_pid_file(p) != own:
        return False
    try:
        p.unlink()
    except OSError:
        return False
    return True


def install_cleanup(path, pid: Optional[int] = None, register=atexit.register,
                    signals: Iterable[int] = DEFAULT_SIGNALS, set_handler=signal.signal):
    """
    Release the lock on orderly exit: an atexit hook, plus handlers for the
    given signals that release and then raise SystemExit(128 + signum) so the
    atexit chain still runs. Best effort by nature - a hard kill or a closed
    console window runs none of this, which is what the stale sweep is for.
    Returns (cleanup, on_signal, installed_signals).
    """
    own = int(pid or os.getpid())

    def cleanup() -> bool:
        return release(path, own)

    def on_signal(signum, frame):                          # noqa: ARG001 - signal handler signature
        cleanup()
        raise SystemExit(128 + int(signum))

    register(cleanup)
    installed = []
    for sig in signals:
        try:
            set_handler(sig, on_signal)
            installed.append(sig)
        except (ValueError, OSError, RuntimeError, TypeError):
            pass                                            # not the main thread, or unsupported here
    return cleanup, on_signal, tuple(installed)
