"""
================================================================================
HL Monarch: Ecosystem Supervisor
================================================================================
Owns the account-level dead man's switch, and nothing else owns it.

WHY OWNERSHIP MATTERS. `scheduleCancel` cancels EVERYTHING resting, across every
strategy. If each executor armed its own switch, one strategy's stalled heartbeat
would cancel another strategy's orders - and worse, a healthy strategy re-arming
on its own timer would keep pushing the deadline out while the stalled one sat
unprotected. One switch, one owner, one heartbeat.

THE PROTECTION IS THE DEADLINE, NOT THE HEARTBEAT. This is the property that
makes the whole thing work: a supervisor that hangs, crashes, deadlocks, or loses
its network stops re-arming, the deadline passes, and the EXCHANGE cancels the
book without us. Every other design needs the dying process to notice it is dying
and do something about it, which is exactly what a dying process cannot do.

So the failure mode is deliberately asymmetric:
  * Supervisor healthy  -> deadline keeps sliding forward, orders rest normally.
  * Supervisor stalls   -> deadline passes, book is flattened, nothing is at risk.
  * Exchange unreachable-> arming fails, `armed` goes False, and `should_trade()`
                           says no. We do not place new orders we cannot protect.

CANCELS ARE NEVER TAX-GATED. `arm()` does not pass through `RiskManager`, and
that is not an oversight: cancelling is risk-REDUCING, and an account that has
exhausted its capital bucket is precisely the account that most needs to be able
to flatten. Gating the exit behind the same check as the entry is how a risk
limit becomes a trap.

RENEWAL MARGIN. Re-arm at `ttl * renewal_fraction` (default a third). A 30s TTL
renewed every 10s tolerates two consecutive failures before the book is cancelled;
renewing at 28s means one slow round trip flattens everything.
================================================================================
"""

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

DEFAULT_TTL_SECONDS = 30.0
DEFAULT_RENEWAL_FRACTION = 1.0 / 3.0


