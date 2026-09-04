''' 
datetime                                                                                                        
2024-06-04 14:35:00    WIF    L LIQ  3.259034  4939.717228  3.259034  3.259034  3.259034  3.259034   4939.717228
2024-06-04 14:36:00   None     None  3.259034     0.000000  3.259034  3.259034  3.259034  3.259034      0.000000
2024-06-04 14:37:00   None     None  3.259034     0.000000  3.259034  3.259034  3.259034  3.259034      0.000000
2024-06-04 14:38:00   None     None  3.259034     0.000000  3.259034  3.259034  3.259034  3.259034      0.000000
2024-06-04 14:39:00   None     None  3.259034     0.000000  3.259034  3.259034  3.259034  3.259034      0.000000
Start                     2024-06-04 14:35:00                                                                                                                                                                                    
End                       2024-06-20 12:33:00
Duration                     15 days 21:58:00
Exposure Time [%]                    9.415769
Equity Final [$]                153487.698511
Equity Peak [$]                 153487.698511
Return [%]                          53.487699
Buy & Hold Return [%]              -35.551158
Return (Ann.) [%]               988701.439809
Volatility (Ann.) [%]           780293.339717
Sharpe Ratio                         1.267089
Sortino Ratio                             inf
Calmar Ratio                    103661.789432
Max. Drawdown [%]                   -9.537762
Avg. Drawdown [%]                   -1.906906
Max. Drawdown Duration        0 days 20:15:00
Avg. Drawdown Duration        0 days 02:36:00
# Trades                                   20
Win Rate [%]                             75.0
Best Trade [%]                        7.64214
Worst Trade [%]                     -6.485137
Avg. Trade [%]                       2.165382
Max. Trade Duration           0 days 15:39:00
Avg. Trade Duration           0 days 01:47:00
Profit Factor                        3.570781
Expectancy [%]                        2.24177
SQN                                  2.642221
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                        Size  Entry...
dtype: object
Best Parameters:
Liquidation Threshold: 100000
Time Window (minutes): 22
Take Profit: 0.01
Stop Loss: 0.03

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
data_path = '/Users/md/Dropbox/dev/github/hyper-liquid-trading-bots/backtests/liquidations/data/WIF_liq_data.csv'  # Data file path
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
    liquidation_thresh=range(100000, 2000000, 200000),
    time_window_mins=range(2, 30, 2),
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