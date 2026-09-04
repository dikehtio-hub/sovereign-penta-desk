# --- Step 1: Get all the tools we need ---

# Import the main Backtest and Strategy classes from the backtesting.py library.
from backtesting import Backtest, Strategy
# Import pandas, which is like a super-powered spreadsheet for Python.
import pandas as pd
# Import TA-Lib for fast technical analysis indicators like SMA.
import talib
# Import numpy, a tool for working with numbers, often used with pandas.
import numpy as np

# --- Step 2: Create our custom trading strategy ---

# We create our strategy by making a new "class" or blueprint that uses the library's Strategy blueprint.
class SMAPullbackStrategy(Strategy):
    """
    A trading strategy that buys when the price is over the 20-day SMA,
    and automatically sets a stop-loss at yesterday's low and a take-profit target.
    """
    # This is a setting for our strategy. We can easily change the SMA length here.
    sma_period = 20

    def init(self):
        """
        This is the setup part of our strategy. It runs only once at the very beginning.
        """
        # We tell the robot to get its own 'Close' price data.
        close_prices = self.data.Close
        # Then we tell it to calculate the SMA using TA-Lib on those close prices.
        # self.I() is a special way to tell backtesting.py to create an indicator.
        self.sma = self.I(talib.SMA, close_prices, self.sma_period)

    def next(self):
        """
        This is the main brain of our strategy. It runs for every single day in our data history.
        """
        # We get today's very latest closing price (the last one in the list).
        current_price = self.data.Close[-1]
        # We get the low price from the day right before today (yesterday's low).
        yesterdays_low = self.data.Low[-1] # [-1] gets the previous candle's low

        # Calculate our stop-loss price (yesterday's low).
        stop_loss_price = yesterdays_low
        # Calculate our take-profit price: move up 1.5 times the distance from
        # today's price to the stop-loss.
        take_profit_price = current_price + 1.5 * (current_price - stop_loss_price)

        # --- The Trading Rules ---

        # Rule 1: If the robot is NOT currently holding any Bitcoin (not self.position),
        # AND today's current price is HIGHER than the 20-day SMA, then BUY!
        if not self.position and current_price > self.sma[-1]:
            # Print a message to see what's happening.
            print(f"BUY signal! Current Price: {current_price:.2f}, SMA: {self.sma[-1]:.2f}, SL: {stop_loss_price:.2f}, TP: {take_profit_price:.2f}")
            # The robot buys Bitcoin. We automatically set the stop-loss (sl)
            # and take-profit (tp) prices. Backtesting.py will manage these for us.
            self.buy(sl=stop_loss_price, tp=take_profit_price)

        # Rule 2: If the robot IS holding Bitcoin (self.position.is_long is true,
        # or just self.position will work as a shortcut for any open position),
        # it doesn't need another 'else' statement here because the stop-loss
        # and take-profit set during the buy will automatically handle the exit.
        # We only take action if we want to buy or if those exits don't trigger.
        # For this strategy, the 'buy' logic handles the entry, and 'sl'/'tp' handle exits.
        pass

# --- Step 3: Load and Prepare the Data ---

# This is the full path to your data file on your computer.
# The 'r' at the beginning is a special instruction to make sure Windows paths work correctly.
data_path = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

# We use pandas to read your spreadsheet (CSV) file.
df = pd.read_csv(
    data_path,
    header=None,       # Your file doesn't have a title row, so we tell pandas that.
    skiprows=1,        # We tell pandas to skip the very first row, which contains the old titles.
    names=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'] # We give the columns names.
)

# Your data is in 15-minute chunks, but our strategy needs daily data.
# First, we tell pandas to understand the 'Timestamp' column as actual dates and times.
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
# Next, we make the 'Timestamp' column the main index, like the row numbers in a spreadsheet.
df.set_index('Timestamp', inplace=True)

# Now, we "resample" or convert the 15-minute data into daily ("D") data.
daily_df = df.resample('D').agg({
    'Open': 'first',      # The opening price for the day is the first one we see.
    'High': 'max',        # The high for the day is the highest price seen all day.
    'Low': 'min',         # The low for the day is the minimum price seen all day.
    'Close': 'last',      # The closing price for the day is the last one we see.
    'Volume': 'sum'       # The total volume is the sum of all trades for the day.
})

# Sometimes, there are days with no data (like weekends). This line removes those empty rows.
daily_df.dropna(inplace=True)


# --- Step 4: Set up and Run the Backtest ---

# We create the backtesting "engine" here.
bt = Backtest(
    daily_df,             # We give it our daily price data.
    SMAPullbackStrategy,  # We give it our custom trading strategy blueprint.
    cash=10000,           # We tell it to start with $10,000 in pretend money.
    commission=.001,      # We set a small 0.1% fee for each trade to make it realistic.
    exclusive_orders=True # This means only one trade can be open at a time.
)

# This command tells the engine to run the simulation.
stats = bt.run()

# --- Step 5: Show the Results ---

# This line prints a report of how well the strategy did.
print(stats)

# This line creates a beautiful chart of the trades and opens it in your web browser.
bt.plot()
