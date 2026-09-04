"""
Asynchronous Hyperliquid WebSocket Client for Real-Time Market Streaming.
Supports automatic reconnection with exponential backoff, application-level
heartbeat/ping-pong, multi-channel subscriptions, and dispatching.
"""
import asyncio
import json
import logging
import random
from typing import Callable, Dict, Any, List, Optional, Set
import websockets
from config.settings import WS_API_URL

logger = logging.getLogger(__name__)

# Hyperliquid drops connections that are idle for ~60s, so an application-level
# ping is required in addition to the protocol-level one negotiated by websockets.
HEARTBEAT_INTERVAL = 30.0
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 30.0


class HyperliquidWsClient:
    """Robust Async WebSocket Client for Hyperliquid."""

    def __init__(self, ws_url: str = WS_API_URL):
        self.ws_url = ws_url
        # Left untyped: the concrete connection class moved between websockets
        # major versions, and pinning the annotation breaks on upgrade.
        self.ws: Optional[Any] = None
        self._running = False
        self._subscriptions: Set[str] = set()
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._lock = asyncio.Lock()

    def register_handler(self, channel: str, handler: Callable[[Dict[str, Any]], None]):
        """Register a callback for messages on a specific channel."""
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

    async def subscribe_trades(self, coin: str):
        """Subscribe to real-time trade feed for a specific coin."""
        sub = {"type": "trades", "coin": coin}
        await self._subscribe(sub)

    async def subscribe_l2_book(self, coin: str):
        """Subscribe to L2 order book updates for a coin."""
        sub = {"type": "l2Book", "coin": coin}
        await self._subscribe(sub)

    async def subscribe_all_mids(self):
        """Subscribe to live allMids feed across all assets."""
        sub = {"type": "allMids"}
        await self._subscribe(sub)

    async def subscribe_explorer_block(self):
        """Subscribe to raw on-chain blocks and liquidation fills."""
        sub = {"type": "explorerBlock"}
        await self._subscribe(sub)

    async def subscribe(self, channel: str, params: Optional[Dict[str, Any]] = None):
        """
        Generic subscribe: `subscribe("trades", {"coin": "SKR"})`.

        The typed helpers above remain the normal path; this exists for callers
        that build subscriptions dynamically at runtime.
        """
        sub = {"type": channel}
        if params:
            sub.update(params)
        await self._subscribe(sub)

    async def unsubscribe(self, channel: str, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Drop a subscription and stop it being replayed on reconnect.

        Removing it from `_subscriptions` is the part that matters: without that,
        a rotated-out coin would silently come back on the next reconnect and the
        subscription set would only ever grow.

        Returns False if the subscription was not held.
        """
        sub = {"type": channel}
        if params:
            sub.update(params)
        sub_str = json.dumps(sub, sort_keys=True)

        async with self._lock:
            existed = sub_str in self._subscriptions
            self._subscriptions.discard(sub_str)
            ws = self.ws

        if existed and ws is not None:
            try:
                await ws.send(json.dumps({"method": "unsubscribe", "subscription": sub}))
            except Exception as e:
                logger.debug(f"Unsubscribe send failed for {sub}: {e}")
        return existed

    async def unsubscribe_trades(self, coin: str) -> bool:
        """Stop receiving the trade feed for one coin."""
        return await self.unsubscribe("trades", {"coin": coin})

    def active_subscriptions(self) -> List[Dict[str, Any]]:
        """Currently held subscriptions, as parsed dicts."""
        return [json.loads(x) for x in self._subscriptions]

    def subscribed_trade_coins(self) -> Set[str]:
        """Coins currently subscribed on the trades channel."""
        out: Set[str] = set()
        for sub in self.active_subscriptions():
            if sub.get("type") == "trades" and sub.get("coin"):
                out.add(sub["coin"])
        return out

    async def _subscribe(self, subscription_dict: Dict[str, Any]):
        sub_str = json.dumps(subscription_dict, sort_keys=True)
        async with self._lock:
            self._subscriptions.add(sub_str)
            ws = self.ws
        if ws is not None:
            try:
                msg = {
                    "method": "subscribe",
                    "subscription": subscription_dict
                }
                await ws.send(json.dumps(msg))
            except Exception as e:
                logger.debug(f"Subscription send skipped (not yet connected): {e}")

    async def _resubscribe_all(self, ws):
        """Resubscribe to all active topics upon reconnection."""
        # Snapshot under the lock: subscribe_* may be running concurrently and
        # mutating the set mid-iteration would raise RuntimeError.
        async with self._lock:
            pending = list(self._subscriptions)
        for sub_str in pending:
            sub_dict = json.loads(sub_str)
            msg = {
                "method": "subscribe",
                "subscription": sub_dict
            }
            await ws.send(json.dumps(msg))

    async def _heartbeat(self, ws):
        """Send an application-level ping so Hyperliquid does not reap the socket."""
        try:
            while self._running:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if not self._running:
                    return
                await ws.send(json.dumps({"method": "ping"}))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Heartbeat stopped: {e}")

    async def start(self):
        """Start the persistent WebSocket connection loop."""
        self._running = True
        reconnect_delay = RECONNECT_BASE_DELAY
        while self._running:
            heartbeat_task = None
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=15,
                    max_size=10_000_000
                ) as ws:
                    self.ws = ws
                    reconnect_delay = RECONNECT_BASE_DELAY  # healthy connection resets backoff
                    logger.info("Connected to Hyperliquid WebSocket feed")
                    await self._resubscribe_all(ws)
                    heartbeat_task = asyncio.create_task(self._heartbeat(ws))

                    while self._running:
                        try:
                            raw_msg = await ws.recv()
                            data = json.loads(raw_msg)
                            self._dispatch(data)
                        except websockets.ConnectionClosed:
                            logger.warning("WebSocket connection closed, reconnecting...")
                            break
                        except json.JSONDecodeError as e:
                            logger.warning(f"Discarding malformed WS frame: {e}")
                        except Exception as e:
                            logger.error(f"Error processing WS message: {e}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(
                    f"WebSocket connection error: {e}. Reconnecting in {reconnect_delay:.1f}s..."
                )
            finally:
                self.ws = None
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except (asyncio.CancelledError, Exception):
                        pass

            if not self._running:
                break
            # Back off on *every* reconnect path. Previously a server that closed
            # cleanly each time produced a hot loop with no delay at all.
            await asyncio.sleep(reconnect_delay + random.uniform(0.0, 0.5))
            reconnect_delay = min(RECONNECT_MAX_DELAY, reconnect_delay * 2.0)

    def _dispatch(self, data: Any):
        """Route parsed message to registered handler callbacks."""
        if isinstance(data, list):
            # explorerBlock or batch events
            for handler in self._handlers.get("explorerBlock", []):
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in explorerBlock handler: {e}")
            return

        if not isinstance(data, dict):
            return

        channel = data.get("channel")
        if not channel or channel in ("pong", "subscriptionResponse"):
            return

        for handler in self._handlers.get(channel, []):
            try:
                handler(data.get("data", data))
            except Exception as e:
                logger.error(f"Error in handler for channel {channel}: {e}")

    async def stop(self):
        """Stop client and close connection."""
        self._running = False
        ws = self.ws
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
