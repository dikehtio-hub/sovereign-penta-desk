"""
High-Performance, Zero-Dependency Hyperliquid REST Client.
Implements weight-aware Token Bucket Rate Limiting, Retry with Exponential Backoff + jitter,
and Type-Safe parsing.
"""
import json
import random
import time
import urllib.request
import urllib.error
import threading
from typing import Dict, Any, List, Optional
from config.settings import (
    REST_API_URL,
    EXCHANGE_API_URL,
    TESTNET_EXCHANGE_API_URL,
    REQUEST_TIMEOUT_SECONDS,
    MAX_REQUEST_WEIGHT_PER_MINUTE,
    RATE_LIMIT_SAFETY_FACTOR,
    DEFAULT_REQUEST_WEIGHT,
    REQUEST_WEIGHTS,
)


def weight_for(request_type: str) -> int:
    """Published Hyperliquid /info weight for a request type."""
    return REQUEST_WEIGHTS.get(request_type, DEFAULT_REQUEST_WEIGHT)


class TokenBucketRateLimiter:
    """
    Thread-safe weight-aware Token Bucket Rate Limiter.

    Tokens are *weight units*, not requests: Hyperliquid meters /info by request
    weight (1200 weight/min per IP), and a metaAndAssetCtxs call costs 20 while an
    l2Book call costs 2. Counting raw requests under-counts heavy calls 10x.
    """

    def __init__(
        self,
        weight_per_minute: int = MAX_REQUEST_WEIGHT_PER_MINUTE,
        safety_factor: float = RATE_LIMIT_SAFETY_FACTOR,
    ):
        budget = float(weight_per_minute) * float(safety_factor)
        self.capacity = budget
        self.tokens = budget
        self.fill_rate = budget / 60.0  # weight units per second
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: float = DEFAULT_REQUEST_WEIGHT):
        """Block until `tokens` weight units are available, then spend them."""
        # A single request can never cost more than the whole bucket.
        tokens = min(float(tokens), self.capacity)
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # Calculate sleep duration needed
                sleep_time = (tokens - self.tokens) / self.fill_rate
            time.sleep(max(0.01, sleep_time))


