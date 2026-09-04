"""
================================================================================
HL Monarch: Asset Index Resolver
================================================================================
Maps a coin name to the integer index Hyperliquid uses in a signed order.

WHY THIS IS ITS OWN MODULE. The index is what a signed action actually names -
`{"a": 0, ...}` is the asset, not the string "BTC". If the mapping is wrong the
signature is perfectly valid and the order lands on a different market. That is
the worst failure available in the execution path, and it is silent: nothing
errors, the fill just arrives on the wrong book.

Three defences, in order of how much they save you:

  1. AN UNKNOWN COIN RAISES. Never a default, never a 0. A missing entry means
     "we do not know", and guessing turns that into a real order somewhere.
  2. A STALE MAPPING EXPIRES. Hyperliquid's universe changes as listings are
     added, and an index learned an hour ago may not mean the same thing now.
     Past `max_age_seconds` the resolver refuses rather than serving a number it
     can no longer vouch for.
  3. THE UNIVERSE IS VALIDATED ON LOAD, ALL OR NOTHING. A payload missing
     `universe`, or carrying duplicate names, is rejected whole - a partially
     applied universe is worse than none, because the entries that DID apply look
     authoritative while the rest raise as if simply unlisted.

Offline by construction: this class never fetches anything. A caller hands it a
`meta` payload - from the API, a fixture, or the bundled fallback - and it only
parses. That keeps the execution path testable with no network, and makes a
refresh an explicit act rather than a hidden one.
================================================================================
"""

import time
from typing import Any, Dict, List, Optional

# A small map for offline simulation and tests. Deliberately NOT authoritative:
# `fallback_only=True` has to be asked for, so nothing reaches a live signature
# through it by accident.
OFFLINE_FALLBACK_UNIVERSE: List[Dict[str, Any]] = [
    {"name": "BTC", "szDecimals": 5},
    {"name": "ETH", "szDecimals": 4},
    {"name": "SOL", "szDecimals": 2},
    {"name": "ARB", "szDecimals": 1},
    {"name": "DOGE", "szDecimals": 0},
]

DEFAULT_MAX_AGE_SECONDS = 3600.0

# Hyperliquid addresses spot markets as 10000 + the pair's index in
# `spotMeta.universe`. That index is a DIFFERENT NUMBERING SPACE from the perp
# index in `meta.universe` - BTC's perp index says nothing about where BTC/USDC
# sits in the spot pair list. Adding this offset to a perp index produces a
# perfectly valid asset id for an unrelated market.
SPOT_ASSET_ID_OFFSET = 10000

# HyperUnit bridges major assets onto Hyperliquid spot under a "U" ticker, while
# the PERP keeps the plain name. A basis pair hedging the BTC perp trades UBTC on
# the spot leg, so "BTC-SPOT" has to find it. Explicit and closed - a general
# "strip the U" rule would map UNI to NI.
UNIT_BRIDGED_ALIASES = {"UBTC": "BTC", "UETH": "ETH", "USOL": "SOL"}


class AssetResolutionError(KeyError):
    """
    A coin could not be resolved to an index that can be vouched for.

    A KeyError subclass so existing `except KeyError` handling in the executor
    keeps working, but its own type so a caller can tell this from any other
    lookup failure.
    """


class StaleUniverseError(AssetResolutionError):
    """The mapping is older than `max_age_seconds` and was not refreshed."""


