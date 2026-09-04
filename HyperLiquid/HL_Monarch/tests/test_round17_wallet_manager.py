"""
Round 17: EIP-712 agent wallet.

Entirely offline with a synthetic key. These tests pin the SHAPE of the signing
scheme and its safety properties; they do NOT prove the domain matches
Hyperliquid's, which only a captured live signature can do - see
`test_domain_is_marked_unverified`.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.wallet_manager import (
    AGENT_KEY_ENV,
    EIP712_DOMAIN,
    MAINNET_SOURCE,
    TESTNET_SOURCE,
    SigningUnavailable,
    WalletManager,
    new_cloid,
)

SYNTHETIC_KEY = "0x" + "11" * 32
OTHER_KEY = "0x" + "22" * 32


@pytest.fixture
def wallet():
    return WalletManager(private_key=SYNTHETIC_KEY, testnet=True)


# ------------------------------------------------------------- key handling

def test_a_synthetic_key_loads_offline(wallet):
    assert wallet.ready
    assert wallet.address.startswith("0x")
    assert len(wallet.address) == 42


def test_the_key_never_appears_in_repr(wallet):
    """A stack trace or debugger that prints this object must not spill it."""
    text = repr(wallet) + str(wallet)
    assert "11" * 32 not in text
    assert SYNTHETIC_KEY not in text
    assert wallet.address in text


def test_the_key_never_appears_in_describe(wallet):
    assert SYNTHETIC_KEY not in str(wallet.describe())


def test_an_invalid_key_does_not_echo_it():
    """The error message must not leak even a fragment of the rejected key."""
    secret = "0xdeadbeefcafe"
    with pytest.raises(ValueError) as exc:
        WalletManager(private_key=secret)
    assert "deadbeef" not in str(exc.value)


def test_a_key_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv(AGENT_KEY_ENV, SYNTHETIC_KEY)
    assert WalletManager().ready


def test_no_key_means_not_ready(monkeypatch):
    monkeypatch.delenv(AGENT_KEY_ENV, raising=False)
    assert WalletManager().ready is False


def test_signing_without_a_key_raises(monkeypatch):
    monkeypatch.delenv(AGENT_KEY_ENV, raising=False)
    action = WalletManager.order_action(0, True, "1.0", "1.0")
    with pytest.raises(SigningUnavailable):
        WalletManager().sign_action(action)


def test_a_key_without_0x_is_accepted():
    assert WalletManager(private_key="11" * 32).ready


# ---------------------------------------------------------- action encoding

def test_order_action_shape():
    action = WalletManager.order_action(coin_asset=5, is_buy=True, limit_px="60000.0",
                                        sz="0.1", cloid="0xabc")
    assert action["type"] == "order"
    order = action["orders"][0]
    assert order["a"] == 5 and order["b"] is True
    assert order["p"] == "60000.0" and order["s"] == "0.1"
    assert order["c"] == "0xabc"


def test_float_prices_and_sizes_are_refused():
    """
    Binary rounding changes the hash, so a float would sign a subtly different
    order than the decimal a human typed. Refused, not coerced.
    """
    with pytest.raises(TypeError):
        WalletManager.order_action(0, True, 60000.0, "0.1")
    with pytest.raises(TypeError):
        WalletManager.order_action(0, True, "60000.0", 0.1)


def test_cancel_actions():
    assert WalletManager.cancel_action(3, 99)["cancels"][0] == {"a": 3, "o": 99}
    by_cloid = WalletManager.cancel_by_cloid_action(3, "0xabc")
    assert by_cloid["type"] == "cancelByCloid"
    assert by_cloid["cancels"][0]["cloid"] == "0xabc"


def test_the_action_hash_is_deterministic():
    action = WalletManager.order_action(0, True, "1.0", "1.0")
    assert WalletManager.action_hash(action, 1) == WalletManager.action_hash(action, 1)


def test_the_hash_changes_with_the_nonce():
    action = WalletManager.order_action(0, True, "1.0", "1.0")
    assert WalletManager.action_hash(action, 1) != WalletManager.action_hash(action, 2)


def test_the_hash_changes_with_every_order_field():
    base = dict(coin_asset=0, is_buy=True, limit_px="1.0", sz="1.0")
    reference = WalletManager.action_hash(WalletManager.order_action(**base), 1)
    for override in (dict(coin_asset=1), dict(is_buy=False),
                     dict(limit_px="1.01"), dict(sz="2.0")):
        changed = WalletManager.action_hash(WalletManager.order_action(**{**base, **override}), 1)
        assert changed != reference, f"{override} did not change the signed hash"


def test_a_vault_address_changes_the_hash():
    action = WalletManager.order_action(0, True, "1.0", "1.0")
    plain = WalletManager.action_hash(action, 1)
    vaulted = WalletManager.action_hash(action, 1, vault_address="0x" + "ab" * 20)
    assert plain != vaulted


# -------------------------------------------------------------------- cloid

def test_cloid_shape_and_uniqueness():
    cloids = {new_cloid() for _ in range(200)}
    assert len(cloids) == 200
    for cloid in list(cloids)[:5]:
        assert cloid.startswith("0x") and len(cloid) == 34


# ------------------------------------------------------------------ signing

def test_signing_is_deterministic(wallet):
    action = WalletManager.order_action(0, True, "60000.0", "0.1")
    first = wallet.sign_action(action, nonce=1700000000000)
    second = wallet.sign_action(action, nonce=1700000000000)
    assert first.signature == second.signature


def test_a_different_key_signs_differently():
    action = WalletManager.order_action(0, True, "60000.0", "0.1")
    a = WalletManager(SYNTHETIC_KEY).sign_action(action, nonce=1)
    b = WalletManager(OTHER_KEY).sign_action(action, nonce=1)
    assert a.signature != b.signature


def test_testnet_and_mainnet_signatures_differ():
    """
    The default is TESTNET so a misconfiguration is rejected by the exchange
    rather than executed on the live account.
    """
    action = WalletManager.order_action(0, True, "60000.0", "0.1")
    testnet = WalletManager(SYNTHETIC_KEY, testnet=True).sign_action(action, nonce=1)
    mainnet = WalletManager(SYNTHETIC_KEY, testnet=False).sign_action(action, nonce=1)
    assert testnet.signature != mainnet.signature
    assert testnet.source == TESTNET_SOURCE and mainnet.source == MAINNET_SOURCE


def test_the_default_network_is_testnet():
    assert WalletManager(SYNTHETIC_KEY).testnet is True


def test_the_signed_payload_carries_no_secret(wallet):
    action = WalletManager.order_action(0, True, "60000.0", "0.1")
    payload = wallet.sign_action(action, nonce=1).to_payload()
    assert SYNTHETIC_KEY not in str(payload)
    assert set(payload) == {"action", "nonce", "signature", "vaultAddress"}


def test_signature_components(wallet):
    signed = wallet.sign_action(WalletManager.order_action(0, True, "1.0", "1.0"), nonce=1)
    assert set(signed.signature) == {"r", "s", "v"}
    assert signed.signature["v"] in (27, 28)
    assert signed.connection_id.startswith("0x")


# ------------------------------------------------------------------- nonces

def test_nonces_strictly_increase(wallet):
    nonces = [wallet.next_nonce() for _ in range(50)]
    assert nonces == sorted(nonces)
    assert len(set(nonces)) == 50


def test_an_explicit_nonce_is_honoured(wallet):
    assert wallet.sign_action(
        WalletManager.order_action(0, True, "1.0", "1.0"), nonce=42).nonce == 42


# ------------------------------------------------------------- verification

def test_domain_verification_is_computed_not_asserted(wallet):
    """
    SUPERSEDES a version asserting False. The encoding has since been checked
    against the official SDK, but the flag is RE-DERIVED from GOLDEN_VECTOR on
    every call rather than hard-coded - a constant True would keep claiming
    verification after someone edited the encoding, which is the exact situation
    the flag exists to catch.
    """
    from execution.wallet_manager import domain_verified
    assert domain_verified() is True
    assert wallet.describe()["domain_verified"] is True


def test_the_golden_vector_pins_the_encoding(wallet):
    """Any change to domain, types, msgpack order or nonce packing breaks this."""
    from execution.wallet_manager import GOLDEN_VECTOR
    produced = wallet.sign_action(GOLDEN_VECTOR["action"], nonce=GOLDEN_VECTOR["nonce"])
    assert produced.connection_id == GOLDEN_VECTOR["connection_id"]
    assert produced.signature == GOLDEN_VECTOR["signature"]


def test_the_domain_is_not_a_real_chain():
    """
    chainId 1337 means an exchange signature cannot be replayed as a mainnet
    transaction, which is the property that makes agent signing safe at all.
    """
    assert EIP712_DOMAIN["chainId"] == 1337
    assert EIP712_DOMAIN["verifyingContract"] == "0x" + "0" * 40


def test_verification_helper_matches_its_own_output(wallet):
    action = WalletManager.order_action(0, True, "60000.0", "0.1")
    signed = wallet.sign_action(action, nonce=7)
    assert wallet.verify_against_known_vector(action, 7, signed.signature)


def test_verification_helper_rejects_a_wrong_signature(wallet):
    action = WalletManager.order_action(0, True, "60000.0", "0.1")
    assert not wallet.verify_against_known_vector(
        action, 7, {"r": "0x0", "s": "0x0", "v": 27})


def test_this_module_contains_no_network_code():
    """A signing module that cannot reach the internet cannot place an order."""
    source = (Path(__file__).resolve().parents[1] / "execution" / "wallet_manager.py").read_text(
        encoding="utf-8")
    for forbidden in ("requests.", "urllib.request", "http://", "https://",
                      "socket.", "aiohttp"):
        assert forbidden not in source, f"wallet_manager should not reference {forbidden}"
