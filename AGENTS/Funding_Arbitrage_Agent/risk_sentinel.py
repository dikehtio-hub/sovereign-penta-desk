"""
Risk Sentinel module for Autonomous Funding Arbitrage Trading Agent.
Monitors position PnL, trailing profit locks, funding compression exits, and triggers emergency kill switches.
"""

from dataclasses import dataclass
import time
from typing import Dict, List, Tuple
from config import Config
from execution_manager import ExecutionManager, ActiveArbitragePosition

@dataclass
class TrailingData:
    pos_id: str
    activation_yield_usd: float
    highest_yield_usd: float
    is_activated: bool = False

class RiskSentinel:
    """
    Monitors all open positions continuously for risk thresholds, trailing profit locks, and funding compression.
    """
    def __init__(self, config: Config, execution_mgr: ExecutionManager):
        self.config = config
        self.execution_mgr = execution_mgr
        self.trailing_trackers: Dict[str, TrailingData] = {}

    def check_position_risk(
        self,
        pos: ActiveArbitragePosition,
        current_spread_apr: float,
        current_mark_price: float
    ) -> Tuple[bool, str]:
        """
        Evaluates risk parameters for a single position.
        Returns: (should_close: bool, reason: str)
        """
        if pos.is_closed:
            return False, "Position already closed"

        notional_val = pos.quantity * current_mark_price
        margin_used = notional_val / pos.leverage if pos.leverage > 0 else notional_val
        net_profit_usd = pos.accumulated_funding_usd + pos.unrealized_pnl_usd
        
        # Leveraged PnL percentage relative to margin
        leveraged_pnl_pct = (net_profit_usd / margin_used * 100.0) if margin_used > 0 else 0.0

        # 1. Check Funding Compression Exit (Spread collapsed below threshold)
        if current_spread_apr < self.config.EXIT_FUNDING_SPREAD_APR:
            return True, f"Funding compression: Spread collapsed to {current_spread_apr:.2f}% APR (< {self.config.EXIT_FUNDING_SPREAD_APR}% threshold)"

        # 2. Check Emergency Stop Loss
        if leveraged_pnl_pct <= self.config.EMERGENCY_STOP_LOSS_PCT:
            return True, f"Emergency Stop Loss hit at {leveraged_pnl_pct:.2f}% (Threshold: {self.config.EMERGENCY_STOP_LOSS_PCT}%)"

        # 3. Check Regular Stop Loss
        if leveraged_pnl_pct <= self.config.REGULAR_STOP_LOSS_PCT:
            return True, f"Regular Stop Loss hit at {leveraged_pnl_pct:.2f}% (Threshold: {self.config.REGULAR_STOP_LOSS_PCT}%)"

        # 4. Check Regular Take Profit
        if leveraged_pnl_pct >= self.config.REGULAR_TAKE_PROFIT_PCT:
            return True, f"Regular Take Profit hit at {leveraged_pnl_pct:.2f}% (Threshold: {self.config.REGULAR_TAKE_PROFIT_PCT}%)"

        # 5. Trailing Take Profit Sentinel
        if pos.position_id not in self.trailing_trackers:
            activation_target_usd = margin_used * (self.config.TRAILING_TP_ACTIVATION_PCT / 100.0)
            self.trailing_trackers[pos.position_id] = TrailingData(
                pos_id=pos.position_id,
                activation_yield_usd=activation_target_usd,
                highest_yield_usd=net_profit_usd,
                is_activated=False
            )

        tracker = self.trailing_trackers[pos.position_id]

        if not tracker.is_activated:
            if leveraged_pnl_pct >= self.config.TRAILING_TP_ACTIVATION_PCT:
                tracker.is_activated = True
                tracker.highest_yield_usd = net_profit_usd
        else:
            # Update peak yield
            if net_profit_usd > tracker.highest_yield_usd:
                tracker.highest_yield_usd = net_profit_usd
                
            # Check pullback from peak
            pullback_usd = tracker.highest_yield_usd - net_profit_usd
            allowed_pullback_usd = margin_used * (self.config.TRAILING_TP_CALLBACK_PCT / 100.0)
            
            if pullback_usd >= allowed_pullback_usd:
                return True, f"Trailing Take Profit triggered: Pulled back ${pullback_usd:.2f} from peak ${tracker.highest_yield_usd:.2f}"

        return False, "Healthy"

    async def audit_all_positions(self, current_rates_by_symbol: Dict[str, Dict]):
        """Audits all active positions and executes auto-close for triggered risks."""
        for pos_id, pos in list(self.execution_mgr.active_positions.items()):
            if pos.is_closed:
                continue

            symbol_rates = current_rates_by_symbol.get(pos.symbol, {})
            high_ex, low_ex, current_spread = 0.0, 0.0, pos.net_spread_apr
            
            mark_px = pos.entry_price
            if symbol_rates:
                rates_list = list(symbol_rates.values())
                if rates_list:
                    mark_px = rates_list[0].mark_price
                    
            should_close, reason = self.check_position_risk(pos, current_spread, mark_px)
            if should_close:
                await self.execution_mgr.close_arbitrage_position(pos_id, mark_px)

    async def emergency_kill_switch_all(self):
        """Unwinds all open arbitrage positions immediately."""
        for pos_id, pos in list(self.execution_mgr.active_positions.items()):
            if not pos.is_closed:
                await self.execution_mgr.close_arbitrage_position(pos_id, pos.entry_price)
