import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover


class RviBollingerBandsStrategy(Strategy):
    def init(self):
        self.bb_middle = self.I(lambda data: data['Close'].rolling(20).mean(), self.data.df)
        self.bb_upper = self.I(lambda data: self.bb_middle + 2 * data['Close'].rolling(20).std(), self.data.df)
        self.bb_lower = self.I(lambda data: self.bb_middle - 2 * data['Close'].rolling(20).std(), self.data.df)
        
        def rvi_numerator(data, i):
            close = data['Close'].iloc
            open_ = data['Open'].iloc
            return (close[i] - open_[i] 
                    + 2 * (close[i-1] - open_[i-1]) 
                    + 2 * (close[i-2] - open_[i-2]) 
                    + (close[i-3] - open_[i-3]))
        
        def rvi_denominator(data, i):
            high = data['High'].iloc
            low = data['Low'].iloc
            return (high[i] - low[i] 
                    + 2 * (high[i-1] - low[i-1]) 
                    + 2 * (high[i-2] - low[i-2]) 
                    + (high[i-3] - low[i-3]))
        
        def rvi(data):
            numerators = [rvi_numerator(data, i) for i in range(3, len(data))]
            denominators = [rvi_denominator(data, i) for i in range(3, len(data))]
            rvi = np.array(numerators) / np.array(denominators)
            return pd.Series(rvi, index=data.index[3:])

        self.rvi_line = self.I(rvi, self.data.df)
        self.rvi_signal = self.I(lambda rvi_line: rvi_line.rolling(4).mean(), self.rvi_line)
        
    def next(self):
        long_signal = (
            self.rvi_line[-1] < 0.2
            and crossover(self.rvi_line, self.rvi_signal)
            and self.data.Close[-1] > self.bb_middle[-1]
        )
        
        short_signal = (
            self.rvi_line[-1] > 0.8
            and crossover(self.rvi_signal, self.rvi_line)
            and self.data.Close[-1] < self.bb_middle[-1]
        )
        
        long_exit = self.data.Close[-1] < self.bb_middle[-1]
        short_exit = self.data.Close[-1] > self.bb_middle[-1]
        
        if long_signal:
            self.buy()
        elif short_signal:
            self.sell()

        if long_exit and self.position.is_long:
            self.position.close()

        if short_exit and self.position.is_short:
            self.position.close()


# Example usage:
# data = pd.read_csv('path_to_historical_data.csv', index_col=0, parse_dates=True)
# bt = Backtest(data, RviBollingerBandsStrategy, cash=10000, commission=.002)
# stats = bt.run()
# bt.plot()

# Please make sure to adapt the code to match your historical data by setting the appropriate path or data source.
