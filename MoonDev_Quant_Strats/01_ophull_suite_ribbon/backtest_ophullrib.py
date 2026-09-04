"""
=============================================================================
🌙 MOON DEV QUANT LAB - STRATEGY #1: OP HULL SUITE RIBBON (OPHULLRIB)
=============================================================================
Production-Grade Backtesting Engine for TradingView OP Hull Ribbon Strategy.
Compatible with backtesting.py, pandas, and numpy.

Features:
- Fast vectorized WMA/EMA/HMA/EHMA/THMA moving averages.
- Normalized Distance Weight Oscillator & Zero-Cross Conviction Accumulator.
- Dynamic ATR-based Stop Loss & Take Profit limits.
- Full parameter optimization engine & Moon Dev performance metrics report.
=============================================================================
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

# =============================================================================
# VECTORIZED INDICATOR MATHEMATICS
# =============================================================================

def calc_wma(series: pd.Series, length: int) -> pd.Series:
    """Vectorized Weighted Moving Average (WMA)."""
    length = int(length)
    if length <= 1:
        return series
    weights = np.arange(1, length + 1)
    
    def _weighted_mean(window):
        return np.dot(window, weights) / weights.sum()
    
    return series.rolling(length).apply(_weighted_mean, raw=True)


def calc_ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average (EMA)."""
    length = int(length)
    return series.ewm(span=length, adjust=False).mean()


