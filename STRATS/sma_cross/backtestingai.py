import backtrader as bt
import datetime
import backtrader.analyzers as btanalyzers

class SmaCross(bt.Strategy):
    """
    This class defines the Simple Moving Average (SMA) Crossover strategy.
    It will buy when the fast SMA crosses above the slow SMA and sell/close
    when the fast SMA crosses below the slow SMA.
    """
    # These are the parameters for the strategy, which you can change
    params = (
        ('fast_length', 2   ),  # Period for the fast moving average
        ('slow_length', 10),  # Period for the slow moving average
    )

    def __init__(self):
        """
        This is the constructor of the strategy. It's called once when
        the strategy is created.
        """
        # Keep a reference to the "close" line of the data feed
        self.dataclose = self.datas[0].close

        # To keep track of pending orders
        self.order = None

        # Add a fast and slow Simple Moving Average
        self.slow_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.p.slow_length)
        self.fast_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.p.fast_length)

        # Add a Crossover signal indicator
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

    def notify_order(self, order):
        """
        Called by backtrader whenever an order's status changes. Clears
        self.order once it's done (filled/canceled/rejected) so next() knows
        it's safe to submit another one -- without this, self.order would
        stay permanently truthy after the first fill and the pending-order
        guard in next() would block every trade after the first.
        """
        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            self.order = None

    def next(self):
        """
        This method is called for each bar of data. This is where the
        main trading logic lives.
        """
        # Don't stack a new order on top of one still being processed.
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            # We are not in the market, check for a buy signal
            if self.crossover > 0:  # fast_sma has crossed above slow_sma
                print('BUY CREATE, %.2f' % self.dataclose[0])
                # Place a buy order
                self.order = self.buy()

        else:
            # We are in the market, check for a sell signal
            if self.crossover < 0:  # fast_sma has crossed below slow_sma
                print('SELL CREATE, %.2f' % self.dataclose[0])
                # FIX: self.sell() here doesn't close the long -- since
                # self.position is truthy for a short too, it kept selling
                # again on every bar the crossover stayed negative, stacking
                # an ever-growing naked short (verified: -$42M final value).
                # self.close() (Strategy method, not Position.close -- that
                # doesn't exist in backtrader) flattens to 0 in one order.
                self.order = self.close()

# --- Cerebro Setup ---

# Create a Cerebro entity
cerebro = bt.Cerebro()

# Add our strategy
cerebro.addstrategy(SmaCross)

# --- Data Feed Setup ---
# By adding an 'r' before the string, we tell Python to treat all characters
# literally and not interpret backslashes as special 'escape' characters.
dataname = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

# Create a Data Feed from the CSV file
data = bt.feeds.GenericCSVData(
    dataname=dataname,
    fromdate=datetime.datetime(2020, 2, 2),
    todate=datetime.datetime(2021, 1, 1),
    dtformat=('%Y-%m-%d %H:%M:%S'),
    datetime=0,
    high=2,
    low=3,
    open=1,
    close=4,
    volume=5,
    openinterest=-1
)

# Add the Data Feed to Cerebro
cerebro.adddata(data)

# --- Broker and Sizer Setup ---

# Set our desired cash start
cerebro.broker.setcash(100000.0)

# Add a sizer to determine the size of each trade
cerebro.addsizer(bt.sizers.FixedSize, stake=1) # Trades 1 unit of the asset

# Set the commission - 0.1% ... divide by 100 to get 0.001
cerebro.broker.setcommission(commission=0.001)


# --- Analyzers Setup ---

# Add analyzers to evaluate the performance
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe_ratio')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')

# --- Run Backtest ---

# Print out the starting conditions
print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

# Run the backtest
results = cerebro.run()

# --- Print Results ---

# Get the strategy instance from the run results
strat = results[0]

# Print out the final result
print('\n--- STRATEGY PERFORMANCE ---')
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

# Print out the analyzer results
sharpe_ratio = strat.analyzers.sharpe_ratio.get_analysis()
trade_analysis = strat.analyzers.trade_analyzer.get_analysis()

print('\nSharpe Ratio:', sharpe_ratio['sharperatio'])
print('\n--- TRADE ANALYSIS ---')
if trade_analysis.total.total > 0:
    print('Total Trades:', trade_analysis.total.total)
    print('Winning Trades:', trade_analysis.won.total)
    print('Losing Trades:', trade_analysis.lost.total)
    print(f"Win Rate: {(trade_analysis.won.total / trade_analysis.total.total) * 100:.2f}%")
else:
    print("No trades were executed.")

# --- Plot Results ---
print('\n--- Generating Plot ---')
# The plot will open in a new window. Close the window to end the script.