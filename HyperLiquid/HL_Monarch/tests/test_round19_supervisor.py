"""
Round 19: the ecosystem supervisor.

`scheduleCancel` is account-wide, so the switch has to have exactly one owner.
These tests pin the three properties that make that ownership safe: the deadline
slides forward while the supervisor is healthy, it stops sliding the moment the
supervisor is not, and arming never passes through the capital gate.

Every test drives `tick()` with an injected clock. Nothing sleeps.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.order_executor import OrderExecutor
from execution.supervisor import (
    DEFAULT_RENEWAL_FRACTION,
    DEFAULT_TTL_SECONDS,
    EcosystemSupervisor,
)


class _Clock:
    """A hand-cranked clock, so a 30s TTL costs no wall time to test."""

    def __init__(self, start: float = 1_700_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _Result:
    def __init__(self, status="SUBMITTED", reason=""):
        self.status = status
        self.reason = reason


class _Executor:
    """Stands in for OrderExecutor: records arms, exposes the deadline it set."""

    def __init__(self, status="SUBMITTED", raises=None, ttl_honoured=True):
        self.status = status
        self.raises = raises
        self.ttl_honoured = ttl_honoured
        self.arms = []
        self.dead_man_deadline_ms = None

    def arm_dead_man_switch(self, ttl_seconds, now_ms=None):
        self.arms.append(ttl_seconds)
        if self.raises:
            raise self.raises
        if self.status in ("SUBMITTED", "DRY_RUN") and self.ttl_honoured:
            self.dead_man_deadline_ms = int((time.time() + ttl_seconds) * 1000)
        return _Result(self.status, reason="rejected by exchange")

    @property
    def dead_man_armed(self):
        if not self.dead_man_deadline_ms:
            return False
        return self.dead_man_deadline_ms > int(time.time() * 1000)


class _Resolver:
    def __init__(self, ok=True, raises=None):
        self.ok = ok
        self.raises = raises
        self.calls = 0

    def refresh_universe(self, rest_client=None, fetch=None):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.ok


def _supervisor(executor=None, clock=None, **kwargs):
    return EcosystemSupervisor(executor=executor or _Executor(),
                               clock=clock or _Clock(), **kwargs)


# ------------------------------------------------------------------ defaults

def test_the_default_ttl_is_thirty_seconds():
    assert DEFAULT_TTL_SECONDS == 30.0


def test_renewal_happens_well_inside_the_ttl():
    """
    A 30s TTL renewed every 10s survives two consecutive failures. Renewing at
    28s means one slow round trip flattens the book.
    """
    assert DEFAULT_RENEWAL_FRACTION <= 0.5
    assert _supervisor().renewal_interval == pytest.approx(10.0)


def test_the_renewal_fraction_is_clamped_so_it_cannot_exceed_the_ttl():
    """A fraction of 1.0 would renew exactly as the deadline expires - a race."""
    assert _supervisor(renewal_fraction=5.0).renewal_interval < DEFAULT_TTL_SECONDS


def test_a_tiny_ttl_still_renews_at_least_once_a_second():
    assert _supervisor(ttl_seconds=0.5).renewal_interval == 1.0


# ------------------------------------------------------------------ heartbeat

def test_the_first_tick_arms():
    executor = _Executor()
    supervisor = _supervisor(executor)
    supervisor.tick()
    assert executor.arms == [30.0]
    assert supervisor.armed is True


def test_a_tick_inside_the_renewal_window_does_not_re_arm():
    """Re-arming every poll would be pointless traffic against a rate limit."""
    clock, executor = _Clock(), _Executor()
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    clock.advance(5.0)
    supervisor.tick()
    assert len(executor.arms) == 1


def test_a_tick_past_the_renewal_window_re_arms():
    clock, executor = _Clock(), _Executor()
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    clock.advance(11.0)
    supervisor.tick()
    assert len(executor.arms) == 2


def test_the_deadline_slides_forward_on_each_arm():
    """This is the whole mechanism: a healthy supervisor keeps pushing it out."""
    clock, executor = _Clock(), _Executor()
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    first = executor.dead_man_deadline_ms
    clock.advance(11.0)
    time.sleep(0.001)          # real clock, so the new deadline is strictly later
    supervisor.tick()
    assert executor.dead_man_deadline_ms > first


def test_a_stalled_supervisor_stops_sliding_the_deadline():
    """
    The point of the design. If nothing ticks, nothing re-arms, and the exchange
    cancels the book on its own - no cooperation from the dying process needed.
    """
    clock, executor = _Clock(), _Executor()
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    frozen = executor.dead_man_deadline_ms
    clock.advance(600.0)       # supervisor hung: no ticks at all
    assert executor.dead_man_deadline_ms == frozen


def test_arms_are_counted():
    supervisor = _supervisor()
    supervisor.tick()
    assert supervisor.snapshot().arms_sent == 1


# ------------------------------------------------------------------- failures

def test_a_raising_executor_is_caught_and_counted():
    executor = _Executor(raises=ConnectionError("socket closed"))
    supervisor = _supervisor(executor)
    assert supervisor.arm() is False
    assert supervisor.snapshot().consecutive_failures == 1
    assert supervisor.snapshot().arms_failed == 1


def test_a_rejected_arm_counts_as_a_failure():
    supervisor = _supervisor(_Executor(status="ERROR"))
    assert supervisor.arm() is False
    assert supervisor.snapshot().consecutive_failures == 1


def test_a_dry_run_arm_counts_as_success():
    """Dry run is a legitimate operating mode, not a failure to arm."""
    assert _supervisor(_Executor(status="DRY_RUN")).arm() is True


def test_a_failure_does_not_clear_an_existing_deadline():
    """
    The old deadline is still running on the exchange and still protecting us.
    Clearing our record of it would understate the protection we actually have.
    """
    clock, executor = _Clock(), _Executor()
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    good = executor.dead_man_deadline_ms
    executor.raises = ConnectionError("down")
    clock.advance(11.0)
    supervisor.tick()
    assert executor.dead_man_deadline_ms == good


def test_a_failed_arm_is_retried_on_the_next_tick():
    """
    `_last_arm_at` only advances on SUCCESS, so a failure leaves the arm due and
    the next tick tries again - rather than waiting out another full interval.
    """
    clock, executor = _Clock(), _Executor(raises=ConnectionError("down"))
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    supervisor.tick()
    assert len(executor.arms) == 2


def test_a_success_resets_the_failure_count():
    executor = _Executor(raises=ConnectionError("down"))
    supervisor = _supervisor(executor)
    supervisor.arm()
    assert supervisor.snapshot().consecutive_failures == 1
    executor.raises = None
    supervisor.arm()
    assert supervisor.snapshot().consecutive_failures == 0


def test_no_executor_means_never_armed():
    supervisor = EcosystemSupervisor(executor=None)
    assert supervisor.arm() is False
    assert supervisor.armed is False
    assert supervisor.should_trade() is False


# ------------------------------------------------------- gating new exposure

def test_an_armed_supervisor_permits_new_exposure():
    supervisor = _supervisor()
    supervisor.tick()
    assert supervisor.should_trade() is True


def test_repeated_arm_failures_stop_new_exposure():
    """
    Not because the book is unprotected yet - the old deadline may still be
    running - but because an order placed NOW could rest past it.
    """
    supervisor = _supervisor(_Executor(raises=ConnectionError("down")),
                             max_consecutive_failures=3)
    for _ in range(3):
        supervisor.arm()
    assert supervisor.should_trade() is False


def test_an_unconfirmed_switch_stops_new_exposure():
    """`armed` asks whether protection is LIVE, not whether we tried to set it."""
    supervisor = _supervisor(_Executor(status="SUBMITTED", ttl_honoured=False))
    supervisor.tick()
    assert supervisor.armed is False
    assert supervisor.should_trade() is False


def test_an_expired_deadline_is_not_armed():
    executor = _Executor()
    executor.dead_man_deadline_ms = int((time.time() - 60) * 1000)
    assert _supervisor(executor).armed is False


# ------------------------------------------------------------------ halting

def test_halting_stops_arming():
    clock, executor = _Clock(), _Executor()
    supervisor = _supervisor(executor, clock)
    supervisor.tick()
    supervisor.halt("manual")
    clock.advance(600.0)
    supervisor.tick()
    assert len(executor.arms) == 1


def test_halting_does_not_send_a_cancel_of_its_own():
    """
    A halt happens when something is wrong. Sending one more action down the same
    possibly-broken path is optimistic; the already-armed deadline does the work
    without needing us to still be healthy.
    """
    executor = _Executor()
    supervisor = _supervisor(executor)
    supervisor.tick()
    supervisor.halt("bad")
    assert executor.arms == [30.0]          # nothing extra was sent


def test_halting_blocks_new_exposure_immediately():
    supervisor = _supervisor()
    supervisor.tick()
    supervisor.halt("drawdown")
    assert supervisor.should_trade() is False


def test_the_halt_reason_is_kept():
    supervisor = _supervisor()
    supervisor.halt("daily loss limit")
    assert supervisor.snapshot().halt_reason == "daily loss limit"


def test_resuming_re_arms_at_once():
    executor = _Executor()
    supervisor = _supervisor(executor)
    supervisor.tick()
    supervisor.halt("x")
    supervisor.resume()
    assert len(executor.arms) == 2
    assert supervisor.should_trade() is True


# --------------------------------------------------------------- ungated
#
# The Round 17 tax gate must NOT reach the cancel path.

def test_arming_is_not_wrapped_by_the_tax_gate():
    assert not getattr(OrderExecutor.arm_dead_man_switch,
                       "__wrapped_by_tax_gate__", False)


def test_the_supervisor_never_touches_a_risk_manager():
    """
    It has no `risk_manager` at all. Cancelling is risk-REDUCING; an account out
    of capital is exactly the one that most needs to flatten, so gating the exit
    behind the entry check would turn a risk limit into a trap.
    """
    assert not hasattr(_supervisor(), "risk_manager")


def test_arming_works_with_a_gate_that_would_reject_everything():
    """A supervisor holding a hostile gate still arms, because it never asks it."""
    class _RejectEverything:
        def check_order(self, *args, **kwargs):
            raise AssertionError("the supervisor must not consult the gate")

    supervisor = _supervisor()
    supervisor.risk_manager = _RejectEverything()   # attached, never consulted
    assert supervisor.arm() is True


# ------------------------------------------------------- universe refresh

def test_the_universe_is_refreshed_on_the_first_tick():
    resolver = _Resolver()
    EcosystemSupervisor(executor=_Executor(), resolver=resolver,
                        clock=_Clock()).tick()
    assert resolver.calls == 1


def test_the_universe_is_not_refreshed_every_tick():
    """It changes on listings, not on seconds. Refreshing per tick is just load."""
    clock, resolver = _Clock(), _Resolver()
    supervisor = EcosystemSupervisor(executor=_Executor(), resolver=resolver,
                                     clock=clock, universe_refresh_seconds=900.0)
    supervisor.tick()
    clock.advance(60.0)
    supervisor.tick()
    assert resolver.calls == 1


def test_the_universe_is_refreshed_once_the_interval_passes():
    clock, resolver = _Clock(), _Resolver()
    supervisor = EcosystemSupervisor(executor=_Executor(), resolver=resolver,
                                     clock=clock, universe_refresh_seconds=900.0)
    supervisor.tick()
    clock.advance(901.0)
    supervisor.tick()
    assert resolver.calls == 2


def test_a_raising_resolver_does_not_kill_the_heartbeat():
    """
    The switch matters more than the asset map. A refresh that throws must not
    take the arming loop down with it.
    """
    executor = _Executor()
    supervisor = EcosystemSupervisor(executor=executor,
                                     resolver=_Resolver(raises=RuntimeError("boom")),
                                     clock=_Clock())
    supervisor.tick()
    assert executor.arms == [30.0]
    assert supervisor.snapshot().universe_refresh_failures == 1


def test_a_failed_refresh_is_retried_on_the_next_tick():
    clock = _Clock()
    resolver = _Resolver(ok=False)
    supervisor = EcosystemSupervisor(executor=_Executor(), resolver=resolver,
                                     clock=clock, universe_refresh_seconds=900.0)
    supervisor.tick()
    supervisor.tick()
    assert resolver.calls == 2


def test_no_resolver_is_fine():
    supervisor = _supervisor()
    assert supervisor.refresh_due() is False
    assert supervisor.refresh_universe() is False


# ------------------------------------------------------------------ the loop

def test_run_forever_is_bounded_by_max_cycles():
    executor = _Executor()
    supervisor = _supervisor(executor)
    assert supervisor.run_forever(poll_seconds=0.001, max_cycles=3) == 3


def test_stop_ends_the_loop():
    supervisor = _supervisor()
    supervisor._stop.set()
    assert supervisor.run_forever(poll_seconds=0.001, max_cycles=10) == 0


def test_the_thread_is_a_daemon_so_the_switch_dies_with_the_process():
    """
    A non-daemon thread would keep re-arming after the strategy that justified
    those orders had exited - the exact scenario the switch exists to prevent.
    """
    supervisor = _supervisor()
    supervisor.start(poll_seconds=0.01)
    try:
        assert supervisor._thread.daemon is True
    finally:
        supervisor.stop(timeout=2.0)


def test_starting_twice_does_not_spawn_a_second_heartbeat():
    """Two heartbeats on one account would each push the other's deadline out."""
    supervisor = _supervisor()
    supervisor.start(poll_seconds=0.01)
    try:
        first = supervisor._thread
        supervisor.start(poll_seconds=0.01)
        assert supervisor._thread is first
    finally:
        supervisor.stop(timeout=2.0)


# ---------------------------------------------------------------- reporting

def test_the_status_line_shows_the_remaining_protection():
    supervisor = _supervisor()
    supervisor.tick()
    assert "armed" in supervisor.status_line()


def test_the_status_line_calls_out_an_unarmed_switch():
    line = _supervisor(_Executor(raises=ConnectionError("down"))).status_line()
    assert "NOT ARMED" in line


def test_the_status_line_calls_out_a_halt():
    supervisor = _supervisor()
    supervisor.halt("drawdown")
    assert "HALTED" in supervisor.status_line()


def test_the_snapshot_is_serialisable():
    supervisor = _supervisor()
    supervisor.tick()
    snapshot = supervisor.snapshot().to_dict()
    assert snapshot["armed"] is True
    assert snapshot["arms_sent"] == 1
