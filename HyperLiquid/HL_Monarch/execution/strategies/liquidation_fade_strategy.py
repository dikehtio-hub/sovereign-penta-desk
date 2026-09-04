"""
!!! RETIRED 2026-09-01 - DOES NOT TRADE. See FADE_STRATEGY_ENABLED in settings. !!!

The entry signal was measured as WRONG-SIDED by the MFE/MAE excursion benchmark:
0.513 against a random-entry control of 1.092 (n=466, 30m horizon), paired
t=-10.52, MAE exceeded MFE in 72.7% of events. Forced liquidations drive momentum,
not mean reversion - price continues through the cascade about twice as far as it
retraces. Deeper limit offsets improve the ratio monotonically (0.392 -> 0.555 at a
1.00% offset) but never reach parity, and cost fill rate.

Kept rather than deleted: this module and its ~100 tests are the record of what was
built and why it failed, and its paper-trading, fee and exit machinery is shared.
The INVERSE trade scores ~1.95 and may be worth a pre-registered test - but that is a
new strategy with taker entry economics, not a sign flip of this one.

Reactive Liquidation Fade Strategy (Paper Trading Simulator).

Purely reactive: it acts on a verified liquidation sweep that has already printed,
and takes no view on whether one was coming. The 24h predictive squeeze classifier
that used to gate this was retired on 2026-08-31 after its pre-registered
validation returned lift 0.351 against a 1.25x floor - it was not merely
uninformative but anti-predictive, so nothing here consults a squeeze score.

Sized for exotics as well as majors. A single $50k trigger meant the strategy could
only ever fire on BTC/ETH: measured over 10,443 exotic fills the median was $69 and
only 2 cleared $25k, so every liquidation the squeeze rotation now records on
exotics would have been ignored. The trigger scales with the market instead - a
$2k forced exit in a thin book is the same event as a $200k one in BTC.
"""
import time
from typing import Any, Dict, List, Optional

from execution.paper_trader import PaperTrader
from execution.risk_manager import STRATEGY_LIQUIDATION_FADE
from config.settings import (
    FADE_MIN_NOTIONAL_MAJOR,
    FADE_MIN_NOTIONAL_EXOTIC,
    FADE_EXOTIC_OI_CEILING,
    FADE_LIMIT_OFFSET_PCT,
    FADE_STOP_LOSS_PCT,
    FADE_TAKE_PROFIT_PCT,
    FADE_POSITION_MAX_HOLD_SECONDS,
    MAKER_FEE_PCT,
    TAKER_FEE_PCT,
    REGIME_ENABLED,
    REGIME_RSI_OVERSOLD,
    REGIME_RSI_OVERBOUGHT,
    REGIME_BLOCK_WHEN_UNKNOWN,
    FADE_ATR_OFFSET_MULT,
    FADE_ATR_OFFSET_FLOOR_PCT,
    FADE_ATR_TARGET_MULT,
    FADE_ATR_STOP_MULT,
    FADE_ATR_TARGET_FLOOR_PCT,
    FADE_USE_DYNAMIC_GEOMETRY,
)


