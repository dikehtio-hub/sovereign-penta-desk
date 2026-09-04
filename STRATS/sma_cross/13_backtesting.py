######## BACKTESTING with backtrader 


from datetime import datetime 
import backtrader as bt 
import backtrader.analyzers as btanalyzers



# THIS IS WHERE WE DEFINE OUR STRATEGY
class SmaCross(bt.SignalStrategy):
    def __init__(self): 
        # when simple moving average crosses the price, can change the number
        sma = bt.ind.SMA(period=20)
        # this grabs the price data from the excel
        price = self.data
        # this defines the cross over.. price and sma
        crossover = bt.ind.CrossOver(price, sma)
        # this tells the code to LONG when it crossover, which is defined above
        self.signal_add(bt.SIGNAL_LONG, crossover)




# this is activating the engine
cerebro = bt.Cerebro()
# this adds the strategy to it
cerebro.addstrategy(SmaCross)


# this is pulling data from yahoo fin but doesnt work well, so i used larrys below
# data = bt.feeds.YahooFinanceData(dataname = "BTC-USD", fromdate=datetime(2015, 1, 1),
#         todate=datetime(2022, 1, 1))


# FIX: this CSV is NOT Yahoo Finance's format (Date,Open,High,Low,Close,Adj Close,
# Volume) -- it's the plain datetime,open,high,low,close,volume file the other
# STRATS/ backtesting.py scripts use (see e.g. flag_backtest.py). Feeding it to
# YahooFinanceCSVData mis-parses every row (wrong date format, missing Adj Close
# column) and never raises, it just hangs. GenericCSVData with explicit column
# indices reads this file's actual layout correctly.
data = bt.feeds.GenericCSVData(

    dataname = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv',

    dtformat = '%Y-%m-%d %H:%M:%S',
    datetime = 0, open = 1, high = 2, low = 3, close = 4, volume = 5, openinterest = -1,

    # do not pass values before this date
    # this is when we want to start the date
    fromdate=datetime(2020, 2, 2),
    # do not passs values after this date
    todate = datetime(2022, 5, 4),
    reverse = False
)


# this sets the cash amount to the back test
cerebro.broker.set_cash(1000000)


# set the commision 0.1% ... divide by 100 to remove the %
# phemex contract is .00075 taker and -.00025 for maker
# phemex spot is .001 for taker & maker
# ftx is .001 for maker and .004 for taker
cerebro.broker.setcommission(commission=0.001)


# this adds the data to the cerebro engine
cerebro.adddata(data)


# this says go all in, well 95% so we dont miss
cerebro.addsizer(bt.sizers.AllInSizer, percents=95)


# now adding some analyzers...
# this one beelow is how we get the sharpe analyzer
cerebro.addanalyzer(btanalyzers.SharpeRatio, _name = 'sharpe')
# this is the transactions analyzer
cerebro.addanalyzer(btanalyzers.Transactions, _name = 'tx')
# this is the trade analyzer
cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name = 'trades')

# now we run our engine & add it to a variable so we can later check perf
back = cerebro.run()

# this gets our value back 
endvalue = cerebro.broker.getvalue() 

# below we are looking at our 3 analyzers.. sharpe here
sharpe = back[0].analyzers.sharpe.get_analysis() 


# this is running out transaction analyzer
txs = back[0].analyzers.tx.get_analysis() 


# this is running our trades analzer
trades = back[0].analyzers.trades.get_analysis() 

#print(txs)

txamount = len(txs)

#print(f"ending value is {endvalue}")
print(f"sharpe ratio is {sharpe} and this many txs: {txamount} final value {cerebro.broker.getvalue()}")
#print(f"transactions are {txs}")
#print(f"trades are {trades}")

# this shows the final portfolio value
#print("final protfolio value: %.2f" % cerebro.broker.getvalue())


# this plots the backtest
cerebro.plot()
