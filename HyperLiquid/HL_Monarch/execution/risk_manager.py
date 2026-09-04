"""
================================================================================
HL Monarch: Sovereign Risk Manager
================================================================================
The gate every HL order passes through. It answers one question - "may this trade
be placed, and how large?" - by combining two limits that constrain different
things and must BOTH hold:

  1. ACCOUNT MARGIN UTILISATION (local). Perpetuals are levered, so a position's
     margin is a fraction of its notional. A book can be well inside its cash
     allocation and still be one adverse move from liquidation. This cap is about
     surviving volatility.
  2. SAFE BANKROLL AND STRATEGY BUCKET (Tax Reserve Agent). Realised gains create
     a tax liability the moment they are booked, so cash overstates risk capital
     by exactly the escrow. This cap is about not spending money that is already
     owed - and about keeping one strategy from reaching another's capital.

The two are not interchangeable. A trade can clear the bankroll and still be
over-levered; it can be modestly levered and still spend the tax escrow. Both are
checked, and the SMALLER limit wins.

DEGRADES, BUT NEVER SILENTLY. If the Tax Reserve Agent is missing, uninitialised,
or broken, the bankroll half is unavailable - and this class then falls back to
the paper balance and says so in `reason`, on every single decision. It does not
pretend the check happened. A caller that wants to refuse trading without the tax
gate can test `tax_gate_available`.

WHY FALL BACK AT ALL rather than fail closed: HL Monarch is a paper simulator
today. Refusing to simulate because an accounting database is absent would stop
research for no risk reduction. THE MOMENT THIS DRIVES REAL ORDERS, the fallback
should become a refusal - see `require_tax_gate`.
================================================================================
"""

import functools
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, Optional

# DEV/HyperLiquid/HL_Monarch/execution/risk_manager.py -> DEV/
DEV_ROOT = Path(__file__).resolve().parents[3]

_IMPORT_ERROR = ""
try:
    if str(DEV_ROOT) not in sys.path:
        sys.path.insert(0, str(DEV_ROOT))
    from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook
except Exception as exc:      # ImportError, broken config, missing yaml, bad allocations
    MonarchBankrollHook = None
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


# HL strategies and their capital buckets in Tax_Reserve_Agent/config.yaml.
# A strategy not listed here is quarantined into `sandbox` by the hook, which is
# the correct treatment for something nobody has budgeted for.
STRATEGY_LIQUIDATION_FADE = "hl_liquidation_fade"
STRATEGY_BASIS_HARVEST = "hl_basis_harvest"
HL_STRATEGIES = (STRATEGY_LIQUIDATION_FADE, STRATEGY_BASIS_HARVEST)

# Fraction of account equity that may be committed as margin. Perps liquidate on
# margin, not on notional, so this is the constraint that actually keeps the book
# alive through a drawdown.
MAX_ACCOUNT_MARGIN_UTILIZATION = 0.50


class RiskBreachException(RuntimeError):
    """
    Raised when an execution path tried to proceed without an approved gate.

    Its own type so it can never be swallowed by a broad `except Exception` that
    was written to keep a trading loop alive. A loop that survives a network blip
    must NOT survive an unapproved order reaching a signing key - those need
    opposite handling, and one exception class for both is how the second becomes
    invisible.
    """


