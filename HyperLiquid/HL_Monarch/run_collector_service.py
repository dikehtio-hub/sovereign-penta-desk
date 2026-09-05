"""
Resilient Collector Service Supervisor.

Everything downstream of the collector - the funding backtester, the squeeze
engine's percentiles and OI deltas - is only as trustworthy as the *continuity* of
`asset_snapshots`. Running `main.py collector` by hand produced ~1.7% coverage of a
72h window: long stretches with no data at all, which the backtester correctly
refuses to annualise.

This supervises the collector as a long-lived service:

  * restarts it automatically when it crashes or exits, with exponential backoff so
    a persistent failure (bad credentials, DNS down) does not become a hot loop;
  * resets that backoff after a run survives long enough to count as healthy, so
    one bad night does not permanently slow recovery;
  * emits structured single-line JSON logs, so uptime and restart causes can be
    grepped or parsed rather than eyeballed;
  * periodically measures and reports real snapshot coverage, which is the metric
    that actually matters - a process that is "up" but not writing rows is not
    doing its job.

Usage:
    python run_collector_service.py                       # run until stopped
    python run_collector_service.py --max-restarts 5      # give up after 5 crashes
    python run_collector_service.py --log-file svc.jsonl  # custom log destination

Stop with Ctrl+C; the child is terminated and a final report is written.
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SERVICE_DIR = Path(__file__).resolve().parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

DEFAULT_LOG_FILE = SERVICE_DIR / "data" / "collector_service.jsonl"
DEFAULT_PID_FILE = SERVICE_DIR / "data" / "collector_service.pid"

# A run that lasts this long is treated as healthy, which resets the backoff.
# Raised from 120s: a collector dying every ~3 minutes would have had its backoff
# reset on every cycle and so never escalated, hammering the API indefinitely.
HEALTHY_RUNTIME_SECONDS = 300.0
INITIAL_BACKOFF_SECONDS = 2.0
# Ceiling must sit above HEALTHY_RUNTIME_SECONDS: with both at 300s a chronically
# failing collector settled into exactly one retry per healthy-window and never
# backed off further.
MAX_BACKOFF_SECONDS = 600.0
COVERAGE_REPORT_INTERVAL = 900.0   # report measured coverage every 15 minutes


# Round 35 (Ruling 5.A): the collector host slept for nine hours and took the
# service with it. While the supervisor runs, Windows is asked not to sleep.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def set_keep_awake(enabled: bool, kernel32: Any = None) -> Optional[int]:
    """
    Ask Windows not to enter automatic sleep while this process lives.

    SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) holds the system
    awake until the same thread clears it with ES_CONTINUOUS alone - which also
    happens when the process exits. It stops the IDLE timer only: it does not
    stop a user choosing Sleep, a lid close configured to sleep, or a critical-
    battery shutdown, and the display may still turn off. Returns the previous
    state, or None where unsupported or refused - the caller logs it and carries
    on, because a collector that runs until the next sleep beats none at all.
    """
    if kernel32 is None:
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
        except Exception:
            return None
    flags = (ES_CONTINUOUS | ES_SYSTEM_REQUIRED) if enabled else ES_CONTINUOUS
    try:
        previous = kernel32.SetThreadExecutionState(flags)
    except Exception:
        return None
    return int(previous) if previous else None


class JsonLineFormatter(logging.Formatter):
    """One JSON object per line: greppable by humans, parseable by tooling."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def build_logger(log_file: Path, quiet: bool = False) -> logging.Logger:
    logger = logging.getLogger("CollectorService")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(JsonLineFormatter())
    logger.addHandler(file_handler)

    if not quiet:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(console)
    return logger


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields):
    logger.log(level, event, extra={"fields": fields})


