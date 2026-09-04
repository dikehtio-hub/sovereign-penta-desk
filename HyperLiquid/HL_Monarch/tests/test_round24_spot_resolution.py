"""
Round 24 audit: spot asset ids are a separate numbering space.

A Hyperliquid spot asset id is `10000 + the pair's index in spotMeta.universe`.
The perp index in `meta.universe` is unrelated. Deriving one from the other is
the single worst failure available in the execution path, because the resulting
order is valid, accepted and filled - on a different market.

Concretely, with BTC at perp index 0 and PURR/USDC at spot pair 0, the old
`resolve(base) + 10000` returned 10000 for "BTC-SPOT" - PURR. The basis harvester
would have bought PURR while shorting BTC perp: an unhedged short plus an
unwanted altcoin position, reported as a successful pair.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.asset_resolver import (
    SPOT_ASSET_ID_OFFSET,
    AssetResolutionError,
    AssetResolver,
    StaleUniverseError,
)
from execution.order_executor import OrderExecutor
from execution.risk_manager import RiskDecision
from execution.wallet_manager import WalletManager

PERP_UNIVERSE = [{"name": "BTC", "szDecimals": 5},
                 {"name": "ETH", "szDecimals": 4},
                 {"name": "SOL", "szDecimals": 2}]

# Mainnet-shaped: PURR is spot pair 0, so it collides with BTC's perp index.
SPOT_META = {"universe": [{"name": "PURR/USDC", "index": 0},
                          {"name": "HYPE/USDC", "index": 1},
                          {"name": "BTC/USDC", "index": 2},
                          {"name": "ETH/USDC", "index": 3}]}


class _Gate:
    def check_order(self, strategy, size_usd, margin_required_usd=None, **kwargs):
        return RiskDecision(approved=True, max_size_usd=1_000_000.0, strategy=strategy,
                            reason="ok")


def _resolver(spot=True):
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    if spot:
        resolver.load_spot_universe(SPOT_META)
    return resolver


def _executor(resolver=None, asset_index=None):
    return OrderExecutor(wallet=WalletManager(private_key="0x" + "11" * 32),
                         risk_manager=_Gate(), asset_resolver=resolver,
                         asset_index=asset_index, dry_run=True)


# --------------------------------------------------------- the numbering space

def test_the_spot_offset_is_ten_thousand():
    assert SPOT_ASSET_ID_OFFSET == 10000


def test_a_spot_id_is_the_offset_plus_the_pair_index():
    assert _resolver().resolve_spot("BTC/USDC") == 10002


def test_the_base_token_resolves_to_its_usdc_pair():
    assert _resolver().resolve_spot("BTC") == 10002


def test_the_spot_suffix_is_accepted_directly():
    assert _resolver().resolve_spot("BTC-SPOT") == 10002


def test_the_explicit_index_field_is_preferred_over_position():
    """It is what the exchange itself asserts; position is only a fallback."""
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe({"universe": [{"name": "AAA/USDC", "index": 7},
                                              {"name": "BBB/USDC", "index": 9}]})
    assert resolver.resolve_spot("AAA") == 10007
    assert resolver.resolve_spot("BBB") == 10009


def test_position_is_used_when_no_index_field_is_given():
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe({"universe": [{"name": "AAA/USDC"},
                                              {"name": "BBB/USDC"}]})
    assert resolver.resolve_spot("BBB") == 10001


# ------------------------------------------------------------- THE ACTUAL BUG

def test_the_spot_id_is_not_the_perp_id_plus_the_offset():
    """
    The regression this file exists for. BTC is perp 0 and spot pair 2, so the
    old arithmetic produced 10000 - PURR/USDC - for an order meant for BTC.
    """
    resolver = _resolver()
    assert resolver.resolve("BTC") == 0
    assert resolver.resolve_spot("BTC") == 10002
    assert resolver.resolve_spot("BTC") != resolver.resolve("BTC") + SPOT_ASSET_ID_OFFSET


def test_the_wrong_derivation_would_have_named_purr():
    """Names the market the old code would actually have traded."""
    resolver = _resolver()
    collided = resolver.resolve("BTC") + SPOT_ASSET_ID_OFFSET
    assert collided == resolver.resolve_spot("PURR/USDC")


def test_the_executor_signs_the_real_spot_index():
    executor = _executor(resolver=_resolver())
    result = executor.execute_order(coin="BTC-SPOT", is_buy=True, sz="0.01",
                                    limit_px="60000.0")
    assert result.payload["action"]["orders"][0]["a"] == 10002


def test_perp_and_spot_legs_of_one_pair_get_different_ids():
    """A basis pair whose legs share an id is not a hedge."""
    executor = _executor(resolver=_resolver())
    assert executor.asset_id("BTC-PERP") != executor.asset_id("BTC-SPOT")


# -------------------------------------------------------------- refusals

def test_spot_without_a_spot_universe_raises():
    """
    Refusing is the point. The perp map cannot answer this question, and the
    previous fallback answered it wrongly instead of admitting that.
    """
    with pytest.raises(AssetResolutionError) as exc:
        _resolver(spot=False).resolve_spot("BTC")
    assert "different numbering space" in str(exc.value)


def test_the_executor_refuses_a_spot_order_with_no_spot_universe():
    executor = _executor(resolver=_resolver(spot=False))
    result = executor.execute_order(coin="BTC-SPOT", is_buy=True, sz="0.01",
                                    limit_px="60000.0")
    assert result.status == "REJECTED"


def test_a_coin_absent_from_the_spot_universe_raises():
    with pytest.raises(AssetResolutionError):
        _resolver().resolve_spot("SOL")       # perp-listed, no spot pair


def test_a_stale_spot_universe_is_refused():
    resolver = AssetResolver(universe=PERP_UNIVERSE, max_age_seconds=10.0)
    resolver.load_spot_universe(SPOT_META, loaded_at=time.time() - 3600)
    with pytest.raises(StaleUniverseError):
        resolver.resolve_spot("BTC")


def test_stale_spot_can_be_allowed_for_analytics():
    resolver = AssetResolver(universe=PERP_UNIVERSE, max_age_seconds=10.0)
    resolver.load_spot_universe(SPOT_META, loaded_at=time.time() - 3600)
    assert resolver.resolve_spot("BTC", allow_stale=True) == 10002


def test_a_static_map_must_name_the_spot_key_explicitly():
    """No silent +10000 on a caller-supplied map either."""
    executor = _executor(asset_index={"BTC": 0})
    with pytest.raises(KeyError):
        executor.asset_id("BTC-SPOT")
    assert _executor(asset_index={"BTC-SPOT": 10002}).asset_id("BTC-SPOT") == 10002


# ----------------------------------------------------------- load validation

def test_the_bare_alias_means_the_USDC_pair_when_several_quotes_exist():
    """
    Only USDC pairs get a bare alias, so "BTC" means BTC/USDC even when BTC/USDT
    is also listed. That is the right reading for a USDC-margined desk, and the
    other quote is still reachable by its full pair name - never silently.
    """
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe({"universe": [{"name": "BTC/USDC", "index": 0},
                                              {"name": "BTC/USDT", "index": 1}]})
    assert resolver.resolve_spot("BTC/USDC") == 10000
    assert resolver.resolve_spot("BTC/USDT") == 10001
    assert resolver.resolve_spot("BTC") == 10000


def test_a_non_canonical_pair_name_gets_no_alias_and_does_not_crash():
    """Hyperliquid lists non-canonical pairs as `@107`; there is no base to alias."""
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe({"universe": [{"name": "@107", "index": 5}]})
    assert resolver.resolve_spot("@107") == 10005
    with pytest.raises(AssetResolutionError):
        resolver.resolve_spot("BTC")


def test_a_non_usdc_pair_gets_no_bare_alias():
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe({"universe": [{"name": "BTC/USDT", "index": 0}]})
    with pytest.raises(AssetResolutionError):
        resolver.resolve_spot("BTC")


def test_duplicate_spot_names_are_rejected_wholesale():
    with pytest.raises(ValueError):
        AssetResolver(universe=PERP_UNIVERSE).load_spot_universe(
            {"universe": [{"name": "BTC/USDC", "index": 0},
                          {"name": "BTC/USDC", "index": 1}]})


def test_an_empty_spot_universe_is_rejected():
    for bad in ([], None, {}, "nope"):
        with pytest.raises(ValueError):
            AssetResolver(universe=PERP_UNIVERSE).load_spot_universe(bad)


def test_loading_spot_does_not_disturb_the_perp_map():
    """Two maps, independently valid. Neither load may corrupt the other."""
    resolver = _resolver()
    assert resolver.resolve("BTC") == 0
    assert resolver.resolve("ETH") == 1
    assert resolver.names() == ["BTC", "ETH", "SOL"]


def test_a_failed_spot_load_leaves_the_previous_spot_map_intact():
    resolver = _resolver()
    with pytest.raises(ValueError):
        resolver.load_spot_universe({"universe": [{"name": "X/USDC"},
                                                  {"name": "X/USDC"}]})
    assert resolver.resolve_spot("BTC") == 10002


# ------------------------------------------------------------------ refresh

def test_a_failed_spot_refresh_keeps_the_old_map():
    """A network blip must not become a trading halt - same rule as perp."""
    class _Down:
        def get_spot_meta(self):
            raise ConnectionError("down")

    resolver = _resolver()
    assert resolver.refresh_spot_universe(rest_client=_Down()) is False
    assert resolver.resolve_spot("BTC") == 10002


def test_a_successful_spot_refresh_replaces_the_map():
    class _Client:
        def get_spot_meta(self):
            return {"universe": [{"name": "NEW/USDC", "index": 0}]}

    resolver = _resolver()
    assert resolver.refresh_spot_universe(rest_client=_Client()) is True
    assert resolver.resolve_spot("NEW") == 10000


def test_a_malformed_spot_response_keeps_the_old_map():
    class _Junk:
        def get_spot_meta(self):
            return {"universe": [{"no_name": True}]}

    resolver = _resolver()
    assert resolver.refresh_spot_universe(rest_client=_Junk()) is False
    assert resolver.resolve_spot("BTC") == 10002


def test_describe_reports_the_spot_map():
    described = _resolver().describe()
    assert described["spot_loaded"] is True
    assert described["spot_pairs"] == 4


# ============================================================================
# Round 25: the shape the LIVE endpoint actually returns.
#
# Antigravity queried mainnet /info {"type":"spotMeta"}: of 326 pairs, exactly
# one - PURR/USDC - is `isCanonical` and readably named. Every other entry is
# named "@1".."@142" and identifies its market through `tokens: [base, quote]`
# indexing the sibling `tokens` array.
#
# The first version of load_spot_universe parsed the NAME for a "/", so on live
# data it indexed one pair out of 326. UBTC, HYPE and every real market were
# unreachable - the resolver would have refused every spot order rather than
# placing a wrong one, so it failed safe, but it failed.
# ============================================================================

LIVE_SPOT_META = {
    "tokens": [
        {"name": "USDC", "index": 0, "szDecimals": 8},
        {"name": "PURR", "index": 1, "szDecimals": 0},
        {"name": "HYPE", "index": 150, "szDecimals": 2},
        {"name": "UBTC", "index": 197, "szDecimals": 5},
        {"name": "UETH", "index": 221, "szDecimals": 4},
    ],
    "universe": [
        {"name": "PURR/USDC", "tokens": [1, 0], "index": 0, "isCanonical": True},
        {"name": "@107", "tokens": [150, 0], "index": 107, "isCanonical": False},
        {"name": "@142", "tokens": [197, 0], "index": 142, "isCanonical": False},
        {"name": "@151", "tokens": [221, 0], "index": 151, "isCanonical": False},
    ],
}


def _live():
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe(LIVE_SPOT_META)
    return resolver


def test_the_one_canonical_pair_still_resolves_by_name():
    assert _live().resolve_spot("PURR/USDC") == 10000


def test_an_at_name_resolves_by_its_raw_name():
    assert _live().resolve_spot("@142") == 10142


def test_an_at_name_also_resolves_by_its_token_pair():
    """`@142` says nothing; `tokens: [197, 0]` says UBTC/USDC."""
    assert _live().resolve_spot("UBTC/USDC") == 10142


def test_the_base_token_of_an_at_pair_resolves():
    resolver = _live()
    assert resolver.resolve_spot("UBTC") == 10142
    assert resolver.resolve_spot("HYPE") == 10107


def test_spot_bitcoin_is_reachable_as_BTC():
    """
    The trade that motivates all of this: the perp is BTC, the spot leg is UBTC,
    and `open_basis_pair` asks for "BTC-SPOT".
    """
    resolver = _live()
    assert resolver.resolve_spot("BTC") == 10142
    assert resolver.resolve_spot("BTC-SPOT") == 10142
    assert resolver.resolve("BTC") == 0          # perp index, untouched


def test_the_bridged_alias_covers_eth_too():
    assert _live().resolve_spot("ETH") == 10151


def test_a_bridged_alias_never_overrides_a_real_listing():
    """If BTC is itself listed, the real pair wins and UBTC does not shadow it."""
    meta = {
        "tokens": [{"name": "USDC", "index": 0}, {"name": "BTC", "index": 5},
                   {"name": "UBTC", "index": 197}],
        "universe": [{"name": "@10", "tokens": [5, 0], "index": 10},
                     {"name": "@142", "tokens": [197, 0], "index": 142}],
    }
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe(meta)
    assert resolver.resolve_spot("BTC") == 10010        # the real BTC pair
    assert resolver.resolve_spot("UBTC") == 10142


def test_an_unlisted_bridged_alias_is_not_invented():
    resolver = _live()
    with pytest.raises(AssetResolutionError):
        resolver.resolve_spot("SOL")        # no USOL in this fixture


def test_the_pair_count_counts_markets_not_spellings():
    """Aliases live in the index; `spot_pairs` stays the number of real markets."""
    assert _live().describe()["spot_pairs"] == 4


def test_every_live_pair_gets_a_distinct_asset_id():
    resolver = _live()
    ids = {resolver.resolve_spot(name)
           for name in ("PURR/USDC", "HYPE", "UBTC", "UETH")}
    assert len(ids) == 4


def test_a_pair_whose_tokens_are_unknown_still_resolves_by_raw_name():
    """A token index we cannot look up must not lose the market entirely."""
    meta = {"tokens": [{"name": "USDC", "index": 0}],
            "universe": [{"name": "@99", "tokens": [4242, 0], "index": 99}]}
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe(meta)
    assert resolver.resolve_spot("@99") == 10099


def test_a_spotMeta_with_no_tokens_array_still_loads():
    """Older/partial payloads fall back to parsing the name."""
    resolver = AssetResolver(universe=PERP_UNIVERSE)
    resolver.load_spot_universe({"universe": [{"name": "BTC/USDC", "index": 3}]})
    assert resolver.resolve_spot("BTC") == 10003
