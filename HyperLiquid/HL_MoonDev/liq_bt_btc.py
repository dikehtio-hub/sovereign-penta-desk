'''
this one i tried opening up to lower liquidation amounts and it succcessfully improved the results

Start                     2024-06-04 13:13:00                                                                              
End                       2024-06-20 12:23:00
Duration                     15 days 23:10:00
Exposure Time [%]                   67.769997
Equity Final [$]                106985.118024
Equity Peak [$]                 107153.315164
Return [%]                           6.985118
Buy & Hold Return [%]               -5.411047
Return (Ann.) [%]                  453.183233
Volatility (Ann.) [%]               83.027369
Sharpe Ratio                         5.458239
Sortino Ratio                      118.159532
Calmar Ratio                       137.115516
Max. Drawdown [%]                    -3.30512
Avg. Drawdown [%]                   -0.839019
Max. Drawdown Duration        3 days 16:50:00
Avg. Drawdown Duration        0 days 09:24:00
# Trades                                   32
Win Rate [%]                            81.25
Best Trade [%]                       1.146434
Worst Trade [%]                     -2.325523
Avg. Trade [%]                       0.324334
Max. Trade Duration           2 days 21:21:00
Avg. Trade Duration           0 days 08:06:00
Profit Factor                        1.785374
Expectancy [%]                       0.332194
SQN                                  1.428291
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                       Size  EntryB...
dtype: object
Best Parameters:
Liquidation Threshold: 900000
Time Window (minutes): 24
Take Profit: 0.01
Stop Loss: 0.02


'''

import numpy as np
from backtesting import Backtest, Strategy
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

class LiquidationStrategy(Strategy):
    liquidation_thresh = 5000  # Default liquidation threshold, will be optimized
    time_window_mins = 30  # Default time window in minutes, will be optimized
    take_profit = 0.10  # Default take profit as 10% (0.10), will be optimized
    stop_loss = 0.05    # Default stop loss as 5% (0.05), will be optimized

    def init(self):
        self.liquidations = self.data.liquidations

    def next(self):
        current_idx = len(self.data.Close) - 1
        current_time = self.data.index[current_idx]  # Current time

        # Define the start time of the window
        start_time = current_time - pd.Timedelta(minutes=self.time_window_mins)

        # Find indices for slicing
        start_idx = np.searchsorted(self.data.index, start_time, side='left')
       
        # Sum liquidations within the time window
        recent_liquidations = self.liquidations[start_idx:current_idx + 1].sum()

        # Buy if liquidations exceed the threshold and we are not in a current position
        if recent_liquidations >= self.liquidation_thresh and not self.position:
            self.buy(sl=self.data.Close[-1] * (1 - self.stop_loss),
                     tp=self.data.Close[-1] * (1 + self.take_profit))

# Load the data
data_path = '/Users/md/Dropbox/dev/github/hyper-liquid-trading-bots/backtests/liquidations/data/BTC_liq_data.csv'  # Data file path
data = pd.read_csv(data_path)

# Convert 'datetime' column to datetime format and set as index
data['datetime'] = pd.to_datetime(data['datetime'])
data.set_index('datetime', inplace=True)

# Ensure necessary columns are present
data = data[['symbol', 'LIQ_SIDE', 'price', 'usd_size']]

# Create required columns for the backtest to run
data['Open'] = data['price']
data['High'] = data['price']
data['Low'] = data['price']
data['Close'] = data['price']

# Aggregate data by minute to handle duplicates
data = data.resample('T').agg({
    'symbol': 'first',
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

# Add a new column 'liquidations' to store preprocessed liquidations data
data['liquidations'] = data['usd_size']

# Ensure the DataFrame is sorted by the index
data.sort_index(inplace=True)

# Print the loaded data to verify
print(data.head())

# Create and configure the backtest
bt = Backtest(data, LiquidationStrategy, cash=100000, commission=0.002)

# Optimization
optimization_results = bt.optimize(
    liquidation_thresh=range(100000, 5000000, 100000),
    time_window_mins=range(10, 30, 2),
    take_profit=[i / 100 for i in range(1, 4, 1)],  # Optimize TP from 5% to 20%
    stop_loss=[i / 100 for i in range(1, 4, 1)],    # Optimize SL from 1% to 10%
    maximize='Equity Final [$]',
    constraint=lambda param: param.liquidation_thresh > 0  # Ensure liquidation threshold is positive
)

# Print the optimization results
print(optimization_results)

# Print the best optimized values
print("Best Parameters:")
print("Liquidation Threshold:", optimization_results._strategy.liquidation_thresh)
print("Time Window (minutes):", optimization_results._strategy.time_window_mins)
print("Take Profit:", optimization_results._strategy.take_profit)
print("Stop Loss:", optimization_results._strategy.stop_loss)