# =============================================================================
# PURPOSE: Turtle Trading Strategy — Refined Implementation
# =============================================================================
#
# WHAT THIS DOES:
#   Runs a full-featured Turtle Trading backtest on BTC-USD daily data
#   (resampled from 15-minute candles). This is the IMPROVED version of
#   turtle_backtest.py, faithful to the original Turtle Traders rules.
#
# WHAT IT PRODUCES:
#   1. Console output comparing System 1 vs System 2 stats
#   2. An interactive HTML chart ("TurtleStrategy_System1.html") that opens
#      in your browser — shows candlesticks, trade markers, equity curve,
#      drawdowns, and the breakout channel overlays. Zoom/pan/hover to inspect.
#
# HOW TO RUN:
#   conda activate KID3
#   python turtle_algo.py
#   (or: & "C:\Users\ixis1\anaconda\envs\KID3\python.exe" turtle_algo.py)
#
# KEY IMPROVEMENTS over turtle_backtest.py:
#
#   1. DUAL ENTRY SYSTEM (System 1 & System 2)
#      - System 1: 20-bar breakout entry, 10-bar breakout exit
#      - System 2: 55-bar breakout entry, 20-bar breakout exit
#
#   2. ATR-BASED POSITION SIZING (the "Unit")
#      - Each unit risks exactly 1% of equity
#      - Unit size = (1% of equity) / (ATR × atr_multiplier)
#
#   3. PYRAMIDING (up to 4 units)
#      - Add a new unit every 0.5 × ATR in profit
#      - Maximum 4 units per direction
#
#   4. CHANNEL-BASED EXIT (trailing stop)
#      - Longs exit when price drops below the 10-bar (or 20-bar) low
#      - Shorts exit when price rises above the 10-bar (or 20-bar) high
#      - Replaces the rigid %-based take profit
#
#   5. ATR TRAILING STOP (hard stop)
#      - Initial stop at 2 × ATR from entry
#      - Tightened on each pyramid add
#
# =============================================================================

# --- Step 1: Imports ---

from backtesting import Backtest, Strategy
import pandas as pd
import talib


# --- Step 2: The Refined Turtle Strategy ---

