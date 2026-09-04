import pandas as pd
import numpy as np
import yfinance as yf
from backtesting import Backtest, Strategy

# =============================================================================
# Turtle Trading Strategy — Fully Parameterized with Auto-Optimization & Notes
# =============================================================================
#
# PARAMETER TUNING GUIDE & NOTES:
# -----------------------------------------------------------------------------
# 1. entry_period (Default: 55 | Suggested Range: 20 to 100)
#    - Controls breakout sensitivity.
#    - Lower (20-30): Catches trend starts early, but triggers more false breakouts.
#    - Higher (55-90): Higher win rate, filters noise, but misses initial trend move.
#
# 2. exit_period (Default: 20 | Suggested Range: 10 to 35)
#    - Controls trailing Donchian channel exit tightness.
#    - Lower (10-15): Locks in profits quickly, but risks premature exits during pullbacks.
#    - Higher (20-35): Gives trades breathing room to capture massive multi-month moves.
#
# 3. atr_multiplier (Default: 2.0 | Suggested Range: 1.5 to 3.5)
#    - Hard Stop Loss multiplier (in units of ATR / N).
#    - Lower (1.0 - 1.5): Tighter stops, lower risk per trade, higher stop-out frequency.
#    - Higher (2.5 - 3.5): Wider stops, avoids getting stopped out by intraday volatility.
#
# 4. risk_per_trade (Default: 0.01 = 1% | Suggested Range: 0.005 to 0.02)
#    - Fraction of account equity risked per trade unit.
#    - 0.5% (0.005): Conservative risk, lower drawdown, smoother growth.
#    - 2.0% (0.020): Aggressive, higher total returns during mega-trends, larger drawdowns.
#
# 5. pyramid_step (Default: 0.5 | Suggested Range: 0.25 to 1.0)
#    - Price move in ATR required before adding an additional unit (up to 4 units).
#    - 0.25 ATR: Aggressive position stacking early in the move.
#    - 0.75 - 1.0 ATR: Conservative scaling, adds only on strong confirmed trends.
# =============================================================================

def ATR(high, low, close, period=14):
    h_l = high - low
    h_c = np.abs(high - np.roll(close, 1))
    l_c = np.abs(low - np.roll(close, 1))
    tr = np.maximum(h_l, np.maximum(h_c, l_c))
    tr[0] = h_l[0]
    # Wilder's smoothing (the actual Turtle "N"), not a plain SMA of true range.
    # ewm(alpha=1/period) is the standard vectorized equivalent of Wilder's recursive average.
    return pd.Series(tr).ewm(alpha=1 / period, min_periods=period, adjust=False).mean().values

def DonchianHigh(high, period=20):
    return pd.Series(high).shift(1).rolling(period).max().values

def DonchianLow(low, period=20):
    return pd.Series(low).shift(1).rolling(period).min().values


