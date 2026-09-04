# =============================================================================
# PURPOSE: Turtle Trading Strategy — Backtest (Basic Version)
# =============================================================================
#
# WHAT THIS DOES:
#   Runs a backtest of the Turtle Trading strategy on BTC-USD 15-minute data.
#   - Enters trades on 55-bar breakouts (long above highs, short below lows)
#   - Exits with a 0.2% take-profit or a 2×ATR stop-loss
#   - Only trades during market hours (9:30 AM – 4:00 PM EST)
#   - Closes all positions at end-of-day Friday
#
# WHAT IT PRODUCES:
#   1. Console output with backtest stats (return %, Sharpe, drawdown, etc.)
#   2. An interactive HTML chart file (e.g. "TurtleStrategy.html") that opens
#      in your browser. This chart shows candlesticks, trade entry/exit markers,
#      the equity curve, drawdowns, and indicator overlays. You can zoom, pan,
#      and hover over individual trades to inspect them.
#
# HOW TO RUN:
#   conda activate KID3
#   python turtle_backtest.py
#   (or: & "C:\Users\ixis1\anaconda\envs\KID3\python.exe" turtle_backtest.py)
#
# SEE ALSO:
#   turtle_algo.py — Refined version with pyramiding, ATR position sizing,
#                     channel-based exits, and System 1 / System 2 support.
# =============================================================================

# --- Step 1: Get all the tools we need ---

# Import the main Backtest and Strategy classes from the backtesting.py library.
from backtesting import Backtest, Strategy
# Import pandas for handling our data.
import pandas as pd
# Import TA-Lib for calculating the Average True Range (ATR).
import talib

# --- Step 2: Create the Turtle Trading Strategy ---

class TurtleStrategy(Strategy):
    """
    A backtesting implementation of the Turtle Trading strategy with specific time constraints.
    - Enters on a 55-bar breakout.
    - Exits on a 0.2% take-profit or a stop-loss of 2x ATR.
    - Only trades between 9:30 AM and 4:00 PM EST.
    - Closes all positions at the end of the day on Friday.
    """
    # --- Strategy Parameters (these can be easily changed) ---
    lookback_period = 55      # The number of bars to look back for a breakout (55 in the original).
    take_profit_pct = 0.002   # The take-profit target (0.2% = 0.002).
    atr_multiplier = 2.0      # The multiplier for the ATR stop-loss (2N).
    atr_period = 14           # The standard period for calculating ATR.

    def init(self):
        """
        This is the setup part of the strategy. It runs once at the beginning.
        """
        # Calculate the Average True Range (ATR) indicator using TA-Lib.
        # We need the High, Low, and Close prices for this calculation.
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)

        # Calculate the highest high and lowest low over the last 55 bars.
        # The self.I() function tells the library to create these as indicators that update automatically.
        self.highest_high = self.I(lambda x: pd.Series(x).rolling(self.lookback_period).max(), self.data.High)
        self.lowest_low = self.I(lambda x: pd.Series(x).rolling(self.lookback_period).min(), self.data.Low)


    def next(self):
        """
        This is the main brain of the strategy. It runs for every single candle in our data history.
        """
        # Get the current time from the data's index. We make it timezone-aware (EST).
        current_time = self.data.index[-1].tz_localize('UTC').tz_convert('US/Eastern')
        current_price = self.data.Close[-1]

        # --- Time-Based Rules ---

        # Rule 1: Check if we are within the allowed trading hours (9:30 AM to 4:00 PM EST).
        is_trading_hours = (current_time.hour == 9 and current_time.minute >= 30) or \
                           (current_time.hour > 9 and current_time.hour < 16)

        # Rule 2: Check if it's Friday and near the end of the trading day.
        # We close positions a few minutes before 4 PM to be safe.
        is_friday_eod = (current_time.weekday() == 4 and current_time.hour == 15 and current_time.minute >= 55)

        # If it's Friday end-of-day and we have a position, close it.
        if is_friday_eod and self.position:
            self.position.close()
            return # Stop processing for this candle after closing.

        # If we are outside of trading hours, do nothing.
        if not is_trading_hours:
            return

        # --- Entry and Exit Logic ---

        # Get the previous bar's breakout levels. We use [-2] because the most recent value [-1]
        # is still being formed by the current price.
        breakout_high = self.highest_high[-2]
        breakout_low = self.lowest_low[-2]
        
        # Get the current ATR value.
        current_atr = self.atr[-1]

        # --- Entry Rules ---
        # We only look for new trades if we are not already in a position.
        if not self.position:
            # Long Entry: If the current price breaks above the 55-bar high.
            if current_price > breakout_high:
                # Calculate the stop-loss price (2 * ATR below the current price).
                sl = current_price - (current_atr * self.atr_multiplier)
                # Calculate the take-profit price (0.2% above the current price).
                tp = current_price * (1 + self.take_profit_pct)
                # Place the buy order with the calculated stop-loss and take-profit.
                self.buy(sl=sl, tp=tp)

            # Short Entry: If the current price breaks below the 55-bar low.
            elif current_price < breakout_low:
                # Calculate the stop-loss price (2 * ATR above the current price).
                sl = current_price + (current_atr * self.atr_multiplier)
                # Calculate the take-profit price (0.2% below the current price).
                tp = current_price * (1 - self.take_profit_pct)
                # Place the sell (short) order with the calculated stop-loss and take-profit.
                self.sell(sl=sl, tp=tp)


# --- Step 3: Load and Prepare the Data ---

# Define the full path to your 15-minute data file.
data_path = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

# Load the data using pandas.
df = pd.read_csv(
    data_path,
    header=None,
    skiprows=1,
    names=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
)

# Convert the 'Timestamp' column to actual datetime objects.
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
# Set the 'Timestamp' column as the main index for our data.
df.set_index('Timestamp', inplace=True)


# --- Step 4: Set up and Run the Backtest ---

# Create the backtesting engine.
bt = Backtest(
    df,                   # We provide our 15-minute data.
    TurtleStrategy,       # We tell it to use our custom Turtle strategy.
    cash=10000,           # Start with $10,000.
    commission=.001,      # Set a 0.1% trading fee.
    exclusive_orders=True # Ensure only one trade is open at a time.
)

# Run the simulation.
stats = bt.run()


# --- Step 5: Show the Results ---

# Print the final statistics report.
print(stats)

# Create and open a beautiful interactive chart of the backtest in a web browser.
bt.plot()