def require_tax_gate(func):
    """
    Hard pre-condition: no order reaches a signing function without approval.

    Wraps a method on an object exposing `.risk_manager`. It calls
    `check_order()` ITSELF rather than trusting the caller to have done so - a
    gate you have to remember to invoke is a gate that eventually is not
    invoked, and the failure is silent because the order simply goes through.

    The approved decision is injected as `risk_decision=` so the wrapped method
    can size against it, and `max_size_usd` is authoritative: a caller that
    ignores it and uses its own number still cannot exceed the gate, because the
    executor clamps to the decision.

    NOTE the name collision with `RiskManager(require_tax_gate=True)`. The
    constructor flag decides whether a MISSING tax gate is fatal; this decorator
    decides whether an UNAPPROVED order is fatal. Both are needed: without the
    flag the gate degrades open, and without the decorator the gate can be
    skipped entirely.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        manager = getattr(self, "risk_manager", None)
        if manager is None:
            raise RiskBreachException(
                f"{func.__qualname__} has no risk manager attached; refusing to "
                f"proceed. An execution path without a gate is not a fast path, "
                f"it is an unguarded one.")

        strategy = kwargs.get("strategy") or getattr(self, "strategy", None)
        size_usd = kwargs.get("size_usd")
        if size_usd is None:
            # Malformed size or price means the notional CANNOT BE COMPUTED, and an
            # order that cannot be measured cannot be gated. Treated as 0, which
            # check_order rejects - so junk input is blocked with a clear risk
            # message rather than crashing the gate with a raw ValueError partway
            # through, which would leave the caller unsure whether it ran at all.
            try:
                size_usd = float(kwargs.get("sz") or 0.0) * float(kwargs.get("limit_px") or 0.0)
            except (TypeError, ValueError):
                size_usd = 0.0
        try:
            size_usd = float(size_usd or 0.0)
        except (TypeError, ValueError):
            size_usd = 0.0
        margin = kwargs.get("margin_required_usd")
        reduce_only = bool(kwargs.get("reduce_only", False))
        decision = manager.check_order(strategy=strategy, size_usd=size_usd,
                                       margin_required_usd=margin,
                                       price=kwargs.get("limit_px"),
                                       reduce_only=reduce_only)
        if not decision.approved:
            raise RiskBreachException(
                f"BLOCKED {func.__qualname__} for {strategy!r}: {decision.reason} "
                f"(requested ${size_usd:,.2f}, approved $0.00)")

        kwargs["risk_decision"] = decision
        return func(self, *args, **kwargs)

    wrapper.__wrapped_by_tax_gate__ = True
    return wrapper


@dataclass
class RiskDecision:
    """
    The answer for one order. `max_size_usd` is authoritative and already clamped
    to every limit, so a caller that ignores `approved` and uses the number still
    cannot overtrade. It is 0.0 whenever `approved` is False.
    """
    approved: bool
    max_size_usd: float
    reason: str
    strategy: str = ""
    margin_utilization: float = 0.0
    margin_headroom_usd: float = 0.0
    safe_bankroll_usd: float = 0.0
    bucket_remaining_usd: float = 0.0
    tax_gate_available: bool = False
    binding_limit: str = ""          # margin | bankroll | none

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        verdict = "APPROVED" if self.approved else "REJECTED"
        return f"[{verdict}] ${self.max_size_usd:,.2f} - {self.reason}"


class RiskManager:
    """
    Order gate for HL Monarch.

    `check_order()` returns a `RiskDecision`; `dict(decision.to_dict())` gives the
    plain `{"approved", "max_size_usd", "reason"}` shape plus the working.
    """

    def __init__(self,
                 trader: Any = None,
                 max_margin_utilization: float = MAX_ACCOUNT_MARGIN_UTILIZATION,
                 hook: Any = None,
                 tax_year: Optional[int] = None,
                 db_path: Optional[Path] = None,
                 require_tax_gate: bool = False,
                 fallback_balance_usd: float = 100_000.0):
        self.trader = trader
        self.max_margin_utilization = max(0.0, min(1.0, float(max_margin_utilization)))
        self.require_tax_gate = bool(require_tax_gate)
        self.fallback_balance_usd = float(fallback_balance_usd)
        self.hook = hook
        self.hook_error = ""

        if self.hook is None:
            if MonarchBankrollHook is None:
                self.hook_error = f"Tax Reserve Agent not importable ({_IMPORT_ERROR})"
            else:
                try:
                    self.hook = MonarchBankrollHook(tax_year=tax_year, db_path=db_path)
                except Exception as exc:
                    self.hook_error = (f"Tax Reserve Agent failed to start "
                                       f"({type(exc).__name__}: {exc})")

    # -- availability -------------------------------------------------------

    @property
    def tax_gate_available(self) -> bool:
        """True only when a hook exists AND its ledger actually reads."""
        if self.hook is None:
            return False
        try:
            return bool(self.hook.snapshot().get("available", False))
        except Exception as exc:
            self.hook_error = f"tax ledger unreadable ({type(exc).__name__}: {exc})"
            return False

    def equity_usd(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Account equity from the paper book, or the configured fallback."""
        if self.trader is None:
            return self.fallback_balance_usd
        try:
            return float(self.trader.get_account_summary(current_prices or {})["equity"])
        except Exception:
            return self.fallback_balance_usd

    def used_margin_usd(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Margin already committed across open positions."""
        if self.trader is None:
            return 0.0
        try:
            summary = self.trader.get_account_summary(current_prices or {})
            return float(summary.get("margin_used", 0.0))
        except Exception:
            return 0.0

    # -- the gate -----------------------------------------------------------

    def check_order(self, strategy: str, size_usd: float,
                    margin_required_usd: Optional[float] = None,
                    current_prices: Optional[Dict[str, float]] = None,
                    price: Optional[float] = None,
                    reduce_only: bool = False) -> RiskDecision:
        """
        Gate and size one order.

        `size_usd` is NOTIONAL; `margin_required_usd` is what the position ties up
        at its leverage. They differ by the leverage factor and the two limits act
        on different ones - the bucket constrains notional, the utilisation cap
        constrains margin - so both are needed. Omitting the margin figure assumes
        1x, which is the conservative reading.
        """
        name = str(strategy or "").strip() or "unattributed"
        size_usd = max(0.0, float(size_usd))
        margin = float(margin_required_usd) if margin_required_usd is not None else size_usd
        margin = max(0.0, margin)
        leverage_ratio = (size_usd / margin) if margin > 0 else 1.0

        equity = self.equity_usd(current_prices)
        used = self.used_margin_usd(current_prices)
        margin_budget = equity * self.max_margin_utilization
        margin_headroom = max(0.0, margin_budget - used)
        utilization = (used / equity) if equity > 0 else 0.0

        gate_up = self.tax_gate_available

        # Reduce-only orders close or reduce existing inventory, so they are
        # risk-reducing by definition. They must never be blocked by capital exhaustion.
        if reduce_only:
            return RiskDecision(
                approved=True, max_size_usd=size_usd, strategy=name,
                reason="reduce-only order approved (risk reducing)",
                margin_utilization=utilization, margin_headroom_usd=margin_headroom,
                safe_bankroll_usd=equity, bucket_remaining_usd=equity,
                tax_gate_available=gate_up, binding_limit="none")

        if self.require_tax_gate and not gate_up:
            return RiskDecision(
                approved=False, max_size_usd=0.0, strategy=name,
                reason=f"tax gate required but unavailable ({self.hook_error or 'unknown'})",
                margin_utilization=utilization, margin_headroom_usd=margin_headroom,
                tax_gate_available=False, binding_limit="bankroll")

        if size_usd <= 0:
            return RiskDecision(False, 0.0, "requested size must be positive", name,
                                utilization, margin_headroom, tax_gate_available=gate_up)

        # 1. Margin utilisation - a local, always-available limit.
        if margin_headroom <= 0:
            return RiskDecision(
                approved=False, max_size_usd=0.0, strategy=name,
                reason=(f"margin utilisation already at {utilization * 100:.1f}% of equity "
                        f"(cap {self.max_margin_utilization * 100:.0f}%); "
                        f"${used:,.2f} of ${margin_budget:,.2f} committed"),
                margin_utilization=utilization, margin_headroom_usd=0.0,
                tax_gate_available=gate_up, binding_limit="margin")

        # Headroom is expressed in MARGIN; convert to the notional it supports.
        margin_capped_notional = margin_headroom * leverage_ratio

        # 2. Safe bankroll and strategy bucket.
        bankroll_capped_notional = float("inf")
        safe_bankroll = 0.0
        bucket_remaining = 0.0
        bankroll_reason = ""
        if gate_up:
            try:
                decision = self.hook.check_order(size_usd, strategy=name, price=price)
                safe_bankroll = float(decision.safe_bankroll)
                bucket_remaining = float(decision.strategy_remaining)
                bankroll_reason = decision.reason
                bankroll_capped_notional = (float(decision.approved_notional)
                                            if decision.approved else 0.0)
            except Exception as exc:
                # Do not silently drop the constraint: say the check failed.
                self.hook_error = f"{type(exc).__name__}: {exc}"
                gate_up = False
                bankroll_reason = f"bankroll check failed ({self.hook_error})"

        allowed = min(size_usd, margin_capped_notional, bankroll_capped_notional)
        binding = ("margin" if margin_capped_notional <= bankroll_capped_notional
                   else "bankroll")

        if allowed <= 0:
            return RiskDecision(
                approved=False, max_size_usd=0.0, strategy=name,
                reason=(bankroll_reason or "no capital available for this strategy"),
                margin_utilization=utilization, margin_headroom_usd=margin_headroom,
                safe_bankroll_usd=safe_bankroll, bucket_remaining_usd=bucket_remaining,
                tax_gate_available=gate_up, binding_limit=binding)

        if not gate_up:
            note = (f"TAX GATE UNAVAILABLE ({self.hook_error or 'not configured'}) - sized "
                    f"on the paper balance only, NOT on safe bankroll")
            reason = (f"${allowed:,.2f} allowed by margin headroom "
                      f"(utilisation {utilization * 100:.1f}%). {note}")
        elif allowed < size_usd:
            reason = (f"trimmed to ${allowed:,.2f} by the {binding} limit "
                      f"(margin headroom ${margin_headroom:,.2f}, "
                      f"{name} bucket ${bucket_remaining:,.2f})")
        else:
            reason = (f"within limits (margin {utilization * 100:.1f}% of a "
                      f"{self.max_margin_utilization * 100:.0f}% cap, "
                      f"{name} bucket ${bucket_remaining:,.2f})")

        return RiskDecision(
            approved=True, max_size_usd=round(allowed, 2), strategy=name, reason=reason,
            margin_utilization=utilization, margin_headroom_usd=margin_headroom,
            safe_bankroll_usd=safe_bankroll, bucket_remaining_usd=bucket_remaining,
            tax_gate_available=gate_up, binding_limit=binding)

    def status_line(self, current_prices: Optional[Dict[str, float]] = None) -> str:
        """One line for a collector banner or the TUI."""
        equity = self.equity_usd(current_prices)
        used = self.used_margin_usd(current_prices)
        util = (used / equity * 100.0) if equity > 0 else 0.0
        if not self.tax_gate_available:
            return (f"[RISK] equity ${equity:,.2f} | margin {util:.1f}% of a "
                    f"{self.max_margin_utilization * 100:.0f}% cap | "
                    f"TAX GATE UNAVAILABLE - {self.hook_error or 'not configured'}")
        try:
            safe = float(self.hook.get_safe_bankroll())
        except Exception:
            safe = 0.0
        return (f"[RISK] equity ${equity:,.2f} | margin {util:.1f}% of a "
                f"{self.max_margin_utilization * 100:.0f}% cap | "
                f"safe bankroll ${safe:,.2f}")
