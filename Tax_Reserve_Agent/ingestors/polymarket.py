"""
Polymarket Ingestor.
Fetches and normalizes Polymarket CTF contract events, CLOB trade fills, and resolution redemptions.

Two layers live here:
  * `PolymarketIngestor` - the convenience REST/manual path (unchanged).
  * `PolymarketChainIngestor` and friends - settlement-layer ingestion straight
    from Gnosis Conditional Tokens logs on Polygon plus the CLOB order-fill
    subgraph. See the section banner below for the cost-basis conventions.
"""
import json
import time
import urllib.request
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path

from .keccak import keccak256, event_topic

class PolymarketIngestor:
    def __init__(self, wallet_addresses: Optional[List[str]] = None):
        self.wallets = wallet_addresses or []
        self.data_api_base = "https://data-api.polymarket.com"

    def fetch_trades_for_wallet(self, wallet_address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches trade history from Polymarket's public data API for a given wallet.
        """
        url = f"{self.data_api_base}/trades?user={wallet_address.lower()}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TaxReserveAgent/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    raw_data = json.loads(response.read().decode())
                    return self._normalize_polymarket_trades(raw_data)
        except Exception as e:
            print(f"[INFO] Polymarket public API query for {wallet_address[:8]}...: {e}")
            return []
        return []

    def _normalize_polymarket_trades(self, raw_trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for t in raw_trades:
            # Polymarket trade payload normalization
            timestamp_raw = t.get("timestamp") or t.get("created_at") or datetime.utcnow().isoformat()
            if isinstance(timestamp_raw, (int, float)):
                ts = datetime.utcfromtimestamp(timestamp_raw).isoformat()
            else:
                ts = str(timestamp_raw)

            side = t.get("side", "BUY").upper()
            size = float(t.get("size", 0.0) or t.get("amount", 0.0))
            price = float(t.get("price", 0.0))
            fee = float(t.get("fee", 0.0))
            symbol = t.get("title") or t.get("market") or t.get("asset_id") or "POLYMARKET_POSITION"
            tx_hash = t.get("transactionHash") or t.get("id") or f"poly_{ts}_{size}_{price}"

            normalized.append({
                "source": "polymarket",
                "tx_hash": tx_hash,
                "timestamp": ts,
                "asset_class": "prediction_market",
                "symbol": str(symbol),
                "side": side,
                "quantity": size,
                "price": price,
                "fee": fee,
                "total_value": size * price,
                "notes": f"Polymarket CLOB Fill: {t.get('outcome', '')}"
            })
        return normalized

    @staticmethod
    def create_redemption_trade(symbol: str, quantity: float, timestamp: str, fee: float = 0.0, tx_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a $1.00 payout redemption record for winning prediction shares.
        """
        return {
            "source": "polymarket",
            "tx_hash": tx_hash or f"redeem_{symbol}_{timestamp}",
            "timestamp": timestamp,
            "asset_class": "prediction_market",
            "symbol": symbol,
            "side": "REDEEM",
            "quantity": float(quantity),
            "price": 1.00,  # Winning shares redeem at $1.00
            "fee": float(fee),
            "total_value": float(quantity) * 1.00,
            "notes": "Market resolution payout redemption at $1.00"
        }

    @staticmethod
    def create_manual_trade(symbol: str, side: str, quantity: float, price: float, timestamp: str,
                            fee: float = 0.0, strategy: Optional[str] = None) -> Dict[str, Any]:
        """`strategy` is stamped into `notes` for per-strategy exposure accounting."""
        from ..interfaces.monarch_hook import tag_strategy
        return tag_strategy({
            "source": "polymarket",
            "tx_hash": f"manual_poly_{timestamp}_{symbol}_{side}",
            "timestamp": timestamp,
            "asset_class": "prediction_market",
            "symbol": symbol,
            "side": side.upper(),
            "quantity": float(quantity),
            "price": float(price),
            "fee": float(fee),
            "total_value": float(quantity) * float(price),
            "notes": "Manual Polymarket entry"
        }, strategy)


# ============================================================================
# ON-CHAIN GNOSIS CTF INGESTION (Polygon RPC + GraphQL subgraph)
# ============================================================================
#
# Everything below reads Polymarket's real settlement layer instead of the
# convenience REST API, so a wallet's tax history survives the data API changing
# shape, rate-limiting, or truncating old fills.
#
# WHAT AN "OUTCOME SHARE" COSTS - the two basis conventions used here, stated up
# front because they are accounting choices, not facts, and a CPA may prefer
# different ones:
#
#   1. SPLIT (PositionSplit): $1 of USDC is locked and becomes one share of EVERY
#      outcome in the partition. The $1 basis is split EQUALLY across the legs
#      ($0.50 / $0.50 on a binary market). The alternative - allocating by market
#      price at split time - needs a price oracle for a moment that may have no
#      trade at all, so it is not deterministic and is not used here. Override
#      with `basis_allocation=` if a different split is wanted.
#   2. MERGE (PositionsMerge): the exact inverse. One share of every leg is
#      burned and $1 comes back, booked as proceeds against each leg using the
#      SAME allocation. Split-then-merge with no trading in between therefore
#      nets to exactly $0 of gain, which is the correct answer.
#
# A merge is emitted as a SELL rather than a MERGE side deliberately: the FIFO
# engine only closes lots for a known set of sides, so a "MERGE" side would be
# written to `transactions` and then silently skipped by the lot matcher - an
# invisible hole in the cost basis. SELL closes the lot; provenance is preserved
# in `notes` and in the on-chain `tx_hash`.

CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"      # ConditionalTokens (Polygon)
NEG_RISK_ADAPTER_ADDRESS = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"  # NegRiskAdapter (Polygon)
USDC_DECIMALS = 6
COLLATERAL_UNIT = 10 ** USDC_DECIMALS

# Public Polygon RPCs, tried in order. A LIST rather than a single URL because
# the previous single default (https://polygon-rpc.com) started answering 401
# Unauthorized and took the whole on-chain sync down with it - the failure a
# hardcoded endpoint eventually always produces. Probed live 2026-09-02:
#   polygon-bor-rpc.publicnode.com   200, ~46ms   <- default
#   1rpc.io/matic                    200, ~165ms
#   polygon.drpc.org                 200, ~79ms
#   polygon-rpc.com                  401 Unauthorized
#   rpc.ankr.com/polygon             200 body carrying a JSON-RPC auth error
#   polygon.llamarpc.com             DNS failure (does not resolve)
# Note ankr: an HTTP 200 whose BODY is an error is why `call()` inspects the
# payload rather than trusting the status code.
DEFAULT_POLYGON_RPC_ENDPOINTS = (
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon.drpc.org",
    "https://1rpc.io/matic",
)
DEFAULT_POLYGON_RPC = DEFAULT_POLYGON_RPC_ENDPOINTS[0]

# How far behind the chain head a sync must stay. Polygon PoS finalises on
# Heimdall milestones roughly every 16-32 blocks; 64 clears that with room to
# spare. This matters more here than in a typical indexer because the ledger has
# no rollback path: a reorged log that has already been through the FIFO engine
# has minted tax lots and realized_pnl rows that nothing will ever retract, and
# the resulting cost basis is silently wrong forever. Staying behind the horizon
# is the only cheap defence.
REORG_SAFETY_BLOCKS = 64
DEFAULT_ORDERBOOK_SUBGRAPH = (
    "https://api.goldsky.com/api/public/"
    "project_cl6mb8i9h0003e201j6li0dii/subgraphs/orderbook-subgraph/prod/gn"
)
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

# topic0 hashes are DERIVED from the canonical signatures (see keccak.py), never
# pasted, so a typo cannot silently turn a sync into "0 logs found".
CTF_EVENT_SIGNATURES = {
    "PositionSplit": "PositionSplit(address,address,bytes32,bytes32,uint256[],uint256)",
    "PositionsMerge": "PositionsMerge(address,address,bytes32,bytes32,uint256[],uint256)",
    "PayoutRedemption": "PayoutRedemption(address,address,bytes32,bytes32,uint256[],uint256)",
}
CTF_TOPICS = {name: event_topic(sig) for name, sig in CTF_EVENT_SIGNATURES.items()}
CTF_TOPIC_LOOKUP = {topic: name for name, topic in CTF_TOPICS.items()}


class CTFDecodeError(ValueError):
    """Raised when a log does not match the CTF ABI layout its topic0 claims."""


def _hex_to_int(value: Any) -> int:
    """Tolerates ints, '0x..' strings and bare decimal strings from mixed RPC providers."""
    if isinstance(value, int):
        return value
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    return int(text, 16) if text.lower().startswith("0x") else int(text)


def _topic_to_address(topic: str) -> str:
    """Left-padded 32-byte topic -> lowercase 20-byte hex address."""
    clean = str(topic)
    clean = clean[2:] if clean.startswith("0x") else clean
    return "0x" + clean[-40:].lower()


def _split_words(data_hex: str) -> List[str]:
    """ABI data blob -> list of 32-byte words as hex strings (no 0x prefix)."""
    clean = data_hex[2:] if str(data_hex).startswith("0x") else str(data_hex)
    if len(clean) % 64 != 0:
        raise CTFDecodeError(f"ABI data is not a whole number of 32-byte words (len={len(clean)})")
    return [clean[i:i + 64] for i in range(0, len(clean), 64)]


def _decode_uint_array(words: List[str], byte_offset: int) -> List[int]:
    """Reads a dynamic uint256[] whose tail starts at `byte_offset` bytes into the data blob."""
    head_index = byte_offset // 32
    if head_index >= len(words):
        raise CTFDecodeError(f"uint256[] offset {byte_offset} points past the end of the log data")
    length = int(words[head_index], 16)
    if head_index + 1 + length > len(words):
        raise CTFDecodeError(f"uint256[] claims {length} elements but the data blob is too short")
    return [int(words[head_index + 1 + i], 16) for i in range(length)]


def index_set_to_outcomes(index_set: int) -> List[int]:
    """Bitmask -> the outcome slot indices it covers. 1 -> [0], 2 -> [1], 3 -> [0, 1]."""
    outcomes = []
    bit = 0
    while (1 << bit) <= index_set:
        if index_set & (1 << bit):
            outcomes.append(bit)
        bit += 1
    return outcomes


class CTFEventDecoder:
    """
    Pure ABI decoder for the three Gnosis ConditionalTokens lifecycle events.

    No network and no state, so it is unit-testable against recorded log fixtures
    and produces byte-identical output on every run.

    Indexed / non-indexed layouts (from the ConditionalTokens source):
      PositionSplit / PositionsMerge
        topics: [sig, stakeholder, parentCollectionId, conditionId]
        data:   [collateralToken, offset(partition), amount, <partition tail>]
      PayoutRedemption
        topics: [sig, redeemer, collateralToken, parentCollectionId]
        data:   [conditionId, offset(indexSets), payout, <indexSets tail>]
    """

    @staticmethod
    def decode_log(log: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        topics = log.get("topics") or []
        if not topics:
            return None
        event_name = CTF_TOPIC_LOOKUP.get(str(topics[0]).lower())
        if event_name is None:
            return None
        if len(topics) < 4:
            raise CTFDecodeError(f"{event_name} log has {len(topics)} topics, expected 4")

        words = _split_words(log.get("data", "0x"))
        if len(words) < 3:
            raise CTFDecodeError(f"{event_name} log data has {len(words)} words, expected at least 3")

        decoded = {
            "event": event_name,
            "tx_hash": str(log.get("transactionHash", "")).lower(),
            "log_index": _hex_to_int(log.get("logIndex", 0)),
            "block_number": _hex_to_int(log.get("blockNumber", 0)),
            "address": str(log.get("address", "")).lower(),
        }

        if event_name in ("PositionSplit", "PositionsMerge"):
            decoded.update({
                "stakeholder": _topic_to_address(topics[1]),
                "parent_collection_id": "0x" + str(topics[2])[-64:],
                "condition_id": "0x" + str(topics[3])[-64:],
                "collateral_token": "0x" + words[0][-40:],
                "index_sets": _decode_uint_array(words, int(words[1], 16)),
                "amount": int(words[2], 16),
            })
        else:  # PayoutRedemption
            decoded.update({
                "stakeholder": _topic_to_address(topics[1]),
                "collateral_token": _topic_to_address(topics[2]),
                "parent_collection_id": "0x" + str(topics[3])[-64:],
                "condition_id": "0x" + words[0],
                "index_sets": _decode_uint_array(words, int(words[1], 16)),
                "payout": int(words[2], 16),
            })
        return decoded

    @staticmethod
    def decode_logs(logs: List[Dict[str, Any]], strict: bool = False) -> List[Dict[str, Any]]:
        """Decodes a batch, skipping unrecognised logs. `strict=True` re-raises decode errors."""
        decoded = []
        for log in logs:
            try:
                event = CTFEventDecoder.decode_log(log)
            except CTFDecodeError as e:
                if strict:
                    raise
                print(f"[WARN] Skipping malformed CTF log {log.get('transactionHash')}: {e}")
                continue
            if event:
                decoded.append(event)
        # Chain order is the only correct FIFO order for same-block activity.
        decoded.sort(key=lambda e: (e["block_number"], e["log_index"]))
        return decoded


# ----------------------------------------------------------------------------
# Transport: Polygon JSON-RPC
# ----------------------------------------------------------------------------

# Function selectors for the ConditionalTokens read methods used to price a
# redemption. Derived, not pasted, for the same reason as the event topics.
_SELECTOR_PAYOUT_NUMERATORS = keccak256(b"payoutNumerators(bytes32,uint256)")[:4].hex()
_SELECTOR_PAYOUT_DENOMINATOR = keccak256(b"payoutDenominator(bytes32)")[:4].hex()
_SELECTOR_OUTCOME_SLOT_COUNT = keccak256(b"getOutcomeSlotCount(bytes32)")[:4].hex()


class RPCError(RuntimeError):
    """A JSON-RPC or transport failure. Always caught at the ingestor boundary."""


class PolygonRPCClient:
    """
    Minimal JSON-RPC client over urllib - no web3 dependency, no API key needed
    for the public endpoints.

    Two things this handles that a naive `eth_getLogs` call does not:
      * Public RPCs cap a log query at ~1k-10k results or a fixed block span and
        answer with an error rather than a truncated list. The range is walked in
        chunks, and a chunk that still errors is halved until it fits.
      * `eth_getBlockByNumber` is called once per DISTINCT block, batched 50 at a
        time, because a wallet's split/merge/redeem logs cluster heavily into the
        same few blocks and the naive version is one round trip per log.
    """

    def __init__(self, rpc_url: Optional[str] = None, timeout: int = 20,
                 max_retries: int = 3, min_interval_s: float = 0.2,
                 endpoints: Optional[List[str]] = None, allow_fallback: bool = True):
        """
        `rpc_url` (or the first of `endpoints`) is tried first; the rest are
        fallbacks. Set `allow_fallback=False` to pin a private node and fail
        rather than silently drift onto a public one.
        """
        configured = list(endpoints) if endpoints else ([rpc_url] if rpc_url else [])
        configured = [u for u in configured if u]
        if allow_fallback:
            configured += [u for u in DEFAULT_POLYGON_RPC_ENDPOINTS if u not in configured]
        self.endpoints = configured or list(DEFAULT_POLYGON_RPC_ENDPOINTS)
        self.rpc_url = self.endpoints[0]
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval_s = min_interval_s
        self._last_call_at = 0.0
        self._request_id = 0
        self._block_ts_cache: Dict[int, str] = {}
        # Learned once per session. Public nodes cap eth_getLogs at an undocumented
        # block span (publicnode rejects anything over 10,000) and only say so by
        # erroring, so the span is discovered by halving. Remembering it stops that
        # rediscovery costing one failed request per topic on every later query.
        self._max_log_span: Optional[int] = None

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_call_at = time.time()

    def _post(self, payload: Any) -> Any:
        """
        Posts to the current endpoint, retrying, then failing over to the next.

        A dead endpoint is not a retryable condition - retrying 401 three times
        just wastes 1.5s before giving the same answer - so the endpoint is
        changed as soon as its retries are exhausted, and the working one is
        pinned for the rest of the session.
        """
        body = json.dumps(payload).encode("utf-8")
        errors: List[str] = []
        start = self.endpoints.index(self.rpc_url) if self.rpc_url in self.endpoints else 0
        ordered = self.endpoints[start:] + self.endpoints[:start]

        for endpoint in ordered:
            last_error: Optional[Exception] = None
            for attempt in range(self.max_retries):
                self._throttle()
                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=body,
                        headers={"Content-Type": "application/json",
                                 "User-Agent": "TaxReserveAgent/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        if endpoint != self.rpc_url:
                            print(f"[INFO] Polygon RPC failed over to {endpoint}")
                            self.rpc_url = endpoint
                        return json.loads(response.read().decode())
                except Exception as e:  # transport-level; RPC-level errors come back as 200s
                    last_error = e
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt))
            errors.append(f"{endpoint}: {last_error}")

        raise RPCError("every Polygon RPC endpoint failed -> " + " | ".join(errors))

    def call(self, method: str, params: List[Any]) -> Any:
        self._request_id += 1
        result = self._post({"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params})
        if isinstance(result, dict) and result.get("error"):
            raise RPCError(f"{method}: {result['error'].get('message', result['error'])}")
        return (result or {}).get("result")

    def block_number(self) -> int:
        return _hex_to_int(self.call("eth_blockNumber", []))

    def finalized_block_number(self) -> Optional[int]:
        """
        The `finalized` tag, or None if this node does not serve it.

        Preferred over head-minus-N when available because it is the chain's own
        statement of irreversibility rather than a guess. Older Bor nodes and some
        third-party RPCs either error or return null for the tag, hence the None.
        """
        try:
            block = self.call("eth_getBlockByNumber", ["finalized", False])
        except RPCError:
            return None
        if not block or block.get("number") is None:
            return None
        return _hex_to_int(block["number"])

    def safe_block_number(self, confirmations: int = REORG_SAFETY_BLOCKS) -> int:
        """
        Highest block a sync may read: the MORE CONSERVATIVE of the node's
        `finalized` tag and head-minus-`confirmations`.

        Taking the minimum, not preferring `finalized`, because public Polygon
        RPCs do not agree on what the tag means. Measured live 2026-09-02 against
        the same chain head:

            polygon-bor-rpc.publicnode.com   finalized = head - 4
            polygon.drpc.org                 finalized = head - 3
            1rpc.io/matic                    finalized = head - 500

        A 3-4 block lag is not Polygon finality - Heimdall milestones run every
        ~16-32 blocks - so those nodes are effectively aliasing the tag near the
        head. Trusting it would have synced to within 4 blocks of the tip and
        quietly voided the whole reorg guard, while 1rpc would have been usefully
        stricter. The minimum keeps the guarantee on both: never nearer the tip
        than `confirmations`, and further back when the node genuinely says so.
        """
        floor = max(0, self.block_number() - max(0, int(confirmations)))
        finalized = self.finalized_block_number()
        if finalized is None:
            return floor
        return max(0, min(finalized, floor))

    def get_logs(self, address: str, topics: List[Any], from_block: int, to_block: int,
                 chunk_size: int = 100_000) -> List[Dict[str, Any]]:
        """Walks [from_block, to_block] in chunks, halving any chunk the RPC rejects."""
        logs: List[Dict[str, Any]] = []
        cursor = from_block
        ceiling = min(chunk_size, self._max_log_span or chunk_size)
        while cursor <= to_block:
            span = min(ceiling, to_block - cursor + 1)
            while True:
                try:
                    logs.extend(self.call("eth_getLogs", [{
                        "address": address,
                        "topics": topics,
                        "fromBlock": hex(cursor),
                        "toBlock": hex(cursor + span - 1),
                    }]) or [])
                    break
                except RPCError as e:
                    if span <= 1:
                        raise
                    span = max(1, span // 2)
                    ceiling = span
                    # Only a REJECTION tells us the node's cap. Recording a
                    # successful span instead would latch onto the last chunk of a
                    # range - often a single block - and make every later query
                    # crawl the chain one block at a time.
                    self._max_log_span = span
                    print(f"[INFO] Narrowing log query to {span} blocks at {cursor} ({e})")
            cursor += span
        return logs

    def get_block_timestamps(self, block_numbers: List[int]) -> Dict[int, str]:
        """Block number -> ISO-8601 UTC timestamp, batched and memoised."""
        wanted = sorted({int(b) for b in block_numbers if int(b) not in self._block_ts_cache})
        for start in range(0, len(wanted), 50):
            batch_blocks = wanted[start:start + 50]
            batch = []
            for block in batch_blocks:
                self._request_id += 1
                batch.append({"jsonrpc": "2.0", "id": self._request_id,
                              "method": "eth_getBlockByNumber", "params": [hex(block), False]})
            responses = self._post(batch)
            if not isinstance(responses, list):
                responses = [responses]
            by_id = {r.get("id"): r for r in responses if isinstance(r, dict)}
            for offset, block in enumerate(batch_blocks):
                entry = by_id.get(batch[offset]["id"]) or {}
                result = entry.get("result") or {}
                if result.get("timestamp") is not None:
                    epoch = _hex_to_int(result["timestamp"])
                    self._block_ts_cache[block] = datetime.fromtimestamp(
                        epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return {b: self._block_ts_cache[b] for b in block_numbers if b in self._block_ts_cache}

    def _read_uint(self, contract: str, selector: str, args_hex: str) -> int:
        raw = self.call("eth_call", [{"to": contract, "data": "0x" + selector + args_hex}, "latest"])
        return _hex_to_int(raw) if raw and raw != "0x" else 0

    def get_payout_ratios(self, condition_id: str, contract: str = CTF_CONTRACT_ADDRESS) -> List[float]:
        """
        Resolved payout per share for each outcome slot, e.g. [0.0, 1.0] for a
        binary market that resolved NO. Empty list if the condition is unresolved
        (denominator 0) or the node refuses the call.
        """
        cid = condition_id[2:] if condition_id.startswith("0x") else condition_id
        cid = cid.rjust(64, "0")
        try:
            denominator = self._read_uint(contract, _SELECTOR_PAYOUT_DENOMINATOR, cid)
            if denominator == 0:
                return []
            slots = self._read_uint(contract, _SELECTOR_OUTCOME_SLOT_COUNT, cid)
            if slots <= 0 or slots > 512:
                return []
            return [
                self._read_uint(contract, _SELECTOR_PAYOUT_NUMERATORS, cid + hex(i)[2:].rjust(64, "0")) / denominator
                for i in range(slots)
            ]
        except RPCError as e:
            print(f"[INFO] Could not read payout ratios for {condition_id[:12]}...: {e}")
            return []


# ----------------------------------------------------------------------------
# Market metadata: conditionId / tokenId -> human-readable symbol
# ----------------------------------------------------------------------------

def canonical_symbol(slug: Optional[str] = None, outcome: Optional[str] = None,
                     condition_id: Optional[str] = None, index_set: Optional[int] = None,
                     token_id: Optional[str] = None) -> str:
    """
    The single symbol authority for every Polymarket code path.

    FIFO matching is keyed on `symbol`, so a CLOB buy and the redemption that
    closes it MUST produce the identical string or the buy is left as an orphan
    open lot and the gain is never realised. Everything - chain events, subgraph
    fills, the REST API, manual entries - funnels through here.

    Falls back to an on-chain-derived identifier when market metadata is
    unavailable (offline, delisted market), which is stable but not pretty.
    """
    if slug and outcome:
        base = f"{slug}-{outcome}".upper()
        return "".join(ch if (ch.isalnum() or ch == "-") else "-" for ch in base).strip("-")
    if condition_id and index_set is not None:
        cid = condition_id[2:] if condition_id.startswith("0x") else condition_id
        return f"CTF-{cid[:10].upper()}-{index_set}"
    if token_id:
        return f"CTF-TOKEN-{str(token_id)[:16]}"
    return "POLYMARKET_POSITION"


class PolymarketMarketResolver:
    """
    Resolves conditionId / CLOB token id to (slug, outcome) via the Gamma API,
    with a JSON disk cache.

    The cache is what keeps re-runs deterministic and offline-repeatable: once a
    market is seen it is never fetched again, so re-importing last year's
    transactions produces identical symbols even after the market is delisted.
    """

    def __init__(self, cache_path: Optional[Path] = None, offline: bool = False):
        self.cache_path = Path(cache_path) if cache_path else (
            Path(__file__).parent.parent / "data" / "cache" / "polymarket_markets.json")
        self.offline = offline
        self._cache: Dict[str, Any] = self._load_cache()
        # Symbols that failed every resolution route this session.
        #
        # DELIBERATELY NOT IN `_cache`, which save() writes to disk. A negative
        # result is almost always transient - a Gamma outage, a rate limit, a
        # network blip - and persisting one would permanently blacklist a
        # perfectly good market, surfacing weeks later as a position that silently
        # refuses to resolve. In memory it costs one wasted lookup per process.
        self._unresolvable: set = set()

    def _load_cache(self) -> Dict[str, Any]:
        try:
            if self.cache_path.exists():
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception as e:
            print(f"[WARN] Market cache unreadable ({e}); starting empty.")
        return {}

    def save(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, sort_keys=True)
        except Exception as e:
            print(f"[WARN] Could not persist market cache: {e}")

    @staticmethod
    def _maybe_json_list(value: Any) -> List[Any]:
        """Gamma returns `outcomes` / `clobTokenIds` as JSON-encoded STRINGS, not arrays."""
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip().startswith("["):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return []

    def _request(self, params: str) -> List[Dict[str, Any]]:
        """One Gamma /markets call. Returns [] on any failure."""
        try:
            req = urllib.request.Request(f"{GAMMA_API_BASE}/markets?{params}",
                                         headers={"User-Agent": "TaxReserveAgent/1.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode())
            if isinstance(payload, dict):
                payload = payload.get("data", [])
            return payload if isinstance(payload, list) else []
        except Exception as e:
            print(f"[INFO] Gamma metadata lookup failed ({e}); falling back to on-chain identifiers.")
            return []

    def _fetch(self, params: str) -> List[Dict[str, Any]]:
        """
        Gamma /markets lookup that can actually see RESOLVED markets.

        GAMMA DEFAULTS TO `closed=false`, AND SAYS NOTHING ABOUT IT. A lookup by
        `condition_ids` or `clob_token_ids` for a market that has resolved returns
        an empty list, not the market - verified live 2026-09-02 against
        `will-joe-biden-get-coronavirus-before-the-election`:

            condition_ids=0xe3b4...              -> 0 rows
            condition_ids=0xe3b4...&closed=true  -> 1 row
            clob_token_ids=5313...               -> 0 rows
            clob_token_ids=5313...&closed=true   -> 1 row

        This silently broke `resolve-markets` COMPLETELY: every resolved condition
        came back as "no Gamma record", so nothing was ever settled and the
        command reported "nothing to settle" no matter what was in the ledger. The
        16 unit tests over it all passed, because they drive a fake resolver -
        the same fake-only blind spot that hid the reorg bug.

        An empty result is therefore retried with `closed=true` before being
        believed. Open markets still answer on the first request; only resolved
        ones pay for the second.
        """
        if self.offline:
            return []
        markets = self._request(params)
        if not markets and "closed=" not in params:
            markets = self._request(f"{params}&closed=true")
        return markets

    def _store(self, market: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "slug": market.get("slug") or market.get("questionID") or "",
            "question": market.get("question", ""),
            "outcomes": [str(o) for o in self._maybe_json_list(market.get("outcomes"))],
            "token_ids": [str(t) for t in self._maybe_json_list(market.get("clobTokenIds"))],
            "condition_id": str(market.get("conditionId", "")).lower(),
        }
        if entry["condition_id"]:
            self._cache[entry["condition_id"]] = entry
        for token_id in entry["token_ids"]:
            self._cache[f"token:{token_id}"] = entry
        return entry

    def remember_symbol(self, symbol: str, condition_id: str, slug: str = "",
                        token_id: str = "") -> None:
        """
        Records that `symbol` belongs to `condition_id`.

        The Data API builds symbols straight from a trade row's `slug` + `outcome`
        and never asks Gamma anything, which is fast but left the metadata cache
        EMPTY - so `resolve-markets` could not map a single open position back to
        its condition and reported every one as "no condition id on record".
        Fills now record the link as they are parsed.

        Only the condition is stored, never the outcome index: a trade row's
        `outcomeIndex` is the sentinel 999 on ~6% of rows, and settling the wrong
        leg would book a winner as worthless. The index is derived at settlement
        time from Gamma's authoritative `outcomes` order instead.
        """
        if not symbol or not condition_id:
            return
        entry = dict(self._cache.get(f"symbol:{symbol}") or {})
        entry["condition_id"] = str(condition_id).lower()
        if slug:
            entry["slug"] = slug
        if token_id:
            entry["token_id"] = str(token_id)
        self._cache[f"symbol:{symbol}"] = entry

    def by_condition(self, condition_id: str) -> Optional[Dict[str, Any]]:
        key = str(condition_id).lower()
        if key in self._cache:
            return self._cache[key]
        for market in self._fetch(f"condition_ids={key}"):
            self._store(market)
        return self._cache.get(key)

    def by_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        key = f"token:{token_id}"
        if key in self._cache:
            return self._cache[key]
        for market in self._fetch(f"clob_token_ids={token_id}"):
            self._store(market)
        return self._cache.get(key)

    def fetch_market_state(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        Raw, UNCACHED Gamma market record for a condition.

        Deliberately bypasses the cache: `closed`, `outcomePrices` and
        `closedTime` change exactly once in a market's life, and a cached "still
        open" answer is the one that matters. Metadata that never changes (slug,
        outcomes, token ids) is still folded into the cache on the way past.
        """
        markets = self._fetch(f"condition_ids={str(condition_id).lower()}")
        for market in markets:
            self._store(market)
            return market
        return None

    def by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Gamma lookup by market slug. Inherits the `closed=true` retry from `_fetch`."""
        for market in self._fetch(f"slug={slug}"):
            return self._store(market)
        return None

    def resolve_symbol(self, symbol: str, max_split_attempts: int = 4) -> Optional[Dict[str, Any]]:
        """
        Symbol -> {condition_id, slug, outcome_index, token_id}, fetching from
        Gamma if the cache has never seen it.

        WHY THIS EXISTS. Both `harvest --live-marks` and `resolve-markets` used to
        read `self._cache` and nothing else, so on a COLD cache - a fresh checkout,
        a ledger built from CSV imports, a cleared cache file - every position came
        back unmarked or unresolvable. Nothing failed loudly; the reports were just
        silently empty.

        Three routes, cheapest first:

        1. A `symbol:` link recorded when the row was written. Free, no network,
           and carries the CLOB token id for live marks.
        2. A `CTF-<prefix>-<indexSet>` symbol. The index set is fully recoverable,
           so the OUTCOME INDEX comes back with no lookup at all. The condition id
           does NOT: `canonical_symbol()` truncates it to 10 of 64 hex characters,
           and 40 bits of a 256-bit id cannot be reversed. The prefix is matched
           against conditions already known; failing that, the outcome index is
           returned alone and the caller reports the position as unresolvable
           rather than settling it against a guessed market.
        3. A `SLUG-OUTCOME` symbol. The slug itself contains hyphens, so the split
           point is ambiguous - candidates are tried right to left against Gamma's
           `?slug=` filter until one matches (the first attempt succeeds for the
           common single-word outcomes). Capped at `max_split_attempts` requests.
        """
        if symbol in self._unresolvable:
            return None

        cached = self._cache.get(f"symbol:{symbol}")
        if cached and cached.get("condition_id"):
            resolved = dict(cached)
            # A link recorded with its token id is already complete for both
            # callers - live marks need the token, and resolve-markets derives the
            # outcome index later from the market it fetches anyway. Returning here
            # keeps the fast path genuinely free of network calls.
            if resolved.get("token_id"):
                return resolved
            market = self.by_condition(cached["condition_id"]) or {}
            if resolved.get("outcome_index") is None:
                resolved["outcome_index"] = self._outcome_index(symbol, market,
                                                                cached["condition_id"])
            token_ids = market.get("token_ids") or []
            index = resolved.get("outcome_index")
            if index is not None and index < len(token_ids):
                resolved["token_id"] = token_ids[index]
            return resolved

        if symbol.startswith("CTF-"):
            parts = symbol.split("-")
            if len(parts) >= 3 and parts[-1].isdigit():
                index_set = int(parts[-1])
                outcomes = index_set_to_outcomes(index_set)
                outcome_index = outcomes[0] if len(outcomes) == 1 else None
                prefix = parts[1].lower()
                for key, entry in self._cache.items():
                    if key.startswith(("symbol:", "token:")) or not isinstance(entry, dict):
                        continue
                    condition_id = str(entry.get("condition_id") or key)
                    if condition_id[2:].lower().startswith(prefix):
                        token_ids = entry.get("token_ids") or []
                        return {"condition_id": condition_id, "slug": entry.get("slug", ""),
                                "outcome_index": outcome_index,
                                "token_id": token_ids[outcome_index]
                                if outcome_index is not None and outcome_index < len(token_ids) else ""}
                # Outcome index is real; the condition id is genuinely not in the symbol.
                # Not marked unresolvable: a chain lookup can still recover the id.
                return {"condition_id": "", "slug": "", "outcome_index": outcome_index,
                        "token_id": "", "condition_prefix": prefix}
            self._unresolvable.add(symbol)
            return None

        parts = symbol.split("-")
        for take in range(1, min(max_split_attempts, len(parts)) + 1):
            candidate_slug = "-".join(parts[:-take]).lower()
            if not candidate_slug:
                break
            market = self.by_slug(candidate_slug)
            if not market:
                continue
            outcome_index = self._outcome_index(symbol, market, market.get("condition_id", ""))
            if outcome_index is None:
                continue
            token_ids = market.get("token_ids") or []
            resolved = {
                "condition_id": market.get("condition_id", ""),
                "slug": market.get("slug", ""),
                "outcome_index": outcome_index,
                "token_id": token_ids[outcome_index] if outcome_index < len(token_ids) else "",
            }
            self.remember_symbol(symbol, resolved["condition_id"], resolved["slug"],
                                 resolved["token_id"])
            return resolved

        # Every split point missed. Remembered for this process so a ledger with a
        # few hand-entered symbols does not re-hammer Gamma with max_split_attempts
        # requests apiece on every run.
        self._unresolvable.add(symbol)
        return None

    @staticmethod
    def _outcome_index(symbol: str, market: Dict[str, Any], condition_id: str) -> Optional[int]:
        """Which outcome slot `symbol` names, per the market's own outcome order."""
        slug = market.get("slug") or ""
        for position, outcome in enumerate(market.get("outcomes") or []):
            if slug and canonical_symbol(slug=slug, outcome=str(outcome)) == symbol:
                return position
            if condition_id and canonical_symbol(condition_id=condition_id,
                                                 index_set=1 << position) == symbol:
                return position
        return None

    def symbol_for_outcome(self, condition_id: str, outcome_index: int) -> str:
        """conditionId + outcome slot -> canonical symbol, degrading gracefully."""
        market = self.by_condition(condition_id)
        outcomes = (market or {}).get("outcomes") or []
        if market and market.get("slug") and 0 <= outcome_index < len(outcomes):
            return canonical_symbol(slug=market["slug"], outcome=outcomes[outcome_index])
        return canonical_symbol(condition_id=condition_id, index_set=1 << outcome_index)

    def symbol_for_token(self, token_id: str) -> str:
        market = self.by_token(token_id)
        if market and market.get("slug"):
            token_ids = market.get("token_ids") or []
            outcomes = market.get("outcomes") or []
            if str(token_id) in token_ids:
                idx = token_ids.index(str(token_id))
                if idx < len(outcomes):
                    return canonical_symbol(slug=market["slug"], outcome=outcomes[idx])
        return canonical_symbol(token_id=token_id)


# ----------------------------------------------------------------------------
# Transport: CLOB order-fill subgraph (GraphQL)
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Live CLOB fee detection
# ----------------------------------------------------------------------------

CLOB_API_BASE = "https://clob.polymarket.com"
FEE_CACHE_TTL_S = 3600.0          # one hour
DEFAULT_FEE_EXPONENT = 1
DEFAULT_FEE_CURVE = "product"   # 2p(1-p); "min" selects min(p, 1-p)


@dataclass
class FeeSchedule:
    """
    A market's live fee terms, as published by Gamma.

    `rate` is the headline number (0.04 = 4% on politics), but the fee CHARGED is
    not `rate` - it scales with how close the contract is to a coin flip. See
    `one_way_fee()`.
    """
    token_id: str = ""
    fee_type: str = ""
    rate: float = 0.0
    exponent: int = DEFAULT_FEE_EXPONENT
    taker_only: bool = True
    rebate_rate: float = 0.0
    fees_enabled: bool = True
    source: str = "unavailable"     # gamma | fallback | disabled | unavailable
    curve: str = "product"          # product = 2p(1-p) | min = min(p, 1-p)

    def one_way_fee(self, price: float) -> float:
        """
        Fee on ONE side of a trade at `price`, as a fraction of notional.

            product (default)   fee = rate * (2 * p * (1-p)) ** exponent
            min                 fee = rate * min(p, 1-p) ** exponent

        BOTH FORMS AGREE AT 50c AND NOWHERE ELSE. Politics at 4% gives 2.00% and
        crypto at 7% gives 3.50% under either, which is exactly why the stated
        anchor points do not tell them apart - but at 10c `product` charges 0.72%
        against `min`'s 0.40%, and the gap widens toward the tails (2x at 2c).

        `product` is the default: it is the curve named in the fee spec, and it is
        uniformly the more conservative of the two, which is the right direction
        to be wrong in for a hurdle. The x2 normalisation is what reaches the
        stated 50c anchors - bare p(1-p) peaks at 0.25 and would halve every fee.

        Still an inference in one respect: Gamma publishes only
        `{rate, exponent, takerOnly, rebateRate}`, so the price term appears
        nowhere we can read. Confirm against a real fill before trusting it to the
        basis point.

        The rebate is deliberately NOT applied - it is conditional on maker
        behaviour we do not model, and shrinking the fee shrinks the hurdle.
        """
        if not self.fees_enabled or self.rate <= 0:
            return 0.0
        p = min(max(float(price), 0.0), 1.0)
        shape = (2.0 * p * (1.0 - p)) if self.curve == "product" else min(p, 1.0 - p)
        return float(self.rate) * (shape ** max(1, int(self.exponent)))

    def round_trip_fee(self, price: float, holds_to_resolution: bool = False) -> float:
        """
        Fee on a full position lifecycle at `price`.

        `holds_to_resolution=True` charges the taker fee ONCE. A contract carried
        to settlement is redeemed against the Conditional Tokens contract, not
        sold through the exchange, so there is no second exchange fee - only gas.
        This is the dutch-book case: every leg is bought and then redeemed.

        `False` (the default) charges twice, which is right for anything that
        exits by selling. `takerOnly` only spares the exit leg if you EXIT as a
        maker - resting an order and waiting - and a scalper crossing the spread
        to get out pays both.

        Defaulting to two legs is deliberate: a strategy that does not declare
        itself is assumed to trade out, and over-stating the hurdle declines a
        marginal trade rather than taking a losing one.
        """
        one_way = self.one_way_fee(price)
        return one_way if holds_to_resolution else one_way * 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolymarketFeeSource:
    """
    Live per-market fee terms, cached for an hour.

    WHY NOT JUST `/fee-rate`. That endpoint answers `{"base_fee": 1000}` for
    essentially every market - measured across 25 live tokens on 2026-09-03, 23
    returned exactly 1000, one returned 0 and one 404'd. It is a constant, not a
    usable rate, and reading it as basis points would imply a 10% fee and a 30%
    hurdle that rejects everything. Gamma publishes the real terms alongside the
    market, so that is what is used; `/fee-rate` is queried only to notice when a
    market is genuinely fee-free.

    Measured live across 300 open markets on 2026-09-03:
        politics_fees        rate 0.04    237 markets
        sports_fees_v2       rate 0.03     31
        economics_fees       rate 0.05     14
        finance_prices_fees  rate 0.04      7
        crypto_fees_v2       rate 0.07      6
        (no schedule)                       5
    295 of 300 had `feesEnabled: true`. Fee-free markets are the rare exception,
    not the rule.
    """

    def __init__(self, resolver: Optional["PolymarketMarketResolver"] = None,
                 timeout: int = 10, ttl_s: float = FEE_CACHE_TTL_S,
                 offline: bool = False):
        self.resolver = resolver
        self.timeout = timeout
        self.ttl_s = float(ttl_s)
        self.offline = offline
        self._cache: Dict[str, Any] = {}   # token_id -> (fetched_at, FeeSchedule)

    def _get_json(self, url: str) -> Optional[Any]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TaxReserveAgent/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except Exception:
            return None

    def fee_schedule(self, token_id: str, force: bool = False) -> FeeSchedule:
        """
        Fee terms for one CLOB token. Cached for `ttl_s`; returns an
        `unavailable` schedule when nothing can be read.
        """
        key = str(token_id or "").strip()
        if not key:
            return FeeSchedule(source="unavailable")

        cached = self._cache.get(key)
        if cached and not force and (time.time() - cached[0]) < self.ttl_s:
            return cached[1]
        if self.offline:
            return FeeSchedule(token_id=key, source="unavailable")

        schedule = self._fetch(key)
        self._cache[key] = (time.time(), schedule)
        return schedule

    def _fetch(self, token_id: str) -> FeeSchedule:
        markets = self._get_json(f"{GAMMA_API_BASE}/markets?clob_token_ids={token_id}")
        if isinstance(markets, dict):
            markets = markets.get("data", [])
        market = markets[0] if isinstance(markets, list) and markets else None

        if not market:
            return FeeSchedule(token_id=token_id, source="unavailable")

        if not market.get("feesEnabled", True):
            return FeeSchedule(token_id=token_id, fee_type=str(market.get("feeType") or ""),
                               rate=0.0, fees_enabled=False, source="disabled")

        raw = market.get("feeSchedule") or {}
        if not isinstance(raw, dict) or not raw.get("rate"):
            # feesEnabled with no schedule: terms exist but are not published.
            # Treated as UNAVAILABLE, never as zero - a missing number is not a
            # free market, and the caller falls back to its assumption.
            return FeeSchedule(token_id=token_id, fee_type=str(market.get("feeType") or ""),
                               source="unavailable")

        return FeeSchedule(
            token_id=token_id,
            fee_type=str(market.get("feeType") or ""),
            rate=float(raw.get("rate") or 0.0),
            exponent=int(raw.get("exponent") or DEFAULT_FEE_EXPONENT),
            taker_only=bool(raw.get("takerOnly", True)),
            rebate_rate=float(raw.get("rebateRate") or 0.0),
            fees_enabled=True,
            source="gamma",
        )

    def round_trip_fee(self, token_id: str, price: float,
                       holds_to_resolution: bool = False) -> Optional[float]:
        """
        Live round-trip fee at `price`, or None when it could not be established.

        None is deliberately distinct from 0.0: "we do not know" must fall back to
        the caller's assumption, while 0.0 means a market genuinely charges
        nothing. Collapsing the two would remove the hurdle exactly when the fee
        data is missing.
        """
        schedule = self.fee_schedule(token_id)
        if schedule.source == "unavailable":
            return None
        return schedule.round_trip_fee(price, holds_to_resolution)


class PolymarketDataAPIClient:
    """
    CLOB fill history from Polymarket's public Data API.

    THIS REPLACED THE GOLDSKY SUBGRAPH, which now answers 404. Probing the Data
    API live (2026-09-02) turned out to make it the better source anyway, because
    a trade row carries its own market metadata:

        {"proxyWallet", "side", "asset", "conditionId", "size", "price",
         "timestamp", "title", "slug", "outcome", "outcomeIndex",
         "transactionHash", ...}

    `slug` + `outcome` are exactly what `canonical_symbol()` needs, so fills name
    themselves without a Gamma round trip - and, more importantly, without
    depending on the metadata cache being warm.

    Three things measured rather than assumed, each of which changes the parser:

      1. FILLS ARE PRE-AGGREGATED. Across 500 live rows there were ZERO
         (transactionHash, asset, side) groups with more than one row, so that
         triple is a safe unique key. The subgraph parser needed a log index to
         avoid collapsing partial fills; this one does not.
      2. `outcomeIndex` IS UNRELIABLE - it was the sentinel 999 in 32 of 500 rows
         (6.4%). The `outcome` STRING is used instead. Anything keyed on the
         index would mis-label one position in fifteen.
      3. THERE IS NO `fee` FIELD. Not on any row. Fees are therefore booked as
         0.00 and cost basis is gross of Polymarket's fees. Under-stating fees
         over-states gains, which over-states the escrow - the safe direction,
         but it is an approximation, not a measurement.

    `size` and `price` arrive as human decimals (shares and dollars), NOT the
    6-decimal base units the on-chain path deals in. No scaling here.
    """

    def __init__(self, base_url: str = DATA_API_BASE, timeout: int = 20,
                 page_size: int = 500, max_pages: int = 60, min_interval_s: float = 0.2,
                 fee_rate: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_size = page_size
        self.max_pages = max_pages
        self.min_interval_s = min_interval_s
        self.fee_rate = max(0.0, float(fee_rate))
        self._last_call_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_call_at = time.time()

    def _get(self, path: str) -> Optional[List[Dict[str, Any]]]:
        self._throttle()
        try:
            req = urllib.request.Request(f"{self.base_url}{path}",
                                         headers={"User-Agent": "TaxReserveAgent/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
            if isinstance(payload, dict):
                payload = payload.get("data", [])
            return payload if isinstance(payload, list) else []
        except Exception as e:
            print(f"[INFO] Data API request failed ({e}); CLOB fills will be incomplete.")
            return None

    @staticmethod
    def trade_key(trade: Dict[str, Any]) -> str:
        """
        Identity of a fill: transaction hash + token + side.

        The same triple the ledger's UNIQUE constraint reduces to, and verified
        collision-free across 500 live rows - the endpoint pre-aggregates partial
        fills, so one wallet cannot have two distinct rows sharing it.
        """
        return (f"{str(trade.get('transactionHash', '')).lower()}|"
                f"{trade.get('asset', '')}|{str(trade.get('side', '')).upper()}")

    def fetch_trades(self, wallet: str, from_timestamp: int = 0) -> List[Dict[str, Any]]:
        """
        Every trade for `wallet`, walked with `offset` until a short page.

        OFFSET PAGING RACES A LIVE FEED. The feed is newest-first, so a trade that
        lands mid-walk pushes every older row toward a HIGHER offset - and the next
        page re-serves rows the previous page already returned. Measured live: a
        2,000-trade walk repeated 15 rows across page boundaries. Every row is
        therefore keyed and de-duplicated across pages.

        The drift only ever OVERLAPS, never gaps: rows shift down the list because
        entries are inserted at the head, and trades are not deleted, so nothing
        can slip past a page boundary unseen. Duplicates are the whole failure
        mode, and de-duplication is the whole fix. The count is reported, because
        a large drift is worth knowing about even though it is handled.

        `user=` matches the PROXY wallet - Polymarket routes orders through a Gnosis
        Safe proxy, so that, not the EOA you sign with, is the address on trades.
        """
        wallet = wallet.lower()
        trades: List[Dict[str, Any]] = []
        seen_keys: set = set()
        duplicates = 0

        for page in range(self.max_pages):
            batch = self._get(f"/trades?user={wallet}&limit={self.page_size}"
                              f"&offset={page * self.page_size}")
            if batch is None:
                break
            for trade in batch:
                key = self.trade_key(trade)
                if key in seen_keys:
                    duplicates += 1
                    continue
                seen_keys.add(key)
                trades.append(trade)
            if len(batch) < self.page_size:
                break
        else:
            # Loop ran to completion, so the last page was FULL - there is almost
            # certainly more history the walk never reached. Silence here hands a
            # high-volume wallet a ledger missing its oldest trades, which quietly
            # removes cost basis and overstates gains.
            print(f"[WARN] Stopped at the {self.max_pages}-page limit "
                  f"({self.max_pages * self.page_size:,} trades) for {wallet[:10]}... and the last "
                  f"page was still full.\n"
                  f"       HISTORY IS TRUNCATED - the oldest trades are missing, so their cost "
                  f"basis is absent and\n"
                  f"       realised gains will read too high. Raise max_pages on "
                  f"PolymarketDataAPIClient to capture the rest.")

        if duplicates:
            print(f"[INFO] Data API returned {duplicates} duplicate row(s) across page "
                  f"boundaries (the wallet traded during the walk); de-duplicated.")
        if from_timestamp:
            trades = [t for t in trades if _hex_to_int(t.get("timestamp", 0)) >= from_timestamp]
        return trades


class PolymarketSubgraphClient:
    """
    Reads CLOB fills from a Graph-protocol orderbook subgraph.

    NO LONGER THE DEFAULT, AND NOT WIRED UP UNLESS YOU CONFIGURE IT. The Goldsky
    endpoint this was written against answers 404 as of 2026-09-02, so
    `chain-sync` reads fills from `PolymarketDataAPIClient` instead. The class is
    kept because the shape is right and a self-hosted or replacement subgraph is
    a legitimate source - set `chain.orderbook_subgraph_url` to switch back.

    Only rows where the wallet is the `maker` are accounted. The `taker` on a
    Polymarket fill is the exchange contract matching the order, so counting both
    sides would double-book every trade.
    """

    ORDER_FILLED_QUERY = """
    query Fills($maker: String!, $skip: Int!, $first: Int!, $fromTs: BigInt!) {
      orderFilledEvents(
        where: { maker: $maker, timestamp_gte: $fromTs }
        orderBy: timestamp
        orderDirection: asc
        skip: $skip
        first: $first
      ) {
        id
        timestamp
        transactionHash
        maker
        taker
        makerAssetId
        takerAssetId
        makerAmountFilled
        takerAmountFilled
        fee
      }
    }
    """

    def __init__(self, subgraph_url: str = DEFAULT_ORDERBOOK_SUBGRAPH, timeout: int = 20,
                 page_size: int = 500, max_pages: int = 40):
        self.subgraph_url = subgraph_url
        self.timeout = timeout
        self.page_size = page_size
        self.max_pages = max_pages

    def _query(self, query: str, variables: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.subgraph_url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": "TaxReserveAgent/1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
            if payload.get("errors"):
                print(f"[WARN] Subgraph returned errors: {payload['errors']}")
                return None
            return payload.get("data")
        except Exception as e:
            print(f"[INFO] Subgraph query failed ({e}); CLOB fills will be skipped.")
            return None

    def fetch_order_fills(self, wallet: str, from_timestamp: int = 0) -> List[Dict[str, Any]]:
        """All fills for `wallet` as maker, from `from_timestamp` (unix seconds) onward."""
        wallet = wallet.lower()
        fills: List[Dict[str, Any]] = []
        for page in range(self.max_pages):
            data = self._query(self.ORDER_FILLED_QUERY, {
                "maker": wallet,
                "skip": page * self.page_size,
                "first": self.page_size,
                "fromTs": str(int(from_timestamp)),
            })
            if not data:
                break
            batch = data.get("orderFilledEvents") or []
            fills.extend(batch)
            if len(batch) < self.page_size:
                break
        return fills


# ----------------------------------------------------------------------------
# Orchestration: on-chain events -> ledger transactions
# ----------------------------------------------------------------------------

class PolymarketChainIngestor:
    """
    Turns Gnosis CTF logs and CLOB fills into transaction dicts the FIFO lot
    engine accepts.

    Every network dependency is injectable (`rpc`, `subgraph`, `resolver`) and
    every parser is a pure method, so the whole class can be exercised offline
    against recorded fixtures - which is how the tests run and why an import is
    reproducible rather than dependent on whatever the chain looks like today.

    IDEMPOTENCY. `tx_hash` is written as `<hash>#<logIndex>`, not the bare hash.
    The ledger's UNIQUE key is (source, tx_hash, symbol, side), and a single
    Polygon transaction routinely contains several fills of the SAME market and
    side against different makers. With bare hashes those fills collide on the
    UNIQUE constraint and all but the first are dropped on the floor -
    understating both cost basis and proceeds. The log index makes each row
    distinct while keeping re-syncs of the same range a no-op.
    """

    def __init__(self,
                 wallets: Optional[List[str]] = None,
                 rpc_url: str = DEFAULT_POLYGON_RPC,
                 subgraph_url: Optional[str] = None,
                 ctf_address: str = CTF_CONTRACT_ADDRESS,
                 basis_allocation: Optional[List[float]] = None,
                 rpc: Optional[PolygonRPCClient] = None,
                 subgraph: Optional[PolymarketSubgraphClient] = None,
                 data_api: Optional[PolymarketDataAPIClient] = None,
                 resolver: Optional[PolymarketMarketResolver] = None,
                 confirmations: int = REORG_SAFETY_BLOCKS,
                 polymarket_fee_rate: float = 0.0,
                 offline: bool = False):
        self.wallets = [w.lower() for w in (wallets or [])]
        self.ctf_address = ctf_address
        self.basis_allocation = basis_allocation
        self.confirmations = max(0, int(confirmations))
        # Fees are real but this endpoint does not report them (see
        # data_api_trade_to_transaction). Default 0.0 keeps the ledger a record of
        # measurements only; set it to book an explicit, clearly-labelled estimate.
        self.polymarket_fee_rate = max(0.0, float(polymarket_fee_rate))
        self.offline = offline
        self.rpc = rpc or (None if offline else PolygonRPCClient(rpc_url))
        # The subgraph is opt-in now that the public one is dead: it is only built
        # when a URL was explicitly configured, so the default path is the Data API.
        self.subgraph = subgraph
        if self.subgraph is None and subgraph_url and not offline:
            self.subgraph = PolymarketSubgraphClient(subgraph_url)
        self.data_api = data_api or (None if offline else PolymarketDataAPIClient())
        self.resolver = resolver or PolymarketMarketResolver(offline=offline)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _to_usd(raw_amount: int) -> float:
        """6-decimal USDC base units -> dollars. Shares are 1:1 with collateral units."""
        return raw_amount / COLLATERAL_UNIT

    def _allocation_for(self, leg_count: int) -> List[float]:
        """
        Per-leg fraction of the $1 set price. Defaults to an equal split; a custom
        allocation is normalised so it always sums to exactly 1.00 and cannot
        invent or destroy basis.
        """
        if not self.basis_allocation or len(self.basis_allocation) != leg_count:
            return [1.0 / leg_count] * leg_count if leg_count else []
        total = float(sum(self.basis_allocation))
        if total <= 0:
            return [1.0 / leg_count] * leg_count
        return [float(w) / total for w in self.basis_allocation]

    def _symbol_for_index_set(self, condition_id: str, index_set: int) -> str:
        """
        An index set covering exactly one outcome slot names that outcome. A
        multi-slot set (a genuine combinatorial position) has no single outcome
        name, so it keeps the raw on-chain identifier rather than being
        misreported as one of its legs.
        """
        outcomes = index_set_to_outcomes(index_set)
        if len(outcomes) == 1:
            symbol = self.resolver.symbol_for_outcome(condition_id, outcomes[0])
        else:
            symbol = canonical_symbol(condition_id=condition_id, index_set=index_set)
        # Record the link here as well as on the Data API path: a wallet that only
        # ever splits and redeems never produces a CLOB fill, and without this its
        # positions would be unresolvable on a cold cache.
        self.resolver.remember_symbol(symbol, condition_id)
        return symbol

    # -- CTF lifecycle events ----------------------------------------------

    def split_to_transactions(self, event: Dict[str, Any], timestamp: str) -> List[Dict[str, Any]]:
        """PositionSplit -> one opening lot per leg, basis allocated across the $1 set."""
        legs = event.get("index_sets") or []
        shares = self._to_usd(event.get("amount", 0))
        if not legs or shares <= 0:
            return []
        allocation = self._allocation_for(len(legs))
        return [{
            "source": "polymarket",
            "tx_hash": f"{event['tx_hash']}#{event['log_index']}#{index_set}",
            "timestamp": timestamp,
            "asset_class": "prediction_market",
            "symbol": self._symbol_for_index_set(event["condition_id"], index_set),
            "side": "BUY",
            "quantity": shares,
            "price": allocation[i],
            "fee": 0.0,
            "total_value": shares * allocation[i],
            "notes": (f"CTF SplitPosition: ${shares:,.2f} collateral into {len(legs)} legs; "
                      f"basis allocated {allocation[i]:.4f}/set | condition {event['condition_id']}"),
        } for i, index_set in enumerate(legs)]

    def merge_to_transactions(self, event: Dict[str, Any], timestamp: str) -> List[Dict[str, Any]]:
        """PositionsMerge -> one closing SELL per leg, proceeds allocated identically to a split."""
        legs = event.get("index_sets") or []
        shares = self._to_usd(event.get("amount", 0))
        if not legs or shares <= 0:
            return []
        allocation = self._allocation_for(len(legs))
        return [{
            "source": "polymarket",
            "tx_hash": f"{event['tx_hash']}#{event['log_index']}#{index_set}",
            "timestamp": timestamp,
            "asset_class": "prediction_market",
            "symbol": self._symbol_for_index_set(event["condition_id"], index_set),
            "side": "SELL",
            "quantity": shares,
            "price": allocation[i],
            "fee": 0.0,
            "total_value": shares * allocation[i],
            "notes": (f"CTF MergePositions: {len(legs)} legs burned for ${shares:,.2f} collateral; "
                      f"proceeds allocated {allocation[i]:.4f}/set | condition {event['condition_id']}"),
        } for i, index_set in enumerate(legs)]

    def redemption_to_transactions(self, event: Dict[str, Any], timestamp: str,
                                   payout_ratios: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """
        PayoutRedemption -> REDEEM rows for the paying leg(s).

        The event carries the total `payout` and the index sets redeemed, but NOT
        the share count per leg, so the share count has to be reconstructed:
        shares = payout / ratio, where ratio is the resolved payout per share read
        from `payoutNumerators`/`payoutDenominator` on chain.

        A binary market resolves 0/1 and one leg pays, which is the overwhelming
        majority of real redemptions and is exact. When the ratios cannot be read
        (offline, or an unresolved condition) the row falls back to the $1.00
        convention and the note is tagged NEEDS-REVIEW rather than quietly
        presenting an assumption as a measurement. Losing legs are worth $0 and
        realise their loss through `build_loser_writeoffs()`, not here - the event
        does not say how many losing shares were burned.
        """
        legs = event.get("index_sets") or []
        payout_usd = self._to_usd(event.get("payout", 0))
        if not legs:
            return []

        ratio_by_leg: Dict[int, float] = {}
        if payout_ratios:
            for index_set in legs:
                slots = index_set_to_outcomes(index_set)
                ratio_by_leg[index_set] = sum(
                    payout_ratios[s] for s in slots if s < len(payout_ratios))

        paying = [idx for idx, ratio in ratio_by_leg.items() if ratio > 0]
        needs_review = ""
        if len(paying) == 1:
            index_set = paying[0]
            ratio = ratio_by_leg[index_set]
            targets = [(index_set, payout_usd / ratio, ratio)]
        elif not ratio_by_leg and payout_usd > 0:
            # No on-chain ratios available: assume the standard $1.00 winner payout.
            index_set = legs[0] if len(legs) == 1 else max(legs)
            targets = [(index_set, payout_usd, 1.0)]
            needs_review = " [NEEDS-REVIEW: payout ratios unavailable, assumed $1.00/share]"
        elif len(paying) > 1:
            # Several legs paid; the event gives no per-leg breakdown to divide by.
            targets = [(paying[0], payout_usd / ratio_by_leg[paying[0]], ratio_by_leg[paying[0]])]
            needs_review = (f" [NEEDS-REVIEW: {len(paying)} legs paid, whole payout attributed "
                            f"to index set {paying[0]}]")
        else:
            return []  # resolved to zero on every redeemed leg; handled as a write-off

        rows = []
        for index_set, shares, ratio in targets:
            if shares <= 0:
                continue
            rows.append({
                "source": "polymarket",
                "tx_hash": f"{event['tx_hash']}#{event['log_index']}#{index_set}",
                "timestamp": timestamp,
                "asset_class": "prediction_market",
                "symbol": self._symbol_for_index_set(event["condition_id"], index_set),
                "side": "SELL",  # priced explicitly; REDEEM would force $1.00 in the engine
                "quantity": shares,
                "price": ratio,
                "fee": 0.0,
                "total_value": shares * ratio,
                "notes": (f"CTF PayoutRedemption: ${payout_usd:,.2f} at ${ratio:.4f}/share "
                          f"| condition {event['condition_id']}{needs_review}"),
            })
        return rows

    def events_to_transactions(self, events: List[Dict[str, Any]],
                               timestamps: Optional[Dict[int, str]] = None,
                               payout_ratios: Optional[Dict[str, List[float]]] = None) -> List[Dict[str, Any]]:
        """
        Decoded CTF events -> ledger transactions.

        `timestamps` (block -> ISO string) and `payout_ratios` (conditionId ->
        ratios) are passed in so this stays a pure function: the tests supply
        them from fixtures, `sync_wallet()` supplies them from the chain.
        """
        timestamps = timestamps or {}
        payout_ratios = payout_ratios or {}
        transactions: List[Dict[str, Any]] = []
        for event in events:
            timestamp = timestamps.get(event.get("block_number"), "")
            if not timestamp:
                print(f"[WARN] No block timestamp for {event['event']} in "
                      f"{event['tx_hash'][:12]}...; skipping (a dateless lot breaks FIFO order).")
                continue
            if event["event"] == "PositionSplit":
                transactions.extend(self.split_to_transactions(event, timestamp))
            elif event["event"] == "PositionsMerge":
                transactions.extend(self.merge_to_transactions(event, timestamp))
            elif event["event"] == "PayoutRedemption":
                transactions.extend(self.redemption_to_transactions(
                    event, timestamp, payout_ratios.get(event["condition_id"])))
        return transactions

    # -- CLOB fills ---------------------------------------------------------

    def fill_to_transaction(self, fill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        One `orderFilledEvent` -> one ledger row.

        Asset id "0" is the USDC collateral leg. Which side of the fill carries it
        is what makes the trade a buy or a sell:
          makerAssetId == 0  ->  maker paid USDC for shares      -> BUY
          takerAssetId == 0  ->  maker gave shares, received USDC -> SELL
        Price comes out of the ratio of the two filled amounts, so it is the real
        executed average for that fill rather than a quoted top-of-book price.
        """
        maker_asset = str(fill.get("makerAssetId", "0"))
        taker_asset = str(fill.get("takerAssetId", "0"))
        maker_amount = _hex_to_int(fill.get("makerAmountFilled", 0))
        taker_amount = _hex_to_int(fill.get("takerAmountFilled", 0))
        fee = self._to_usd(_hex_to_int(fill.get("fee", 0)))

        if maker_asset == "0" and taker_asset != "0":
            side, token_id, shares, usdc = "BUY", taker_asset, taker_amount, maker_amount
        elif taker_asset == "0" and maker_asset != "0":
            side, token_id, shares, usdc = "SELL", maker_asset, maker_amount, taker_amount
        else:
            # Token-for-token fill (neither leg is collateral): no USD basis to book.
            return None

        share_count = self._to_usd(shares)
        if share_count <= 0:
            return None
        price = self._to_usd(usdc) / share_count

        epoch = _hex_to_int(fill.get("timestamp", 0))
        timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        tx_hash = str(fill.get("transactionHash") or fill.get("id") or "").lower()
        unique_id = str(fill.get("id") or f"{tx_hash}#{token_id}")

        return {
            "source": "polymarket",
            "tx_hash": f"{tx_hash}#{unique_id[-16:]}",
            "timestamp": timestamp,
            "asset_class": "prediction_market",
            "symbol": self.resolver.symbol_for_token(token_id),
            "side": side,
            "quantity": share_count,
            "price": price,
            "fee": fee,
            "total_value": share_count * price,
            "notes": f"Polymarket CLOB fill (subgraph) | token {token_id[:16]}...",
        }

    def data_api_trade_to_transaction(self, trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        One Data API trade row -> one ledger row.

        The row names its own market (`slug` + `outcome`), so the symbol is built
        without a Gamma lookup and matches what the on-chain path produces for the
        same position - which is what lets a CLOB buy and a CTF redemption close
        against each other in FIFO.

        `outcomeIndex` is deliberately ignored: it was the sentinel 999 on 6.4% of
        live rows, so anything keyed on it mislabels roughly one position in
        fifteen. The `outcome` string is always populated.
        """
        side = str(trade.get("side", "")).strip().upper()
        if side not in ("BUY", "SELL"):
            return None
        try:
            quantity = float(trade.get("size", 0.0))
            price = float(trade.get("price", 0.0))
        except (TypeError, ValueError):
            return None
        if quantity <= 0:
            return None

        epoch = _hex_to_int(trade.get("timestamp", 0))
        if epoch <= 0:
            return None
        timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        slug = str(trade.get("slug") or "").strip()
        outcome = str(trade.get("outcome") or "").strip()
        condition_id = str(trade.get("conditionId") or "").strip()
        token_id = str(trade.get("asset") or "").strip()
        if slug and outcome:
            symbol = canonical_symbol(slug=slug, outcome=outcome)
        elif token_id:
            symbol = self.resolver.symbol_for_token(token_id)
        else:
            symbol = canonical_symbol(condition_id=condition_id, index_set=1)

        # Record symbol -> condition so resolve-markets can find this position later.
        if condition_id:
            self.resolver.remember_symbol(symbol, condition_id, slug, token_id)

        tx_hash = str(trade.get("transactionHash") or "").lower()
        # (tx, asset, side) is unique on this endpoint - fills arrive pre-aggregated,
        # verified across 500 live rows - and side is already in the ledger's UNIQUE
        # key, so hash + asset is enough to keep two markets in one tx apart.
        unique = f"{tx_hash}#{token_id[:24]}" if tx_hash else f"dataapi_{symbol}_{timestamp}_{side}"

        # THE ENDPOINT REPORTS NO FEE ON ANY ROW (checked across 500 live trades),
        # so a fill is booked gross unless a rate is configured. Leaving fees out
        # overstates gains and therefore the escrow - the safe direction, but on a
        # venue where edges run 1-4% it is not a small error: a 2% round-trip fee
        # against a 4% gross edge means tax is assessed on roughly double the
        # profit actually earned. The lot engine already capitalises whatever fee
        # it is handed (basis + fee on a buy, proceeds - fee on a sell); the gap is
        # purely that this source has no fee to hand it.
        #
        # An estimate is opt-in and OFF by default, because a guessed number in a
        # tax ledger is the same mistake as a guessed market price - and every row
        # it touches says so in `notes`.
        fee = quantity * price * self.polymarket_fee_rate
        fee_note = (f"fee ESTIMATED at {self.polymarket_fee_rate * 100:.2f}% (endpoint reports none)"
                    if self.polymarket_fee_rate > 0 else
                    "fees not reported by endpoint - basis is GROSS of fees")

        return {
            "source": "polymarket",
            "tx_hash": unique,
            "timestamp": timestamp,
            "asset_class": "prediction_market",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "fee": fee,
            "total_value": quantity * price,
            "notes": (f"Polymarket CLOB fill (data API) | {trade.get('title', '')[:60]} "
                      f"| condition {condition_id} | {fee_note}"),
        }

    def data_api_trades_to_transactions(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        for trade in trades:
            try:
                row = self.data_api_trade_to_transaction(trade)
            except (ValueError, TypeError, KeyError) as e:
                print(f"[WARN] Skipping unparseable Data API trade "
                      f"{trade.get('transactionHash', '?')}: {e}")
                continue
            if row:
                rows.append(row)
        return rows

    def fills_to_transactions(self, fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        for fill in fills:
            try:
                row = self.fill_to_transaction(fill)
            except (ValueError, TypeError, ZeroDivisionError) as e:
                print(f"[WARN] Skipping unparseable CLOB fill {fill.get('id')}: {e}")
                continue
            if row:
                rows.append(row)
        return rows

    # -- write-offs for resolved losers -------------------------------------

    @staticmethod
    def open_lot_quantities(symbols: List[str], db_path: Optional[Path] = None) -> Dict[str, float]:
        """Symbol -> still-open share count, for symbols that have any."""
        from ..database.db import get_connection  # local import: keeps parsing importable standalone

        if not symbols:
            return {}
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in symbols)
            cursor.execute(f"""
                SELECT symbol, SUM(remaining_qty) AS open_qty
                FROM tax_lots
                WHERE is_closed = 0 AND symbol IN ({placeholders})
                GROUP BY symbol
            """, list(symbols))
            rows = cursor.fetchall()
        finally:
            conn.close()
        return {row["symbol"]: float(row["open_qty"] or 0.0) for row in rows
                if float(row["open_qty"] or 0.0) > 1e-9}

    @staticmethod
    def build_settlements(symbol_payouts: Dict[str, float], timestamp: str,
                          db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Closes every still-open lot in `symbol_payouts` at its resolved payout.

        The general form of a resolution: each symbol maps to its payout per share
        ($0.00 for a losing outcome, $1.00 for a winner, a fraction for a partial
        resolution). Booking a whole condition's legs together is what keeps the
        arithmetic honest - see `build_loser_writeoffs` for why doing only the
        losers is worse than doing nothing.
        """
        quantities = PolymarketChainIngestor.open_lot_quantities(list(symbol_payouts), db_path)
        rows = []
        for symbol, quantity in sorted(quantities.items()):
            payout = float(symbol_payouts.get(symbol, 0.0))
            note = ("Market resolved against this outcome - shares worthless (realised capital loss)"
                    if payout <= 0 else
                    f"Market resolved in favour of this outcome - settled at ${payout:,.4f}/share")
            rows.append({
                "source": "polymarket",
                "tx_hash": f"settle_{symbol}_{timestamp}",
                "timestamp": timestamp,
                "asset_class": "prediction_market",
                "symbol": symbol,
                "side": "SELL",
                "quantity": quantity,
                "price": payout,
                "fee": 0.0,
                "total_value": quantity * payout,
                "notes": note,
            })
        return rows

    @staticmethod
    def build_loser_writeoffs(condition_symbols: List[str], timestamp: str,
                              db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Closes still-open lots in `condition_symbols` at $0.00.

        A market resolving does not emit an event per losing share - the shares
        simply become worthless and are usually never redeemed at all. Without
        this the losing lots sit open forever and the realised loss never offsets
        anything.

        CAUTION - do not call this on its own for a condition whose WINNING leg is
        also still open. Splitting $100 and holding both legs to resolution is a
        wash: +$50 on the winner, -$50 on the loser. Booking only the loser
        invents a $50 loss that never happened, which lowers the tax escrow and
        leaves the reserve SHORT. `MarketResolutionSync` always settles a
        condition's legs together for exactly this reason.
        """
        return PolymarketChainIngestor.build_settlements(
            {symbol: 0.0 for symbol in condition_symbols}, timestamp, db_path)

    # -- top-level sync -----------------------------------------------------

    def sync_wallet(self, wallet: str, from_block: int = 0, to_block: Optional[int] = None,
                    include_clob: bool = True, from_timestamp: int = 0) -> List[Dict[str, Any]]:
        """
        Full on-chain history for one wallet as ledger transactions.

        Never raises on a network failure: a partial import is recoverable, a
        crashed sync mid-write is not. Whatever could be read is returned and the
        gap is printed.
        """
        transactions: List[Dict[str, Any]] = []
        wallet = wallet.lower()

        if self.rpc is not None:
            try:
                to_block = self.block_ceiling(to_block)
                wallet_topic = "0x" + wallet[2:].rjust(64, "0")
                logs: List[Dict[str, Any]] = []
                for name, topic in CTF_TOPICS.items():
                    # stakeholder / redeemer is topic1 on all three events.
                    logs.extend(self.rpc.get_logs(self.ctf_address, [topic, wallet_topic],
                                                  from_block, to_block))
                events = CTFEventDecoder.decode_logs(logs)
                timestamps = self.rpc.get_block_timestamps([e["block_number"] for e in events])
                ratios = {
                    e["condition_id"]: self.rpc.get_payout_ratios(e["condition_id"], self.ctf_address)
                    for e in events if e["event"] == "PayoutRedemption"
                }
                transactions.extend(self.events_to_transactions(events, timestamps, ratios))
            except RPCError as e:
                print(f"[WARN] CTF log sync failed for {wallet[:10]}...: {e}")

        chain_rows = len(transactions)
        clob_rows = 0
        if include_clob:
            if self.subgraph is not None:
                fills = self.subgraph.fetch_order_fills(wallet, from_timestamp=from_timestamp)
                clob_transactions = self.fills_to_transactions(fills)
            elif self.data_api is not None:
                trades = self.data_api.fetch_trades(wallet, from_timestamp=from_timestamp)
                clob_transactions = self.data_api_trades_to_transactions(trades)
            else:
                clob_transactions = []
            clob_rows = len(clob_transactions)
            transactions.extend(clob_transactions)
            self.warn_if_probably_not_a_proxy_wallet(wallet, chain_rows, clob_rows)

        self.resolver.save()
        transactions.sort(key=lambda t: t["timestamp"])
        return transactions

    @staticmethod
    def warn_if_probably_not_a_proxy_wallet(wallet: str, chain_rows: int, clob_rows: int) -> Optional[str]:
        """
        Flags the address most likely to produce a half-populated ledger.

        Polymarket routes orders through a Gnosis Safe PROXY, so `/trades?user=`
        only matches the proxy address - while the CTF contract logs
        split/merge/redeem against whichever address actually called it. Configure
        the EOA you sign with and the sync happily returns on-chain rows and ZERO
        fills, which looks like a wallet that only ever split and redeemed rather
        than like a misconfiguration. Cost basis is then built from redemptions
        with no purchases behind them.

        Returns the warning text (for tests) or None. Chain rows with no fills is
        the strong signal; nothing at all is more likely an empty or wrong address.
        """
        if clob_rows > 0:
            return None
        if chain_rows > 0:
            message = (f"[WARN] {wallet[:10]}... produced {chain_rows} on-chain CTF row(s) but ZERO "
                       f"CLOB fills.\n"
                       f"       Polymarket trades through a Gnosis Safe PROXY wallet, and the Data "
                       f"API only matches that\n"
                       f"       proxy address - an EOA returns on-chain activity and no fills. Find "
                       f"your proxy address on\n"
                       f"       your Polymarket profile page and put THAT in config.yaml, or cost "
                       f"basis will be built from\n"
                       f"       redemptions with no purchases behind them.")
        else:
            message = (f"[INFO] {wallet[:10]}... returned no on-chain activity and no CLOB fills. "
                       f"If this address does trade,\n"
                       f"       check you configured the Polymarket PROXY wallet (a Gnosis Safe) "
                       f"rather than the EOA you sign with.")
        print(message)
        return message

    def block_ceiling(self, to_block: Optional[int]) -> int:
        """
        Resolves the last block a sync may read.

        An explicit `to_block` is still capped at the safe horizon: asking for a
        range that runs into the unfinalised tip is almost always an oversight,
        and honouring it would write reorg-vulnerable lots that the ledger cannot
        later retract.
        """
        safe_head = self.rpc.safe_block_number(self.confirmations)
        if to_block is None:
            return safe_head
        if to_block > safe_head:
            print(f"[INFO] Capping --to-block {to_block:,} at the reorg-safe head {safe_head:,} "
                  f"({self.confirmations} confirmations).")
        return min(int(to_block), safe_head)

    def sync_all(self, from_block: int = 0, to_block: Optional[int] = None,
                 include_clob: bool = True) -> List[Dict[str, Any]]:
        """Every configured wallet, concatenated and re-sorted into one chronological batch."""
        transactions: List[Dict[str, Any]] = []
        for wallet in self.wallets:
            wallet_txs = self.sync_wallet(wallet, from_block, to_block, include_clob)
            print(f"[SYNC] {wallet[:10]}...: {len(wallet_txs)} on-chain transactions")
            transactions.extend(wallet_txs)
        transactions.sort(key=lambda t: t["timestamp"])
        return transactions
