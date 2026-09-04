''' 
(tflow) (base) md@mds-MacBook-Pro hyper-liquid-trading-bots % /Users/md/miniforge3/envs/tflow/bin/python /Users/md/Dropbox/dev/github/hyper-liquid-trading-bots/backtests/liquidations/liq_bt_eth.py
                    symbol LIQ_SIDE    price    usd_size     Open     High      Low    Close  liquidations
datetime                                                                                                  
2024-06-04 13:04:00    ETH    S LIQ  3790.13  6723.69062  3790.13  3790.13  3790.13  3790.13    6723.69062
2024-06-04 13:05:00    ETH    S LIQ  3790.93  8139.12671  3790.93  3790.93  3790.93  3790.93    8139.12671
2024-06-04 13:06:00   None     None  3790.93     0.00000  3790.93  3790.93  3790.93  3790.93       0.00000
2024-06-04 13:07:00   None     None  3790.93     0.00000  3790.93  3790.93  3790.93  3790.93       0.00000
2024-06-04 13:08:00   None     None  3790.93     0.00000  3790.93  3790.93  3790.93  3790.93       0.00000
Start                     2024-06-04 13:04:00                                                                                                                                                                                    
End                       2024-06-20 12:33:00
Duration                     15 days 23:29:00
Exposure Time [%]                   29.843546
Equity Final [$]                104670.147671
Equity Peak [$]                 106443.323671
Return [%]                           4.670148
Buy & Hold Return [%]               -5.648619
Return (Ann.) [%]                  231.973235
Volatility (Ann.) [%]                 106.367
Sharpe Ratio                         2.180876
Sortino Ratio                       19.689701
Calmar Ratio                         39.95442
Max. Drawdown [%]                   -5.805947
Avg. Drawdown [%]                   -1.305205
Max. Drawdown Duration       11 days 02:26:00
Avg. Drawdown Duration        0 days 19:22:00
# Trades                                   38
Win Rate [%]                        73.684211
Best Trade [%]                       1.718885
Worst Trade [%]                     -2.713246
Avg. Trade [%]                       0.120358
Max. Trade Duration           1 days 02:35:00
Avg. Trade Duration           0 days 03:00:00
Profit Factor                         1.22271
Expectancy [%]                       0.130923
SQN                                  0.528714
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                       Size  EntryB...
dtype: object
Best Parameters:
Liquidation Threshold: 500,000
Time Window (minutes): 4
Take Profit: 0.01
Stop Loss: 0.02

--- updated data june 25




'''

import numpy as np
from backtesting import Backtest, Strategy
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

class LiquidationStrategy(Strategy):
    liquidation_thresh = 300000  # Default liquidation threshold
    time_window_mins = 4  # Default time window in minutes
    take_profit = 0.01  # Default take profit as 10% (0.10)
    stop_loss = 0.02    # Default stop loss as 5% (0.05)

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
data_path = '/Users/md/Dropbox/dev/github/hyper-liquid-trading-bots/backtests/liquidations/data/ETH_liq_data.csv'  # Data file path
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

# Run the backtest with default parameters and print the results
stats_default = bt.run()
print("Default Parameters Results:")
print(stats_default)

# Now perform the optimization
optimization_results = bt.optimize(
    liquidation_thresh=range(200000, 2000000, 100000),
    time_window_mins=range(2, 22, 2),
    take_profit=[i / 100 for i in range(1, 4, 1)],  # Optimize TP from 1% to 3%
    stop_loss=[i / 100 for i in range(1, 4, 1)],    # Optimize SL from 1% to 3%
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