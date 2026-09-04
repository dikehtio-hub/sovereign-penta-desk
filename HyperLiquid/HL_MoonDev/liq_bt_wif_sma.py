'''

vs the og data

(OPTIMIZED)
Start                     2024-06-04 14:35:00
End                       2024-07-18 11:28:00
Duration                     43 days 20:53:00
Exposure Time [%]                    6.165511
Equity Final [$]                137713.995001
Equity Peak [$]                 172202.521668
Return [%]                          37.713995
Buy & Hold Return [%]              -24.088448
Return (Ann.) [%]                 1240.499404
Volatility (Ann.) [%]             1118.237458
Sharpe Ratio                         1.109335
Sortino Ratio                       27.859806
Calmar Ratio                        36.031102
Max. Drawdown [%]                  -34.428573
Avg. Drawdown [%]                   -3.197212
Max. Drawdown Duration       24 days 01:34:00
Avg. Drawdown Duration        1 days 06:46:00
# Trades                                   55
Win Rate [%]                        65.454545
Best Trade [%]                        7.64214
Worst Trade [%]                     -6.633182
Avg. Trade [%]                       0.583537
Max. Trade Duration           0 days 15:39:00
Avg. Trade Duration           0 days 01:10:00
Profit Factor                        1.448142
Expectancy [%]                       0.663126
SQN                                  0.989939
_strategy                 LiquidationStrategy
_equity_curve                             ...
_trades                         Size  Entr...


this strategy takes the og liq strat and adds in a an sma to only trade if under sma
the initial thot was over, but since liqs are buy opps we want to buy when under the sma... 

todo-
on the 4 hour or something like that... need to pull in btc/eth

(NOT OPTIMIZED)
Default Parameters Results:
Start                     2024-06-04 14:35:00
End                       2024-07-18 11:28:00
Duration                     43 days 20:53:00
Exposure Time [%]                    3.572672
Equity Final [$]                223047.712831
Equity Peak [$]                 223047.712831
Return [%]                         123.047713
Buy & Hold Return [%]              -24.088448
Return (Ann.) [%]                66871.967526
Volatility (Ann.) [%]            42408.390284
Sharpe Ratio                         1.576857
Sortino Ratio                      4188.23004
Calmar Ratio                      7011.246323
Max. Drawdown [%]                   -9.537815
Avg. Drawdown [%]                   -1.557455
Max. Drawdown Duration        3 days 11:52:00
Avg. Drawdown Duration        0 days 07:39:00
# Trades                                   31
Win Rate [%]                        83.870968
Best Trade [%]                        7.64214
Worst Trade [%]                     -6.485137
Avg. Trade [%]                        2.62159
Max. Trade Duration           0 days 05:07:00
Avg. Trade Duration           0 days 01:12:00
Profit Factor                        5.356344
Expectancy [%]                       2.678592
SQN                                  4.491456
_strategy                 LiquidationStrategy
_equity_curve                             ...
_trades                         Size  Entr...

(SMA OPTMIZED)
Start                     2024-06-04 14:35:00                                       
End                       2024-07-18 11:28:00
Duration                     43 days 20:53:00
Exposure Time [%]                    3.662899
Equity Final [$]                 253521.96802
Equity Peak [$]                  253521.96802
Return [%]                         153.521968
Buy & Hold Return [%]              -24.088448
Return (Ann.) [%]               189141.073051
Volatility (Ann.) [%]            129381.20279
Sharpe Ratio                          1.46189
Sortino Ratio                    11847.695159
Calmar Ratio                     19830.651048
Max. Drawdown [%]                   -9.537815
Avg. Drawdown [%]                   -1.491734
Max. Drawdown Duration        3 days 11:52:00
Avg. Drawdown Duration        0 days 06:45:00
# Trades                                   34
Win Rate [%]                        85.294118
Best Trade [%]                        7.64214
Worst Trade [%]                     -6.485137
Avg. Trade [%]                       2.773917
Max. Trade Duration           0 days 05:07:00
Avg. Trade Duration           0 days 01:08:00
Profit Factor                        6.390449
Expectancy [%]                       2.824708
SQN                                  5.349498
_strategy                 LiquidationStrat...
_equity_curve                             ...
_trades                         Size  Entr...
dtype: object
Best Parameters:
Liquidation Threshold: 100000
Time Window (minutes): 26
Take Profit: 0.01
Stop Loss: 0.03






'''
import numpy as np
from backtesting import Backtest, Strategy
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

class LiquidationStrategy(Strategy):
    liquidation_thresh = 100000  # Default liquidation threshold, will be optimized
    time_window_mins = 22  # Default time window in minutes, will be optimized
    take_profit = 0.01  # Default take profit as 10% (0.10), will be optimized
    stop_loss = 0.03   # Default stop loss as 5% (0.05), will be optimized
    sma_period = 20  # Default SMA period, can be adjusted or optimized if needed

    def init(self):
        self.liquidations = self.data['liquidations']
        self.sma = self.I(self.calculate_sma, pd.Series(self.data.Close), self.sma_period)

    def calculate_sma(self, series, period):
        sma = series.rolling(window=period).mean()
        return sma.fillna(0).to_numpy()  # Convert to numpy array and fill NaN with 0

    def next(self):
        current_idx = len(self.data.Close) - 1
        current_time = self.data.index[current_idx]  # Current time

        # Define the start time of the window
        start_time = current_time - pd.Timedelta(minutes=self.time_window_mins)

        # Find indices for slicing
        start_idx = np.searchsorted(self.data.index, start_time, side='left')

        # Sum liquidations within the time window
        recent_liquidations = self.liquidations[start_idx:current_idx + 1].sum()

        # Debug prints
        #print(f"Index: {current_idx}, Close: {self.data.Close[-1]}, SMA: {self.sma[-1]}, Recent Liquidations: {recent_liquidations}")

        # Buy if liquidations exceed the threshold, price is above the SMA, and we are not in a current position
        if recent_liquidations >= self.liquidation_thresh and self.data.Close[-1] < self.sma[-1] and not self.position:
            #print("Buying...")
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
bt = Backtest(data, LiquidationStrategy, cash=100000, commission=0.002) # .001

# Run the backtest with default parameters and print the results
stats_default = bt.run()
print("Default Parameters Results:")
print(stats_default)

# Optimization
optimization_results = bt.optimize(
    liquidation_thresh=range(100000, 2000000, 200000),
    time_window_mins=range(2, 30, 2),
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