# --- Step 1: Import all the tools we need ---

# Import the main Backtest and Strategy classes from the backtesting.py library.
from backtesting import Backtest, Strategy
# Import a helper tool to check for when one line crosses another.
from backtesting.lib import crossover
# Import the pandas library, which is excellent for handling data like our price history.
import pandas as pd

# --- Step 2: Create our custom trading strategy ---

# This function will calculate the Simple Moving Average (SMA) for a given set of data.
def SMA(array, n):
    """Function to calculate the Simple Moving Average (SMA)"""
    # Create a pandas Series (a column of data) and use its built-in rolling mean function.
    return pd.Series(array).rolling(n).mean()

# We create our strategy by making a new class that inherits from the library's Strategy class.
class SmaCross(Strategy):
    """
    A trading strategy based on a Simple Moving Average (SMA) Crossover.
    """
    # Define a parameter for the length of the moving average. We can change this later.
    n1 = 5  # The period for the 5-day SMA.

    def init(self):
        """
        This is the setup part of our strategy. It runs only once at the very beginning.
        """
        # Get the closing price data for our asset.
        price = self.data.Close
        # Create our 20-day SMA indicator. The self.I() function tells backtesting.py
        # to apply our SMA function to the closing price data.
        self.sma1 = self.I(SMA, price, self.n1)

    def next(self):
        """
        This is the main logic of our strategy. It runs for every single day in our data history.
        """
        # The crossover() function checks if the first value just crossed above the second value.
        # Here, we check if the closing price just crossed above our 20-day SMA.
        if crossover(self.data.Close, self.sma1):
            # If it crossed above, it's a buy signal.
            # self.buy() will open a long position using all our available cash.
            self.buy()

        # This checks if the SMA just crossed above the price (meaning the price crossed below).
        elif crossover(self.sma1, self.data.Close):
            # If the price crossed below, it's a sell signal.
            # self.position.close() will sell any open position we have.
            self.position.close()

# --- Step 3: Load and Prepare the Data ---

# Define the full path to your CSV data file. The 'r' makes sure Windows paths work correctly.
data_path = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

# Read the CSV file using pandas.
df = pd.read_csv(
    data_path,
    header=None,
    skiprows=1,  # This is the fix: It tells pandas to skip the first row (the header).
    names=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
)

# Manually and explicitly convert the 'Timestamp' column into datetime objects.
# This is a more reliable way to ensure we get a proper DatetimeIndex.
df['Timestamp'] = pd.to_datetime(df['Timestamp'])

# Set the 'Timestamp' column as the index of the DataFrame.
df.set_index('Timestamp', inplace=True)


# Your data is 15-minute data, but the strategy needs daily data for a 20-day SMA.
# We will resample the data into daily ("D") candles.
daily_df = df.resample('D').agg({
    'Open': 'first',      # The daily open is the first open price of the day.
    'High': 'max',        # The daily high is the highest price of the day.
    'Low': 'min',         # The daily low is the lowest price of the day.
    'Close': 'last',      # The daily close is the last closing price of the day.
    'Volume': 'sum'       # The daily volume is the sum of all volume for the day.
})

# Remove any days where there was no trading data (like weekends).
daily_df.dropna(inplace=True)

# --- Step 4: Set up and Run the Backtest ---

# Initialize the Backtest object.
bt = Backtest(
    daily_df,             # The daily price data we just prepared.
    SmaCross,             # Our custom trading strategy class.
    cash=100000,           # The starting cash for our simulation, $10,000.
    commission=.001       # A 0.1% commission fee for each trade.
)

# Run the backtest and store the results.
stats = bt.run()

# --- Step 5: Show the Results ---

# Print the final statistics of the backtest.
print(stats)

# Create a plot of the backtest results, which will open in a new browser window.
bt.plot()
