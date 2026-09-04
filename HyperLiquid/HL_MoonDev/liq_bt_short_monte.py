import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class LiquidationStrategy(Strategy):
    long_liquidation_thresh = 1000  # Default long liquidation threshold for buying
    short_liquidation_thresh = 1000  # Default short liquidation threshold for shorting
    time_window_mins = 2  # Default time window in minutes
    long_liquidation_closure_thresh = 1000  # Default long liquidation threshold for closing shorts
    short_liquidation_closure_thresh = 1000  # Default short liquidation threshold for closing longs

    def init(self):
        self.liquidations = self.data.liquidations
        self.short_liquidations = self.data.short_liquidations
        self.long_liquidations = self.data.long_liquidations
        self.trade_start_idx = None  # To track the start index of the current trade

    def next(self):
        current_idx = len(self.data.Close) - 1
        current_time = self.data.index[current_idx]  # Current time

        # Define the start time of the window
        start_time = current_time - pd.Timedelta(minutes=self.time_window_mins)

        # Find indices for slicing
        start_idx = np.searchsorted(self.data.index, start_time, side='left')

        # Sum long and short liquidations within the time window for entry
        recent_long_liquidations = self.long_liquidations[start_idx:current_idx + 1].sum()
        recent_short_liquidations = self.short_liquidations[start_idx:current_idx + 1].sum()

        # Buy if long liquidations exceed the threshold and we are not in a current position
        if recent_long_liquidations >= self.long_liquidation_thresh and not self.position:
            self.buy()
            self.trade_start_idx = current_idx  # Note the index where the trade started

        # Short if short liquidations exceed the threshold and we are not in a current position
        elif recent_short_liquidations >= self.short_liquidation_thresh and not self.position:
            self.sell()
            self.trade_start_idx = current_idx  # Note the index where the trade started

        # Check if a long position is open and we should close it based on short liquidations
        if self.position.is_long:
            # Sum short liquidations since the trade was opened for exit
            trade_short_liquidations = self.short_liquidations[self.trade_start_idx:current_idx + 1].sum()
            if trade_short_liquidations >= self.short_liquidation_closure_thresh:
                self.position.close()

        # Check if a short position is open and we should close it based on long liquidations
        if self.position.is_short:
            # Sum long liquidations since the trade was opened for exit
            trade_long_liquidations = self.long_liquidations[self.trade_start_idx:current_idx + 1].sum()
            if trade_long_liquidations >= self.long_liquidation_closure_thresh:
                self.position.close()

# Load the data
data_path = '/Users/md/Dropbox/dev/github/hyper-liquid-trading-bots/backtests/liquidations/data/SOL_liq_data.csv'
data = pd.read_csv(data_path)

# Convert 'datetime' column to datetime format and set as index
data['datetime'] = pd.to_datetime(data['datetime'])
data.set_index('datetime', inplace=True)

# Ensure necessary columns are present
data = data[['symbol', 'side', 'LIQ_SIDE', 'price', 'usd_size']]

# Create required columns for the backtest to run
data['Open'] = data['price']
data['High'] = data['price']
data['Low'] = data['price']
data['Close'] = data['price']

# Aggregate data by minute to handle duplicates
data = data.resample('T').agg({
    'symbol': 'first',
    'side': 'first',
    'LIQ_SIDE': 'first',
    'price': 'mean',
    'usd_size': 'sum',
    'Open': 'mean',
    'High': 'mean',
    'Low': 'mean',
    'Close': 'mean'
})

# Forward fill price-related columns
price_columns = ['price', 'Open', 'High', 'Low', 'Close']
data[price_columns] = data[price_columns].ffill()

# Set usd_size to 0 for missing data
data['usd_size'].fillna(0, inplace=True)

# Add new columns 'liquidations', 'short_liquidations', and 'long_liquidations'
data['liquidations'] = data['usd_size']
data['short_liquidations'] = data.apply(lambda row: row['usd_size'] if row['side'] == 'BUY' else 0, axis=1)
data['long_liquidations'] = data.apply(lambda row: row['usd_size'] if row['side'] == 'SELL' else 0, axis=1)

# Ensure the DataFrame is sorted by the index
data.sort_index(inplace=True)

# Function to perform a Monte Carlo simulation
def monte_carlo_simulation(data, n=100):
    results = []
    equity_curves = []

    for i in range(n):
        # Resample and shuffle data
        shuffled_data = data.sample(frac=1, replace=True, random_state=np.random.randint(0, 10000))

        # Create and configure the backtest
        bt = Backtest(shuffled_data, LiquidationStrategy, cash=100000, commission=0.002)

        # Run the backtest
        stats = bt.run()
        
        # Access the equity curve through the results
        equity_curve = stats['_equity_curve']['Equity']
        equity_curves.append(equity_curve.values)
        final_equity = equity_curve.iloc[-1]
        expectancy = stats['Expectancy [%]']
        avg_return = stats['Return [%]']
        max_drawdown = stats['Max. Drawdown [%]']
        
        results.append((final_equity, expectancy, avg_return, max_drawdown))
        
        print(f"Run {i+1}/{n}: Final Equity = {final_equity:.2f}, Expectancy = {expectancy:.2f}%, "
              f"Return = {avg_return:.2f}%, Max Drawdown = {max_drawdown:.2f}%")
    
    return results, equity_curves

# Perform Monte Carlo simulation
n_simulations = 100
results, equity_curves = monte_carlo_simulation(data, n_simulations)

# Plot results
plt.figure(figsize=(12, 6))
for equity_curve in equity_curves:
    plt.plot(equity_curve, color='blue', alpha=0.1)
    
plt.title(f'Monte Carlo Simulation ({n_simulations} runs)')
plt.xlabel('Time')
plt.ylabel('Equity')
plt.show()
