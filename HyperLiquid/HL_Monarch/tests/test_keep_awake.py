"""
Round 35 Ruling 5.A: the supervisor holds the host awake while it runs.

The collector host slept for nine hours on 2026-09-04 and neither the
supervisor nor its child survived the resume. These tests pin the Windows call
without making it: a stub kernel32 records the flags.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_collector_service as svc


class StubKernel:
    def __init__(self, previous=0x80000000, fail=False):
        self.calls = []
        self.previous = previous
        self.fail = fail

    def SetThreadExecutionState(self, flags):
        if self.fail:
            raise OSError("refused")
        self.calls.append(flags)
        return self.previous


def test_the_flags_are_the_documented_windows_constants():
    assert svc.ES_CONTINUOUS == 0x80000000
    assert svc.ES_SYSTEM_REQUIRED == 0x00000001


def test_enable_requests_continuous_plus_system_required():
    k = StubKernel(previous=0x80000000)
    assert svc.set_keep_awake(True, kernel32=k) == 0x80000000
    assert k.calls == [svc.ES_CONTINUOUS | svc.ES_SYSTEM_REQUIRED]


def test_disable_clears_to_continuous_only():
    k = StubKernel(previous=0x80000001)
    assert svc.set_keep_awake(False, kernel32=k) == 0x80000001
    assert k.calls == [svc.ES_CONTINUOUS]


def test_a_refusal_is_none_not_an_exception():
    assert svc.set_keep_awake(True, kernel32=StubKernel(fail=True)) is None
    assert svc.set_keep_awake(True, kernel32=StubKernel(previous=0)) is None


def test_the_supervisor_holds_the_host_awake_by_default(tmp_path):
    held = svc.CollectorSupervisor(log_file=tmp_path / "a.jsonl", pid_file=tmp_path / "a.pid", quiet=True)
    assert held.keep_awake and held._awake_state is None
    free = svc.CollectorSupervisor(log_file=tmp_path / "b.jsonl", pid_file=tmp_path / "b.pid", quiet=True,
                                   keep_awake=False)
    assert not free.keep_awake


def test_the_child_collector_writes_to_a_log_file_that_rotates(tmp_path):
    """
    Round 52. The supervisor spawned the collector with stdout=DEVNULL, so every
    line the collector logged in service mode was lost. The child now writes
    to data/collector.log, appended across restarts and rotated once past a cap.
    """
    import sys
    import time
    log = tmp_path / "collector.log"
    sup = svc.CollectorSupervisor(log_file=tmp_path / "svc.jsonl", pid_file=tmp_path / "svc.pid", quiet=True,
                                  keep_awake=False, child_log=log, child_log_max_bytes=100,
                                  python_executable=sys.executable,
                                  child_command=["-c", "import sys; print('collector hello'); print('warn', file=sys.stderr)"])
    proc = sup._spawn()
    assert proc.wait(timeout=30) == 0
    sup._child_log_handle.close()
    text = log.read_text(encoding="utf-8")
    assert "collector hello" in text and "warn" in text                        # stdout AND stderr, one file
    # A second spawn APPENDS (a restart must not erase the death's last lines) ...
    proc = sup._spawn()
    assert proc.wait(timeout=30) == 0
    sup._child_log_handle.close()
    assert log.read_text(encoding="utf-8").count("collector hello") == 2
    # ... until the cap, after which the file rotates to .1 and a fresh one starts.
    log.write_text("x" * 200, encoding="utf-8")
    proc = sup._spawn()
    assert proc.wait(timeout=30) == 0
    sup._child_log_handle.close()
    assert (tmp_path / "collector.log.1").read_text(encoding="utf-8") == "x" * 200
    assert log.read_text(encoding="utf-8").count("collector hello") == 1
    events = [__import__("json").loads(l)["event"] for l in (tmp_path / "svc.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events.count("child_log") == 3
