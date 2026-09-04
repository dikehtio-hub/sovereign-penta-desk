from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

# This is a helper function to calculate the Simple Moving Average (SMA)
def SMA(array, n):
    """Function to calculate the Simple Moving Average (SMA)"""
    return pd.Series(array).rolling(n).mean()

# This is the strategy class that your main script is looking for.
# The name 'FlagCont' must match exactly.
class FlagCont(Strategy):
    """
    A simple Flag Continuation breakout strategy.
    Looks for a strong upward move (pole) followed by a consolidation (flag).
    Enters a long position when the price breaks above the high of the flag.
    """
    # --- Strategy Parameters ---
    # These can be adjusted to change the strategy's behavior.
    pole_length = 20      # How many candles to look back for the "pole" (strong move).
    flag_length = 10      # How many candles to look for the consolidation "flag".
    breakout_strength = 1.05 # How much the pole must move (e.g., 1.05 = 5% move).
    stop_loss_pct = 0.02  # A 2% stop-loss from the entry price.
    take_profit_pct = 0.05 # A 5% take-profit from the entry price.

    def init(self):
        """
        This is the setup part of the strategy. It runs once at the beginning.
        """
        # We don't need any special indicators for this strategy, so we can leave this empty.
        pass

    def next(self):
        """
        This is the main logic. It runs for every candle in our data history.
        """
        # Ensure we have enough data to check for a pole and a flag.
        if len(self.data.Close) < self.pole_length + self.flag_length:
            return

        # --- Identify the Flag Pattern ---

        # 1. Define the time periods for the pole and the flag.
        flag_period = self.data.Close[-self.flag_length:]
        pole_period_start_index = -(self.pole_length + self.flag_length)
        pole_period_end_index = -self.flag_length
        pole_period = self.data.Close[pole_period_start_index:pole_period_end_index]

        # 2. Check for the "pole": a strong upward move.
        # The start of the pole should be significantly lower than the end.
        is_pole = pole_period[-1] > pole_period[0] * self.breakout_strength

        # 3. Check for the "flag": a consolidation period.
        # Find the highest high and lowest low during the flag period.
        flag_high = max(self.data.High[-self.flag_length:])
        flag_low = min(self.data.Low[-self.flag_length:])
        # The flag should be relatively flat (not a huge price range).
        is_flag = (flag_high - flag_low) < (pole_period[-1] - pole_period[0]) * 0.5

        # --- Trading Logic ---

        # Check if we have a valid flag pattern and are not already in a position.
        if is_pole and is_flag and not self.position:
            # 4. Check for a breakout: the current price must close above the flag's high.
            if self.data.Close[-1] > flag_high:
                # If all conditions are met, open a long position.
                # Set the stop-loss and take-profit levels for the trade.
                self.buy(
                    sl=self.data.Close[-1] * (1 - self.stop_loss_pct),
                    tp=self.data.Close[-1] * (1 + self.take_profit_pct)
                )
