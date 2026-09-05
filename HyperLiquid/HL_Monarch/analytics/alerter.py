"""
Webhook & Real-Time Alerter for HL_Monarch.
Dispatches asynchronous notifications to Discord webhooks, Telegram bots,
and local terminal alerts on large whale executions, liquidation cascades, and margin calls.
"""
import json
import logging
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

from config.settings import (
    ALERT_EXOTIC_MIN_NOTIONAL,
    ALERT_EXOTIC_MIN_SLIPPAGE_PCT,
    ALERT_COOLDOWN_SECONDS,
)

logger = logging.getLogger("Alerter")

def _registry_user_env(name: str) -> Optional[str]:
    """The USER-level environment variable as Windows stores it (HKCU\\Environment); None elsewhere."""
    if os.name != "nt":
        return None
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        value, _kind = winreg.QueryValueEx(key, name)
    return str(value).strip() or None


def user_env(name: str, environ=None, registry=None) -> Optional[str]:
    """
    Round 54 (Ruling 54-6). A process only sees the environment it was born
    with, so a webhook written to the user's variables AFTER a service or
    dashboard started stays invisible to it. Look in os.environ first, then in
    the user-level registry value, so a relaunched or long-lived process finds
    the webhook without a fresh shell. Never raises.
    """
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    if value:
        return value
    registry = _registry_user_env if registry is None else registry
    try:
        value = registry(name)
    except Exception:                                       # noqa: BLE001 - missing key, no registry, anything
        return None
    value = str(value).strip() if value is not None else ""
    return value or None


