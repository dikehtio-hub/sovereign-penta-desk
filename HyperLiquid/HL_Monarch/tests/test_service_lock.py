"""
Rounds 34-35: exactly one process owns retention, and it is re-decided every cycle.

The dashboard embeds a full collector. Launched before a settings change, it
kept the old retention in memory and pruned at 72h every five minutes while the
restarted service collector held 192h - two pruners, two windows, the shorter
one winning every time. The dashboard's collector now asks whether a service
collector is alive before every maintenance cycle, and a live PID counts only if
its command line says "collector" - after a reboot a stale lock can name anything.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.market_collector import MarketCollector, service_collector_alive


def _lock(tmp_path, pid):
    lock = tmp_path / "collector.pid"
    lock.write_text(str(pid), encoding="utf-8")
    return lock


def test_a_missing_or_unreadable_lock_means_no_service(tmp_path):
    assert not service_collector_alive(tmp_path / "nope.pid")
    junk = tmp_path / "junk.pid"
    junk.write_text("not a pid", encoding="utf-8")
    assert not service_collector_alive(junk)


def test_our_own_pid_is_not_another_service(tmp_path):
    assert not service_collector_alive(_lock(tmp_path, os.getpid()),
                                       probe=lambda pid: (True, "python main.py collector"))


def test_a_live_collector_pid_counts(tmp_path):
    lock = _lock(tmp_path, 4242)
    assert service_collector_alive(lock, probe=lambda pid: (True, "python -u main.py collector"))
    assert service_collector_alive(lock, probe=lambda pid: (True, "python run_collector_service.py"))


def test_a_dead_pid_does_not(tmp_path):
    assert not service_collector_alive(_lock(tmp_path, 4242), probe=lambda pid: (False, None))


def test_a_reused_pid_running_something_else_does_not_count(tmp_path):
    """Post-reboot the number in a stale lock file can belong to anything."""
    assert not service_collector_alive(_lock(tmp_path, 4242),
                                       probe=lambda pid: (True, "notepad.exe C:\\notes.txt"))
    assert not service_collector_alive(_lock(tmp_path, 4242),
                                       probe=lambda pid: (True, "python -m pytest tests/"))


def test_an_uninspectable_process_is_honoured_rather_than_doubled(tmp_path):
    assert service_collector_alive(_lock(tmp_path, 4242), probe=lambda pid: (True, None))
    assert service_collector_alive(_lock(tmp_path, 4242), probe=lambda pid: None)   # no psutil


def test_the_default_probe_sees_this_process(tmp_path):
    lock = _lock(tmp_path, os.getpid())
    # Our own pid is excluded before the probe; exercise the probe on our parent.
    import psutil
    parent = psutil.Process().parent()
    if parent is None:
        return
    lock.write_text(str(parent.pid), encoding="utf-8")
    # The parent is whatever launched pytest; the answer depends only on its
    # command line, which is exactly the point.
    expected = "collector" in " ".join(parent.cmdline()).lower()
    assert service_collector_alive(lock) is expected


def _bare_collector(maintenance=True, yield_to_service=False):
    """A MarketCollector without __init__ - no clients, no sockets, just the flags."""
    c = MarketCollector.__new__(MarketCollector)
    c.maintenance = maintenance
    c.yield_to_service = yield_to_service
    c._yield_logged = False
    return c


def test_ownership_is_re_decided_every_cycle(monkeypatch):
    import collectors.market_collector as mc
    alive = {"value": True}
    monkeypatch.setattr(mc, "service_collector_alive", lambda *a, **k: alive["value"])

    service = _bare_collector(maintenance=True, yield_to_service=False)
    assert service._owns_maintenance()                       # the service never yields

    embedded = _bare_collector(maintenance=True, yield_to_service=True)
    assert not embedded._owns_maintenance()                  # service alive: yield
    alive["value"] = False
    assert embedded._owns_maintenance()                      # service gone: take over
    alive["value"] = True
    assert not embedded._owns_maintenance()                  # service back: yield again

    assert not _bare_collector(maintenance=False)._owns_maintenance()


def test_the_flags_default_to_a_service_collector():
    assert MarketCollector.__init__.__defaults__ == (True, False)
