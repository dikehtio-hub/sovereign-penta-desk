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