class LiquidationFadeStrategy:
    def __init__(
        self,
        paper_trader: PaperTrader,
        fade_threshold_usd: float = FADE_MIN_NOTIONAL_MAJOR,
        position_size_usd: float = 10_000.0,
        take_profit_pct: float = FADE_TAKE_PROFIT_PCT,
        stop_loss_pct: float = FADE_STOP_LOSS_PCT,
        exotic_threshold_usd: float = FADE_MIN_NOTIONAL_EXOTIC,
        exotic_position_size_usd: float = 1_000.0,
        limit_offset_pct: float = FADE_LIMIT_OFFSET_PCT,
        use_limit_orders: bool = True,
        max_hold_seconds: float = FADE_POSITION_MAX_HOLD_SECONDS,
        regime_enabled: bool = REGIME_ENABLED,
        dynamic_geometry: bool = FADE_USE_DYNAMIC_GEOMETRY,
    ):
        self.trader = paper_trader
        self.threshold = fade_threshold_usd
        self.order_size_usd = position_size_usd
        self.tp_pct = take_profit_pct
        self.sl_pct = stop_loss_pct
        self.exotic_threshold = exotic_threshold_usd
        self.exotic_order_size_usd = exotic_position_size_usd
        self.limit_offset_pct = limit_offset_pct
        self.use_limit_orders = use_limit_orders
        self.max_hold_seconds = max_hold_seconds
        self.regime_enabled = regime_enabled
        self.dynamic_geometry = dynamic_geometry
        self.blocked_by_regime = 0

    @staticmethod
    def is_exotic(event: Dict[str, Any]) -> bool:
        """
        Whether to judge this event on the exotic scale.

        Uses the market's own open interest when the event carries it, falling
        back to the notional itself. A cascade is "big" relative to the book it
        happens in, not in absolute dollars.
        """
        oi = event.get("notional_oi")
        if oi is not None:
            try:
                return float(oi) < FADE_EXOTIC_OI_CEILING
            except (TypeError, ValueError):
                pass
        return float(event.get("notional") or 0.0) < FADE_MIN_NOTIONAL_MAJOR

    def thresholds_for(self, event: Dict[str, Any]):
        """(trigger_notional, position_size_usd) appropriate to this market."""
        if self.is_exotic(event):
            return self.exotic_threshold, self.exotic_order_size_usd
        return self.threshold, self.order_size_usd

    @staticmethod
    def regime_permits(order_side: str, regime: Optional[Dict[str, Any]],
                       rsi_oversold: float = REGIME_RSI_OVERSOLD,
                       rsi_overbought: float = REGIME_RSI_OVERBOUGHT,
                       block_when_unknown: bool = REGIME_BLOCK_WHEN_UNKNOWN) -> bool:
        """
        Whether the prevailing trend allows this fade.

            BUY  : price >= EMA  OR  RSI <= oversold
            SELL : price <= EMA  OR  RSI >= overbought

        The OR is the point. In an uptrend a dip is a dip and buying it is the
        trade; in a downtrend the same dip is a falling knife, and only a
        genuinely washed-out RSI justifies catching it. The unfiltered baseline
        had no such gate and lost GROSS by fading every waterfall it met.

        An unavailable regime BLOCKS by default: "unknown" is not "fine", and
        permitting on unknown would quietly reinstate the strategy just rejected.
        """
        if regime is None or not regime.get("sufficient"):
            return not block_when_unknown

        price, ema_v, rsi_v = regime.get("price"), regime.get("ema"), regime.get("rsi")
        if price is None or ema_v is None or rsi_v is None:
            return not block_when_unknown

        if order_side == "BUY":
            return price >= ema_v or rsi_v <= rsi_oversold
        return price <= ema_v or rsi_v >= rsi_overbought

    @staticmethod
    def geometry_for(regime: Optional[Dict[str, Any]],
                     static_offset_pct: float,
                     static_target_pct: float,
                     dynamic: bool = True,
                     static_stop_pct: Optional[float] = None):
        """
        (offset_pct, target_pct) scaled to this market's own volatility.

            offset = max(floor, 0.50 x ATR%)   - rest deeper in a violent market
            target = max(floor, 1.00 x ATR%)   - and aim proportionally further

        Both floors earn their place. Without the offset floor a quiet major
        rests inside its own noise; without the target floor a pure 1.0x ATR
        target on BTC is ~0.15%, of which the 4.5bp round-trip fee is ~31% - the
        strategy would hand a third of its gross edge to the exchange.

        Falls back to the static geometry when ATR is unavailable; `static_stop_pct`
        defaults to `static_target_pct` so the fallback stays 1:1 too.
        """
        if static_stop_pct is None:
            static_stop_pct = static_target_pct
        if not dynamic or not regime or regime.get("atr_pct") is None:
            return static_offset_pct, static_target_pct, static_stop_pct
        atr = float(regime["atr_pct"])
        offset = max(FADE_ATR_OFFSET_FLOOR_PCT, FADE_ATR_OFFSET_MULT * atr)
        target = max(FADE_ATR_TARGET_FLOOR_PCT, FADE_ATR_TARGET_MULT * atr)
        stop = max(FADE_ATR_TARGET_FLOOR_PCT, FADE_ATR_STOP_MULT * atr)
        return offset, target, stop

    def on_liquidation_event(
        self, event: Dict[str, Any], mark_price: float,
        regime: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Triggered when a liquidation or sweep occurs.

        A forced SELL cascade (side 'A') drives price below fair value -> fade by
        buying. A forced BUY cascade (side 'B') overshoots upward -> fade by
        selling. With limit orders the entry rests *deeper* into the move, so the
        fade is only taken if the cascade overshoots further; if it does not, the
        order simply never fills, which is the correct outcome.
        """
        notional = float(event.get("notional") or 0.0)
        coin = event.get("coin", "")
        side = event.get("side", "")

        if mark_price <= 0 or not coin:
            return None

        trigger, size_usd = self.thresholds_for(event)
        if notional < trigger:
            return None

        # One position per coin; a cascade prints many fills and should not
        # compound into an oversized position.
        if coin in self.trader.positions:
            return None
        if any(o["coin"] == coin for o in self.trader.open_orders):
            return None

        # Volatility-scaled geometry, falling back to the static percentages when
        # this market has no usable ATR.
        offset_pct, target_pct, stop_pct = self.geometry_for(
            regime, self.limit_offset_pct, self.tp_pct,
            dynamic=self.dynamic_geometry, static_stop_pct=self.sl_pct,
        )
        offset = offset_pct / 100.0
        sl_offset = stop_pct / 100.0
        tp_offset = target_pct / 100.0

        # Both legs sit the same distance from the limit, so the trade is 1:1 and
        # breaks even at a 50% win rate. Targeting the pre-cascade mark exactly
        # (the previous design) paired a ~0.5% reward with a 1.5% stop - roughly
        # 1:3, which needed >75% wins just to stand still.
        #
        # At a 0.5% offset the 0.65% target lands slightly BEYOND the pre-cascade
        # mark, which is the intended snapback: a cascade that reverts usually
        # overshoots its own starting point rather than stopping dead on it.
        if side == "A":      # forced selling -> fade long
            entry = mark_price * (1.0 - offset) if self.use_limit_orders else mark_price
            tp = entry * (1.0 + tp_offset)
            sl = entry * (1.0 - sl_offset)
            order_side = "BUY"
        elif side == "B":    # forced buying -> fade short
            entry = mark_price * (1.0 + offset) if self.use_limit_orders else mark_price
            tp = entry * (1.0 - tp_offset)
            sl = entry * (1.0 + sl_offset)
            order_side = "SELL"
        else:
            return None

        # Trend gate last, so a rejection is attributable to the regime
        # rather than to any of the earlier filters.
        if self.regime_enabled and not self.regime_permits(order_side, regime):
            self.blocked_by_regime += 1
            return None

        size = size_usd / entry
        if self.use_limit_orders:
            return self.trader.place_limit_order(
                coin=coin, side=order_side, size=size, limit_price=entry,
                leverage=10, stop_loss_px=sl, take_profit_px=tp,
            )
        return self.trader.place_market_order(
            coin=coin, side=order_side, size=size, current_price=entry,
            leverage=10, stop_loss_px=sl, take_profit_px=tp,
            fee_pct=TAKER_FEE_PCT,   # market-order mode crosses the book
        )

    def on_liquidation_batch(
        self, events, marks: Dict[str, float]
    ):
        """
        Feed a batch of liquidation events, then settle any resting orders.

        This is the entry point for live ingestion: the collector records
        liquidations for whatever the squeeze rotation currently has subscribed,
        so exotics reach the paper engine the same way majors always did.
        """
        placed = []
        for event in events or []:
            mark = marks.get(event.get("coin", ""))
            if not mark:
                continue
            result = self.on_liquidation_event(event, mark)
            if result and result.get("status") in ("OPEN", "FILLED"):
                placed.append(result)

        filled = self.trader.check_open_orders(marks)
        return {"placed": placed, "filled": filled}

    def on_liquidation_sweep(self, sweep: Dict[str, Any], pre_cascade_mark: float,
                             notional_oi: Optional[float] = None,
                             regime: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        React to a verified sweep the moment it prints on the trade feed.

        `pre_cascade_mark` is the mark in force *before* the sweep - the collector
        already tracks it from allMids/REST polling, and it is both the reversion
        target and the reference the fade rests beneath. Passing the sweep's own
        print price instead would anchor the trade to the dislocation it is
        trying to fade.
        """
        event = dict(sweep)
        if notional_oi is not None:
            event["notional_oi"] = notional_oi
        return self.on_liquidation_event(event, pre_cascade_mark, regime=regime)

    def check_open_positions(self, current_mids: Dict[str, float],
                             now_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Enforce take-profit, stop-loss and the time-stop on every open position.

        Until this existed, `stop_loss` and `take_profit` were merely *stored* on a
        filled position and nothing ever acted on them: a fade sat open forever and
        the reported PnL measured entries only. This is what turns the paper
        account into an actual measure of the strategy.

        Resolution order is deliberate:
          1. Stop first. If a tick straddles both levels we cannot know which
             traded first, so we assume the loss - a paper account that resolves
             ambiguity in its own favour is worth nothing.
          2. Then take-profit.
          3. Then the time-stop: a snapback that has not happened in ten minutes
             is not going to, and the position exits at the prevailing mid.
        """
        if not self.trader.positions:
            return []
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        closed = []

        for coin, pos in list(self.trader.positions.items()):
            mid = current_mids.get(coin)
            if mid is None or mid <= 0:
                continue

            size = float(pos.get("size") or 0.0)
            if size == 0:
                continue
            is_long = size > 0
            sl = pos.get("stop_loss")
            tp = pos.get("take_profit")

            exit_px = None
            reason = None

            # 1. Stop first (pessimistic).
            if sl:
                if (is_long and mid <= float(sl)) or (not is_long and mid >= float(sl)):
                    exit_px, reason = float(sl), "STOP_LOSS"

            # 2. Take-profit.
            if exit_px is None and tp:
                if (is_long and mid >= float(tp)) or (not is_long and mid <= float(tp)):
                    exit_px, reason = float(tp), "TAKE_PROFIT"

            # 3. Time-stop, at the prevailing mid rather than a level.
            if exit_px is None and self.max_hold_seconds:
                opened_at = float(pos.get("opened_at") or 0.0)
                if opened_at and (now_ms / 1000.0 - opened_at) >= self.max_hold_seconds:
                    exit_px, reason = float(mid), "TIME_STOP"

            if exit_px is None:
                continue

            # A take-profit rests as a limit and earns the maker rate; a stop or
            # a time-stop has to cross the book to get out and pays taker.
            fee_pct = MAKER_FEE_PCT if reason == "TAKE_PROFIT" else TAKER_FEE_PCT
            result = self.trader.place_market_order(
                coin=coin,
                side="SELL" if is_long else "BUY",   # flatten
                size=abs(size),
                current_price=exit_px,
                leverage=int(pos.get("leverage") or 10),
                fee_pct=fee_pct,
                strategy=STRATEGY_LIQUIDATION_FADE,
                exit_reason=reason,
            )
            if result.get("status") != "FILLED":
                continue
            result["exit_reason"] = reason
            result["entry_price"] = float(pos.get("entry_price") or 0.0)
            closed.append(result)

        return closed

    def wind_down(self) -> int:
        """
        Cancel every resting limit and report how many were pulled.

        A retired strategy must WIND DOWN, not freeze mid-flight. Disabling new
        placement alone left orders resting that could still fill and open real
        directional positions - the retirement would have removed the signal
        while leaving the exposure.
        """
        n = len(self.trader.open_orders)
        self.trader.open_orders.clear()
        return n

    def on_mids(self, current_mids: Dict[str, float],
                allow_fills: bool = True) -> Dict[str, Any]:
        """
        One tick of the live loop: settle resting limits, then manage positions.

        Order matters - an order that fills on this tick becomes a position that
        the same tick can legitimately stop out, which is what would happen in a
        real market during a fast cascade.

        `allow_fills=False` is the retired mode: resting orders are CANCELLED
        rather than filled, while open positions are still managed to their exits.
        Freezing exits instead would strand real exposure with nothing watching it.
        """
        if not allow_fills:
            cancelled = self.wind_down()
            closed = self.check_open_positions(current_mids)
            return {"filled": [], "closed": closed, "cancelled": cancelled}

        filled = self.trader.check_open_orders(current_mids)
        closed = self.check_open_positions(current_mids)
        return {"filled": filled, "closed": closed, "cancelled": 0}
