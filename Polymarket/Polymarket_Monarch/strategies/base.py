"""
================================================================================
Monarch: Base Strategy Interface
================================================================================
The contract every strategy plug-in implements. Subclassing this is what buys a
strategy its risk controls - a capital bucket, the after-tax edge hurdle, and
magnitude-adjusted position sizing - so that adding a strategy cannot
accidentally add an unguarded path to the account.

    class MyStrategy(BaseStrategy):
        name = "my_strategy"

        def scan(self):
            return [Opportunity(market="...", price=0.42, edge=0.06).as_dict()]

        def evaluate_opportunity(self, opportunity, hook):
            return hook.check_order(
                desired_notional=self.default_notional,
                price=opportunity["price"],
                category=opportunity.get("category"),
                strategy=self.name,
            )

TWO RULES THAT ARE NOT NEGOTIABLE, enforced here rather than left to each
implementation:

1. `min_edge` DEFAULTS TO THE AFTER-TAX BREAK-EVEN, never to zero. Under
   gross-of-fees accounting the tax lands on the gross gain while the fees come
   out of pocket unrecorded, so the hurdle is fee/(1-tax) - 3.08% at a 2% round
   trip and a 35% composite rate, not 2%. A strategy defaulting to 0 would surface
   trades that clear their fees and still lose money after tax.

2. `size()` ALWAYS ROUTES THROUGH THE HOOK, tagged with `self.name`. That tag is
   what places the trade in its capital bucket; an untagged strategy is
   quarantined into `sandbox`, which is the correct treatment for something nobody
   has budgeted for.

A strategy may override `min_edge`, but overriding it DOWNWARD is a decision to
trade below break-even, and `validate()` says so out loud.
================================================================================
"""

import csv
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tax_gate import DEV_ROOT, TaxGate

# Where csv_watcher looks. A receipt dropped here is picked up on the next sweep
# and ingested with its strategy tag intact.
IMPORTS_DIR = DEV_ROOT / "Tax_Reserve_Agent" / "data" / "imports"