class WebhookAlerter:
    def __init__(
        self,
        discord_webhook_url: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        cooldown_seconds: float = ALERT_COOLDOWN_SECONDS,
    ):
        self.discord_url = discord_webhook_url or user_env("DISCORD_WEBHOOK_URL")
        self.tg_token = telegram_bot_token or user_env("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = telegram_chat_id or user_env("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.discord_url or (self.tg_token and self.tg_chat_id))
        # Per-coin alert cooldown. One liquidation cascade prints many qualifying
        # fills within seconds - without this, a single event becomes a dozen
        # near-identical webhooks and the channel trains its readers to ignore it.
        # Keyed by (category, coin) so a margin-call warning is not swallowed by an
        # unrelated whale-trade alert on the same market.
        self.cooldown_seconds = cooldown_seconds
        self._last_alert_time: Dict[str, float] = {}
        self._cooldown_lock = threading.Lock()
        self.suppressed_count = 0
        # A liquidation cascade fires many alerts at once; a fixed pool keeps that
        # from spawning an unbounded number of webhook threads.
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hl-alert")

    def alert_whale_trade(self, coin: str, side: str, px: float, ntl: float, is_liq: bool = False):
        """Dispatch whale order alert."""
        if not self.should_send("whale" if not is_liq else "liquidation", coin):
            return
        icon = "💥 LIQUIDATION" if is_liq else "🐋 WHALE TRADE"
        title = f"{icon}: {side.upper()} {coin}"
        description = (
            f"**Asset:** `{coin}`\n"
            f"**Side:** `{side.upper()}`\n"
            f"**Notional:** `${ntl:,.2f}`\n"
            f"**Price:** `${px:,.2f}`\n"
            f"**Type:** `{'Forced Liquidation' if is_liq else 'Whale Execution'}`"
        )
        color = 0xFF0000 if is_liq or side.upper() in ("SELL", "A") else 0x00FF00
        self._dispatch_alert(title, description, color)

    @staticmethod
    def qualifies_as_exotic_sweep(
        notional: float,
        slippage_pct: float,
        min_notional: float = ALERT_EXOTIC_MIN_NOTIONAL,
        min_slippage_pct: float = ALERT_EXOTIC_MIN_SLIPPAGE_PCT,
    ) -> bool:
        """
        Whether a thin-book sweep is worth waking someone for.

        Size alone is the wrong test on an exotic: the median fill there is under
        $100, so a notional bar high enough to be meaningful on BTC filters out
        every real event. The exotic tier trades size for violence instead - a
        $2.5k fill printing 1.5% away from mark is a forced exit, not flow.
        """
        return abs(float(slippage_pct)) >= min_slippage_pct and float(notional) >= min_notional

    def alert_exotic_sweep(self, coin: str, side: str, px: float, ntl: float,
                           slippage_pct: float, mark_px: float = 0.0):
        """Dispatch an exotic thin-book sweep alert."""
        if not self.should_send("exotic_sweep", coin):
            return
        direction = "SELL-OFF" if str(side).upper() in ("A", "SELL") else "SQUEEZE"
        title = f"⚡ EXOTIC SWEEP: {direction} {coin}"
        description = (
            f"**Asset:** `{coin}`\n"
            f"**Side:** `{str(side).upper()}`\n"
            f"**Notional:** `${ntl:,.2f}`\n"
            f"**Price:** `${px:,.4f}`\n"
            f"**Slippage vs Mark:** `{slippage_pct:+.2f}%`"
            + (f"\n**Mark:** `${mark_px:,.4f}`" if mark_px else "")
            + "\n**Type:** `Thin-book forced exit`"
        )
        self._dispatch_alert(title, description, 0x9B59B6)

    def alert_danger_position(self, address: str, coin: str, dist_pct: float, val: float, liq_px: float):
        """Dispatch margin call danger warning."""
        if not self.should_send(f"margin:{address[:10]}", coin):
            return
        title = f"⚠️ MARGIN CALL DANGER: {address[:8]}... ({coin})"
        description = (
            f"**Address:** `{address}`\n"
            f"**Asset:** `{coin}`\n"
            f"**Distance to Liq:** `{dist_pct:.2f}%`\n"
            f"**Position Size:** `${val:,.2f}`\n"
            f"**Liquidation Price:** `${liq_px:,.2f}`"
        )
        self._dispatch_alert(title, description, 0xFFA500)

    def alert_funding_arb(self, coin: str, apr: float, strategy: str):
        """Dispatch extreme funding yield opportunity alert."""
        if not self.should_send("funding", coin):
            return
        title = f"📈 FUNDING HARVEST: {coin} ({apr:+.1f}% APR)"
        description = (
            f"**Asset:** `{coin}`\n"
            f"**Annualized Yield:** `{apr:+.2f}% APR`\n"
            f"**Recommended Strategy:** `{strategy}`"
        )
        self._dispatch_alert(title, description, 0x00BFFF)

    def alert_service_down(self, pid, reason: str = "process gone"):
        """Round 53 (Ruling 53-2): the collector service died under a read-only dashboard."""
        if not self.should_send("service", "COLLECTOR"):
            return
        self._dispatch_alert("🛑 COLLECTOR SERVICE DOWN",
                             f"**Service PID:** `{pid}`\n**Reason:** `{reason}`\n"
                             "**Effect:** no ingestion until relaunched (the dashboard's watchdog tries once per cooldown)",
                             0xFF0000)

    def alert_service_abandoned(self, pid, attempts: int):
        """Round 54 (Ruling 54-2): the watchdog gave up; a human has to look. Its own cooldown key so the
        service-down alert of the same episode never swallows it."""
        if not self.should_send("abandoned", "COLLECTOR"):
            return
        self._dispatch_alert("🚨 COLLECTOR WATCHDOG GAVE UP",
                             f"**Service PID:** `{pid}`\n**Relaunches issued:** `{attempts}` - the service never came back\n"
                             "**Likely cause:** a live process holds data/collector_service.pid, or the launcher fails\n"
                             "**Action:** run start_collector.bat by hand and read data/collector_service.jsonl; "
                             "the watchdog resumes once the service is seen alive",
                             0xFF0000)

    def alert_status_stale(self, age_seconds: float, max_age_seconds: float):
        """Round 53 (Ruling 53-2): the collector status file is older than its window while the service is alive."""
        if not self.should_send("status", "COLLECTOR"):
            return
        self._dispatch_alert("⚠️ COLLECTOR STATUS STALE",
                             f"**Age:** `{age_seconds / 3600.0:.1f}h` (window `{max_age_seconds / 3600.0:.1f}h`)\n"
                             "**Meaning:** the hourly cycle is not writing collector_status.json - check data/collector.log",
                             0xFFA500)

    def _cooldown_key(self, category: str, coin: str) -> str:
        return f"{category}:{str(coin).strip().upper()}"

    def should_send(self, category: str, coin: str, now: Optional[float] = None) -> bool:
        """
        Whether this (category, coin) is outside its cooldown window.

        Consumes the slot when it returns True, so concurrent callers during a
        cascade cannot both pass the check for the same market.
        """
        if self.cooldown_seconds is None or self.cooldown_seconds <= 0:
            return True
        now = time.monotonic() if now is None else now
        key = self._cooldown_key(category, coin)
        with self._cooldown_lock:
            last = self._last_alert_time.get(key)
            if last is not None and (now - last) < self.cooldown_seconds:
                self.suppressed_count += 1
                return False
            self._last_alert_time[key] = now
            return True

    def reset_cooldowns(self):
        """Clear all cooldown state (used by tests and on reconfiguration)."""
        with self._cooldown_lock:
            self._last_alert_time.clear()
            self.suppressed_count = 0

    def _dispatch_alert(self, title: str, description: str, color: int = 0x00FF00):
        """Asynchronously dispatch to configured webhooks."""
        def send_task():
            # 1. Send Discord Webhook
            if self.discord_url:
                try:
                    payload = {
                        "embeds": [{
                            "title": title,
                            "description": description,
                            "color": color,
                            "footer": {"text": "HL_Monarch Market Intelligence Suite"}
                        }]
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        self.discord_url,
                        data=data,
                        headers={"Content-Type": "application/json", "User-Agent": "HL_Monarch"}
                    )
                    urllib.request.urlopen(req, timeout=5).close()
                except Exception as e:
                    logger.warning(f"Failed to send Discord alert: {e}")

            # 2. Send Telegram Alert
            if self.tg_token and self.tg_chat_id:
                try:
                    clean_text = f"*{title}*\n\n{description.replace('**', '*').replace('`', '')}"
                    url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
                    payload = {
                        "chat_id": self.tg_chat_id,
                        "text": clean_text,
                        "parse_mode": "Markdown"
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={"Content-Type": "application/json", "User-Agent": "HL_Monarch"}
                    )
                    urllib.request.urlopen(req, timeout=5).close()
                except Exception as e:
                    logger.warning(f"Failed to send Telegram alert: {e}")

        try:
            self._pool.submit(send_task)
        except RuntimeError:
            logger.debug("Alerter pool shut down; dropping alert.")

    def shutdown(self, wait: bool = False):
        """Stop accepting new webhook dispatches."""
        self._pool.shutdown(wait=wait)
