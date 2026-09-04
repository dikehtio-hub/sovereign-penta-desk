"""
Round 18: asset index resolution.

The index is what a signed order actually names. A wrong one produces a perfectly
valid signature on a different market - the worst failure in the execution path,
and a silent one.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.asset_resolver import (
    DEFAULT_MAX_AGE_SECONDS,
    OFFLINE_FALLBACK_UNIVERSE,
    AssetResolutionError,
    AssetResolver,
    StaleUniverseError,
)
from execution.order_executor import OrderExecutor
from execution.risk_manager import STRATEGY_BASIS_HARVEST, RiskDecision
from execution.wallet_manager import WalletManager

UNIVERSE = [{"name": "BTC", "szDecimals": 5},
            {"name": "ETH", "szDecimals": 4},
            {"name": "SOL", "szDecimals": 2}]


class _Gate:
    def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
        return RiskDecision(approved=True, max_size_usd=1_000_000.0, strategy=strategy,
                            reason="ok")


# ------------------------------------------------------------- resolution

def test_index_is_position_in_the_universe():
    resolver = AssetResolver(universe=UNIVERSE)
    assert resolver.resolve("BTC") == 0
    assert resolver.resolve("ETH") == 1
    assert resolver.resolve("SOL") == 2


def test_lookup_is_case_insensitive():
    assert AssetResolver(universe=UNIVERSE).resolve("btc") == 0


def test_whitespace_is_tolerated():
    assert AssetResolver(universe=UNIVERSE).resolve("  BTC  ") == 0


def test_a_prefixed_spot_name_resolves_on_its_own_entry():
    """Names like `xyz:GOLD` are ordinary entries, not something to parse."""
    resolver = AssetResolver(universe=UNIVERSE + [{"name": "xyz:GOLD", "szDecimals": 2}])
    assert resolver.resolve("xyz:GOLD") == 3


def test_size_decimals_are_available():
    assert AssetResolver(universe=UNIVERSE).size_decimals("BTC") == 5


def test_names_are_listed():
    assert AssetResolver(universe=UNIVERSE).names() == ["BTC", "ETH", "SOL"]


# --------------------------------------------------------------- refusals

def test_an_unknown_coin_raises_rather_than_defaulting_to_zero():
    """Defaulting to 0 would place a real order on whatever holds that index."""
    with pytest.raises(AssetResolutionError) as exc:
        AssetResolver(universe=UNIVERSE).resolve("NOPE")
    assert "refusing to guess" in str(exc.value).lower()


def test_an_empty_resolver_raises():
    with pytest.raises(AssetResolutionError):
        AssetResolver().resolve("BTC")


def test_an_empty_name_raises():
    with pytest.raises(AssetResolutionError):
        AssetResolver(universe=UNIVERSE).resolve("")


# ------------------------------------------------------------- stale guard

def test_a_stale_universe_is_refused():
    resolver = AssetResolver(universe=UNIVERSE, max_age_seconds=10.0,
                             loaded_at=time.time() - 3600)
    with pytest.raises(StaleUniverseError) as exc:
        resolver.resolve("BTC")
    assert "stale index" in str(exc.value)


def test_stale_can_be_allowed_explicitly_for_analytics():
    resolver = AssetResolver(universe=UNIVERSE, max_age_seconds=10.0,
                             loaded_at=time.time() - 3600)
    assert resolver.resolve("BTC", allow_stale=True) == 0


def test_a_fresh_universe_resolves():
    assert AssetResolver(universe=UNIVERSE, max_age_seconds=3600.0).resolve("BTC") == 0


def test_reloading_refreshes_the_clock():
    resolver = AssetResolver(universe=UNIVERSE, max_age_seconds=10.0,
                             loaded_at=time.time() - 3600)
    assert resolver.is_stale
    resolver.load_universe(UNIVERSE)
    assert not resolver.is_stale
    assert resolver.resolve("BTC") == 0


def test_the_default_age_limit_is_an_hour():
    assert DEFAULT_MAX_AGE_SECONDS == 3600.0


def test_a_zero_age_limit_disables_the_check():
    resolver = AssetResolver(universe=UNIVERSE, max_age_seconds=0.0,
                             loaded_at=time.time() - 99_999)
    assert resolver.resolve("BTC") == 0


# ---------------------------------------------------------- load validation

def test_a_meta_payload_is_unwrapped():
    assert AssetResolver(universe={"universe": UNIVERSE}).resolve("ETH") == 1


def test_duplicate_names_are_rejected_wholesale():
    """Two entries claiming one name means no index can be vouched for."""
    with pytest.raises(ValueError) as exc:
        AssetResolver(universe=UNIVERSE + [{"name": "BTC", "szDecimals": 5}])
    assert "duplicate" in str(exc.value)


def test_a_nameless_entry_is_rejected():
    with pytest.raises(ValueError):
        AssetResolver(universe=[{"name": "BTC"}, {"szDecimals": 2}])


def test_an_empty_universe_is_rejected():
    for bad in ([], None, "not a list", {}):
        with pytest.raises(ValueError):
            AssetResolver().load_universe(bad)


def test_a_rejected_load_leaves_the_previous_mapping_intact():
    """
    All-or-nothing. A partially applied universe is worse than none: the entries
    that loaded look authoritative while the rest raise as merely unlisted.
    """
    resolver = AssetResolver(universe=UNIVERSE)
    with pytest.raises(ValueError):
        resolver.load_universe([{"name": "BTC"}, {"name": "BTC"}])
    assert resolver.resolve("BTC") == 0
    assert resolver.names() == ["BTC", "ETH", "SOL"]


# ------------------------------------------------------------- offline mode

def test_the_offline_fallback_must_be_asked_for():
    """It is not authoritative, so nothing reaches a signature through it silently."""
    assert AssetResolver().loaded is False
    assert AssetResolver(fallback_only=True).loaded is True


def test_the_offline_fallback_resolves():
    resolver = AssetResolver(fallback_only=True)
    assert resolver.resolve("BTC") == 0
    assert resolver.describe()["source"] == "offline-fallback"


def test_the_fallback_universe_has_no_duplicates():
    names = [entry["name"] for entry in OFFLINE_FALLBACK_UNIVERSE]
    assert len(names) == len(set(names))


# ---------------------------------------------------- wired into the executor

def _executor(resolver=None, asset_index=None):
    return OrderExecutor(wallet=WalletManager(private_key="0x" + "11" * 32),
                         risk_manager=_Gate(), strategy=STRATEGY_BASIS_HARVEST,
                         asset_index=asset_index, asset_resolver=resolver,
                         dry_run=True)


def test_the_executor_resolves_through_the_resolver():
    executor = _executor(resolver=AssetResolver(universe=UNIVERSE))
    assert executor.asset_id("ETH") == 1


def test_the_resolver_outranks_a_static_map():
    """The resolver is the one that knows whether its mapping is still fresh."""
    executor = _executor(resolver=AssetResolver(universe=UNIVERSE),
                         asset_index={"ETH": 99})
    assert executor.asset_id("ETH") == 1


def test_a_stale_resolver_blocks_the_order_rather_than_falling_back():
    """
    A resolver saying "stale" is information. Falling back to the static map
    would discard it and place the order anyway.
    """
    stale = AssetResolver(universe=UNIVERSE, max_age_seconds=1.0,
                          loaded_at=time.time() - 3600)
    executor = _executor(resolver=stale, asset_index={"BTC": 0})
    result = executor.execute_order(coin="BTC", is_buy=True, sz="0.1",
                                    limit_px="60000.0")
    assert result.status == "REJECTED"
    assert "stale" in result.reason.lower()


def test_an_unknown_coin_through_the_resolver_is_rejected():
    executor = _executor(resolver=AssetResolver(universe=UNIVERSE))
    result = executor.execute_order(coin="NOPE", is_buy=True, sz="0.1",
                                    limit_px="60000.0")
    assert result.status == "REJECTED"


def test_the_static_map_still_works_without_a_resolver():
    assert _executor(asset_index={"BTC": 7}).asset_id("BTC") == 7


def test_the_resolved_index_reaches_the_signed_action():
    """The index is the point - it must land in the payload, not just the lookup."""
    executor = _executor(resolver=AssetResolver(universe=UNIVERSE))
    result = executor.execute_order(coin="SOL", is_buy=True, sz="1.0", limit_px="150.0")
    assert result.payload["action"]["orders"][0]["a"] == 2
