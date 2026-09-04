"""
================================================================================
Polymarket Monarch: Tax-Aware Sizing Gate
================================================================================
Bridge from Monarch to the Tax Reserve Agent (`DEV/Tax_Reserve_Agent`), which
tracks FIFO cost basis across Polymarket, spot and options and knows how much of
the wallet balance is already owed in tax.

The number every sizing decision should be made against is not the wallet
balance, it is the balance MINUS the escrow on gains already realised this year.
Sizing off the raw balance is how a profitable year turns into an April funded by
liquidating positions.

WHY THIS FILE EXISTS AT ALL. Monarch and the agent are separate projects in
sibling folders, neither on the other's import path. Rather than scatter
`sys.path` surgery and try/except imports through every scanner, the coupling
lives here: one import, one failure mode, one place to change when either project
moves.

FAIL-OPEN, LOUDLY - AND ONLY HERE. The agent's own hook is deliberately
fail-CLOSED: if it cannot read the ledger it rejects the order, because a
spending limit that silently stops limiting is worse than no limit. Monarch's
scanners place no orders - they price hypothetical positions and print tables -
so refusing to scan because an accounting database is missing would be absurd.
This shim therefore falls back to the requested size when the agent is
unavailable, and every consumer is required to print the `status_line()`, which
says UNGATED in that case. If you ever wire this into something that actually
sends an order, use `MonarchBankrollHook.check_order()` directly and honour its
rejection instead.
================================================================================
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# DEV/Polymarket/Polymarket_Monarch/tax_gate.py -> DEV/
DEV_ROOT = Path(__file__).resolve().parents[2]

# Used ONLY when the agent cannot be reached. The live figure is always computed
# as fee/(1 - tax) from config; this is what that evaluates to at the 2%
# round-trip and 35% composite rate the analysis was done at. It is a FAILSAFE,
# not a default - if fees or tax rates move and the agent is down, this constant
# silently lies, so the scanners print which figure they are using.
FALLBACK_AFTER_TAX_EDGE = 0.0308

_IMPORT_ERROR = ""
try:
    if str(DEV_ROOT) not in sys.path:
        sys.path.insert(0, str(DEV_ROOT))
    from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook
except Exception as exc:  # ImportError, but also a broken config or missing yaml
    MonarchBankrollHook = None
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


@dataclass
class GatedSize:
    """The outcome of clamping a requested position size against risk capital."""
    requested_shares: float
    approved_shares: float
    cost_per_share: float
    gated: bool             # False = the agent was unreachable, size is UNCLAMPED
    reason: str
    category: str = ""
    strategy: str = "default"
    safe_bankroll: float = 0.0
    tax_escrow: float = 0.0
    max_notional: float = 0.0

    @property
    def clamped(self) -> bool:
        return self.gated and self.approved_shares < self.requested_shares

    @property
    def blocked(self) -> bool:
        return self.gated and self.approved_shares <= 0.0

    def __str__(self) -> str:
        if not self.gated:
            return f"{self.requested_shares:,.0f} shares (UNGATED: {self.reason})"
        if self.blocked:
            return f"0 shares - {self.reason}"
        if self.clamped:
            return (f"{self.approved_shares:,.0f} shares "
                    f"(trimmed from {self.requested_shares:,.0f}: {self.reason})")
        return f"{self.approved_shares:,.0f} shares (within limits)"


class TaxGate:
    """
    Thin Monarch-facing wrapper over `MonarchBankrollHook`.

    `available` is False when the agent could not be imported or its ledger could
    not be read; in that state `clamp_shares()` passes the requested size through
    untouched and `status_line()` announces it.
    """

    def __init__(self,
                 max_position_pct: float = 0.05,
                 live_cash: Optional[float] = None,
                 tax_year: Optional[int] = None,
                 db_path: Optional[Path] = None,
                 enabled: bool = True,
                 hook: Any = None):
        self.live_cash = live_cash
        self.enabled = enabled
        self.reason = ""
        self.hook = hook
        # A MISCONFIGURATION IS NOT AN OUTAGE. Everything else here degrades to
        # UNGATED, which is right when the agent is merely unreachable - Monarch
        # places no orders and refusing to scan over a missing database would be
        # absurd. But an impossible capital plan is the operator asking for
        # something that cannot be honoured, and passing sizes through untouched
        # would turn a typo into "all sizing protection silently off". That case
        # blocks instead.
        self.fatal_config_error = ""

        if not enabled:
            self.reason = "tax gate disabled (--no-tax-gate)"
        elif self.hook is None:
            if MonarchBankrollHook is None:
                self.reason = f"Tax Reserve Agent not importable ({_IMPORT_ERROR})"
            else:
                try:
                    self.hook = MonarchBankrollHook(tax_year=tax_year, db_path=db_path,
                                                    max_position_pct=max_position_pct)
                except Exception as exc:
                    self.reason = f"Tax Reserve Agent failed to start ({type(exc).__name__}: {exc})"
                    if type(exc).__name__ == "StrategyAllocationError":
                        self.fatal_config_error = str(exc)

    @property
    def available(self) -> bool:
        """True only when a hook exists AND its ledger actually reads."""
        if self.hook is None:
            return False
        try:
            return bool(self.hook.snapshot(self.live_cash).get("available", False))
        except Exception as exc:
            self.reason = f"tax ledger unreadable ({type(exc).__name__}: {exc})"
            return False

    def status_line(self) -> str:
        """One line for a scanner banner or the TUI header. Never raises."""
        if self.fatal_config_error:
            return f"[TAX] BLOCKED - {self.fatal_config_error}"
        if not self.available:
            return f"[TAX] UNGATED - {self.reason or 'tax reserve agent unavailable'}"
        try:
            return self.hook.status_line(self.live_cash)
        except Exception as exc:
            return f"[TAX] UNGATED - status unavailable ({type(exc).__name__}: {exc})"

    def breakeven_gross_edge(self, default: float = FALLBACK_AFTER_TAX_EDGE) -> float:
        """
        Smallest gross edge that survives fees and tax, or `default` when the agent
        is unavailable.

        Under gross-of-fees accounting the tax lands on the GROSS gain while the
        fees come out of pocket unrecorded, so break-even is fee/(1-tax), not fee:
        2% round trip at a 35% composite rate needs 3.08%, and the 1.08pp gap is
        purely the cost of the ledger not seeing fees.
        """
        if not self.available:
            print(f"[TAX] break-even falling back to {float(default) * 100:.2f}% - "
                  f"the agent could not compute it from live fee and tax settings.")
            return float(default)
        try:
            return float(self.hook.breakeven_gross_edge())
        except Exception:
            return float(default)

    def breakeven_gross_edge_for(self, token_id: str, price: float,
                                 default: float = FALLBACK_AFTER_TAX_EDGE,
                                 holds_to_resolution: bool = False) -> float:
        """
        Per-market hurdle from the live fee schedule; falls back, never to zero.

        `holds_to_resolution` halves it for strategies that redeem rather than
        sell - a dutch book pays the exchange once, on the way in.
        """
        if not self.available:
            return float(default)
        try:
            return float(self.hook.breakeven_gross_edge(
                token_id=token_id, price=price, holds_to_resolution=holds_to_resolution))
        except Exception:
            return float(default)

    def clamp_shares(self, shares: float, cost_per_share: float = 1.0,
                     category: Optional[str] = None,
                     strategy: str = "default") -> GatedSize:
        """
        Clamps a share count to what the safe bankroll actually supports.

        `cost_per_share` converts shares to dollars. For a negative-risk dutch
        book that is the summed ask across all legs - a complete set costs about
        $1, so the default of 1.0 is the right approximation when the real book
        has not been walked yet.
        """
        requested = max(0.0, float(shares))
        price = float(cost_per_share)
        if self.fatal_config_error:
            # Blocked, not passed through: see `fatal_config_error` above.
            return GatedSize(requested, 0.0, price, True,
                             f"capital plan is invalid - {self.fatal_config_error}")
        if price <= 0:
            # Free shares cannot exhaust a bankroll; nothing to clamp against.
            return GatedSize(requested, requested, price, False,
                             "cost per share is zero or negative - nothing to size against")
        if not self.available:
            return GatedSize(requested, requested, price, False,
                             self.reason or "tax reserve agent unavailable")

        # `category` lets the agent size on measured edge for this market type
        # rather than one flat percentage; `price` is the per-share cost, which is
        # what the Kelly stake actually depends on.
        decision = self.hook.check_order(requested * price, live_cash=self.live_cash,
                                         category=category, price=price, strategy=strategy)
        approved_shares = decision.approved_notional / price if decision.approved else 0.0
        return GatedSize(
            requested_shares=requested,
            approved_shares=approved_shares,
            cost_per_share=price,
            gated=True,
            reason=decision.reason,
            category=getattr(decision, "category", "") or "",
            strategy=getattr(decision, "strategy", "default") or "default",
            safe_bankroll=decision.safe_bankroll,
            tax_escrow=decision.tax_escrow,
            max_notional=decision.max_position_size,
        )


def build_gate(args: Any = None, **kwargs: Any) -> TaxGate:
    """
    Constructs a gate from parsed CLI args, so every Monarch tool wires it the
    same way. Recognises `--no-tax-gate`, `--cash` and `--max-position-pct`.
    """
    if args is not None:
        kwargs.setdefault("enabled", not getattr(args, "no_tax_gate", False))
        kwargs.setdefault("live_cash", getattr(args, "cash", None))
        kwargs.setdefault("max_position_pct", getattr(args, "max_position_pct", 0.05))
    return TaxGate(**kwargs)


def add_tax_arguments(parser: Any) -> Any:
    """Adds the shared tax-gate flags to an argparse parser."""
    parser.add_argument("--no-tax-gate", action="store_true",
                        help="Do not clamp sizing against the Tax Reserve Agent's safe bankroll")
    parser.add_argument("--cash", type=float, default=None,
                        help="Live cash balance in USD (overrides the agent's config value)")
    parser.add_argument("--max-position-pct", type=float, default=0.05,
                        help="Max fraction of the SAFE bankroll per position (default: 0.05)")
    return parser


if __name__ == "__main__":
    gate = TaxGate()
    print(gate.status_line())
    print(" 100 shares @ $1.00 ->", gate.clamp_shares(100.0))
    print("5000 shares @ $1.00 ->", gate.clamp_shares(5000.0))