class HyperliquidRestClient:
    """Direct client for Hyperliquid Info REST API."""

    def __init__(
        self,
        base_url: str = REST_API_URL,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url
        # Shared by default: the budget is per-IP, so every client in the process
        # must draw from one bucket or the ceiling is silently multiplied.
        self.rate_limiter = rate_limiter or _shared_rate_limiter()
        self.timeout = timeout

    @staticmethod
    def _retry_after_seconds(err: urllib.error.HTTPError) -> Optional[float]:
        """Honor a server-supplied Retry-After header when present."""
        try:
            raw = err.headers.get("Retry-After") if err.headers else None
        except Exception:
            return None
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return None

    def _post(self, payload: Dict[str, Any], url: Optional[str] = None,
              max_retries: int = 3, idempotent: bool = True) -> Any:
        """
        POST to Hyperliquid with weight-aware limiting and retry logic.

        `idempotent` says whether a retry is SAFE, and it is False for anything
        that places an order. Info reads can be repeated freely; a submission
        cannot. A 5xx or a timeout arrives with the request's fate unknown - the
        order may already be resting - and re-sending it there is how a "failed"
        order becomes two positions, or (because the nonce is fixed inside the
        signed payload) how a resting order comes back as a confident duplicate-
        nonce REJECTION that invites the caller to place it again.

        A 429 is different and stays retryable either way: it is refused on the
        rate limiter, before the matching engine ever sees it.
        """
        target_url = url or self.base_url
        encoded_data = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'HL_Monarch_Terminal/1.0'
        }
        # If payload is an EIP-712 action, extract action type; otherwise use request type
        req_type = payload.get("type", "")
        if not req_type and "action" in payload:
            req_type = payload.get("action", {}).get("type", "order")
        cost = weight_for(req_type)

        last_error = None
        for attempt in range(max_retries):
            self.rate_limiter.acquire(cost)
            req = urllib.request.Request(target_url, data=encoded_data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = resp.read().decode('utf-8')
                    return json.loads(resp_data)
            except urllib.error.HTTPError as e:
                last_error = e
                # A 429 never reached the matching engine, so it is always safe
                # to repeat. A 5xx is only safe to repeat for a read.
                retryable = e.code == 429 or (idempotent and e.code in (500, 502, 503, 504))
                if retryable:
                    if attempt == max_retries - 1:
                        break
                    retry_after = self._retry_after_seconds(e)
                    # Jitter avoids every in-flight caller retrying in lockstep.
                    backoff = retry_after if retry_after is not None else (2 ** attempt) * 0.5
                    time.sleep(backoff + random.uniform(0.0, 0.25))
                    continue
                if not idempotent and e.code in (500, 502, 503, 504):
                    raise RuntimeError(
                        f"Hyperliquid returned {e.code} on a SUBMITTED action. NOT "
                        f"retrying: the request may already have been accepted and "
                        f"the order may be resting. ORDER STATE UNKNOWN - reconcile "
                        f"on the cloid before re-sending, or a retry duplicates it."
                    ) from e
                raise
            except Exception as e:
                last_error = e
                if not idempotent:
                    raise RuntimeError(
                        f"Transport failure on a SUBMITTED action "
                        f"({type(e).__name__}: {e}). NOT retrying: the order may "
                        f"already be resting. ORDER STATE UNKNOWN - reconcile on the "
                        f"cloid before re-sending, or a retry duplicates it."
                    ) from e
                if attempt == max_retries - 1:
                    break
                time.sleep((2 ** attempt) * 0.5 + random.uniform(0.0, 0.25))
                continue

        raise RuntimeError(f"Failed Hyperliquid POST request after {max_retries} retries: {last_error}")

    def post_action(self, payload: Dict[str, Any], testnet: bool = True) -> Dict[str, Any]:
        """
        Submit a signed EIP-712 action to the Hyperliquid /exchange endpoint.
        
        testnet: If True, submits to testnet exchange API; if False, to mainnet.
        payload: The signed action dict containing action, nonce, signature, vaultAddress.
        """
        target_url = TESTNET_EXCHANGE_API_URL if testnet else EXCHANGE_API_URL
        # idempotent=False: this places an order. See `_post`.
        return self._post(payload, url=target_url, idempotent=False)

    def get_open_orders(self, user_address: str) -> List[Dict[str, Any]]:
        """Fetch all open resting orders for a user."""
        return self._post({"type": "openOrders", "user": user_address})

    def get_order_status(self, user_address: str, oid: int) -> Dict[str, Any]:
        """Fetch status of a specific order by user and order ID (oid)."""
        return self._post({"type": "orderStatus", "user": user_address, "oid": oid})

    def get_meta_and_asset_ctxs(self, dex: Optional[str] = None) -> List[Any]:
        """
        Fetch universe metadata and real-time asset contexts.
        dex: None or "main" for default crypto perp DEX, "xyz" for TradFi DEX, "km", "flx", "cash", "para", etc.
        Returns [universe_metadata, asset_contexts]
        """
        payload = {"type": "metaAndAssetCtxs"}
        if dex and dex.lower() != "main":
            payload["dex"] = dex
        return self._post(payload)

    def get_all_perp_metas(self) -> List[Any]:
        """Fetch perpetual market metadata for all DEXes."""
        return self._post({"type": "allPerpMetas"})

    def get_perp_dexs(self) -> List[Any]:
        """Fetch list and configurations of all HIP-3 perp DEXes."""
        return self._post({"type": "perpDexs"})

    def get_spot_meta(self) -> Dict[str, Any]:
        """Fetch the spot universe (token list), used to test for a hedgeable spot leg."""
        return self._post({"type": "spotMeta"})

    def get_all_mids(self) -> Dict[str, str]:
        """Fetch mid prices across all coins."""
        return self._post({"type": "allMids"})

    def get_l2_book(self, coin: str) -> Dict[str, Any]:
        """Fetch L2 order book snapshot for a specific coin (e.g. 'BTC' or 'xyz:TSLA')."""
        return self._post({"type": "l2Book", "coin": coin})

    def get_recent_trades(self, coin: str) -> List[Dict[str, Any]]:
        """Fetch recent executions for a coin."""
        return self._post({"type": "recentTrades", "coin": coin})

    def get_clearinghouse_state(self, user_address: str) -> Dict[str, Any]:
        """Fetch user account state and positions."""
        return self._post({"type": "clearinghouseState", "user": user_address})


_SHARED_LIMITER: Optional[TokenBucketRateLimiter] = None
_SHARED_LIMITER_LOCK = threading.Lock()


def _shared_rate_limiter() -> TokenBucketRateLimiter:
    """Process-wide limiter, since Hyperliquid's weight budget is per-IP."""
    global _SHARED_LIMITER
    with _SHARED_LIMITER_LOCK:
        if _SHARED_LIMITER is None:
            _SHARED_LIMITER = TokenBucketRateLimiter()
        return _SHARED_LIMITER