class ParameterizedTurtleStrategy(Strategy):
    """
    Turtle Strategy with flexible parameters for backtesting and auto-optimization.
    """
    entry_period = 70       # Range to test: [20, 30, 40, 55, 75]
    exit_period = 25        # Range to test: [10, 15, 20, 25, 30]
    atr_period = 20         # Range to test: [10, 14, 20]
    atr_multiplier = 2.5    # Range to test: [1.5, 2.0, 2.5, 3.0]
    risk_per_trade = 0.02   # Range to test: [0.005, 0.01, 0.02]
    max_units = 5           # Range to test: [2, 3, 4, 5]
    pyramid_step = 0.75      # Range to test: [0.25, 0.5, 0.75, 1.0]

    def init(self):
        self.entry_high = self.I(DonchianHigh, self.data.High, self.entry_period)
        self.entry_low = self.I(DonchianLow, self.data.Low, self.entry_period)
        self.exit_high = self.I(DonchianHigh, self.data.High, self.exit_period)
        self.exit_low = self.I(DonchianLow, self.data.Low, self.exit_period)
        self.atr = self.I(ATR, self.data.High, self.data.Low, self.data.Close, self.atr_period)
        self.unit_entries = []

    def _position_fraction(self, atr, price):
        # Fraction of equity whose stop-out loss equals risk_per_trade.
        # units*stop_distance = equity*risk_pct, and size_fraction = units*price/equity,
        # so equity cancels: fraction = risk_pct * (price / stop_distance).
        stop_distance = atr * self.atr_multiplier
        if stop_distance <= 0:
            return 0.0
        return min(0.99, self.risk_per_trade * price / stop_distance)

    def _enter(self, direction, price, atr, tighten_existing=False):
        fraction = self._position_fraction(atr, price)
        if fraction <= 0:
            return
        sl = price - direction * atr * self.atr_multiplier
        if direction == 1:
            self.buy(size=fraction, sl=sl)
        else:
            self.sell(size=fraction, sl=sl)
        self.unit_entries.append({'price': price, 'sl': sl})
        if tighten_existing:
            for t in self.trades[:-1]:
                t.sl = sl

    def next(self):
        price = self.data.Close[-1]
        atr = self.atr[-1]

        if np.isnan(atr) or atr <= 0:
            return

        if not self.position:
            self.unit_entries = []
            if price > self.entry_high[-1]:
                self._enter(1, price, atr)
            elif price < self.entry_low[-1]:
                self._enter(-1, price, atr)
            return

        is_long = self.position.is_long
        direction = 1 if is_long else -1

        if (is_long and price < self.exit_low[-1]) or (not is_long and price > self.exit_high[-1]):
            self.position.close()
            self.unit_entries = []
            return

        if len(self.unit_entries) < self.max_units:
            last_entry = self.unit_entries[-1]['price']
            if direction * (price - last_entry) >= self.pyramid_step * atr:
                self._enter(direction, price, atr, tighten_existing=True)


# =============================================================================
# AUTO-OPTIMIZATION RUNNER
# =============================================================================
def run_optimization_demo(ticker='ETH-USD'):
    print(f"\nFetching historical data for {ticker}...")
    df = yf.download(ticker, start='2022-01-01', progress=False)  # end omitted = up to today
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

    bt = Backtest(df, ParameterizedTurtleStrategy, cash=1000000, commission=0.0005, trade_on_close=True)

    print("\n1. BASELINE RUN (Default Parameters: Entry=55, Exit=20, Stop=2.0N)...")
    baseline_stats = bt.run()
    print(f"   Baseline Net Return : {baseline_stats['Return [%]']:.2f}%")
    print(f"   Baseline Win Rate   : {baseline_stats['Win Rate [%]']:.2f}%")
    print(f"   Baseline Profit Fac : {baseline_stats['Profit Factor']:.2f}")
    print(f"   Baseline Max Drawdown: {baseline_stats['Max. Drawdown [%]']:.2f}%")

    print("\n2. RUNNING AUTOMATED OPTIMIZER (Searching for highest Profit Factor)...")
    opt_stats = bt.optimize(
        entry_period=[30, 45, 55, 70],
        exit_period=[10, 15, 20, 25],
        atr_multiplier=[1.5, 2.0, 2.5],
        maximize='Profit Factor',
        constraint=lambda p: p.entry_period > p.exit_period
    )

    strat = opt_stats._strategy

    print("\n" + "="*70)
    print("                 AUTO-OPTIMIZATION RESULTS                    ")
    print("="*70)
    print(f"Optimal Entry Period   : {strat.entry_period} bars")
    print(f"Optimal Exit Period    : {strat.exit_period} bars")
    print(f"Optimal ATR Multiplier : {strat.atr_multiplier}N")
    print("-" * 70)
    print(f"Optimized Return       : {opt_stats['Return [%]']:.2f}%")
    print(f"Optimized Win Rate     : {opt_stats['Win Rate [%]']:.2f}%")
    print(f"Optimized Profit Factor: {opt_stats['Profit Factor']:.2f}")
    print(f"Optimized Max Drawdown : {opt_stats['Max. Drawdown [%]']:.2f}%")
    print("="*70)

if __name__ == '__main__':
    run_optimization_demo('ETH-USD')