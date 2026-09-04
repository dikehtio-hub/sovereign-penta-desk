"""
================================================================================
HL Monarch: Native Order Executor
================================================================================
The only path from a strategy's intent to a signed order. Its whole job is
ordering: GATE, then SIGN, then SUBMIT, then RECEIPT - in that order, with no way
to skip a step.

    executor = OrderExecutor(wallet, risk_manager, strategy="hl_basis_harvest")
    result = executor.execute_order(coin="BTC", is_buy=True, sz="0.1",
                                    limit_px="60000.0")

`execute_order` is wrapped in `@require_tax_gate`, which calls the risk manager
ITSELF rather than trusting this class to remember. An unapproved order raises
`RiskBreachException` before the wallet is touched, so a signing key is never
reachable from an unchecked path.

DRY RUN BY DEFAULT, AND THERE IS NO SUBMITTER. `submit_fn` is None unless someone
passes one, and this module contains no HTTP client, no URL and no socket. A
signed payload is produced and returned; sending it is a separate act that has to
be written deliberately. The signing constants are verified against the official
SDK and pinned by a golden vector - see `wallet_manager.domain_verified()`.

TWO LEGS, ONE SIZING DECISION. `execute_basis_pair()` gates the WHOLE pair before
either leg is placed, so the gate can never clamp one leg and leave the book
directionally exposed. Both legs then use the same agreed size.

What the gate cannot control is the fill. If one leg fills 0.1 and the other 0.04,
the ledger is told 0.1 and 0.04 - never a tidy symmetric pair that did not happen,
because a phantom hedge is worse than a visible gap nobody can miss.
================================================================================
"""

import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from execution.risk_manager import (
    STRATEGY_BASIS_HARVEST,
    RiskBreachException,
    RiskManager,
    require_tax_gate,
)
from execution.wallet_manager import SignedAction, SigningUnavailable, WalletManager, new_cloid