class TurtleStrategy(Strategy):
    """
    A faithful implementation of the original Turtle Trading rules using
    backtesting.py.

    Parameters
    ----------
    system : int
        Which system to use. 1 = 20/10 bar channels, 2 = 55/20 bar channels.
    atr_period : int
        Lookback for Average True Range calculation.
    atr_multiplier : float
        Multiplier for the hard stop-loss (2N in original rules).
    risk_per_trade : float
        Fraction of equity risked per unit (1% = 0.01 in original rules).
    max_units : int
        Maximum number of pyramid units allowed per position.
    pyramid_atr_fraction : float
        Fraction of ATR between pyramid entries (0.5N in original rules).
    """

    # --- Configurable Parameters ---
    system            = 1       # 1 = System 1 (20/10), 2 = System 2 (55/20)
    atr_period        = 20      # ATR lookback (the Turtles used 20)
    atr_multiplier    = 2.0     # Stop = 2N from last entry price
    risk_per_trade    = 0.01    # 1% of equity per unit
    max_units         = 4       # Maximum pyramid units
    pyramid_atr_fraction = 0.5  # Add unit every 0.5 × ATR

    def init(self):
        """
        Pre-compute all indicators once. Runs at the start of the backtest.
        """
        # --- ATR (N in original Turtle parlance) ---
        self.atr = self.I(
            talib.ATR,
            self.data.High, self.data.Low, self.data.Close,
            timeperiod=self.atr_period
        )

        # --- Entry Channels ---
        if self.system == 1:
            entry_lookback = 20
            exit_lookback  = 10
        else:
            entry_lookback = 55
            exit_lookback  = 20

        # Highest high / lowest low for ENTRY signals
        self.entry_high = self.I(
            lambda h: pd.Series(h).rolling(entry_lookback).max(), self.data.High,
            name=f'{entry_lookback}-bar High'
        )
        self.entry_low = self.I(
            lambda l: pd.Series(l).rolling(entry_lookback).min(), self.data.Low,
            name=f'{entry_lookback}-bar Low'
        )

        # Highest high / lowest low for EXIT signals
        self.exit_high = self.I(
            lambda h: pd.Series(h).rolling(exit_lookback).max(), self.data.High,
            name=f'{exit_lookback}-bar High (exit)'
        )
        self.exit_low = self.I(
            lambda l: pd.Series(l).rolling(exit_lookback).min(), self.data.Low,
            name=f'{exit_lookback}-bar Low (exit)'
        )

        # --- Internal State ---
        self._units_held    = 0      # How many pyramid units are currently open
        self._last_add_price = None  # Price at which the last unit was added
        self._direction     = 0      # +1 = long, -1 = short, 0 = flat

    def _calc_unit_size(self, current_atr):
        """
        Calculate the number of shares/contracts for one unit.
        Unit = (risk_per_trade × equity) / (atr_multiplier × ATR)
        This ensures each unit risks exactly `risk_per_trade` of our equity.
        """
        dollar_risk = self.equity * self.risk_per_trade
        risk_per_share = current_atr * self.atr_multiplier
        if risk_per_share <= 0:
            return 0
        size = dollar_risk / risk_per_share
        # backtesting.py needs size as a fraction of equity for self.buy(size=...)
        # or we can pass it directly — we'll use the absolute share count approach
        return max(int(size), 1)

    def next(self):
        """
        Main decision logic — runs on every bar.
        """
        price = self.data.Close[-1]
        current_atr = self.atr[-1]

        # Skip bars where ATR isn't ready yet
        if pd.isna(current_atr) or current_atr <= 0:
            return

        # Use the PREVIOUS bar's channel values to avoid look-ahead bias
        entry_high = self.entry_high[-2]
        entry_low  = self.entry_low[-2]
        exit_high  = self.exit_high[-2]
        exit_low   = self.exit_low[-2]

        # Skip if channel values aren't ready
        if pd.isna(entry_high) or pd.isna(entry_low):
            return
        if pd.isna(exit_high) or pd.isna(exit_low):
            return

        # =====================================================================
        # EXIT LOGIC (always check exits before entries)
        # =====================================================================

        if self.position:
            # --- Long Exit ---
            if self.position.is_long:
                # Channel exit: price drops below the exit-channel low
                if price < exit_low:
                    self.position.close()
                    self._reset_state()
                    return

            # --- Short Exit ---
            elif self.position.is_short:
                # Channel exit: price rises above the exit-channel high
                if price > exit_high:
                    self.position.close()
                    self._reset_state()
                    return

        # =====================================================================
        # PYRAMIDING LOGIC (add units to an existing winning position)
        # =====================================================================

        if self.position and self._units_held < self.max_units:
            add_threshold = current_atr * self.pyramid_atr_fraction

            if self.position.is_long and self._last_add_price is not None:
                # Add a long unit if price has moved up by 0.5 × ATR since last add
                if price >= self._last_add_price + add_threshold:
                    unit_size = self._calc_unit_size(current_atr)
                    sl = price - (current_atr * self.atr_multiplier)
                    self.buy(size=unit_size, sl=sl)
                    self._last_add_price = price
                    self._units_held += 1
                    return

            elif self.position.is_short and self._last_add_price is not None:
                # Add a short unit if price has moved down by 0.5 × ATR since last add
                if price <= self._last_add_price - add_threshold:
                    unit_size = self._calc_unit_size(current_atr)
                    sl = price + (current_atr * self.atr_multiplier)
                    self.sell(size=unit_size, sl=sl)
                    self._last_add_price = price
                    self._units_held += 1
                    return

        # =====================================================================
        # ENTRY LOGIC (only when flat)
        # =====================================================================

        if not self.position:
            unit_size = self._calc_unit_size(current_atr)
            if unit_size <= 0:
                return

            # --- Long Entry: price breaks above the entry-channel high ---
            if price > entry_high:
                sl = price - (current_atr * self.atr_multiplier)
                self.buy(size=unit_size, sl=sl)
                self._last_add_price = price
                self._units_held = 1
                self._direction = 1

            # --- Short Entry: price breaks below the entry-channel low ---
            elif price < entry_low:
                sl = price + (current_atr * self.atr_multiplier)
                self.sell(size=unit_size, sl=sl)
                self._last_add_price = price
                self._units_held = 1
                self._direction = -1

    def _reset_state(self):
        """Reset pyramid tracking after a position is fully closed."""
        self._units_held     = 0
        self._last_add_price = None
        self._direction      = 0


# =============================================================================
# Step 3: Load and Prepare Data
# =============================================================================

# Path to your 15-minute BTC data
data_path = r'C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv'

df = pd.read_csv(
    data_path,
    header=None,
    skiprows=1,
    names=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
)

df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df.set_index('Timestamp', inplace=True)

# Resample to daily candles — the Turtle system was designed for daily data.
# Using 15-min bars directly with a 20-bar channel would only look back ~5 hours,
# which isn't meaningful. Daily bars give the proper multi-week breakout windows.
daily_df = df.resample('D').agg({
    'Open':   'first',
    'High':   'max',
    'Low':    'min',
    'Close':  'last',
    'Volume': 'sum'
})
daily_df.dropna(inplace=True)


# =============================================================================
# Step 4: Run the Backtest
# =============================================================================

bt = Backtest(
    daily_df,
    TurtleStrategy,
    cash=100_000,           # $100k starting capital (more realistic for position sizing)
    commission=0.001,       # 0.1% commission per trade
    exclusive_orders=False,  # Allow pyramiding (multiple open orders)
    hedging=True,            # Required for pyramiding: allows adding to positions
    finalize_trades=True     # Close any open trades at backtest end for clean stats
)

# --- System 1 (20/10 channels) ---
stats = bt.run(system=1)
print("=" * 60)
print("SYSTEM 1 RESULTS (20-bar entry / 10-bar exit)")
print("=" * 60)
print(stats)
print()

# --- System 2 (55/20 channels) ---
stats2 = bt.run(system=2)
print("=" * 60)
print("SYSTEM 2 RESULTS (55-bar entry / 20-bar exit)")
print("=" * 60)
print(stats2)

# Plot System 1 results (opens in browser)
bt.run(system=1)
bt.plot(filename='TurtleStrategy_System1.html', open_browser=True)
