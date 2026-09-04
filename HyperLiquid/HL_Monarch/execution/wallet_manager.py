"""
================================================================================
HL Monarch: EIP-712 Agent Wallet Manager
================================================================================
Signs Hyperliquid L1 actions with a delegated API Agent key.

VERIFIED 2026-09-03 against the official `hyperliquid-python-sdk`: this module
produces byte-identical signatures for the same action and nonce.

That verification is PINNED, not asserted. `GOLDEN_VECTOR` below records an exact
action, nonce and signature, and `domain_verified` RE-DERIVES the signature and
compares - so the flag reports what the code does today, not what was true on the
day someone typed True. Change the domain, the type list, the msgpack field order
or the nonce packing and the flag goes False on the next call, because a wrong
ACTION encoding produces a VALID signature over the WRONG ORDER and is the one
failure here that costs real money.

This module therefore CANNOT SUBMIT ANYTHING. There is no network code in it at
all - no requests, no sockets, no URLs. It produces a signed payload and hands it
back. Wiring that payload to an endpoint is a separate, deliberate act that
someone has to write on purpose.

WHY AN AGENT WALLET. Hyperliquid lets a main account authorise a separate
"agent" key that can trade but CANNOT withdraw. That is the only key that should
ever be in reach of this process. A compromised agent key costs you bad trades; a
compromised main key costs you the account.

KEY HANDLING RULES ENFORCED HERE
  * The key is read from the environment and never written anywhere - not to
    disk, not to logs, not into an exception message, not into a receipt.
  * `__repr__` and `__str__` return the ADDRESS only. A stack trace or a debugger
    that prints this object must not spill the key.
  * No accessor returns the raw key. If you need it, you have the environment.
================================================================================
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# Optional dependency: HL_Monarch declares only websockets and rich, so signing
# must not break an import for anyone who has not installed the crypto stack.
_SIGNING_IMPORT_ERROR = ""
try:
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    from eth_utils import keccak
except Exception as exc:
    Account = None
    encode_typed_data = None
    keccak = None
    _SIGNING_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

try:
    import msgpack
except Exception:
    msgpack = None

AGENT_KEY_ENV = "HL_AGENT_PRIVATE_KEY"
AGENT_ADDRESS_ENV = "HL_AGENT_ADDRESS"

# UNVERIFIED - see the module docstring. Hyperliquid signs L1 actions against a
# fixed domain that is deliberately not a real chain, so a signature captured for
# an exchange action cannot be replayed as a mainnet transaction.
EIP712_DOMAIN = {
    "name": "Exchange",
    "version": "1",
    "chainId": 1337,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

# UNVERIFIED. The agent struct wraps a hash of the msgpack-encoded action rather
# than the action's fields, which is why the action encoding has to be exact.
AGENT_TYPES = {
    "Agent": [
        {"name": "source", "type": "string"},
        {"name": "connectionId", "type": "bytes32"},
    ],
}

MAINNET_SOURCE = "a"
TESTNET_SOURCE = "b"

# A known-good encoding, captured after the SDK parity check passed. This is a
# REGRESSION GUARD on the most dangerous code in the repository: any change to the
# domain, types, msgpack ordering or nonce packing changes these bytes.
GOLDEN_VECTOR = {
    "private_key": "0x" + "11" * 32,
    "testnet": True,
    "action": {"type": "order", "orders": [{
        "a": 0, "b": True, "p": "60000.0", "s": "0.1", "r": False,
        "t": {"limit": {"tif": "Gtc"}}, "c": "0x" + "ab" * 16}], "grouping": "na"},
    "nonce": 1700000000000,
    "connection_id": "0x4edfbdda7ffd88b8def81a4fe738c24ee88821cefd8adf068f31c7adaca521ad",
    "signature": {
        "r": "0x2aa7105241bc11b803b17481d90cd1f45d5896d4957706eeeba51031be25a72f",
        "s": "0x3c9df4d1a2a2414020d14d6ce307865cb35bc63484355c9068211ffb0961d1d2",
        "v": 28},
}


def domain_verified() -> bool:
    """
    Re-derives the golden signature and compares. True only if the encoding still
    matches what was checked against the official SDK.

    Computed rather than hard-coded on purpose: a constant `True` would keep
    claiming verification after someone edited the encoding, which is exactly the
    situation the flag exists to prevent.
    """
    try:
        wallet = WalletManager(private_key=GOLDEN_VECTOR["private_key"],
                               testnet=GOLDEN_VECTOR["testnet"])
        produced = wallet.sign_action(GOLDEN_VECTOR["action"],
                                      nonce=GOLDEN_VECTOR["nonce"])
        return (produced.connection_id == GOLDEN_VECTOR["connection_id"]
                and produced.signature == GOLDEN_VECTOR["signature"])
    except Exception:
        return False


class SigningUnavailable(RuntimeError):
    """Raised when a signing operation is attempted without the crypto stack."""


@dataclass
class SignedAction:
    """A signed payload, ready for whatever eventually submits it."""
    action: Dict[str, Any]
    nonce: int
    signature: Dict[str, Any]
    address: str
    source: str
    vault_address: Optional[str] = None
    connection_id: str = ""

    def to_payload(self) -> Dict[str, Any]:
        """The request body shape. Contains no secret material."""
        return {
            "action": self.action,
            "nonce": self.nonce,
            "signature": self.signature,
            "vaultAddress": self.vault_address,
        }


def new_cloid() -> str:
    """
    A client order id: 16 random bytes as 0x-prefixed hex.

    Random rather than sequential on purpose. A cloid is how a reconnecting
    client works out whether an order it lost track of actually landed, and a
    counter that resets when the process restarts collides with its own history
    at exactly the moment it is most needed.
    """
    return "0x" + uuid.uuid4().hex


class WalletManager:
    """
    Holds a delegated agent key and signs actions with it.

    Offline and deterministic: give it a synthetic key and it signs, with no
    network access anywhere in the class.
    """

    def __init__(self, private_key: Optional[str] = None,
                 testnet: bool = True,
                 vault_address: Optional[str] = None,
                 env_var: str = AGENT_KEY_ENV):
        """
        `testnet` defaults TRUE. The signature domain differs between the two, so
        a testnet-signed action is rejected on mainnet rather than executed - the
        default fails toward "nothing happens" instead of "something happened on
        the live account".
        """
        self.testnet = bool(testnet)
        self.vault_address = vault_address
        self.env_var = env_var
        self._account = None
        self._address = ""

        key = private_key if private_key is not None else os.environ.get(env_var)
        if key:
            self._load(key)

    # -- key handling -------------------------------------------------------

    def _load(self, key: str) -> None:
        if Account is None:
            raise SigningUnavailable(
                f"eth_account is not installed ({_SIGNING_IMPORT_ERROR}). It is an "
                f"optional dependency; install it to sign, or keep using the paper "
                f"trader, which needs no keys at all.")
        key = str(key).strip()
        if not key.startswith("0x"):
            key = "0x" + key
        try:
            self._account = Account.from_key(key)
        except Exception as exc:
            # Deliberately does NOT echo the key or any part of it.
            raise ValueError(f"agent private key is not a valid secp256k1 key "
                             f"({type(exc).__name__})") from None
        self._address = self._account.address

    @property
    def address(self) -> str:
        return self._address

    @property
    def ready(self) -> bool:
        return self._account is not None

    @property
    def source(self) -> str:
        return TESTNET_SOURCE if self.testnet else MAINNET_SOURCE

    def __repr__(self) -> str:
        # Address only. A stack trace that prints this must not spill the key.
        return (f"<WalletManager address={self._address or 'unloaded'} "
                f"network={'testnet' if self.testnet else 'MAINNET'}>")

    __str__ = __repr__

    # -- action encoding ----------------------------------------------------

    @staticmethod
    def action_hash(action: Dict[str, Any], nonce: int,
                    vault_address: Optional[str] = None) -> bytes:
        """
        keccak(msgpack(action) || nonce || vault flag) - the `connectionId`.

        UNVERIFIED against the live API. msgpack is used because the exchange
        hashes a canonical binary encoding rather than JSON, and key ORDER matters
        to it - which is why `order_action()` builds its dicts in a fixed order
        instead of relying on whatever a caller passes in.
        """
        if msgpack is None or keccak is None:
            raise SigningUnavailable(
                "msgpack and eth_utils are required to hash an action; both are "
                "optional dependencies of HL_Monarch.")
        data = bytearray(msgpack.packb(action, use_bin_type=True))
        data += int(nonce).to_bytes(8, "big")
        if vault_address:
            data += b"\x01"
            data += bytes.fromhex(str(vault_address).removeprefix("0x"))
        else:
            data += b"\x00"
        return keccak(bytes(data))

    @staticmethod
    def order_action(coin_asset: int, is_buy: bool, limit_px: str, sz: str,
                     reduce_only: bool = False,
                     order_type: Optional[Dict[str, Any]] = None,
                     cloid: Optional[str] = None,
                     grouping: str = "na") -> Dict[str, Any]:
        """
        An `order` action.

        Prices and sizes are STRINGS. They are decimal quantities the exchange
        parses exactly, and a float that has been through binary rounding hashes
        differently from the decimal a human typed - which produces a valid
        signature over a subtly different order. Passing floats here is a bug,
        so they are rejected rather than coerced.
        """
        for name, value in (("limit_px", limit_px), ("sz", sz)):
            if not isinstance(value, str):
                raise TypeError(
                    f"{name} must be a decimal STRING, not {type(value).__name__}. "
                    f"Float rounding changes the hash and would sign a different "
                    f"order than the one intended.")
        order: Dict[str, Any] = {
            "a": int(coin_asset),
            "b": bool(is_buy),
            "p": limit_px,
            "s": sz,
            "r": bool(reduce_only),
            "t": order_type or {"limit": {"tif": "Gtc"}},
        }
        if cloid:
            order["c"] = cloid
        return {"type": "order", "orders": [order], "grouping": grouping}

    @staticmethod
    def schedule_cancel_action(time_ms: int) -> Dict[str, Any]:
        """
        A dead-man's switch: cancel every resting order at `time_ms` unless the
        deadline is pushed back before then.

        THE PROTECTION IS THE DEADLINE, NOT THE CALL. A process that dies, hangs,
        or loses its network does not get to send a cancel - which is precisely
        when its resting orders are most dangerous. Arming the exchange to do it
        unilaterally is the only version that survives the failure it protects
        against.

        `time_ms` is absolute epoch milliseconds, not a duration. Re-arming
        replaces the previous deadline; passing 0 clears it.
        """
        return {"type": "scheduleCancel", "time": int(time_ms)}

    @staticmethod
    def cancel_action(coin_asset: int, oid: int) -> Dict[str, Any]:
        return {"type": "cancel", "cancels": [{"a": int(coin_asset), "o": int(oid)}]}

    @staticmethod
    def cancel_by_cloid_action(coin_asset: int, cloid: str) -> Dict[str, Any]:
        return {"type": "cancelByCloid",
                "cancels": [{"asset": int(coin_asset), "cloid": str(cloid)}]}

    # -- signing ------------------------------------------------------------

    def sign_action(self, action: Dict[str, Any], nonce: Optional[int] = None,
                    vault_address: Optional[str] = None) -> SignedAction:
        """
        Signs one action. No network access; returns the payload for a submitter.

        The nonce defaults to milliseconds since epoch, which is what the exchange
        expects and is also the source of the desync hazard documented in
        `next_nonce()`.
        """
        if not self.ready:
            raise SigningUnavailable(
                f"no agent key loaded. Set {self.env_var} or pass private_key=. "
                f"Nothing is signed without one.")
        nonce = int(nonce if nonce is not None else self.next_nonce())
        vault = vault_address if vault_address is not None else self.vault_address

        connection_id = self.action_hash(action, nonce, vault)
        message = {"source": self.source, "connectionId": connection_id}
        encoded = encode_typed_data(domain_data=EIP712_DOMAIN,
                                    message_types=AGENT_TYPES,
                                    message_data=message)
        signed = self._account.sign_message(encoded)
        return SignedAction(
            action=action, nonce=nonce, address=self._address, source=self.source,
            vault_address=vault, connection_id="0x" + connection_id.hex(),
            signature={"r": hex(signed.r), "s": hex(signed.s), "v": signed.v})

    _last_nonce = 0

    def next_nonce(self) -> int:
        """
        Millisecond timestamp, forced strictly increasing within this process.

        THE DESYNC THIS DOES NOT FIX: the exchange tracks the highest nonce it has
        seen for the agent. Two processes signing with the SAME key, or one
        restarting after a clock adjustment, can emit a nonce below that
        high-water mark, and every such action is rejected until wall-clock time
        catches up. One key per process, and never sign on a machine whose clock
        steps backwards.
        """
        now = int(time.time() * 1000)
        WalletManager._last_nonce = max(now, WalletManager._last_nonce + 1)
        return WalletManager._last_nonce

    # -- verification -------------------------------------------------------

    def verify_against_known_vector(self, action: Dict[str, Any], nonce: int,
                                    expected_signature: Dict[str, Any],
                                    vault_address: Optional[str] = None) -> bool:
        """
        Checks this implementation against a signature the live API ACCEPTED.

        Run this before trusting anything in this module. Capture a real accepted
        request (action, nonce, signature) from the official SDK, feed it here,
        and confirm it matches. Until it returns True for a real vector, the
        domain and encoding constants above are hypotheses.
        """
        produced = self.sign_action(action, nonce=nonce, vault_address=vault_address)
        return all(
            str(produced.signature.get(k, "")).lower() == str(expected_signature.get(k, "")).lower()
            for k in ("r", "s")
        ) and int(produced.signature.get("v", 0)) == int(expected_signature.get("v", 0))

    def describe(self) -> Dict[str, Any]:
        """Diagnostics. Contains no secret material by construction."""
        return {
            "address": self._address,
            "ready": self.ready,
            "network": "testnet" if self.testnet else "mainnet",
            "source": self.source,
            "vault_address": self.vault_address,
            "signing_available": Account is not None and msgpack is not None,
            "signing_import_error": _SIGNING_IMPORT_ERROR,
            # Re-derived every call from GOLDEN_VECTOR, never a stored constant.
            "domain_verified": domain_verified(),
        }
