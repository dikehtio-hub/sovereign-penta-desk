'''

extending on liq_bt_liqclose.py


update to this one is that we will only buy if its longs getting liqqed


this is the og results with no optimization
Equity Peak [$]                  105230.26729
Return [%]                           -0.86288
Buy & Hold Return [%]              -16.893138
Return (Ann.) [%]                  -13.392242
Volatility (Ann.) [%]               25.319363
Sharpe Ratio                              0.0
Sortino Ratio                             0.0
Calmar Ratio                              0.0
Max. Drawdown [%]                  -13.477614
Avg. Drawdown [%]                   -3.579778
Max. Drawdown Duration       18 days 01:24:00
Avg. Drawdown Duration        4 days 13:41:00
# Trades                                   21
Win Rate [%]                        47.619048
Best Trade [%]                        6.08585
Worst Trade [%]                      -5.54198
Avg. Trade [%]                      -0.041322
Max. Trade Duration           0 days 15:54:00
Avg. Trade Duration           0 days 04:16:00
Profit Factor                         0.98178
Expectancy [%]                      -0.014361
SQN                                 -0.081175
_strategy                 LiquidationStrategy
_equity_curve                             ...
_trades                       Size  EntryB...

--- new one no opt
Start                     2024-06-04 13:19:00
End                       2024-06-25 14:57:00
Duration                     21 days 01:38:00
Exposure Time [%]                    13.77435
Equity Final [$]                 97779.055891
Equity Peak [$]                  105230.26729
Return [%]                          -2.220944
Buy & Hold Return [%]              -16.893138
Return (Ann.) [%]                   -31.10787
Volatility (Ann.) [%]               17.588874
Sharpe Ratio                              0.0
Sortino Ratio                             0.0
Calmar Ratio                              0.0
Max. Drawdown [%]                  -13.832528
Avg. Drawdown [%]                   -3.668506
Max. Drawdown Duration       18 days 01:24:00
Avg. Drawdown Duration        4 days 13:41:00
# Trades                                    9
Win Rate [%]                        44.444444
Best Trade [%]                        6.08585
Worst Trade [%]                      -5.54198
Avg. Trade [%]                      -0.249167
Max. Trade Duration           0 days 15:54:00
Avg. Trade Duration           0 days 07:44:00
Profit Factor                        0.880213
Expectancy [%]                      -0.189125
SQN                                 -0.207183
_strategy                 LiquidationStrategy
_equity_curve                             ...
_trades                      Size  EntryBa...
dtype: object

----
Start                     2024-06-04 13:19:00                                                                                                                                                                                                                                                          
End                       2024-06-25 14:57:00
Duration                     21 days 01:38:00
Exposure Time [%]                   21.282837
Equity Final [$]                206289.430003
Equity Peak [$]                 206289.430003
Return [%]                          106.28943
Buy & Hold Return [%]              -16.893138
Return (Ann.) [%]             16498949.209458
Volatility (Ann.) [%]         13452564.373922
Sharpe Ratio                         1.226454
Sortino Ratio                  1914505.487162
Calmar Ratio                   1795031.465463
Max. Drawdown [%]                   -9.191454
Avg. Drawdown [%]                   -1.236574
Max. Drawdown Duration        4 days 12:36:00
Avg. Drawdown Duration        0 days 03:32:00
# Trades                                   79
Win Rate [%]                        84.810127
Best Trade [%]                       2.986812
Worst Trade [%]                     -5.582242
Avg. Trade [%]                       0.921237
Max. Trade Duration           0 days 09:17:00
Avg. Trade Duration           0 days 01:21:00
Profit Factor                        4.811876
Expectancy [%]                       0.930846
SQN                                  6.635641
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                       Size  EntryB...
dtype: object
Best Parameters:
Liquidation Threshold: 80000
Time Window (minutes): 10
Short Liquidation Closure Threshold: 14000

-----
Start                     2024-06-04 13:19:00                                                                                                                                                                                                                                                          
End                       2024-06-25 14:57:00
Duration                     21 days 01:38:00
Exposure Time [%]                   48.248129
Equity Final [$]                256686.932299
Equity Peak [$]                 256686.932299
Return [%]                         156.686932
Buy & Hold Return [%]              -16.893138
Return (Ann.) [%]            326363182.165848
Volatility (Ann.) [%]        286510935.801294
Sharpe Ratio                         1.139095
Sortino Ratio                 43508447.961168
Calmar Ratio                  36422880.132988
Max. Drawdown [%]                   -8.960389
Avg. Drawdown [%]                   -1.528865
Max. Drawdown Duration        1 days 13:01:00
Avg. Drawdown Duration        0 days 03:06:00
# Trades                                  149
Win Rate [%]                        76.510067
Best Trade [%]                       3.891865
Worst Trade [%]                     -5.190386
Avg. Trade [%]                       0.634943
Max. Trade Duration           0 days 11:38:00
Avg. Trade Duration           0 days 01:38:00
Profit Factor                        3.449309
Expectancy [%]                       0.643143
SQN                                  6.240742
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                        Size  Entry...
dtype: object
Best Parameters:
Liquidation Threshold: 10000
Time Window (minutes): 4
Short Liquidation Closure Threshold: 10000


--- just getting better

Start                     2024-06-04 13:19:00                                                                                                                                                                                                                                                            
End                       2024-06-25 14:57:00
Duration                     21 days 01:38:00
Exposure Time [%]                   52.206731
Equity Final [$]                440193.415101
Equity Peak [$]                 440193.415101
Return [%]                         340.193415
Buy & Hold Return [%]              -16.893138
Return (Ann.) [%]         2005633046095.62...
Volatility (Ann.) [%]     3113575163162.28...
Sharpe Ratio                         0.644158
Sortino Ratio                             inf
Calmar Ratio              253543655276.774811
Max. Drawdown [%]                   -7.910405
Avg. Drawdown [%]                    -1.05783
Max. Drawdown Duration        0 days 18:36:00
Avg. Drawdown Duration        0 days 02:01:00
# Trades                                  225
Win Rate [%]                        79.111111
Best Trade [%]                       3.711781
Worst Trade [%]                      -6.03798
Avg. Trade [%]                       0.661094
Max. Trade Duration           0 days 12:19:00
Avg. Trade Duration           0 days 01:10:00
Profit Factor                        4.621224
Expectancy [%]                       0.666493
SQN                                  9.464814
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                        Size  Entry...
dtype: object
Best Parameters:
Liquidation Threshold: 1000
Time Window (minutes): 2
Short Liquidation Closure Threshold: 3000
'''

