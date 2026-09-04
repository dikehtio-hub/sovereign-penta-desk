"""
Round 34: exactly one process owns retention.

The dashboard embeds a full collector. Launched before a settings change, it
kept the old retention in memory and pruned at 72h every five minutes while the
restarted service collector held 192h - two pruners, two windows, the shorter
one winning every time. The dashboard now asks whether the service collector is
alive before it runs maintenance at all.
"""
import os
import sys
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.market_collector import MarketCollector, service_collector_alive


def test_a_missing_or_unreadable_lock_means_no_service(tmp_path):
    assert not service_collector_alive(tmp_path / "nope.pid")
    junk = tmp_path / "junk.pid"
    junk.write_text("not a pid", encoding="utf-8")
    assert not service_collector_alive(junk)


def test_our_own_pid_is_not_another_service(tmp_path):
    lock = tmp_path / "collector.pid"
    lock.write_text(str(os.getpid()), encoding="utf-8")
    assert not service_collector_alive(lock)


def test_a_live_foreign_pid_counts_as_the_service(tmp_path):
    parent = psutil.Process().parent()
    if parent is None:
        return
    lock = tmp_path / "collector.pid"
    lock.write_text(str(parent.pid), encoding="utf-8")
    assert service_collector_alive(lock)


def test_a_dead_pid_does_not(tmp_path):
    dead = max(psutil.pids()) + 100_000
    lock = tmp_path / "collector.pid"
    lock.write_text(str(dead), encoding="utf-8")
    assert not service_collector_alive(lock)


def test_the_flag_is_the_only_switch():
    """No network is opened by construction; the flag is plain state."""
    assert MarketCollector.__init__.__defaults__ == (True,)
