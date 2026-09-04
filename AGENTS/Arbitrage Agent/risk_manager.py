"""
Risk Management & Off-Ramp Milestone Guard for Base L2 Arbitrage Agent
"""

from termcolor import cprint
import config

class RiskManager:
    def __init__(
        self,
        starting_usdc: float = None,
        gas_reserve_eth: float = None,
        offramp_trigger: float = None,
    ):
        self.starting_usdc = starting_usdc or config.CAPITAL_CONFIG["WORKING_USDC"]
        self.current_usdc = self.starting_usdc
        self.gas_reserve_eth = gas_reserve_eth or config.CAPITAL_CONFIG["GAS_RESERVE_ETH"]
        self.offramp_trigger_usdc = offramp_trigger or config.CAPITAL_CONFIG["OFFRAMP_TRIGGER_USDC"]
        self.consecutive_reverts = 0
        self.max_consecutive_reverts = config.CAPITAL_CONFIG["MAX_CONSECUTIVE_REVERTS"]
        self.min_gas_reserve_eth = config.CAPITAL_CONFIG["MIN_GAS_RESERVE_ETH"]
        self.total_net_pnl = 0.0
        self.total_trades_executed = 0

    def record_trade_result(self, result: dict) -> dict:
        """
        Updates PnL, tracks consecutive reverts, and checks off-ramp milestones.
        """
        status = result.get("status")

        if status == "SUCCESS":
            self.consecutive_reverts = 0
            net_profit = result.get("net_profit_usd", 0.0)
            gas_used = result.get("gas_used_eth", 0.00008)
            
            self.current_usdc += net_profit
            self.gas_reserve_eth -= gas_used
            self.total_net_pnl += net_profit
            self.total_trades_executed += 1

            # Check Off-Ramp Milestone Trigger
            if self.current_usdc >= self.offramp_trigger_usdc:
                harvest_amount = self.current_usdc - self.starting_usdc
                cprint(
                    f"\n[MILESTONE ALERT] OFF-RAMP TRIGGER REACHED! Wallet Balance: ${self.current_usdc:.2f} USDC",
                    "white",
                    "on_green",
                    attrs=["bold"],
                )
                cprint(
                    f"ACTION RECOMMENDED: Transfer +${harvest_amount:.2f} USDC profit back to Coinbase (leaving ${self.starting_usdc:.2f} principal).",
                    "green",
                )
                return {"circuit_breaker": False, "offramp_triggered": True, "harvest_amount": harvest_amount}

            return {"circuit_breaker": False, "offramp_triggered": False}

        elif status == "REVERTED":
            self.consecutive_reverts += 1
            gas_used = result.get("gas_used_eth", 0.00002)
            self.gas_reserve_eth -= gas_used

            if self.consecutive_reverts >= self.max_consecutive_reverts:
                cprint(
                    f"\n[CIRCUIT BREAKER] {self.consecutive_reverts} Consecutive Reverts Detected! Pausing Bot to preserve gas.",
                    "white",
                    "on_red",
                    attrs=["bold"],
                )
                # Reset the streak so the pause actually buys a fresh 3-strike window.
                # Without this, a single revert right after the pause would re-trip
                # the breaker immediately instead of requiring 3 more in a row.
                self.consecutive_reverts = 0
                return {"circuit_breaker": True, "offramp_triggered": False}

            return {"circuit_breaker": False, "offramp_triggered": False}

        elif status == "LIVE_PENDING":
            # Live on-chain execution isn't implemented yet (see ExecutionEngine /
            # README "Going Live"), so there is nothing real to record. Surface
            # that loudly rather than silently skipping PnL/gas tracking.
            cprint(
                "[WARNING] LIVE_PENDING result received — on-chain execution and PnL "
                "tracking are not implemented yet. This trade was NOT recorded.",
                "yellow",
            )
            return {"circuit_breaker": False, "offramp_triggered": False}

        return {"circuit_breaker": False, "offramp_triggered": False}

    def check_gas_reserve(self) -> bool:
        """
        Ensures ETH gas reserve remains above minimum threshold.
        """
        return self.gas_reserve_eth >= self.min_gas_reserve_eth
