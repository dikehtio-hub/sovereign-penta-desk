# --- Step 1: Get all the tools we need ---

# Import the main Backtest and Strategy classes from the backtesting.py library.
from backtesting import Backtest, Strategy
# Import the pandas library, which is like a super-powered spreadsheet for Python.
import pandas as pd

# --- Step 2: Create our custom trading strategy ---

# This is a helper function to calculate the Simple Moving Average (SMA).
def SMA(array, n):
    """A helper function to calculate the Simple Moving Average (SMA)."""
    # We turn our price history into a pandas Series and use its built-in rolling mean tool.
    return pd.Series(array).rolling(n).mean()

# We create our strategy by making a new "class" or blueprint that uses the library's Strategy blueprint.
class SmaAndLow(Strategy):
    """
    A trading strategy with the following rules:
    - Buy if the price is above the 20-day SMA.
    - Sell if the price drops below the previous day's low.
    """
    # This is a setting for our strategy. We can easily change the SMA length here.
    sma_period = 20

    def init(self):
        """
        This is the setup part of our strategy. It runs only once at the very beginning.
        """
        # We tell the strategy to calculate the 20-day SMA on the closing prices.
        # The self.I() function is a special way to tell the library to create an indicator.
        self.sma = self.I(SMA, self.data.Close, self.sma_period)

    def next(self):
        """
        This is the main brain of our strategy. It runs for every single day in our data history.
        """
        # We get the current closing price for today.
        current_price = self.data.Close[-1]
        # We get the low price from yesterday. `[-1]` is today's own (current) bar in
        # backtesting.py's indexing -- `[-2]` is the previous bar, i.e. yesterday.
        yesterdays_low = self.data.Low[-2]

        # --- The Buy Rule ---
        # First, we check if we are NOT already holding a position.
        if not self.position:
            # Next, we check if today's price is higher than the 20-day SMA.
            if current_price > self.sma[-1]:
                # If both things are true, we buy!
                self.buy()

        # --- The Sell Rule ---
        # We only check this rule if we ARE currently in a position.
        else:
            # We check if today's price has dropped below yesterday's low price.
            if current_price < yesterdays_low:
                # If it has, we sell our position.
                self.position.close()

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
    'High': 'max',        # The high for the day is the maximum price seen all day.
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
    SmaAndLow,            # We give it our custom trading strategy blueprint.
    cash=10000,           # We tell it to start with $10,000 in pretend money.
    commission=.001       # We set a small 0.1% fee for each trade to make it realistic.
)

# This command tells the engine to run the simulation.
stats = bt.run()

# --- Step 5: Show the Results ---

# This line prints a report of how well the strategy did.
print(stats)

# This line creates a beautiful chart of the trades and opens it in your web browser.
bt.plot()