import numpy as np
from backtesting import Backtest, Strategy
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

class LiquidationStrategy(Strategy):
    liquidation_thresh = 300000  # Default long liquidation threshold for buying
    time_window_mins = 4  # Default time window in minutes
    short_liquidation_closure_thresh = 100000  # Default short liquidation threshold for closing

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

        # Sum long liquidations within the time window for entry
        recent_long_liquidations = self.long_liquidations[start_idx:current_idx + 1].sum()

        # Buy if long liquidations exceed the threshold and we are not in a current position
        if recent_long_liquidations >= self.liquidation_thresh and not self.position:
            self.buy()
            self.trade_start_idx = current_idx  # Note the index where the trade started
        
        # Check if a position is open and we should close it based on short liquidations
        if self.position:
            # Sum short liquidations since the trade was opened for exit
            trade_short_liquidations = self.short_liquidations[self.trade_start_idx:current_idx + 1].sum()
            if trade_short_liquidations >= self.short_liquidation_closure_thresh:
                self.position.close()

# Load the data
data_path = '/Users/md/Dropbox/dev/github/hyper-liquid-trading-bots/backtests/liquidations/data/SOL_liq_data.csv'  # replace with the correct path
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
    liquidation_thresh=range(500, 5000, 250),
    time_window_mins=range(1, 7, 1),
    short_liquidation_closure_thresh=range(500, 5000, 250),  # Optimize short liquidation closure threshold
    maximize='Equity Final [$]',
    constraint=lambda param: param.liquidation_thresh > 0  # Ensure liquidation threshold is positive
)

# Print the optimization results
print(optimization_results)

# Print the best optimized values
print("Best Parameters:")
print("Liquidation Threshold:", optimization_results._strategy.liquidation_thresh)
print("Time Window (minutes):", optimization_results._strategy.time_window_mins)
print("Short Liquidation Closure Threshold:", optimization_results._strategy.short_liquidation_closure_thresh)