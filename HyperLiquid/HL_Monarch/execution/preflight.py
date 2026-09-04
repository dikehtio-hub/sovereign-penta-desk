"""
================================================================================
HL Monarch: Live Pre-Flight Harness
================================================================================
One order, constructed and shown to a human before anything is signed or sent.

This exists because the first real order should be placed by a person looking at
the payload, not by a strategy loop. Everything it prints is the exact material
the exchange will see: the resolved asset index, the action, the connection id,
and the signature - so a mistake in any of them is visible BEFORE it becomes a
fill rather than after.

FOUR SAFETY DEFAULTS, all of which have to be turned off deliberately:
  * `--dry-run` is on. Nothing is submitted.
  * `--testnet` is on. The signing domain differs, so a testnet-signed action is
    rejected on mainnet rather than executed against real money.
  * Submission additionally requires a `submit_fn`, which this harness does not
    construct. Two switches plus a missing transport.
  * Mainnet + live requires typing an explicit confirmation phrase. A flag is too
    easy to leave in a shell history and re-run by arrow-key.

It is still gated by `RiskManager` like every other path. A pre-flight order that
skipped the gate would be testing something other than the system.
================================================================================
"""

import json
from typing import Any, Dict, Optional

from api.asset_resolver import AssetResolver
from execution.order_executor import OrderExecutor
from execution.risk_manager import RiskBreachException, RiskManager
from execution.wallet_manager import WalletManager, domain_verified, new_cloid

LIVE_CONFIRMATION_PHRASE = "SEND IT LIVE"


def build_preflight(coin: str, sz: str, px: str, is_buy: bool = True,
                    testnet: bool = True, dry_run: bool = True,
                    strategy: str = "hl_preflight",
                    wallet: Optional[WalletManager] = None,
                    risk_manager: Optional[RiskManager] = None,
                    resolver: Optional[AssetResolver] = None,
                    submit_fn: Optional[Any] = None,
                    trader: Any = None) -> Dict[str, Any]:
    """
    Gates, signs and (optionally) submits ONE order, returning everything a human
    needs to check it.

    `sz` and `px` stay strings the whole way down - see
    `WalletManager.order_action` for why a float would sign a different order than
    the one typed.
    """
    if wallet is None:
        try:
            wallet = WalletManager(testnet=testnet)
        except Exception as exc:
            # A missing eth_account, or a malformed key in the environment. Report
            # it as a block rather than a traceback: the operator needs to know
            # nothing was signed, which a stack trace does not say.
            return {"coin": coin, "sz": sz, "px": px,
                    "network": "testnet" if testnet else "MAINNET",
                    "dry_run": dry_run, "wallet_ready": False,
                    "blocked": f"wallet unavailable: {type(exc).__name__}: {exc}",
                    "result": None}
    resolver = resolver if resolver is not None else AssetResolver(fallback_only=True)
    if risk_manager is None:
        # A LIVE order demands a working tax gate; a dry run does not, so the
        # harness still runs on a machine with no ledger attached. The strictness
        # tracks the thing that can actually lose money.
        risk_manager = RiskManager(trader=trader, require_tax_gate=not dry_run)

    executor = OrderExecutor(
        wallet=wallet, risk_manager=risk_manager, strategy=strategy,
        submit_fn=submit_fn, asset_resolver=resolver, dry_run=dry_run,
        receipts_enabled=False)   # a pre-flight is not a strategy; it books nothing

    report: Dict[str, Any] = {
        "coin": coin, "side": "BUY" if is_buy else "SELL", "sz": sz, "px": px,
        "network": "testnet" if testnet else "MAINNET",
        "dry_run": dry_run,
        "wallet_ready": wallet.ready,
        "wallet_address": wallet.address,
        "domain_verified": domain_verified(),
        "resolver": resolver.describe(),
        "blocked": None,
        "result": None,
    }

    if not wallet.ready:
        report["blocked"] = ("no agent key loaded. Set HL_AGENT_PRIVATE_KEY. Nothing "
                             "was signed.")
        return report
    if not report["domain_verified"]:
        # The encoding no longer matches the vector that was checked against the
        # official SDK, so a signature produced now may name a different order.
        report["blocked"] = ("SIGNING ENCODING HAS CHANGED - domain_verified() is "
                             "False. Refusing to sign until the golden vector "
                             "matches again.")
        return report

    try:
        report["asset_index"] = resolver.resolve(coin)
    except Exception as exc:
        report["blocked"] = f"asset resolution failed: {type(exc).__name__}: {exc}"
        return report

    try:
        result = executor.execute_order(coin=coin, is_buy=is_buy, sz=sz, limit_px=px,
                                        cloid=new_cloid(), strategy=strategy)
    except RiskBreachException as exc:
        report["blocked"] = f"risk gate: {exc}"
        return report

    report["result"] = result.to_dict()

    # The connectionId is what the signature actually commits to. Showing it lets
    # an operator (or a second tool) re-derive the hash independently and confirm
    # the signature names THIS order and not a different one.
    payload = result.payload or {}
    if payload.get("action") and result.nonce is not None:
        try:
            report["connection_id"] = "0x" + WalletManager.action_hash(
                payload["action"], result.nonce,
                payload.get("vaultAddress")).hex()
        except Exception as exc:
            report["connection_id"] = f"<unavailable: {type(exc).__name__}>"
    return report