@dataclass
class Opportunity:
    """
    One candidate trade. A plain shape, so `scan()` implementations stay simple
    and the gate still gets the fields it needs to size correctly.

    `price` and `edge` are both required: the Kelly stake depends on what the
    contract pays, and the hurdle applies to the edge.
    """
    market: str
    price: float                      # per-share cost, 0 < price < 1
    edge: float                       # expected GROSS edge as a decimal, e.g. 0.045
    category: Optional[str] = None    # for measured per-category sizing
    token_id: Optional[str] = None    # enables the live per-market fee hurdle
    outcome: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseStrategy(ABC):
    """
    Abstract base for a Monarch strategy plug-in.

    Subclasses must set `name` and implement `scan()` and `evaluate_opportunity()`.
    Everything else has a working default.
    """

    name: str = "unnamed_strategy"
    default_notional: float = 100.0
    # True for anything that BUYS and then REDEEMS (a dutch book): settlement runs
    # through the CTF contract, not the exchange, so only the entry pays a taker
    # fee. Left False by default - an undeclared strategy is assumed to trade out,
    # and over-stating the hurdle declines a marginal trade rather than taking a
    # losing one.
    holds_to_resolution: bool = False

    def __init__(self, gate: Optional[TaxGate] = None, min_edge: Optional[float] = None,
                 default_notional: Optional[float] = None):
        self.gate = gate if gate is not None else TaxGate()
        self._min_edge_override = min_edge
        if default_notional is not None:
            self.default_notional = float(default_notional)

    # -- the hurdle ---------------------------------------------------------

    @property
    def min_edge(self) -> float:
        """
        Minimum gross edge worth trading: the after-tax break-even, unless a
        subclass overrides it.

        Computed live from the configured fee and tax rates, falling back to the
        shim's failsafe when the agent is unreachable - never to zero, because a
        missing ledger must not silently remove the hurdle.
        """
        if self._min_edge_override is not None:
            return float(self._min_edge_override)
        return self.gate.breakeven_gross_edge()

    def hurdle_for(self, opportunity: Dict[str, Any]) -> float:
        """
        The hurdle for THIS opportunity, using its live fee when a token id is
        available.

        Polymarket fees scale with `min(p, 1-p)`, so one flat hurdle is wrong at
        both ends: on a 7% crypto book a coin-flip contract needs 10.77% while a
        2c contract needs 0.43%. Measured per market, the filter stops rejecting
        cheap tails and stops waving through expensive mids.
        """
        if self._min_edge_override is not None:
            return float(self._min_edge_override)
        token = opportunity.get("token_id") or (opportunity.get("detail") or {}).get("token_id")
        price = opportunity.get("price")
        if token and price:
            try:
                return self.gate.breakeven_gross_edge_for(
                    str(token), float(price), holds_to_resolution=self.holds_to_resolution)
            except Exception:
                pass
        return self.gate.breakeven_gross_edge()

    def clears_hurdle(self, opportunity: Dict[str, Any]) -> bool:
        """True when this opportunity's edge survives fees and tax."""
        try:
            return float(opportunity.get("edge", 0.0)) >= self.hurdle_for(opportunity)
        except (TypeError, ValueError):
            return False

    # -- the interface ------------------------------------------------------

    @abstractmethod
    def scan(self) -> List[Dict[str, Any]]:
        """
        Find candidate trades. Returns `Opportunity`-shaped dicts.

        Implementations should NOT filter on `min_edge` here - `opportunities()`
        does it, so every strategy applies the same hurdle the same way and a
        forgotten filter cannot become an unguarded path.
        """

    @abstractmethod
    def evaluate_opportunity(self, opportunity: Dict[str, Any], hook: Any) -> Any:
        """
        Turn one opportunity into a sized `BankrollDecision` via the hook.

        Implementations must pass `strategy=self.name` so the order lands in this
        strategy's capital bucket.
        """

    # -- defaults built on the interface ------------------------------------

    def opportunities(self) -> List[Dict[str, Any]]:
        """`scan()` with the after-tax hurdle applied. The cheapest correct default."""
        return [o for o in self.scan() if self.clears_hurdle(o)]

    def size(self, opportunity: Dict[str, Any], notional: Optional[float] = None) -> Any:
        """
        Sized decision for one opportunity, always tagged with this strategy.

        Returns None when the agent is unavailable rather than an unsized number:
        a caller that wants to trade anyway must make that choice explicitly, and
        `gate.status_line()` will already be saying UNGATED.
        """
        if not self.gate.available:
            return None
        enriched = dict(opportunity)
        enriched["_notional"] = notional if notional is not None else self.default_notional
        return self.evaluate_opportunity(enriched, self.gate.hook)

    def log_execution_receipt(self, market: str, token_id: str, size: float, price: float,
                              strategy: Optional[str] = None, side: str = "BUY",
                              imports_dir: Optional[Path] = None,
                              timestamp: Optional[str] = None,
                              tx_hash: Optional[str] = None) -> Optional[Path]:
        """
        Writes one fill to `data/imports/` so `csv_watcher` ingests it TAGGED.

        This is what closes the strategy-attribution loop. Bucket ceilings are
        measured from open lots carrying a `strategy:<name>;` note, so a fill that
        reaches the ledger untagged counts against no bucket and quietly loosens
        every ceiling. Writing the receipt at execution time is the only moment
        the strategy is known for certain.

        The file lands in the drop folder with a `polymarket` token in its name so
        the watcher classifies it without guessing, and each receipt gets its own
        file - the watcher moves a file once it is ingested, so appending to a
        shared one would race that move.

        Returns the path written, or None on failure. NEVER RAISES: a bookkeeping
        problem must not take down an execution path.
        """
        name = str(strategy or self.name)
        stamp = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        target_dir = Path(imports_dir) if imports_dir else IMPORTS_DIR
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            # uuid4, not a clock suffix: two fills in the same millisecond are
            # entirely normal and a collision would overwrite a real receipt.
            filename = (f"fills_polymarket_{name}_"
                        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_"
                        f"{uuid.uuid4().hex[:8]}.csv")
            path = target_dir / filename
            # PASS THE CHAIN HASH IF YOU HAVE IT. The ledger dedupes on
            # (source, tx_hash, symbol, side), and the Data API sync writes
            # `<tx>#<asset[:24]>`. Matching that format is what makes the receipt
            # and the synced row the SAME row rather than two rows for one fill -
            # without it the position is counted twice, doubling cost basis and
            # realised gains. Whichever lands first wins the insert; csv_watcher
            # then back-fills the strategy tag onto it.
            if tx_hash:
                ledger_key = f"{str(tx_hash).lower()}#{str(token_id)[:24]}"
            else:
                ledger_key = f"{name}_{token_id}_{stamp}".replace(" ", "_")

            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["timestamp", "symbol", "side", "quantity", "price",
                                 "fee", "tx_hash", "source", "notes"])
                writer.writerow([stamp, market, side.upper(), f"{float(size):.6f}",
                                 f"{float(price):.6f}", "0", ledger_key,
                                 "polymarket", f"strategy:{name};"])
            return path
        except Exception as e:
            print(f"[WARN] Could not write execution receipt for {market}: "
                  f"{type(e).__name__}: {e}. The fill will reach the ledger UNTAGGED "
                  f"and will not count against the {name} bucket.")
            return None

    def validate(self) -> List[str]:
        """
        Configuration problems worth surfacing before the strategy runs.

        Returns warnings rather than raising: an unusual hurdle is a choice, not a
        crash - but it should not be a silent one.
        """
        problems: List[str] = []
        if not self.name or self.name == "unnamed_strategy":
            problems.append("strategy has no `name`; it will be quarantined into the "
                            "sandbox bucket rather than getting its own allocation")
        breakeven = self.gate.breakeven_gross_edge()
        if self._min_edge_override is not None and self._min_edge_override < breakeven:
            problems.append(f"min_edge {self._min_edge_override * 100:.2f}% is BELOW the "
                            f"after-tax break-even of {breakeven * 100:.2f}% - trades "
                            f"clearing this hurdle can still lose money after tax")
        if self.default_notional <= 0:
            problems.append("default_notional must be positive")
        return problems

    def status_line(self) -> str:
        return f"[{self.name}] hurdle {self.min_edge * 100:.2f}% | {self.gate.status_line()}"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} min_edge={self.min_edge:.4f}>"