@dataclass
class ExecutionResult:
    """One attempt to place an order, whatever happened to it."""
    status: str                       # DRY_RUN | SUBMITTED | FILLED | PARTIAL | REJECTED | ERROR
    coin: str
    side: str
    requested_sz: float = 0.0
    filled_sz: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    cloid: str = ""
    oid: Optional[int] = None
    nonce: Optional[int] = None
    reason: str = ""
    strategy: str = ""
    approved_usd: float = 0.0
    receipt_path: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

    @property
    def unfilled_sz(self) -> float:
        return max(0.0, self.requested_sz - self.filled_sz)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OrderExecutor:
    """
    Gate -> sign -> (optionally) submit -> receipt.

    `submit_fn(payload) -> dict` is the only way anything leaves this process. It
    is injected, so the tests drive it and no transport is implied.
    """

    def __init__(self,
                 wallet: Optional[WalletManager] = None,
                 risk_manager: Optional[RiskManager] = None,
                 strategy: str = STRATEGY_BASIS_HARVEST,
                 submit_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                 asset_index: Optional[Dict[str, int]] = None,
                 asset_resolver: Any = None,
                 receipts_enabled: bool = False,
                 receipts_dir: Optional[Path] = None,
                 dry_run: bool = True):
        self.wallet = wallet
        self.risk_manager = risk_manager
        self.strategy = strategy
        self.submit_fn = submit_fn
        self.asset_index = asset_index or {}
        # A resolver, when supplied, OUTRANKS the static map: it is the one that
        # knows whether its mapping is still fresh, and a stale index signs a
        # valid order on whatever market now holds that slot.
        self.asset_resolver = asset_resolver
        self.dead_man_deadline_ms: Optional[int] = None
        self.receipts_enabled = bool(receipts_enabled)
        self.receipts_dir = Path(receipts_dir) if receipts_dir else None
        # Live submission requires BOTH an explicit dry_run=False and a submitter.
        # Two independent switches, so neither a stray default nor a stray
        # injection is enough on its own.
        self.dry_run = bool(dry_run)

    # -- helpers ------------------------------------------------------------

    def asset_id(self, coin: str) -> int:
        """
        Coin name -> exchange asset index.

        Resolver first, static map second. Unknown coins RAISE, and so does a
        STALE resolver: the index is what the signed action actually names, so
        defaulting an unmapped symbol to 0 - or serving a mapping that may have
        been reindexed since - signs a valid order on the wrong market. That is
        the single worst failure available here, and it is silent.
        """
        key = str(coin).upper()

        # SPOT IS A SEPARATE NUMBERING SPACE. A spot asset id is 10000 + the
        # pair's index in `spotMeta.universe`, which has no relationship to the
        # perp index in `meta.universe`. Deriving one from the other - as
        # `resolve(base) + 10000` did - yields a valid id for an unrelated pair:
        # on mainnet BTC's perp index is 0, so spot BTC resolved to 10000, which
        # is PURR/USDC. The basis harvester would have bought PURR while shorting
        # BTC perp, leaving an unhedged short and an unwanted altcoin position,
        # with no error anywhere. Spot now resolves ONLY against a real spotMeta
        # payload, and raises until one is loaded.
        if key.endswith("-SPOT"):
            if self.asset_resolver is not None:
                return int(self.asset_resolver.resolve_spot(key[:-5]))
            if key in self.asset_index:
                return int(self.asset_index[key])
            raise KeyError(
                f"no spot asset id for {key!r}. Refusing to derive one from the "
                f"perp index - that arithmetic names a different market. Supply a "
                f"resolver with a spotMeta universe, or map {key!r} explicitly.")

        if self.asset_resolver is not None:
            try:
                return int(self.asset_resolver.resolve(key))
            except Exception:
                if key.endswith("-PERP"):
                    return int(self.asset_resolver.resolve(key[:-5]))
                raise

        if key not in self.asset_index:
            if key.endswith("-PERP") and key[:-5] in self.asset_index:
                return int(self.asset_index[key[:-5]])
            raise KeyError(
                f"no asset index for {key!r}. Refusing to guess: an unmapped coin "
                f"would sign an order against whichever market holds that index.")
        return int(self.asset_index[key])

    # -- dead man's switch --------------------------------------------------

    def arm_dead_man_switch(self, ttl_seconds: float = 60.0,
                            now_ms: Optional[int] = None) -> ExecutionResult:
        """
        Tells the exchange to cancel everything resting at now + `ttl_seconds`.

        THE POINT IS THAT IT SURVIVES US. A process that hangs, crashes, or loses
        its network cannot send a cancel - which is exactly when its resting
        orders are most dangerous, because the market is moving and nothing is
        managing them. Handing the exchange a deadline is the only version of this
        protection that works during the failure it protects against.

        Re-arm on a timer comfortably shorter than the TTL. A 60s switch re-armed
        every 20s tolerates two missed heartbeats; one re-armed every 55s cancels
        the whole book on a single slow round trip.

        `ttl_seconds <= 0` DISARMS (sends time 0), which is a deliberate act and
        not something any other path does implicitly.
        """
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        deadline = 0 if ttl_seconds <= 0 else int(now + ttl_seconds * 1000)

        if self.wallet is None:
            return ExecutionResult(status="ERROR", coin="", side="",
                                   strategy=self.strategy,
                                   reason="no wallet attached; cannot arm the switch")
        try:
            action = WalletManager.schedule_cancel_action(deadline)
            signed = self.wallet.sign_action(action)
        except (SigningUnavailable, TypeError, ValueError) as exc:
            return ExecutionResult(status="ERROR", coin="", side="",
                                   strategy=self.strategy,
                                   reason=f"could not sign scheduleCancel: "
                                          f"{type(exc).__name__}: {exc}")

        result = ExecutionResult(
            status="DRY_RUN", coin="", side="", strategy=self.strategy,
            nonce=signed.nonce, payload=signed.to_payload(),
            reason=(f"dead man's switch {'DISARMED' if deadline == 0 else f'armed to {deadline}'} "
                    f"(signed, not submitted)"))

        if self.dry_run or self.submit_fn is None:
            self.dead_man_deadline_ms = deadline or None
            return result

        try:
            self.submit_fn(signed.to_payload())
        except Exception as exc:
            # An unconfirmed arm is NOT an armed switch. Recording it would leave
            # the caller believing it has protection it does not have.
            return ExecutionResult(status="ERROR", coin="", side="",
                                   strategy=self.strategy,
                                   reason=f"scheduleCancel submit failed "
                                          f"({type(exc).__name__}: {exc}). THE SWITCH IS "
                                          f"NOT ARMED - resting orders are unprotected.")
        self.dead_man_deadline_ms = deadline or None
        result.status = "SUBMITTED"
        result.reason = ("dead man's switch disarmed" if deadline == 0
                         else f"dead man's switch armed until {deadline}")
        return result

    @property
    def dead_man_armed(self) -> bool:
        """True only if a deadline is set AND still in the future."""
        if not self.dead_man_deadline_ms:
            return False
        return self.dead_man_deadline_ms > int(time.time() * 1000)

    # -- the gated path -----------------------------------------------------

    @require_tax_gate
    def execute_order(self, coin: str, is_buy: bool, sz: str, limit_px: str,
                      order_type: Optional[Dict[str, Any]] = None,
                      cloid: Optional[str] = None,
                      reduce_only: bool = False,
                      strategy: Optional[str] = None,
                      size_usd: Optional[float] = None,
                      margin_required_usd: Optional[float] = None,
                      risk_decision: Any = None) -> ExecutionResult:
        """
        Place one order. Raises `RiskBreachException` if the gate did not approve.

        `sz` and `limit_px` are decimal STRINGS - see `WalletManager.order_action`
        for why floats are refused rather than coerced.

        `risk_decision` is injected by the decorator; a caller never passes it.
        The approved notional is authoritative and the size is CLAMPED to it, so
        a strategy asking for more than the gate allowed gets the gate's number
        rather than an exception - the order still happens, just correctly sized.
        """
        name = strategy or self.strategy
        cloid = cloid or new_cloid()

        try:
            requested_sz = float(sz)
            price = float(limit_px)
        except (TypeError, ValueError):
            return ExecutionResult(status="REJECTED", coin=coin,
                                   side="BUY" if is_buy else "SELL", cloid=cloid,
                                   strategy=name, reason="size or price is not numeric")
        if requested_sz <= 0 or price <= 0:
            return ExecutionResult(status="REJECTED", coin=coin,
                                   side="BUY" if is_buy else "SELL", cloid=cloid,
                                   strategy=name, reason="size and price must be positive")

        approved_usd = float(getattr(risk_decision, "max_size_usd", 0.0) or 0.0)
        notional = requested_sz * price
        send_sz, send_px = sz, limit_px
        clamped_note = ""
        if approved_usd > 0 and notional > approved_usd:
            # Re-derive the string from the approved notional. Kept at 8dp, which
            # is finer than any HL size increment, so the clamp never rounds UP
            # past what the gate allowed.
            clamped = approved_usd / price
            send_sz = f"{clamped:.8f}"
            clamped_note = (f"size clamped from {requested_sz:g} to {clamped:.8f} by the "
                            f"risk gate (${approved_usd:,.2f})")

        try:
            asset = self.asset_id(coin)
        except KeyError as exc:
            return ExecutionResult(status="REJECTED", coin=coin,
                                   side="BUY" if is_buy else "SELL", cloid=cloid,
                                   strategy=name, reason=str(exc))

        if self.wallet is None:
            raise RiskBreachException(
                "execute_order reached signing with no wallet attached. Refusing to "
                "continue rather than silently doing nothing - a caller that thinks "
                "it placed an order and did not is worse than an error.")

        try:
            action = WalletManager.order_action(
                coin_asset=asset, is_buy=is_buy, limit_px=send_px, sz=send_sz,
                reduce_only=reduce_only, order_type=order_type, cloid=cloid)
            signed = self.wallet.sign_action(action)
        except (SigningUnavailable, TypeError, ValueError) as exc:
            return ExecutionResult(status="ERROR", coin=coin,
                                   side="BUY" if is_buy else "SELL", cloid=cloid,
                                   strategy=name, requested_sz=float(send_sz),
                                   reason=f"signing failed: {type(exc).__name__}: {exc}")

        result = ExecutionResult(
            status="DRY_RUN", coin=coin, side="BUY" if is_buy else "SELL",
            requested_sz=float(send_sz), avg_price=price, cloid=cloid,
            nonce=signed.nonce, strategy=name, approved_usd=approved_usd,
            reason=clamped_note or "signed, not submitted (dry run)",
            payload=signed.to_payload())

        if self.dry_run or self.submit_fn is None:
            return result

        return self._submit(result, signed, name)

    def _submit(self, result: ExecutionResult, signed: SignedAction,
                strategy: str) -> ExecutionResult:
        """
        Hands the payload to the injected submitter and interprets the reply.

        A transport failure is UNKNOWN, not "did not happen". The order may well
        be resting on the exchange, so the status says so and names the cloid to
        reconcile with - silently reporting a rejection would invite a duplicate.
        """
        try:
            response = self.submit_fn(signed.to_payload()) or {}
        except Exception as exc:
            result.status = "ERROR"
            result.reason = (f"submit failed ({type(exc).__name__}: {exc}). ORDER STATE "
                             f"UNKNOWN - it may be resting. Reconcile on cloid "
                             f"{result.cloid} before retrying, or a retry duplicates it.")
            return result

        filled = float(response.get("filled_sz", response.get("totalSz", 0.0)) or 0.0)
        result.filled_sz = filled
        result.oid = response.get("oid")
        result.fee = float(response.get("fee", 0.0) or 0.0)
        if response.get("avg_price"):
            result.avg_price = float(response["avg_price"])

        if response.get("status") == "rejected" or filled <= 0:
            result.status = "REJECTED" if filled <= 0 else "PARTIAL"
            result.reason = str(response.get("reason") or "no fill")
            if filled <= 0:
                return result
        elif filled + 1e-12 < result.requested_sz:
            result.status = "PARTIAL"
            result.reason = (f"filled {filled:g} of {result.requested_sz:g}; "
                             f"{result.unfilled_sz:g} unfilled")
        else:
            result.status = "FILLED"
            result.reason = "filled"

        result.receipt_path = self._write_receipt(result, strategy)
        return result

    def _write_receipt(self, result: ExecutionResult, strategy: str) -> Optional[str]:
        """
        Books EXACTLY what filled - never what was requested.

        This is the whole point of the partial-fill handling. Writing the
        requested size would put inventory in the tax ledger that the account
        does not hold, and every downstream number - cost basis, open exposure,
        the capital bucket ceiling - would be wrong in the same direction.
        """
        if not self.receipts_enabled or result.filled_sz <= 0:
            return None
        try:
            from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt
        except Exception as exc:
            print(f"[WARN] Receipts unavailable ({type(exc).__name__}: {exc}); this fill "
                  f"will reach the ledger unattributed.")
            return None

        path = log_execution_receipt(
            symbol=result.coin, side=result.side, quantity=result.filled_sz,
            price=result.avg_price, strategy=strategy, venue="hyperliquid",
            fee=result.fee, tx_hash=str(result.oid or result.cloid),
            imports_dir=self.receipts_dir,
            extra_notes=(f"cloid={result.cloid}; "
                         f"requested={result.requested_sz:g}; filled={result.filled_sz:g}"))
        return str(path) if path else None

    # -- basis pair ---------------------------------------------------------

    def pair_gate(self, coin: str, sz: str, spot_px: str,
                  perp_px: str) -> Dict[str, Any]:
        """
        Gates the WHOLE pair once and returns the size both legs must use.

        THE BUG THIS FIXES. Gating each leg separately lets the gate clamp leg 1
        to one size and leg 2 to another - and a cash-and-carry whose legs differ
        in size is not delta-neutral, it is a naked directional position wearing a
        hedge's name. The account ends up long or short the difference without
        anyone deciding to be.

        So the pair is priced as one thing: `sz * (spot_px + perp_px)` is the
        total notional committed across both legs. Whatever the gate approves is
        divided by that same combined price to get ONE size, which both legs then
        use. Clamping the pair keeps it balanced by construction.
        """
        size = float(sz)
        spot = float(spot_px)
        perp = float(perp_px)
        combined_px = spot + perp
        if size <= 0 or spot <= 0 or perp <= 0:
            return {"approved": False, "sz": "0", "reason": "size and both prices must be positive"}

        total_notional = size * combined_px
        decision = self.risk_manager.check_order(
            strategy=STRATEGY_BASIS_HARVEST, size_usd=total_notional,
            margin_required_usd=None, price=spot)

        if not decision.approved:
            return {"approved": False, "sz": "0", "reason": decision.reason,
                    "requested_notional": total_notional, "approved_notional": 0.0}

        approved = float(decision.max_size_usd)
        clamped_sz = min(size, approved / combined_px)
        return {
            "approved": True,
            "sz": f"{clamped_sz:.8f}",
            "clamped": clamped_sz < size - 1e-12,
            "requested_notional": total_notional,
            "approved_notional": approved,
            "reason": decision.reason,
        }

    def execute_basis_pair(self, coin: str, sz: str, spot_px: str, perp_px: str,
                           **kwargs: Any) -> Dict[str, Any]:
        """
        Long spot, short perp, sized as ONE decision.

        The pair is gated first and BOTH legs get the same clamped size, so the
        gate can never leave the book directionally exposed by trimming one leg.

        After that, the legs still fill independently and the exchange owes us
        nothing: if one fills and the other does not, `residual_sz` reports the
        real unhedged exposure rather than smoothing it away. A phantom symmetric
        hedge in the ledger is worse than a visible gap, because nobody goes
        looking for it.

        If leg 1 comes back a different size than the pair agreed - the gate moved
        underneath us between calls - LEG 2 IS NOT PLACED. Better to hold one
        known leg and say so than to add a second at the wrong size.

        Filled legs are never auto-unwound: unwinding is itself a market order
        into whatever just moved, and doing it inside an executor turns one bad
        fill into two.
        """
        gate = self.pair_gate(coin, sz, spot_px, perp_px)
        if not gate["approved"]:
            raise RiskBreachException(
                f"BLOCKED basis pair for {coin}: {gate['reason']}")

        agreed_sz = gate["sz"]
        spot = self.execute_order(coin=f"{coin}-SPOT", is_buy=True, sz=agreed_sz,
                                  limit_px=spot_px, strategy=STRATEGY_BASIS_HARVEST,
                                  **kwargs)

        if abs(spot.requested_sz - float(agreed_sz)) > 1e-9:
            return {"spot": spot, "perp": None,
                    "residual_sz": round(spot.filled_sz, 10),
                    "hedged": False, "gate": gate,
                    "aborted": (f"spot leg was re-sized to {spot.requested_sz:g} against an "
                                f"agreed {agreed_sz}; perp leg NOT placed rather than "
                                f"building a mismatched pair")}

        perp = self.execute_order(coin=f"{coin}-PERP", is_buy=False, sz=agreed_sz,
                                  limit_px=perp_px, strategy=STRATEGY_BASIS_HARVEST,
                                  **kwargs)
        residual = abs(spot.filled_sz - perp.filled_sz)
        return {"spot": spot, "perp": perp, "gate": gate,
                "residual_sz": round(residual, 10),
                "hedged": residual < 1e-9,
                "aborted": None}

    def close_basis_pair(self, coin: str, sz: str, spot_px: str, perp_px: str,
                         **kwargs: Any) -> Dict[str, Any]:
        """
        Unwinds a cash-and-carry pair: sell spot, buy back perp.
        Unwinding is risk-reducing and does not require pre-gate capital clamping.
        """
        spot = self.execute_order(coin=f"{coin}-SPOT", is_buy=False, sz=sz,
                                  limit_px=spot_px, strategy=STRATEGY_BASIS_HARVEST,
                                  reduce_only=True, **kwargs)
        perp = self.execute_order(coin=f"{coin}-PERP", is_buy=True, sz=sz,
                                  limit_px=perp_px, strategy=STRATEGY_BASIS_HARVEST,
                                  reduce_only=True, **kwargs)
        residual = abs(spot.filled_sz - perp.filled_sz)
        return {"spot": spot, "perp": perp,
                "residual_sz": round(residual, 10),
                "unwound": residual < 1e-9}

    def status_line(self) -> str:
        mode = "DRY RUN" if (self.dry_run or self.submit_fn is None) else "LIVE"
        wallet = self.wallet.address if self.wallet and self.wallet.ready else "no key"
        return f"[EXEC] {mode} | strategy {self.strategy} | agent {wallet}"
