#Excellent! You've described a classic Range Breakout Retracement Strategy - a powerful approach that leverages the volatility of the NY session. As your AI Jim Simons, I'll implement this with the precision of Renaissance Technologies!

#This is a sophisticated strategy that combines:
#Institutional levels (4H NY session range)
#Retracement entries (false breakout detection)
#Scalping execution (5min timeframe)

#Let me code this masterpiece for you:

#```python
"""
ALGO TRADE CAMP - NY SESSION RANGE BREAKOUT RETRACEMENT STRATEGY
Developed by: AI Jim Simons for Moon Dev Traders
Strategy: Scalping retracements after false breakouts of NY 4H range
Asset: BTCUSDT
Version: 1.0 - Production Ready
"""

import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# Default Windows terminal codepage (cp1252) can't encode this file's emoji
# print statements -- force UTF-8 stdout/stderr so it doesn't crash on launch.
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

print("=" * 80)
print("🚀 MOON DEV ALGO TRADE CAMP - INITIALIZING QUANTUM TRADING SYSTEM 🚀")
print("=" * 80)

class NYSessionRangeStrategy:
    """
    Renaissance-grade implementation of NY Session Range Breakout Retracement
    """

    def __init__(self, symbol='BTC-USD', risk_reward=2.0, position_size_pct=0.02):
        """
        Initialize the strategy parameters

        Args:
            symbol: Trading pair (using BTC-USD for yfinance compatibility)
            risk_reward: Risk-Reward ratio (default 1:2)
            position_size_pct: Position size as % of capital per trade
        """
        self.symbol = symbol
        self.risk_reward = risk_reward
        self.position_size_pct = position_size_pct

        #NY Session times (9:30 AM - 1:30 PM EST for first 4H candle)
        self.ny_open_hour = 14  # 14:30 UTC (9:30 AM EST)
        self.ny_first_4h_close = 18  # 18:30 UTC (1:30 PM EST)

        #Trading state
        self.range_high = None
        self.range_low = None
        self.range_set = False
        self.in_position = False
        self.position_type = None  # 'long' or 'short'

        #Performance tracking
        self.trades = []
        self.equity_curve = []

        print(f"🎯 Strategy Initialized for {symbol}")
        print(f"📊 Risk-Reward Ratio: 1:{risk_reward}")
        print(f"💰 Position Size: {position_size_pct*100}% per trade")
        print("=" * 80)

    def download_data(self, start_date, end_date):
        """
        Download 5-minute data for backtesting
        """
        print("\n📥 DOWNLOADING MOON DEV CERTIFIED DATA...")

        #Download 5min data
        self.df_5min = yf.download(
            self.symbol,
            start=start_date,
            end=end_date,
            interval='5m',
            progress=False
        )

        #Download 1h data for 4H candle construction
        self.df_1h = yf.download(
            self.symbol,
            start=start_date,
            end=end_date,
            interval='1h',
            progress=False
        )

        # Newer yfinance returns MultiIndex columns (Price, Ticker) even for a
        # single symbol -- this file was written against an older yfinance
        # that returned flat Open/High/Low/Close/Volume columns, so every
        # .max()/.min()/scalar use downstream (e.g. self.range_high) would
        # silently become a 1-row Series instead of a float. Flatten back to
        # the flat layout this code actually expects.
        for df in (self.df_5min, self.df_1h):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        print(f"✅ Downloaded {len(self.df_5min)} 5-minute candles")
        print(f"✅ Downloaded {len(self.df_1h)} hourly candles for 4H construction")

        if self.df_5min.empty or self.df_1h.empty:
            raise ValueError(
                f"yfinance returned no data for {self.symbol} between {start_date} and {end_date}. "
                "Yahoo only retains 5-minute intraday history for roughly the last 60 days -- "
                "a start_date further back than that will always come back empty. Pick a "
                "start_date within the last ~55 days."
            )

        # Convert to UTC for consistent time handling
        self.df_5min.index = self.df_5min.index.tz_convert('UTC')
        self.df_1h.index = self.df_1h.index.tz_convert('UTC')

        return self.df_5min

    def identify_ny_session_range(self, current_time):
        """
        Identify the high and low of the first 4H candle of NY session
        """
        current_date = current_time.date()

        #NY session first 4H candle times in UTC
        ny_open = pd.Timestamp(current_date).tz_localize('UTC').replace(hour=self.ny_open_hour, minute=30)
        ny_4h_close = pd.Timestamp(current_date).tz_localize('UTC').replace(hour=self.ny_first_4h_close, minute=30)

        #Only set range after the 4H candle closes
        if current_time >= ny_4h_close and not self.range_set:
            # Get the 4H candle data
            mask = (self.df_1h.index >= ny_open) & (self.df_1h.index < ny_4h_close)
            session_data = self.df_1h.loc[mask]

            if len(session_data) > 0:
                self.range_high = session_data['High'].max()
                self.range_low = session_data['Low'].min()
                self.range_set = True

                print(f"\n🎯 NY SESSION RANGE SET - Moon Dev Levels Locked!")
                print(f"📅 Date: {current_date}")
                print(f"📈 Range High: ${self.range_high:.2f}")
                print(f"📉 Range Low: ${self.range_low:.2f}")
                print(f"📏 Range Size: ${self.range_high - self.range_low:.2f}")

        # Reset range for next day
        elif current_time.hour >= 0 and current_time.hour < self.ny_open_hour:
            self.range_set = False
            self.range_high = None
            self.range_low = None

    def check_entry_signals(self, row, prev_row):
        """
        Check for breakout and retracement entry signals
        """
        if not self.range_set or self.in_position:
            return None

        current_price = row['Close']
        prev_price = prev_row['Close']

        # Long Signal: Price broke above range_high and retraced back into range
        if prev_price > self.range_high and current_price <= self.range_high and current_price > self.range_low:
            return 'long'

        # Short Signal: Price broke below range_low and retraced back into range
        elif prev_price < self.range_low and current_price >= self.range_low and current_price < self.range_high:
            return 'short'

        return None

    def execute_trade(self, signal, entry_price, entry_time, capital):
        """
        Execute trade with proper risk management
        """
        position_size = capital * self.position_size_pct

        if signal == 'long':
            stop_loss = self.range_low
            risk_per_share = entry_price - stop_loss
            take_profit = entry_price + (risk_per_share * self.risk_reward)

            print(f"\n🚀 LONG ENTRY - MOON DEV SIGNAL TRIGGERED!")
            print(f"⏰ Time: {entry_time}")
            print(f"💵 Entry Price: ${entry_price:.2f}")
            print(f"🛑 Stop Loss: ${stop_loss:.2f}")
            print(f"🎯 Take Profit: ${take_profit:.2f}")
            print(f"📊 Risk: ${risk_per_share:.2f} | Reward: ${risk_per_share * self.risk_reward:.2f}")

        else:  # short
            stop_loss = self.range_high
            risk_per_share = stop_loss - entry_price
            take_profit = entry_price - (risk_per_share * self.risk_reward)

            print(f"\n🔻 SHORT ENTRY - MOON DEV SIGNAL TRIGGERED!")
            print(f"⏰ Time: {entry_time}")
            print(f"💵 Entry Price: ${entry_price:.2f}")
            print(f"🛑 Stop Loss: ${stop_loss:.2f}")
            print(f"🎯 Take Profit: ${take_profit:.2f}")
            print(f"📊 Risk: ${risk_per_share:.2f} | Reward: ${risk_per_share * self.risk_reward:.2f}")

        self.in_position = True
        self.position_type = signal

        return {
            'entry_time': entry_time,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'signal': signal
        }

    def check_exit(self, current_price, current_time, trade_info):
        """
        Check if position should be closed
        """
        if not self.in_position:
            return None

        exit_reason = None
        exit_price = None

        if self.position_type == 'long':
            if current_price <= trade_info['stop_loss']:
                exit_reason = 'Stop Loss'
                exit_price = trade_info['stop_loss']
            elif current_price >= trade_info['take_profit']:
                exit_reason = 'Take Profit'
                exit_price = trade_info['take_profit']

        else:  # short
            if current_price >= trade_info['stop_loss']:
                exit_reason = 'Stop Loss'
                exit_price = trade_info['stop_loss']
            elif current_price <= trade_info['take_profit']:
                exit_reason = 'Take Profit'
                exit_price = trade_info['take_profit']

        if exit_reason:
            # Calculate P&L
            if self.position_type == 'long':
                pnl = (exit_price - trade_info['entry_price']) / trade_info['entry_price']
            else:
                pnl = (trade_info['entry_price'] - exit_price) / trade_info['entry_price']

            pnl_dollar = pnl * trade_info['position_size']

            # Print exit info
            emoji = "🎊" if pnl > 0 else "💔"
            print(f"\n{emoji} TRADE CLOSED - {exit_reason}")
            print(f"⏰ Exit Time: {current_time}")
            print(f"💵 Exit Price: ${exit_price:.2f}")
            print(f"📊 P&L: {pnl*100:.2f}% (${pnl_dollar:.2f})")

            # Reset position
            self.in_position = False
            self.position_type = None

            # Record trade
            self.trades.append({
                'entry_time': trade_info['entry_time'],
                'exit_time': current_time,
                'signal': trade_info['signal'],
                'entry_price': trade_info['entry_price'],
                'exit_price': exit_price,
                'pnl_pct': pnl * 100,
                'pnl_dollar': pnl_dollar,
                'exit_reason': exit_reason
            })

            return pnl_dollar

        return None

    def backtest(self, start_date='2024-01-01', end_date='2024-03-01', initial_capital=10000):
        """
        Run the full backtest
        """
        print("\n" + "=" * 80)
        print("🚀 STARTING MOON DEV BACKTEST - PREPARE FOR LIFTOFF! 🚀")
        print("=" * 80)

        # Download data
        self.download_data(start_date, end_date)

        # Initialize capital
        capital = initial_capital
        self.equity_curve = [capital]

        # Current trade info
        current_trade = None

        print(f"\n💰 Initial Capital: ${initial_capital:,.2f}")
        print("🔄 Starting backtest loop...\n")

        # Backtest loop
        for i in range(1, len(self.df_5min)):
            current_row = self.df_5min.iloc[i]
            prev_row = self.df_5min.iloc[i-1]
            current_time = self.df_5min.index[i]

            # Update NY session range
            self.identify_ny_session_range(current_time)

            # Check for entry signals
            if self.range_set and not self.in_position:
                signal = self.check_entry_signals(current_row, prev_row)
                if signal:
                    current_trade = self.execute_trade(
                        signal,
                        current_row['Close'],
                        current_time,
                        capital
                    )

            # Check for exit
            if self.in_position and current_trade:
                pnl = self.check_exit(
                    current_row['Close'],
                    current_time,
                    current_trade
                )
                if pnl is not None:
                    capital += pnl
                    current_trade = None

            # Update equity curve
            self.equity_curve.append(capital)

        print("\n" + "=" * 80)
        print("✅ BACKTEST COMPLETE - MOON DEV RESULTS READY!")
        print("=" * 80)

        return self.generate_report(initial_capital)

    def generate_report(self, initial_capital):
        """
        Generate comprehensive performance report
        """
        if len(self.trades) == 0:
            print("\n⚠️ No trades executed during backtest period")
            return None

        # Convert trades to DataFrame
        trades_df = pd.DataFrame(self.trades)

        # Calculate metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl_pct'] > 0])
        losing_trades = len(trades_df[trades_df['pnl_pct'] <= 0])
        win_rate = (winning_trades / total_trades) * 100

        avg_win = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl_pct'] <= 0]['pnl_pct'].mean() if losing_trades > 0 else 0

        total_pnl = trades_df['pnl_dollar'].sum()
        total_return = (total_pnl / initial_capital) * 100
        final_capital = self.equity_curve[-1]

        # Calculate max drawdown
        equity_series = pd.Series(self.equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()

        # Print report
        print("\n" + "=" * 80)
        print("📊 MOON DEV ALGO TRADE CAMP - PERFORMANCE REPORT 📊")
        print("=" * 80)

        print(f"\n📈 TRADE STATISTICS:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Winning Trades: {winning_trades} 🎯")
        print(f"   Losing Trades: {losing_trades} ❌")
        print(f"   Win Rate: {win_rate:.2f}%")
        print(f"   Average Win: {avg_win:.2f}%")
        print(f"   Average Loss: {avg_loss:.2f}%")

        print(f"\n💰 PERFORMANCE:")
        print(f"   Total P&L: ${total_pnl:,.2f}")
        print(f"   Total Return: {total_return:.2f}%")
        print(f"   Final Capital: ${final_capital:,.2f}")
        print(f"   Max Drawdown: {max_drawdown:.2f}%")
        print("=" * 80)

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'final_capital': final_capital,
            'max_drawdown': max_drawdown,
        }


if __name__ == "__main__":
    # Yahoo only retains 5-minute intraday history for roughly the last 60
    # days, so a fixed past date range (this used to be hardcoded to
    # 2024-01-01/2024-03-01) silently returns 0 rows once that window has
    # rolled past it. Use a window relative to today instead so this keeps
    # working whenever it's run.
    end = datetime.now()
    start = end - timedelta(days=55)
    strategy = NYSessionRangeStrategy(symbol='BTC-USD', risk_reward=2.0, position_size_pct=0.02)
    strategy.backtest(start_date=start.strftime('%Y-%m-%d'), end_date=end.strftime('%Y-%m-%d'), initial_capital=10000)