@dataclass
class SupervisorState:
    """A snapshot of what the supervisor believes right now."""
    running: bool = False
    armed: bool = False
    halted: bool = False
    deadline_ms: Optional[int] = None
    seconds_to_deadline: Optional[float] = None
    last_arm_ok: bool = False
    last_arm_at: Optional[float] = None
    consecutive_failures: int = 0
    arms_sent: int = 0
    arms_failed: int = 0
    universe_refreshes: int = 0
    universe_refresh_failures: int = 0
    halt_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EcosystemSupervisor:
    """
    One heartbeat, one switch, for the whole account.

    `tick()` is the entire supervisor: arm if due, refresh the universe if due.
    `run_forever()` just calls it on a timer, and `start()` does that on a thread.
    Splitting it that way means the logic is testable without ever sleeping.
    """

    def __init__(self,
                 executor: Any = None,
                 resolver: Any = None,
                 rest_client: Any = None,
                 ttl_seconds: float = DEFAULT_TTL_SECONDS,
                 renewal_fraction: float = DEFAULT_RENEWAL_FRACTION,
                 universe_refresh_seconds: float = 900.0,
                 max_consecutive_failures: int = 3,
                 clock: Optional[Callable[[], float]] = None,
                 reconciler: Optional[Any] = None,
                 user_address: Optional[str] = None,
                 reconcile_interval_seconds: float = 10.0):
        self.executor = executor
        self.resolver = resolver
        self.rest_client = rest_client
        self.reconciler = reconciler
        self.user_address = user_address
        self.reconcile_interval_seconds = float(reconcile_interval_seconds)
        self.ttl_seconds = float(ttl_seconds)
        self.renewal_fraction = min(max(float(renewal_fraction), 0.05), 0.9)
        self.universe_refresh_seconds = float(universe_refresh_seconds)
        self.max_consecutive_failures = int(max_consecutive_failures)
        self._clock = clock or time.time

        self.state = SupervisorState()
        self._last_arm_at: Optional[float] = None
        self._last_refresh_at: Optional[float] = None
        self._last_reconcile_at: Optional[float] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- timing -------------------------------------------------------------

    @property
    def renewal_interval(self) -> float:
        """How often to re-arm. Well inside the TTL, so a miss is survivable."""
        return max(1.0, self.ttl_seconds * self.renewal_fraction)

    def arm_due(self) -> bool:
        if self._last_arm_at is None:
            return True
        return (self._clock() - self._last_arm_at) >= self.renewal_interval

    def refresh_due(self) -> bool:
        if self.resolver is None or self.universe_refresh_seconds <= 0:
            return False
        if self._last_refresh_at is None:
            return True
        return (self._clock() - self._last_refresh_at) >= self.universe_refresh_seconds

    def reconcile_due(self) -> bool:
        if self.reconciler is None or not self.user_address or self.reconcile_interval_seconds <= 0:
            return False
        if self._last_reconcile_at is None:
            return True
        return (self._clock() - self._last_reconcile_at) >= self.reconcile_interval_seconds

    # -- the heartbeat ------------------------------------------------------

    def arm(self) -> bool:
        """
        Push the deadline out by one TTL. Returns whether the exchange took it.

        NOT tax-gated - see the module docstring. Cancelling is the one action an
        out-of-capital account must always be able to take.

        A failure does NOT clear a previously good deadline: the old one is still
        running on the exchange and still protecting us until it expires. What it
        does do is count, so `should_trade()` can stop opening NEW exposure long
        before the existing protection lapses.
        """
        if self.executor is None:
            self.state.last_arm_ok = False
            return False
        try:
            result = self.executor.arm_dead_man_switch(self.ttl_seconds)
        except Exception as exc:
            with self._lock:
                self.state.arms_failed += 1
                self.state.consecutive_failures += 1
                self.state.last_arm_ok = False
            print(f"[SUPERVISOR] arm failed ({type(exc).__name__}: {exc}); "
                  f"{self.state.consecutive_failures} consecutive.")
            return False

        ok = str(getattr(result, "status", "")) in ("SUBMITTED", "DRY_RUN")
        with self._lock:
            self.state.arms_sent += 1
            self.state.last_arm_ok = ok
            self.state.last_arm_at = self._clock()
            if ok:
                self._last_arm_at = self._clock()
                self.state.consecutive_failures = 0
                self.state.deadline_ms = getattr(self.executor, "dead_man_deadline_ms", None)
            else:
                self.state.arms_failed += 1
                self.state.consecutive_failures += 1
                print(f"[SUPERVISOR] arm rejected: {getattr(result, 'reason', 'unknown')}")
        return ok

    def refresh_universe(self) -> bool:
        """
        Keep the asset maps fresh so the executor is not blocked by staleness.

        BOTH maps. Spot is a separate universe with its own numbering space, and
        the basis harvester needs it to trade its spot leg at all - refreshing
        only the perp map would leave spot permanently stale and every spot leg
        refused. A resolver with no spot support is fine and does not count as a
        failure; a resolver that HAS it and fails does.
        """
        if self.resolver is None:
            return False
        ok = False
        try:
            ok = bool(self.resolver.refresh_universe(rest_client=self.rest_client))
        except Exception as exc:
            print(f"[SUPERVISOR] universe refresh raised ({type(exc).__name__}: {exc}).")

        spot_ok = True
        if hasattr(self.resolver, "refresh_spot_universe"):
            try:
                spot_ok = bool(
                    self.resolver.refresh_spot_universe(rest_client=self.rest_client))
            except Exception as exc:
                print(f"[SUPERVISOR] spot universe refresh raised "
                      f"({type(exc).__name__}: {exc}).")
                spot_ok = False

        ok = ok and spot_ok
        with self._lock:
            if ok:
                self.state.universe_refreshes += 1
                self._last_refresh_at = self._clock()
            else:
                self.state.universe_refresh_failures += 1
        return ok

    def tick(self) -> Dict[str, Any]:
        """
        One supervisor cycle. Everything the loop does, without any sleeping.

        A halted supervisor keeps ticking but stops arming, so the deadline runs
        down and the exchange flattens the book. That is the intended shape of a
        halt: stop protecting the orders and let them be cancelled, rather than
        trying to cancel them from a process that may itself be the problem.
        """
        actions: List[str] = []
        if self.state.halted:
            actions.append("halted: not re-arming, letting the deadline expire")
        elif self.arm_due():
            actions.append("armed" if self.arm() else "arm-failed")
        if self.refresh_due():
            actions.append("universe-refreshed" if self.refresh_universe()
                           else "universe-refresh-failed")
        if self.reconcile_due():
            try:
                rec_res = self.reconciler.reconcile_once(self.user_address)
                self._last_reconcile_at = self._clock()
                filled = rec_res.get("newly_filled", 0)
                canceled = rec_res.get("newly_canceled", 0)
                actions.append(f"reconciled: {filled} filled, {canceled} canceled")
            except Exception as exc:
                actions.append(f"reconcile-failed: {exc}")
        return {"actions": actions, "state": self.snapshot().to_dict()}

    # -- halt ---------------------------------------------------------------

    def halt(self, reason: str = "manual halt") -> None:
        """
        Stop re-arming. The exchange flattens the book when the deadline passes.

        Deliberately NOT an immediate cancel. If the supervisor is halting because
        something is wrong, sending one more action through the same broken path
        is optimistic; letting the already-armed deadline do the work is the
        version that does not depend on us still being healthy. The cost is
        waiting up to one TTL, which is why the TTL is 30s and not 30 minutes.
        """
        with self._lock:
            self.state.halted = True
            self.state.halt_reason = reason
        print(f"[SUPERVISOR] HALTED: {reason}. No further arming; resting orders will "
              f"be cancelled by the exchange within {self.ttl_seconds:.0f}s.")

    def resume(self) -> None:
        with self._lock:
            self.state.halted = False
            self.state.halt_reason = ""
        self.arm()

    def should_trade(self) -> bool:
        """
        Whether it is safe to open NEW exposure.

        False while halted, while the switch is not confirmed armed, or after
        repeated arm failures - because an order placed now might rest without
        protection. Existing positions are unaffected; this gates opening, not
        holding.
        """
        if self.state.halted:
            return False
        if self.state.consecutive_failures >= self.max_consecutive_failures:
            return False
        return self.armed

    @property
    def armed(self) -> bool:
        """True only if a deadline exists AND is still in the future."""
        if self.executor is None:
            return False
        return bool(getattr(self.executor, "dead_man_armed", False))

    def snapshot(self) -> SupervisorState:
        deadline = getattr(self.executor, "dead_man_deadline_ms", None) if self.executor else None
        with self._lock:
            self.state.deadline_ms = deadline
            self.state.armed = self.armed
            self.state.running = self._thread is not None and self._thread.is_alive()
            self.state.seconds_to_deadline = (
                (deadline / 1000.0 - time.time()) if deadline else None)
            return self.state

    # -- loop ---------------------------------------------------------------

    def run_forever(self, poll_seconds: float = 1.0,
                    max_cycles: Optional[int] = None) -> int:
        """Tick on a timer. `max_cycles` bounds it so tests never sleep forever."""
        cycles = 0
        while not self._stop.is_set() and (max_cycles is None or cycles < max_cycles):
            self.tick()
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                if self._stop.wait(poll_seconds):
                    break
        return cycles

    def start(self, poll_seconds: float = 1.0) -> None:
        """
        Run the heartbeat on a daemon thread.

        DAEMON ON PURPOSE. If the main process exits, this thread dies with it and
        stops re-arming - so the exchange cancels the book. A non-daemon thread
        would keep the switch alive after the strategy that justified those orders
        had gone, which is the exact scenario the switch exists to prevent.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self.arm()
        self._thread = threading.Thread(target=self.run_forever, args=(poll_seconds,),
                                        name="hl-supervisor", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def status_line(self) -> str:
        state = self.snapshot()
        if state.halted:
            return f"[SUPERVISOR] HALTED ({state.halt_reason})"
        if not state.armed:
            return (f"[SUPERVISOR] NOT ARMED - {state.consecutive_failures} consecutive "
                    f"failures; not safe to open new exposure")
        remaining = state.seconds_to_deadline or 0.0
        return (f"[SUPERVISOR] armed, {remaining:.0f}s to deadline "
                f"(TTL {self.ttl_seconds:.0f}s, renew every "
                f"{self.renewal_interval:.0f}s) | arms {state.arms_sent} "
                f"({state.arms_failed} failed)")