def measure_coverage(hours: float = 24.0, max_gap_hours: float = 0.5) -> Dict[str, Any]:
    """
    Observed fraction of the last `hours` of snapshot history.

    Deliberately measured from the database rather than from process uptime: a
    collector that is running but failing to persist looks identical to a healthy
    one from the outside, and this is the number the backtester gates on.
    """
    try:
        from storage.repository import MarketRepository
        repo = MarketRepository()
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - int(hours * 3_600_000)
        with repo.db.connection as conn:
            rows = conn.execute(
                "SELECT DISTINCT timestamp FROM asset_snapshots "
                "WHERE timestamp >= ? ORDER BY timestamp ASC;",
                (cutoff,),
            ).fetchall()
        stamps = [int(r[0]) for r in rows]
    except Exception as e:
        return {"error": str(e), "coverage_pct": 0.0, "samples": 0}

    if len(stamps) < 2:
        return {"coverage_pct": 0.0, "samples": len(stamps), "gap_hours": hours}

    observed_h = 0.0
    gap_h = 0.0
    for a, b in zip(stamps, stamps[1:]):
        dt_h = (b - a) / 3_600_000.0
        if dt_h <= 0:
            continue
        if dt_h > max_gap_hours:
            gap_h += dt_h
        else:
            observed_h += dt_h

    return {
        "coverage_pct": round(min(100.0, observed_h / hours * 100.0), 2),
        "observed_hours": round(observed_h, 3),
        "gap_hours": round(gap_h, 3),
        "samples": len(stamps),
    }


def pid_is_alive(pid: int) -> bool:
    """
    Whether a process with this id currently exists.

    NOT implemented with os.kill(pid, 0). That is the standard POSIX liveness
    probe, but on Windows CPython maps os.kill() for any signal other than
    CTRL_C_EVENT/CTRL_BREAK_EVENT onto TerminateProcess() - so `os.kill(pid, 0)`
    *kills the process with exit code 0* rather than inspecting it. Using it here
    meant `--status` silently terminated the supervisor it was asked to report on,
    orphaning the collector child.

    Windows therefore goes through OpenProcess + GetExitCodeProcess, and POSIX
    keeps the signal-0 probe.
    """
    if pid <= 0:
        return False

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                # Handle opened but state unreadable: assume it exists.
                return True
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def read_pid_file(pid_file: Path) -> Optional[int]:
    """The pid recorded in the lockfile, or None if absent/corrupt."""
    path = Path(pid_file)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def running_supervisor_pid(pid_file: Path = DEFAULT_PID_FILE) -> Optional[int]:
    """
    The pid of a live supervisor, or None.

    Replaces command-line string matching, which was fragile in both directions:
    it reported a phantom process from a stale `wmic` parse, and later matched any
    command line that merely *named* the script (a linter run, a test run). A
    lockfile the supervisor itself writes is a positive identifier, and pairing it
    with a liveness probe means a stale file after a hard kill self-heals.
    """
    pid = read_pid_file(pid_file)
    if pid is None:
        return None
    return pid if pid_is_alive(pid) else None


def acquire_pid_lock(pid_file: Path = DEFAULT_PID_FILE) -> bool:
    """
    Claim the lockfile for this process. False if another supervisor holds it.

    A stale file - one naming a pid that no longer exists - is taken over rather
    than treated as a conflict, so a machine that lost power does not need manual
    cleanup before the service can start again.
    """
    path = Path(pid_file)
    existing = running_supervisor_pid(path)
    if existing is not None and existing != os.getpid():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_pid_lock(pid_file: Path = DEFAULT_PID_FILE) -> None:
    """Remove the lockfile, but only if it is still ours."""
    path = Path(pid_file)
    pid = read_pid_file(path)
    if pid is not None and pid != os.getpid():
        return  # someone else owns it now; leave it alone
    try:
        path.unlink()
    except OSError:
        pass