class AssetResolver:
    """Coin name -> asset index, with an age bound. Raises rather than guessing."""

    def __init__(self, universe: Optional[List[Dict[str, Any]]] = None,
                 max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
                 fallback_only: bool = False,
                 loaded_at: Optional[float] = None):
        self.max_age_seconds = float(max_age_seconds)
        self._index: Dict[str, int] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}
        self.loaded_at: Optional[float] = None
        self.source = "empty"
        # Spot is kept in a SEPARATE map on purpose - see SPOT_ASSET_ID_OFFSET.
        # Empty until a spotMeta payload is loaded, and `resolve_spot` raises
        # while it is empty rather than deriving an id from the perp index.
        self._spot_index: Dict[str, int] = {}
        self._spot_meta: Dict[str, Dict[str, Any]] = {}
        self.spot_loaded_at: Optional[float] = None
        self.spot_source = "empty"

        if universe is not None:
            self.load_universe(universe, loaded_at=loaded_at, source="provided")
        elif fallback_only:
            self.load_universe(OFFLINE_FALLBACK_UNIVERSE, loaded_at=loaded_at,
                               source="offline-fallback")

    # -- loading ------------------------------------------------------------

    def load_universe(self, universe: Any, loaded_at: Optional[float] = None,
                      source: str = "provided") -> int:
        """
        Replaces the mapping. Returns how many assets loaded.

        The index is POSITION in the universe array, which is how Hyperliquid
        assigns it. That is why order matters, and why a truncated response must
        not be accepted: every index past the truncation point would be right by
        accident or wrong in silence.
        """
        if isinstance(universe, dict):
            universe = universe.get("universe")
        if not isinstance(universe, list) or not universe:
            raise ValueError("universe must be a non-empty list of asset entries")

        index: Dict[str, int] = {}
        meta: Dict[str, Dict[str, Any]] = {}
        for position, entry in enumerate(universe):
            if not isinstance(entry, dict):
                raise ValueError(f"universe entry {position} is not an object")
            name = str(entry.get("name") or "").strip()
            if not name:
                raise ValueError(f"universe entry {position} has no name")
            key = name.upper()
            if key in index:
                # Two entries claiming one name means we cannot say which index
                # the coin refers to. Refusing beats picking one.
                raise ValueError(f"universe contains duplicate name {name!r}; "
                                 f"cannot resolve it unambiguously")
            index[key] = position
            meta[key] = dict(entry)

        self._index = index
        self._meta = meta
        self.loaded_at = float(loaded_at if loaded_at is not None else time.time())
        self.source = source
        return len(index)

    # -- state --------------------------------------------------------------

    @property
    def loaded(self) -> bool:
        return bool(self._index)

    @property
    def age_seconds(self) -> Optional[float]:
        return None if self.loaded_at is None else max(0.0, time.time() - self.loaded_at)

    @property
    def is_stale(self) -> bool:
        age = self.age_seconds
        if age is None:
            return True
        return self.max_age_seconds > 0 and age > self.max_age_seconds

    def names(self) -> List[str]:
        return sorted(self._index)

    # -- resolution ---------------------------------------------------------

    def resolve(self, coin: str, allow_stale: bool = False) -> int:
        """
        Coin name -> asset index. Raises rather than guessing, ever.

        `allow_stale` exists for analytics and backtests, which want the mapping
        without the freshness guarantee. An EXECUTION path must never pass it: a
        signed order names an index, and an index nobody can vouch for names an
        unknown market.
        """
        key = str(coin or "").strip().upper()
        if not key:
            raise AssetResolutionError("no coin given")
        if not self.loaded:
            raise AssetResolutionError(
                f"no asset universe loaded; cannot resolve {key!r}. Call "
                f"load_universe() with a meta payload, or construct with "
                f"fallback_only=True for offline work.")
        if self.is_stale and not allow_stale:
            raise StaleUniverseError(
                f"asset universe is {self.age_seconds:.0f}s old (limit "
                f"{self.max_age_seconds:.0f}s) and may no longer match the "
                f"exchange. Refusing to resolve {key!r}: a stale index signs a "
                f"valid order on whatever market now holds it. Refresh first.")
        if key not in self._index:
            raise AssetResolutionError(
                f"{key!r} is not in the loaded universe ({len(self._index)} assets). "
                f"Refusing to guess an index - a wrong one places a real order on "
                f"the wrong market.")
        return self._index[key]

    # -- refresh ------------------------------------------------------------

    def refresh_universe(self, rest_client: Any = None,
                         fetch: Optional[Any] = None) -> bool:
        """
        Re-reads the asset universe from `/info {"type": "meta"}`. Returns success.

        A FAILED REFRESH KEEPS THE OLD MAPPING. Clearing it on a network blip
        would turn a transient outage into a total trading halt, and - worse - a
        caller that then re-loaded from the offline fallback would be signing
        against a hard-coded map that has no relationship to the live exchange.
        Keeping the previous universe and letting it AGE OUT is the honest
        failure: it still blocks orders once stale, but only after the staleness
        bound says it should.

        The client is duck-typed rather than imported, so this module still has
        no network dependency of its own and every test stays offline. Any of
        `fetch()`, `client.get_meta()`, `client.get_meta_and_asset_ctxs()` or
        `client._post({"type": "meta"})` will do.
        """
        try:
            payload = self._fetch_meta(rest_client, fetch)
        except Exception as exc:
            print(f"[WARN] Asset universe refresh failed ({type(exc).__name__}: {exc}). "
                  f"KEEPING the previous mapping - it will age out on its own rather "
                  f"than being cleared, so a network blip does not become a halt.")
            return False

        if not payload:
            print("[WARN] Asset universe refresh returned nothing; keeping the previous "
                  "mapping.")
            return False

        try:
            # Validation happens BEFORE the swap, and load_universe is
            # all-or-nothing, so a malformed response cannot half-apply.
            self.load_universe(payload, source="live")
            return True
        except ValueError as exc:
            print(f"[WARN] Asset universe response was malformed ({exc}); keeping the "
                  f"previous mapping.")
            return False

    @staticmethod
    def _fetch_meta(rest_client: Any = None, fetch: Optional[Any] = None) -> Any:
        """Whatever the caller has, in order of directness."""
        if fetch is not None:
            return fetch()
        if rest_client is None:
            raise ValueError("no rest_client or fetch callable given")
        if hasattr(rest_client, "get_meta"):
            return rest_client.get_meta()
        if hasattr(rest_client, "get_meta_and_asset_ctxs"):
            # Returns [meta, assetCtxs]; only the meta half carries the universe.
            response = rest_client.get_meta_and_asset_ctxs()
            return response[0] if isinstance(response, (list, tuple)) and response else response
        if hasattr(rest_client, "_post"):
            return rest_client._post({"type": "meta"})
        raise AttributeError(f"{type(rest_client).__name__} exposes no way to fetch meta")

    # -- spot ---------------------------------------------------------------

    def load_spot_universe(self, payload: Any, loaded_at: Optional[float] = None,
                           source: str = "provided") -> int:
        """
        Loads `spotMeta` and maps pair names to SPOT asset ids. Returns the count.

        The id is `SPOT_ASSET_ID_OFFSET + index`, where `index` is the pair's own
        index in `spotMeta.universe` - a numbering space unrelated to the perp
        universe. The explicit `index` field is preferred over position because it
        is what the exchange itself asserts.

        LIVE NAMES ARE NOT PAIR NAMES. Of the 326 pairs the mainnet endpoint
        returns, exactly one - PURR/USDC - is `isCanonical` and carries a
        readable name. Every other entry is named `@1`, `@2`, ... `@142`, and the
        tradeable pair is described instead by `tokens: [base_index, quote_index]`
        indexing the sibling `tokens` array. Parsing the NAME for a "/" therefore
        indexed almost nothing on live data: the first version of this method
        would have failed to find UBTC, HYPE, or any real market.

        So each pair is registered under every name that can identify it:
          * its raw name             `@142`
          * its resolved token pair  `UBTC/USDC`
          * its base token, if the quote is USDC   `UBTC`
        plus the bridged-asset aliases below.
        """
        tokens_raw = payload.get("tokens") if isinstance(payload, dict) else None
        universe = payload.get("universe") if isinstance(payload, dict) else payload
        if not isinstance(universe, list) or not universe:
            raise ValueError("spot universe must be a non-empty list of pair entries")

        # token index -> token name, for turning `tokens: [1, 0]` into "PURR/USDC".
        token_map: Dict[int, str] = {}
        if isinstance(tokens_raw, list):
            for position, token in enumerate(tokens_raw):
                if not isinstance(token, dict):
                    continue
                name = str(token.get("name") or "").strip().upper()
                if not name:
                    continue
                raw = token.get("index")
                token_map[int(raw) if raw is not None else position] = name

        index: Dict[str, int] = {}
        meta: Dict[str, Dict[str, Any]] = {}
        alias_counts: Dict[str, int] = {}
        aliases: Dict[str, int] = {}
        base_tokens: set = set()

        for position, entry in enumerate(universe):
            if not isinstance(entry, dict):
                raise ValueError(f"spot universe entry {position} is not an object")
            name = str(entry.get("name") or "").strip()
            if not name:
                raise ValueError(f"spot universe entry {position} has no name")
            key = name.upper()
            if key in index:
                raise ValueError(f"spot universe contains duplicate name {name!r}; "
                                 f"cannot resolve it unambiguously")
            raw_index = entry.get("index")
            pair_index = int(raw_index) if raw_index is not None else position
            asset_id = SPOT_ASSET_ID_OFFSET + pair_index
            index[key] = asset_id
            meta[key] = dict(entry)

            # Prefer the token pair over the name: `@142` says nothing, but
            # `tokens: [n, 0]` says UBTC/USDC.
            base = quote = ""
            pair = entry.get("tokens")
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                try:
                    base = token_map.get(int(pair[0]), "")
                    quote = token_map.get(int(pair[1]), "")
                except (TypeError, ValueError):
                    base = quote = ""
            if not base or not quote:
                base, _, quote = key.partition("/")

            if base and quote:
                pair_name = f"{base}/{quote}"
                if pair_name != key and pair_name not in index:
                    # Aliases live in `index` only. `meta` stays one entry per
                    # real pair so `spot_pairs` counts markets, not spellings.
                    index[pair_name] = asset_id
                if quote == "USDC":
                    base_tokens.add(base)
                    alias_counts[base] = alias_counts.get(base, 0) + 1
                    aliases[base] = asset_id

        for alias, count in alias_counts.items():
            # An alias is a convenience. One that could mean two markets is not.
            if count == 1 and alias not in index:
                index[alias] = aliases[alias]

        # BRIDGED ASSETS TRADE UNDER A PREFIXED TICKER. Spot Bitcoin on
        # Hyperliquid is UBTC (Unit Bitcoin), while the PERP is plain BTC - so a
        # basis pair asking for "BTC-SPOT" means UBTC and would otherwise resolve
        # to nothing. Only a fixed, known set is aliased, and only when the bare
        # ticker is not itself a listed token: guessing that any `U<X>` means
        # `<X>` would silently turn UNI into NI.
        for bridged, bare in UNIT_BRIDGED_ALIASES.items():
            if bridged in index and bare not in index and bare not in base_tokens:
                index[bare] = index[bridged]

        self._spot_index = index
        self._spot_meta = meta
        self.spot_loaded_at = float(loaded_at if loaded_at is not None else time.time())
        self.spot_source = source
        return len(meta)

    @property
    def spot_loaded(self) -> bool:
        return bool(self._spot_index)

    @property
    def spot_age_seconds(self) -> Optional[float]:
        if self.spot_loaded_at is None:
            return None
        return max(0.0, time.time() - self.spot_loaded_at)

    @property
    def spot_is_stale(self) -> bool:
        age = self.spot_age_seconds
        if age is None:
            return True
        return self.max_age_seconds > 0 and age > self.max_age_seconds

    def resolve_spot(self, coin: str, allow_stale: bool = False) -> int:
        """
        Spot pair name -> spot asset id. Raises rather than deriving one.

        There is deliberately NO fallback to `resolve() + SPOT_ASSET_ID_OFFSET`.
        That arithmetic is valid-looking and wrong: it lands on whichever pair
        happens to occupy the perp's slot in the spot list, and the resulting
        order is signed, accepted and filled on the wrong market in silence.
        Refusing to trade spot until a spotMeta payload is loaded is the only
        safe reading of "we do not know".
        """
        key = str(coin or "").strip().upper()
        if key.endswith("-SPOT"):
            key = key[:-5]
        if not key:
            raise AssetResolutionError("no coin given")
        if not self.spot_loaded:
            raise AssetResolutionError(
                f"no SPOT universe loaded; cannot resolve {key!r}. The perp "
                f"universe cannot answer this - spot ids are "
                f"{SPOT_ASSET_ID_OFFSET} + the pair's index in spotMeta.universe, "
                f"which is a different numbering space. Call "
                f"load_spot_universe() with a spotMeta payload.")
        if self.spot_is_stale and not allow_stale:
            raise StaleUniverseError(
                f"spot universe is {self.spot_age_seconds:.0f}s old (limit "
                f"{self.max_age_seconds:.0f}s). Refusing to resolve {key!r}: a "
                f"stale index signs a valid order on whatever pair now holds it.")
        if key not in self._spot_index:
            raise AssetResolutionError(
                f"{key!r} is not in the loaded spot universe "
                f"({len(self._spot_meta)} pairs). Refusing to guess an index - a "
                f"wrong one places a real order on the wrong market.")
        return self._spot_index[key]

    def refresh_spot_universe(self, rest_client: Any = None,
                              fetch: Optional[Any] = None) -> bool:
        """`refresh_universe`, for spot. Same keep-the-old-map-on-failure rule."""
        try:
            payload = self._fetch_spot_meta(rest_client, fetch)
        except Exception as exc:
            print(f"[WARN] Spot universe refresh failed ({type(exc).__name__}: {exc}). "
                  f"KEEPING the previous mapping; it will age out on its own.")
            return False
        if not payload:
            print("[WARN] Spot universe refresh returned nothing; keeping the previous "
                  "mapping.")
            return False
        try:
            self.load_spot_universe(payload, source="live")
            return True
        except ValueError as exc:
            print(f"[WARN] Spot universe response was malformed ({exc}); keeping the "
                  f"previous mapping.")
            return False

    @staticmethod
    def _fetch_spot_meta(rest_client: Any = None, fetch: Optional[Any] = None) -> Any:
        if fetch is not None:
            return fetch()
        if rest_client is None:
            raise ValueError("no rest_client or fetch callable given")
        if hasattr(rest_client, "get_spot_meta"):
            return rest_client.get_spot_meta()
        if hasattr(rest_client, "_post"):
            return rest_client._post({"type": "spotMeta"})
        raise AttributeError(f"{type(rest_client).__name__} exposes no way to fetch "
                             f"spotMeta")

    def size_decimals(self, coin: str) -> Optional[int]:
        """`szDecimals` for a coin, used to round a size to a valid increment."""
        entry = self._meta.get(str(coin or "").strip().upper())
        return None if entry is None else entry.get("szDecimals")

    def as_dict(self, allow_stale: bool = True) -> Dict[str, int]:
        """The whole mapping, for a caller that wants to hold it directly."""
        if self.is_stale and not allow_stale:
            raise StaleUniverseError("universe is stale")
        return dict(self._index)

    def describe(self) -> Dict[str, Any]:
        return {
            "loaded": self.loaded,
            "assets": len(self._index),
            "source": self.source,
            "age_seconds": self.age_seconds,
            "is_stale": self.is_stale,
            "max_age_seconds": self.max_age_seconds,
            "spot_loaded": self.spot_loaded,
            "spot_pairs": len(self._spot_meta),
            "spot_source": self.spot_source,
            "spot_is_stale": self.spot_is_stale,
        }
