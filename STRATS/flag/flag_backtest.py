'''
Today we are backting a Flag Pattern Breakout strategy. This strategy is a simple breakout strategy that looks for a flag pattern to form, and then breaks out of the pattern. The strategy is based on the following assumptions:

NOTE- must have data imported on the line that says data = pd.read_csv(....)
'''


# get data on the 15min timeframe


from backtesting import Backtest
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
# FIX: Changed the import to be specific.
# This explicitly tells Python to find the 'FlagCont' class inside the 'strats_26.py' file.
from strats_26 import FlagCont


# The function now accepts a 'strategy_class' directly, not a string name.
def run_backtest(strategy_class, symbol, timeframe, start_time, plot=True, save_data=True):

    # The 'r' at the beginning helps prevent path errors on Windows.
    data_path = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

    # Load the data, skipping the header row and naming the columns.
    data = pd.read_csv(
        data_path,
        header=None,
        skiprows=1,
        names=['datetime', 'Open', 'High', 'Low', 'Close', 'Volume'],
        index_col='datetime',
        parse_dates=True
    )

    # run the backtest
    # We pass the strategy_class directly to Backtest, removing the need for eval().
    bt = Backtest(data, strategy_class, cash=10000, commission=.001, exclusive_orders=True)

    # get the results
    output = bt.run()
    print(output) # Print the results to the console

    # plot the results
    if plot:
        bt.plot()


# We call the function with the actual FlagCont class, not the string 'FlagCont'.
run_backtest(FlagCont, 'BTC-USD', timeframe='1h', start_time=datetime(2022, 1, 1, 12,0, 0), plot=True, save_data=False)


# # The code below this line is for data analysis and is currently commented out.
# # It will not run unless you uncomment it.
# data_path_analysis = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

# data_analysis = pd.read_csv(
#     data_path_analysis,
#     header=None,
#     names=['datetime', 'Open', 'High', 'Low', 'Close', 'Volume'],
#     index_col='datetime',
#     parse_dates=True
# )


# # fill in missing data with previous data
# # data_analysis = data_analysis.fillna(method='ffill')
# # save the new data as datafilled
# # data_analysis.to_csv('feb23/BTC-USD-15m_filled.csv')


'''
run_backtest('FlagCont', 'ETH-USD', timeframe='1h', start_time=datetime(2022, 1, 1, 12,0, 0), plot=True, save_data=False)
tp_perc = 29
sl_perc = 7
==
Return [%]                              43.980268
Buy & Hold Return [%]                 -56.152373


test 2
run_backtest('FlagCont', 'ETH-USD', timeframe='h', start_time=datetime(2020, 1, 1, 12,0, 0), plot=True, save_data=False)


** remember to put in bootcamp folder
'''