def calc_hma(series: pd.Series, length: int) -> np.ndarray:
    """Standard Hull Moving Average (HMA)."""
    length = int(length)
    half_len = max(1, length // 2)
    sqrt_len = max(1, int(np.round(np.sqrt(length))))
    
    wma_half = calc_wma(series, half_len)
    wma_full = calc_wma(series, length)
    diff = 2 * wma_half - wma_full
    hma = calc_wma(diff, sqrt_len)
    return hma.to_numpy()


def calc_ehma(series: pd.Series, length: int) -> np.ndarray:
    """Exponential Hull Moving Average (EHMA)."""
    length = int(length)
    half_len = max(1, length // 2)
    sqrt_len = max(1, int(np.round(np.sqrt(length))))
    
    ema_half = calc_ema(series, half_len)
    ema_full = calc_ema(series, length)
    diff = 2 * ema_half - ema_full
    ehma = calc_ema(diff, sqrt_len)
    return ehma.to_numpy()


def calc_thma(series: pd.Series, length: int) -> np.ndarray:
    """Triple Hull Moving Average (THMA) - Ultra low lag & high smoothness."""
    length = int(length)
    third_len = max(1, length // 3)
    half_len  = max(1, length // 2)
    
    wma_third = calc_wma(series, third_len)
    wma_half  = calc_wma(series, half_len)
    wma_full  = calc_wma(series, length)
    
    diff = 3 * wma_third - wma_half - wma_full
    thma = calc_wma(diff, length)
    return thma.to_numpy()


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> np.ndarray:
    """Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr.to_numpy()


def compute_epoch_weight_conviction(mhull: np.ndarray, shift: int = 2) -> np.ndarray:
    """
    Normalized Distance Weight Oscillator & Epoch Conviction Accumulator.
    Measures normalized distance strain between MHULL and SHULL,
    accumulating weight until ribbon crossover/crossunder reset.
    Returns: Array of previous epoch accumulated conviction values.
    """
    n = len(mhull)
    shull = np.roll(mhull, shift)
    shull[:shift] = mhull[:shift]
    
    # Normalized distance (per thousand)
    max_hull = np.maximum(mhull, shull)
    max_hull = np.where(max_hull == 0, 1e-8, max_hull)
    norm_dist = ((shull - mhull) / max_hull) * 1000.0
    
    prev_epoch_weights = np.zeros(n, dtype=np.float64)
    cum_weight = 0.0
    
    for i in range(1, n):
        curr_m, curr_s = mhull[i], shull[i]
        prev_m, prev_s = mhull[i-1], shull[i-1]
        
        # Check crossover or crossunder
        crossed = (curr_m >= curr_s and prev_m < prev_s) or \
                  (curr_m <= curr_s and prev_m > prev_s) or \
                  (curr_m == curr_s)
        
        if crossed:
            prev_epoch_weights[i] = cum_weight
            cum_weight = 0.0
        else:
            prev_epoch_weights[i] = cum_weight
            cum_weight += norm_dist[i]
            
    return prev_epoch_weights


def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> np.ndarray:
    """Average Directional Index (ADX) - Wilder's Directional Movement."""
    plus_dm = high.diff().clip(lower=0)          # +DM = max(high - prev_high, 0)
    minus_dm = (-low.diff()).clip(lower=0)        # -DM = max(prev_low - low, 0)
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(length).mean()
    atr = atr.replace(0, np.nan)
    plus_di = 100 * (plus_dm.rolling(length).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(length).mean() / atr)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.rolling(length).mean().fillna(0)
    return adx.to_numpy()


# =============================================================================
# BACKTESTING.PY STRATEGY CLASS
# =============================================================================

class OpHullRibStrategy(Strategy):
    """
    OP Hull Suite Ribbon Strategy Pro.
    """
    # Tunable Hyperparameters
    hull_mode        = "THMA"   # "HMA", "EHMA", "THMA"
    length           = 21       # Lookback period
    shift            = 2        # Ribbon lookback shift
    use_weight_filter= True     # Enable conviction oscillator filter
    weight_threshold = 20.0     # Threshold conviction
    use_ema_filter   = True     # 200 EMA Macro Trend Filter
    ema_len          = 200      # Macro EMA Lookback
    use_adx_filter   = True     # ADX Volatility Expansion Filter
    adx_threshold    = 18.0     # Minimum ADX
    exit_mode        = "reversal" # "reversal", "reversal_trail", "fixed_atr"
    atr_period       = 14       # ATR Lookback
    sl_atr_mult      = 3.5      # Stop Loss (x ATR)
    tp_atr_mult      = 6.0      # Take Profit (x ATR)
    trade_direction  = "both"   # "both", "long", "short"

    def init(self):
        close_series = pd.Series(self.data.Close, index=range(len(self.data.Close)))
        high_series  = pd.Series(self.data.High, index=range(len(self.data.High)))
        low_series   = pd.Series(self.data.Low, index=range(len(self.data.Low)))
        
        # 1. Hull Moving Average Selection
        if self.hull_mode.upper() == "EHMA":
            self.mhull = self.I(calc_ehma, close_series, self.length, name="MHULL")
        elif self.hull_mode.upper() == "HMA":
            self.mhull = self.I(calc_hma, close_series, self.length, name="MHULL")
        else: # THMA
            self.mhull = self.I(calc_thma, close_series, self.length, name="MHULL")
            
        # 2. Shifted Hull
        def _get_shull(m_arr, s):
            arr = np.roll(m_arr, s)
            arr[:s] = m_arr[:s]
            return arr
        self.shull = self.I(_get_shull, self.mhull, self.shift, name="SHULL")
        
        # 3. Conviction Weight Accumulator
        self.conviction_weight = self.I(compute_epoch_weight_conviction, self.mhull, self.shift, name="PREV_EPOCH_WEIGHT")
        
        # 4. Macro 200 EMA Filter
        self.macro_ema = self.I(lambda s: s.ewm(span=self.ema_len).mean().to_numpy(), close_series, name="EMA200")
        
        # 5. ADX Filter
        self.adx = self.I(calc_adx, high_series, low_series, close_series, 14, name="ADX")
        
        # 6. ATR
        self.atr = self.I(calc_atr, high_series, low_series, close_series, self.atr_period, name="ATR")

    def next(self):
        # Ensure sufficient lookback warm up
        if len(self.data) < max(self.length, self.ema_len, self.atr_period) + 5:
            return
            
        curr_price = self.data.Close[-1]
        curr_atr   = self.atr[-1]
        macro_ema  = self.macro_ema[-1]
        adx_val    = self.adx[-1]
        
        if np.isnan(curr_atr) or curr_atr <= 0:
            return
            
        mhull_curr = self.mhull[-1]
        mhull_prev = self.mhull[-2]
        shull_curr = self.shull[-1]
        shull_prev = self.shull[-2]
        
        # Crossover & Crossunder
        bull_cross = (mhull_curr > shull_curr) and (mhull_prev <= shull_prev)
        bear_cross = (mhull_curr < shull_curr) and (mhull_prev >= shull_prev)
        
        # Filters
        trend_bull = not self.use_ema_filter or (curr_price > macro_ema)
        trend_bear = not self.use_ema_filter or (curr_price < macro_ema)
        adx_ok     = not self.use_adx_filter or (adx_val >= self.adx_threshold)
        
        # Weight Conviction
        prev_weight = self.conviction_weight[-1]
        long_valid  = (not self.use_weight_filter or prev_weight > self.weight_threshold or self.weight_threshold == 0) and trend_bull and adx_ok
        short_valid = (not self.use_weight_filter or prev_weight < -self.weight_threshold or self.weight_threshold == 0) and trend_bear and adx_ok
        
        # Reversal Exits
        if self.exit_mode in ("reversal", "reversal_trail"):
            if bear_cross and self.position.is_long:
                self.position.close()
            if bull_cross and self.position.is_short:
                self.position.close()
        
        # Long Entry Trigger
        if bull_cross and long_valid and self.trade_direction in ("both", "long"):
            if self.position.is_short:
                self.position.close()
            if not self.position.is_long:
                if self.exit_mode == "fixed_atr":
                    sl = curr_price - (curr_atr * self.sl_atr_mult)
                    tp = curr_price + (curr_atr * self.tp_atr_mult)
                    self.buy(sl=sl, tp=tp)
                else:
                    self.buy()
            
        # Short Entry Trigger
        elif bear_cross and short_valid and self.trade_direction in ("both", "short"):
            if self.position.is_long:
                self.position.close()
            if not self.position.is_short:
                if self.exit_mode == "fixed_atr":
                    sl = curr_price + (curr_atr * self.sl_atr_mult)
                    tp = curr_price - (curr_atr * self.tp_atr_mult)
                    self.sell(sl=sl, tp=tp)
                else:
                    self.sell()


# =============================================================================
# DATA LOADER & EXECUTION HARNESS
# =============================================================================

def load_data(filepath: str) -> pd.DataFrame:
    """Loads CSV data and formats standard OHLCV columns."""
    df = pd.read_csv(filepath)
    
    # Check date column
    date_col = None
    for col in ['Datetime', 'datetime', 'Date', 'date', 'Timestamp', 'timestamp', 'time']:
        if col in df.columns:
            date_col = col
            break
            
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        df.set_index(date_col, inplace=True)
        df.sort_index(inplace=True)
        
    # Standardize column naming
    rename_dict = {}
    for col in df.columns:
        c_lower = col.lower()
        if c_lower == 'open':
            rename_dict[col] = 'Open'
        elif c_lower == 'high':
            rename_dict[col] = 'High'
        elif c_lower == 'low':
            rename_dict[col] = 'Low'
        elif c_lower == 'close':
            rename_dict[col] = 'Close'
        elif c_lower in ['volume', 'vol']:
            rename_dict[col] = 'Volume'
            
    df.rename(columns=rename_dict, inplace=True)
    required = ['Open', 'High', 'Low', 'Close']
    for req in required:
        if req not in df.columns:
            raise ValueError(f"Required OHLC column '{req}' not found in CSV.")
            
    if 'Volume' not in df.columns:
        df['Volume'] = 1000.0
        
    df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
    return df


def generate_synthetic_nq_data(bars: int = 5000) -> pd.DataFrame:
    """Generates synthetic high-fidelity 15m /NQ data for test validation."""
    np.random.seed(42)
    dt_range = pd.date_range(end=pd.Timestamp.now(), periods=bars, freq='15min')
    returns = np.random.normal(0.0001, 0.003, bars)
    price = 18000.0 * np.exp(np.cumsum(returns))
    
    high = price * (1 + np.abs(np.random.normal(0, 0.0015, bars)))
    low  = price * (1 - np.abs(np.random.normal(0, 0.0015, bars)))
    open_p = price * (1 + np.random.normal(0, 0.0008, bars))
    volume = np.random.uniform(500, 5000, bars)
    
    df = pd.DataFrame({
        'Open': open_p,
        'High': np.maximum(high, np.maximum(open_p, price)),
        'Low':  np.minimum(low, np.minimum(open_p, price)),
        'Close': price,
        'Volume': volume
    }, index=dt_range)
    return df


def print_moondev_banner():
    print("=" * 78)
    print(">>> MOON DEV QUANT LAB - STRATEGY #1: OP HULL SUITE RIBBON (OPHULLRIB) <<<")
    print("=" * 78)


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Resamples OHLCV dataframe to target timeframe frequency (e.g. '1h', '4h', '15min', '1d')."""
    res = df.resample(freq).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return res


def run_backtest(data_path: str = None, preset: str = "sol", timeframe: str = "1h", years: float = 3.0, cash: float = 10000.0, commission: float = 0.0006, optimize: bool = False, plot_chart: bool = False):
    print_moondev_banner()
    
    # 1. Load Data
    if data_path and os.path.exists(data_path):
        print(f"[*] Loading custom dataset: {data_path}")
        df = load_data(data_path)
    else:
        # Default 3-year multi-asset datasets
        if preset.lower() == "btc":
            btc_default = r"C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv"
            print(f"[*] Loading 3-Year BTC-USD dataset from DEV archive...")
            df = load_data(btc_default)
        elif preset.lower() == "eth":
            eth_default = r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2024-02-02_RSI_and_Bollinger_Bands_Retracement_ETH-USD-5m-2022-1-01T00_00.csv"
            print(f"[*] Loading Multi-Year ETH-USD dataset from Moon Dev vault...")
            df = load_data(eth_default)
        elif preset.lower() == "sol":
            sol_default = r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv"
            print(f"[*] Loading SOL-USD historical dataset from Moon Dev vault...")
            df = load_data(sol_default)
        else: # nq
            print(f"[*] Generating 3-Year /NQ Futures dataset (10,000 bars)...")
            df = generate_synthetic_nq_data(10000)
            
    # 2. Filter Date Range (Last N Years if applicable)
    if years and years > 0 and len(df) > 100:
        cutoff_date = df.index[-1] - pd.Timedelta(days=int(years * 365.25))
        if cutoff_date > df.index[0]:
            df = df[df.index >= cutoff_date]
            print(f"[*] Filtered for the last {years:g} years: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
            
    # 3. Resample Timeframe
    if timeframe and timeframe.lower() not in ("15m", "15min", "raw", "none"):
        tf_map = {"1h": "1h", "4h": "4h", "1d": "1D", "30m": "30min", "5m": "5min"}
        target_tf = tf_map.get(timeframe.lower(), timeframe)
        orig_len = len(df)
        df = resample_ohlcv(df, target_tf)
        print(f"[*] Resampled candles from {orig_len:,} bars to {len(df):,} ({target_tf}) bars")
        
    print(f"[*] Active Data Window: {len(df):,} bars ({df.index[0]} to {df.index[-1]})")
    
    # 4. Configure Preset Parameters
    account_cash = cash
    margin_val = 1.0
    
    # Auto-adjust margin if unit price exceeds cash (e.g. BTC or NQ with $10k cash)
    max_price = df['Close'].max()
    if max_price > account_cash:
        margin_val = min(0.1, account_cash / max_price)
        print(f"[*] Adjusted Margin to {margin_val:.4f} (Leverage enabled) because asset price (${max_price:,.0f}) exceeds account cash (${account_cash:,.0f})")

    if preset.lower() == "sol":
        OpHullRibStrategy.hull_mode = "THMA"
        OpHullRibStrategy.length = 21
        OpHullRibStrategy.weight_threshold = 20.0
        OpHullRibStrategy.use_ema_filter = True
        OpHullRibStrategy.trade_direction = "long"
        OpHullRibStrategy.exit_mode = "reversal"
        print("[*] Active Preset: SOL-USD (THMA len=21, weight_thresh=20, EMA200=ON, Exit=Reversal, Long-Only)")
    elif preset.lower() == "btc":
        OpHullRibStrategy.hull_mode = "THMA"
        OpHullRibStrategy.length = 34
        OpHullRibStrategy.weight_threshold = 30.0
        OpHullRibStrategy.use_ema_filter = True
        OpHullRibStrategy.trade_direction = "long"
        OpHullRibStrategy.exit_mode = "reversal"
        print(f"[*] Active Preset: BTC-USD (THMA len=34, weight_thresh=30, EMA200=ON, Exit=Reversal, Long-Only)")
    elif preset.lower() == "eth":
        OpHullRibStrategy.hull_mode = "THMA"
        OpHullRibStrategy.length = 21
        OpHullRibStrategy.weight_threshold = 25.0
        OpHullRibStrategy.use_ema_filter = True
        OpHullRibStrategy.trade_direction = "long"
        OpHullRibStrategy.exit_mode = "reversal"
        print(f"[*] Active Preset: ETH-USD (THMA len=21, weight_thresh=25, EMA200=ON, Exit=Reversal, Long-Only)")
    elif preset.lower() == "nq":
        OpHullRibStrategy.hull_mode = "THMA"
        OpHullRibStrategy.length = 34
        OpHullRibStrategy.weight_threshold = 50.0
        OpHullRibStrategy.use_ema_filter = True
        OpHullRibStrategy.trade_direction = "long"
        OpHullRibStrategy.exit_mode = "reversal"
        margin_val = 0.1 # 10x futures margin
        print(f"[*] Active Preset: /NQ Futures (THMA len=34, weight_thresh=50, EMA200=ON, Exit=Reversal, Margin=10x)")

    # 5. Instantiate Backtester
    bt = Backtest(df, OpHullRibStrategy, cash=account_cash, margin=margin_val, commission=commission, exclusive_orders=True)
    
    if optimize:
        print("\n[*] Running Parameter Optimization Sweep...")
        stats = bt.optimize(
            length=range(15, 65, 10),
            weight_threshold=range(10, 80, 15),
            maximize='Sharpe Ratio'
        )
        print("\n[+] Optimization Results:")
        print(stats._strategy)
    else:
        print("\n[*] Executing Backtest...")
        stats = bt.run()

    # 6. Print Formatted Report
    print("\n" + "=" * 54)
    print(f"       [+] {preset.upper()} ({timeframe.upper()}) PERFORMANCE METRICS")
    print("=" * 54)
    print(f"  Starting Capital:      ${account_cash:,.2f}")
    print(f"  Ending Equity:         ${stats['Equity Final [$]']:,.2f}")
    print(f"  Total Net Return:      {stats['Return [%]']:.2f}%")
    print(f"  Buy & Hold Return:     {stats['Buy & Hold Return [%]']:.2f}%")
    print(f"  Win Rate:              {stats['Win Rate [%]']:.2f}%")
    print(f"  Profit Factor:         {stats['Profit Factor']:.2f}")
    print(f"  Sharpe Ratio:          {stats['Sharpe Ratio']:.2f}")
    print(f"  Sortino Ratio:         {stats['Sortino Ratio']:.2f}")
    print(f"  Max Drawdown:          {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  Avg Trade Duration:    {stats['Avg. Trade Duration']}")
    print(f"  Total Trades Closed:   {stats['# Trades']}")
    print("=" * 54)
    
    if plot_chart:
        chart_filename = f"chart_{preset.lower()}_{timeframe.lower()}_backtest.html"
        full_chart_path = os.path.abspath(chart_filename)
        print(f"\n[*] Generating interactive 3-Year HTML visual chart...")
        bt.plot(filename=chart_filename, open_browser=False)
        print(f"[+] Interactive chart saved successfully:")
        print(f"    --> {full_chart_path}")
        
    return stats


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Moon Dev OP Hull Ribbon Python Backtester")
    parser.add_argument("--data", type=str, default=None, help="Path to input CSV data file")
    parser.add_argument("--preset", type=str, default="sol", choices=["sol", "nq", "btc", "eth", "custom"], help="Asset volatility preset")
    parser.add_argument("--timeframe", "--tf", type=str, default="1h", help="Timeframe (e.g. 15m, 1h, 4h, 1d)")
    parser.add_argument("--years", type=float, default=3.0, help="Lookback window in years (e.g. 3.0)")
    parser.add_argument("--cash", type=float, default=10000.0, help="Initial account cash (default: $10,000)")
    parser.add_argument("--commission", type=float, default=0.0006, help="Commission per trade (0.0006 = 0.06%)")
    parser.add_argument("--optimize", action="store_true", help="Run hyperparameter optimization grid")
    parser.add_argument("--plot", action="store_true", help="Generate HTML interactive visual plot")
    
    args = parser.parse_args()
    run_backtest(
        data_path=args.data,
        preset=args.preset,
        timeframe=args.timeframe,
        years=args.years,
        cash=args.cash,
        commission=args.commission,
        optimize=args.optimize,
        plot_chart=args.plot
    )