class CollectorSupervisor:
    """Keeps one collector process alive and reports on what it is producing."""

    def __init__(
        self,
        log_file: Path = DEFAULT_LOG_FILE,
        max_restarts: Optional[int] = None,
        quiet: bool = False,
        python_executable: Optional[str] = None,
        pid_file: Path = DEFAULT_PID_FILE,
        keep_awake: bool = True,
        child_log: Optional[Path] = None,
        child_log_max_bytes: int = 20_000_000,
        child_command: Optional[list] = None,
    ):
        self.logger = build_logger(Path(log_file), quiet=quiet)
        # Round 52: where the child's stdout/stderr go. It was DEVNULL, which made
        # every collector log line unobservable in service mode.
        self.child_log = Path(child_log) if child_log else SERVICE_DIR / "data" / "collector.log"
        self.child_log_max_bytes = int(child_log_max_bytes)
        self.child_command = list(child_command) if child_command else ["-u", "main.py", "collector"]
        self._child_log_handle = None
        self.keep_awake = bool(keep_awake)
        self._awake_state: Optional[int] = None
        self.pid_file = Path(pid_file)
        self.max_restarts = max_restarts
        self.python = python_executable or sys.executable
        self.running = False
        self.process: Optional[subprocess.Popen] = None
        self.restarts = 0
        self.started_at = 0.0
        self._last_coverage_report = 0.0

    def _open_child_log(self):
        """
        An append handle on the child log, rotating once (`.1`) when the file
        has grown past the cap. Falls back to DEVNULL if the file cannot be
        opened - a log failure must never stop the collector from starting.
        """
        try:
            if self._child_log_handle is not None:
                try:
                    self._child_log_handle.close()
                except Exception:                           # noqa: BLE001
                    pass
            self.child_log.parent.mkdir(parents=True, exist_ok=True)
            if self.child_log.exists() and self.child_log.stat().st_size > self.child_log_max_bytes:
                rotated = self.child_log.with_suffix(self.child_log.suffix + ".1")
                try:
                    if rotated.exists():
                        rotated.unlink()
                    self.child_log.rename(rotated)
                except OSError:
                    pass
            self._child_log_handle = open(self.child_log, "ab")
            return self._child_log_handle
        except Exception as e:                              # noqa: BLE001
            log_event(self.logger, "child_log_unavailable", level=logging.WARNING, path=str(self.child_log),
                      error=f"{type(e).__name__}: {e}")
            self._child_log_handle = None
            return subprocess.DEVNULL

    def _spawn(self) -> subprocess.Popen:
        """Start the collector as a child process; its stdout/stderr go to the child log."""
        sink = self._open_child_log()
        if sink is not subprocess.DEVNULL:
            log_event(self.logger, "child_log", path=str(self.child_log))
        return subprocess.Popen(
            [self.python] + self.child_command,
            cwd=str(SERVICE_DIR),
            stdout=sink,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
        )

    def _maybe_report_coverage(self):
        now = time.monotonic()
        if now - self._last_coverage_report < COVERAGE_REPORT_INTERVAL:
            return
        self._last_coverage_report = now
        stats = measure_coverage()
        level = logging.INFO if stats.get("coverage_pct", 0.0) >= 95.0 else logging.WARNING
        log_event(
            self.logger, "coverage_report", level=level,
            uptime_seconds=round(time.time() - self.started_at, 1),
            restarts=self.restarts, **stats,
        )

    def stop(self, *_):
        """Signal handler: stop supervising and terminate the child."""
        self.running = False
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def run(self) -> Dict[str, Any]:
        """Supervise until stopped or the restart budget is exhausted."""
        self.running = True
        self.started_at = time.time()
        backoff = INITIAL_BACKOFF_SECONDS

        signal.signal(signal.SIGINT, self.stop)
        try:
            signal.signal(signal.SIGTERM, self.stop)
        except (AttributeError, ValueError):
            pass  # not available on every platform / thread

        if not acquire_pid_lock(self.pid_file):
            holder = running_supervisor_pid(self.pid_file)
            log_event(self.logger, "already_running", level=logging.ERROR, holder_pid=holder)
            self.running = False
            return {"uptime_seconds": 0.0, "restarts": 0, "already_running": True,
                    "holder_pid": holder, "coverage_pct": 0.0}

        log_event(self.logger, "service_start", pid=os.getpid(), pid_file=str(self.pid_file),
                  cwd=str(SERVICE_DIR), max_restarts=self.max_restarts)

        if self.keep_awake:
            self._awake_state = set_keep_awake(True)
            held = self._awake_state is not None
            log_event(self.logger, "keep_awake",
                      level=logging.INFO if held else logging.WARNING,
                      enabled=held, previous_state=self._awake_state,
                      note=("ES_CONTINUOUS|ES_SYSTEM_REQUIRED held while supervising" if held
                            else "unsupported or refused - the host may still sleep"))

        while self.running:
            run_started = time.time()
            try:
                self.process = self._spawn()
            except Exception as e:
                log_event(self.logger, "spawn_failed", level=logging.ERROR, error=str(e))
                time.sleep(backoff)
                backoff = min(MAX_BACKOFF_SECONDS, backoff * 2)
                continue

            log_event(self.logger, "collector_started", child_pid=self.process.pid)

            # Poll rather than block, so coverage can be reported mid-run and
            # Ctrl+C is handled promptly.
            while self.running and self.process.poll() is None:
                time.sleep(1.0)
                self._maybe_report_coverage()

            runtime = time.time() - run_started

            if not self.running:
                log_event(self.logger, "collector_stopped_by_operator",
                          runtime_seconds=round(runtime, 1))
                break

            exit_code = self.process.returncode
            self.restarts += 1

            if runtime >= HEALTHY_RUNTIME_SECONDS:
                # It ran long enough to be healthy, so treat this as a fresh
                # incident rather than an escalating failure.
                backoff = INITIAL_BACKOFF_SECONDS
                log_event(self.logger, "collector_exited", level=logging.WARNING,
                          exit_code=exit_code, runtime_seconds=round(runtime, 1),
                          restarts=self.restarts, backoff_seconds=backoff)
            else:
                log_event(self.logger, "collector_crashed_early", level=logging.ERROR,
                          exit_code=exit_code, runtime_seconds=round(runtime, 1),
                          restarts=self.restarts, backoff_seconds=backoff)

            if self.max_restarts is not None and self.restarts >= self.max_restarts:
                log_event(self.logger, "restart_budget_exhausted", level=logging.ERROR,
                          restarts=self.restarts)
                break

            slept = 0.0
            while self.running and slept < backoff:
                time.sleep(min(0.5, backoff - slept))
                slept += 0.5
            backoff = min(MAX_BACKOFF_SECONDS, backoff * 2)

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

        if self.keep_awake and self._awake_state is not None:
            set_keep_awake(False)
            log_event(self.logger, "keep_awake_released")
        release_pid_lock(self.pid_file)

        final = measure_coverage()
        summary = {
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "restarts": self.restarts,
            **final,
        }
        log_event(self.logger, "service_stop", **summary)
        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Supervise the HL_Monarch collector as a resilient background service."
    )
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE),
                        help=f"Structured JSONL log destination (default: {DEFAULT_LOG_FILE})")
    parser.add_argument("--max-restarts", type=int, default=None,
                        help="Give up after this many restarts (default: unlimited)")
    parser.add_argument("--quiet", action="store_true",
                        help="Log to file only, no console output")
    parser.add_argument("--coverage-only", action="store_true",
                        help="Report current snapshot coverage and exit without supervising")
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE),
                        help=f"Lockfile path (default: {DEFAULT_PID_FILE})")
    parser.add_argument("--status", action="store_true",
                        help="Report whether a supervisor holds the lock, plus coverage, then exit")
    parser.add_argument("--allow-sleep", action="store_true",
                        help="Do NOT hold the host awake while supervising (default: hold it awake)")
    args = parser.parse_args()

    if args.status:
        pid = running_supervisor_pid(Path(args.pid_file))
        print(json.dumps({
            "running": pid is not None,
            "supervisor_pid": pid,
            "pid_file": str(args.pid_file),
            **measure_coverage(),
        }, indent=2))
        return

    if args.coverage_only:
        stats = measure_coverage()
        print(json.dumps(stats, indent=2))
        return

    supervisor = CollectorSupervisor(
        log_file=Path(args.log_file),
        max_restarts=args.max_restarts,
        quiet=args.quiet,
        pid_file=Path(args.pid_file),
        keep_awake=not args.allow_sleep,
    )
    summary = supervisor.run()
    if summary.get("already_running"):
        print(f"\nAnother supervisor is already running (PID {summary.get('holder_pid')}). "
              f"Nothing started.")
        sys.exit(1)
    print(f"\nService stopped. Uptime {summary['uptime_seconds']}s, "
          f"{summary['restarts']} restart(s), "
          f"24h snapshot coverage {summary.get('coverage_pct', 0.0)}%.")


if __name__ == "__main__":
    main()