def render_preflight(report: Dict[str, Any]) -> str:
    """The human-readable page. Everything the exchange will see, before it sees it."""
    lines = ["=" * 78, "  HYPERLIQUID PRE-FLIGHT - ONE ORDER", "=" * 78]
    network = report.get("network", "?")
    lines.append(f"  network        : {network}"
                 + ("   <-- REAL MONEY" if network == "MAINNET" else ""))
    lines.append(f"  mode           : {'DRY RUN (nothing submitted)' if report.get('dry_run') else 'LIVE SUBMIT'}")
    lines.append(f"  agent wallet   : {report.get('wallet_address') or 'no key loaded'}")
    lines.append(f"  signing verified: {report.get('domain_verified')}")

    resolver = report.get("resolver") or {}
    lines.append(f"  asset universe : {resolver.get('assets', 0)} assets from "
                 f"{resolver.get('source', '?')}, "
                 f"{'STALE' if resolver.get('is_stale') else 'fresh'}")
    if "asset_index" in report:
        lines.append(f"  resolved index : {report['coin']} -> {report['asset_index']}")
    lines.append("-" * 78)
    lines.append(f"  ORDER          : {report.get('side')} {report.get('sz')} "
                 f"{report.get('coin')} @ {report.get('px')}")

    if report.get("blocked"):
        lines.append("-" * 78)
        lines.append(f"  BLOCKED: {report['blocked']}")
        lines.append("=" * 78)
        return "\n".join(lines)

    result = report.get("result") or {}
    lines.append(f"  status         : {result.get('status')}")
    lines.append(f"  cloid          : {result.get('cloid')}")
    lines.append(f"  nonce          : {result.get('nonce')}")
    if report.get("connection_id"):
        lines.append(f"  connectionId   : {report['connection_id']}")
    if result.get("approved_usd"):
        lines.append(f"  gate approved  : ${result['approved_usd']:,.2f}")
    if result.get("reason"):
        lines.append(f"  note           : {result['reason']}")

    payload = result.get("payload") or {}
    if payload:
        lines.append("-" * 78)
        lines.append("  SIGNED PAYLOAD (exactly what would be sent):")
        for line in json.dumps(payload, indent=2, sort_keys=True).splitlines():
            lines.append(f"    {line}")
    lines.append("=" * 78)
    if report.get("dry_run"):
        lines.append("  Nothing was submitted. Re-run with --no-dry-run to send it.")
    lines.append("  Check the asset index and the price before sending anything live.")
    lines.append("=" * 78)
    return "\n".join(lines)


def confirm_live(network_is_mainnet: bool, dry_run: bool,
                 typed: Optional[str] = None) -> bool:
    """
    Gate on a typed phrase for a real mainnet order.

    A flag is not enough: `--no-dry-run --mainnet` sits in a shell history and is
    one arrow-key away from being re-run against a different price. A phrase has
    to be retyped every time, which is the point.
    """
    if dry_run or not network_is_mainnet:
        return True
    return (typed or "").strip() == LIVE_CONFIRMATION_PHRASE
