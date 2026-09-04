"""
=============================================================================
🌙 MOON DEV QUANT LAB - MULTI-PRODUCT BACKTEST HARNESS
=============================================================================
Strategy #1: OP Hull Suite Ribbon (ophullrib)
Benchmarked across SOL-USD, BTC-USD, ETH-USD, and /NQ Futures.
=============================================================================
"""

import os
import glob
import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

# =============================================================================
# INDICATOR FUNCTIONS
# =============================================================================

def calc_wma(series: pd.Series, length: int) -> pd.Series:
    length = int(length)
    if length <= 1:
        return series
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda w: np.dot(w, weights) / weights.sum(), raw=True)


def calc_ema(series: pd.Series, length: int) -> pd.Series:
    length = int(length)
    return series.ewm(span=length, adjust=False).mean()


def calc_hma(series: pd.Series, length: int) -> np.ndarray:
    length = int(length)
    half_len = max(1, length // 2)
    sqrt_len = max(1, int(np.round(np.sqrt(length))))
    w_half = calc_wma(series, half_len)
    w_full = calc_wma(series, length)
    diff = 2 * w_half - w_full
    return calc_wma(diff, sqrt_len).to_numpy()


def calc_thma(series: pd.Series, length: int) -> np.ndarray:
    length = int(length)
    third_len = max(1, length // 3)
    half_len  = max(1, length // 2)
    w_third = calc_wma(series, third_len)
    w_half  = calc_wma(series, half_len)
    w_full  = calc_wma(series, length)
    diff = 3 * w_third - w_half - w_full
    return calc_wma(diff, length).to_numpy()


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> np.ndarray:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean().to_numpy()


def compute_epoch_weight(mhull: np.ndarray, shift: int = 2) -> np.ndarray:
    n = len(mhull)
    shull = np.roll(mhull, shift)
    shull[:shift] = mhull[:shift]
    max_h = np.maximum(mhull, shull)
    max_h = np.where(max_h == 0, 1e-8, max_h)
    norm_dist = ((shull - mhull) / max_h) * 1000.0
    prev_weights = np.zeros(n)
    cum = 0.0
    for i in range(1, n):
        crossed = (mhull[i] >= shull[i] and mhull[i-1] < shull[i-1]) or \
                  (mhull[i] <= shull[i] and mhull[i-1] > shull[i-1]) or \
                  (mhull[i] == shull[i])
        if crossed:
            prev_weights[i] = cum
            cum = 0.0
        else:
            prev_weights[i] = cum
            cum += norm_dist[i]
    return prev_weights


def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> np.ndarray:
    """Average Directional Index (ADX) - Wilder's Directional Movement."""
    plus_dm = high.diff().clip(lower=0)          # +DM = max(high - prev_high, 0)
    minus_dm = (-low.diff()).clip(lower=0)        # -DM = max(prev_low - low, 0)
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(length).mean().replace(0, np.nan)
    plus_di = 100 * (plus_dm.rolling(length).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(length).mean() / atr)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.rolling(length).mean().fillna(0)
    return adx.to_numpy()


# =============================================================================
# STRATEGY CLASS
# =============================================================================

class MultiAssetOpHullStrategy(Strategy):
    hull_mode        = "THMA"
    length           = 21
    shift            = 2
    weight_threshold = 20.0
    use_ema_filter   = True
    use_adx_filter   = True
    adx_threshold    = 18.0
    ema_len          = 200
    trade_direction  = "long"   # "long", "both"
    exit_mode        = "reversal" # "reversal"
    
    def init(self):
        close_s = pd.Series(self.data.Close, index=range(len(self.data.Close)))
        high_s  = pd.Series(self.data.High, index=range(len(self.data.High)))
        low_s   = pd.Series(self.data.Low, index=range(len(self.data.Low)))
        
        if self.hull_mode.upper() == "HMA":
            self.mhull = self.I(calc_hma, close_s, self.length, name="MHULL")
        else:
            self.mhull = self.I(calc_thma, close_s, self.length, name="MHULL")
            
        def _get_shull(m_arr, s):
            arr = np.roll(m_arr, s)
            arr[:s] = m_arr[:s]
            return arr
            
        self.shull = self.I(_get_shull, self.mhull, self.shift, name="SHULL")
        self.weights = self.I(compute_epoch_weight, self.mhull, self.shift, name="WEIGHT")
        self.macro_ema = self.I(lambda s: s.ewm(span=self.ema_len).mean().to_numpy(), close_s, name="EMA200")
        self.adx = self.I(calc_adx, high_s, low_s, close_s, 14, name="ADX")
        
    def next(self):
        if len(self.data) < max(self.length, self.ema_len) + 20:
            return
            
        curr_price = self.data.Close[-1]
        macro_ema  = self.macro_ema[-1]
        adx_val    = self.adx[-1]
        mhull_curr = self.mhull[-1]
        mhull_prev = self.mhull[-2]
        shull_curr = self.shull[-1]
        shull_prev = self.shull[-2]
        w          = self.weights[-1]
        
        bull_cross = (mhull_curr > shull_curr) and (mhull_prev <= shull_prev)
        bear_cross = (mhull_curr < shull_curr) and (mhull_prev >= shull_prev)
        
        trend_bull = not self.use_ema_filter or (curr_price > macro_ema)
        trend_bear = not self.use_ema_filter or (curr_price < macro_ema)
        adx_ok     = not self.use_adx_filter or (adx_val >= self.adx_threshold)
        
        long_ok  = (w > self.weight_threshold or self.weight_threshold == 0) and trend_bull and adx_ok
        short_ok = (w < -self.weight_threshold or self.weight_threshold == 0) and trend_bear and adx_ok
        
        # Exit on opposite ribbon crossover
        if bear_cross and self.position.is_long:
            self.position.close()
        if bull_cross and self.position.is_short:
            self.position.close()
            
        # Entry
        if bull_cross and long_ok and self.trade_direction in ("both", "long"):
            if not self.position.is_long:
                self.buy()
        elif bear_cross and short_ok and self.trade_direction in ("both", "short"):
            if not self.position.is_short:
                self.sell()


# =============================================================================
# DATA HELPERS & RESAMPLING
# =============================================================================

def load_clean_ohlcv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    date_col = None
    for col in ['Datetime', 'datetime', 'Date', 'date', 'Timestamp', 'timestamp', 'time']:
        if col in df.columns:
            date_col = col
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        df.set_index(date_col, inplace=True)
        df.sort_index(inplace=True)
        
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
    if 'Volume' not in df.columns:
        df['Volume'] = 1000.0
    df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
    return df


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    res = df.resample(freq).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return res


def get_synthetic_nq(bars: int = 10000) -> pd.DataFrame:
    np.random.seed(42)
    dt_range = pd.date_range(end=pd.Timestamp.now(), periods=bars, freq='15min')
    returns = np.random.normal(0.00012, 0.0035, bars)
    price = 18000.0 * np.exp(np.cumsum(returns))
    high = price * (1 + np.abs(np.random.normal(0, 0.0015, bars)))
    low  = price * (1 - np.abs(np.random.normal(0, 0.0015, bars)))
    open_p = price * (1 + np.random.normal(0, 0.0008, bars))
    volume = np.random.uniform(500, 5000, bars)
    return pd.DataFrame({
        'Open': open_p,
        'High': np.maximum(high, np.maximum(open_p, price)),
        'Low':  np.minimum(low, np.minimum(open_p, price)),
        'Close': price,
        'Volume': volume
    }, index=dt_range)


# =============================================================================
# MULTI-PRODUCT BACKTEST EXECUTION
# =============================================================================

def run_all_product_backtests(years: float = 3.0, cash: float = 10000.0, generate_charts: bool = True):
    print("=" * 96)
    print(">>> MOON DEV QUANT LAB - 3-YEAR MULTI-PRODUCT QUANT BENCHMARK ($10,000 Starting Cash) <<<")
    print("Strategy #1: OP Hull Suite Ribbon (THMA / HMA + Weight Conviction + 200 EMA + Reversal Exits)")
    print("=" * 96)
    
    products = [
        {
            "name": "SOL-USD (15m)",
            "chart_name": "chart_benchmark_sol_15m.html",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv",
            "resample": None,
            "cash": cash,
            "margin": 1.0,
            "comm": 0.0006,
            "params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 20.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "SOL-USD (1H)",
            "chart_name": "chart_benchmark_sol_1h.html",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv",
            "resample": "1h",
            "cash": cash,
            "margin": 1.0,
            "comm": 0.0006,
            "params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 20.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "SOL-USD (4H)",
            "chart_name": "chart_benchmark_sol_4h.html",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv",
            "resample": "4h",
            "cash": cash,
            "margin": 1.0,
            "comm": 0.0006,
            "params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 30.0, "use_ema_filter": False, "trade_direction": "long"}
        },
        {
            "name": "ETH-USD (15m)",
            "chart_name": "chart_benchmark_eth_15m.html",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2024-02-02_RSI_and_Bollinger_Bands_Retracement_ETH-USD-5m-2022-1-01T00_00.csv",
            "resample": "15min",
            "cash": cash,
            "margin": 1.0,
            "comm": 0.0006,
            "params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 30.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "ETH-USD (1H)",
            "chart_name": "chart_benchmark_eth_1h.html",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2024-02-02_RSI_and_Bollinger_Bands_Retracement_ETH-USD-5m-2022-1-01T00_00.csv",
            "resample": "1h",
            "cash": cash,
            "margin": 1.0,
            "comm": 0.0006,
            "params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 25.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "BTC-USD (15m)",
            "chart_name": "chart_benchmark_btc_15m.html",
            "file": r"C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv",
            "resample": None,
            "cash": cash,
            "margin": 0.1,  # 10x margin for BTC with $10k cash
            "comm": 0.0004,
            "params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 50.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "BTC-USD (1H)",
            "chart_name": "chart_benchmark_btc_1h.html",
            "file": r"C:\Users\ixis1\Desktop\DEV\backtesting\BTC-USD-15m-2020-2-02T00_00.csv",
            "resample": "1h",
            "cash": cash,
            "margin": 0.1,  # 10x margin for BTC with $10k cash
            "comm": 0.0004,
            "params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 30.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "/NQ Futures (15m)",
            "chart_name": "chart_benchmark_nq_15m.html",
            "file": "synthetic",
            "resample": None,
            "cash": cash,
            "margin": 0.1,  # 10x futures margin
            "comm": 0.0002,
            "params": {"hull_mode": "HMA", "length": 55, "weight_threshold": 75.0, "use_ema_filter": True, "trade_direction": "long"}
        },
        {
            "name": "/NQ Futures (1H)",
            "chart_name": "chart_benchmark_nq_1h.html",
            "file": "synthetic",
            "resample": "1h",
            "cash": cash,
            "margin": 0.1,  # 10x futures margin
            "comm": 0.0002,
            "params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 50.0, "use_ema_filter": True, "trade_direction": "long"}
        }
    ]
    
    summary_rows = []
    generated_charts = []
    
    for item in products:
        p_name = item["name"]
        print(f"\n[*] Benchmarking {p_name} ($10k Capital, 3-Year Window)...")
        
        if item["file"] == "synthetic":
            df = get_synthetic_nq(10000)
        else:
            df = load_clean_ohlcv(item["file"])
            
        # 3-Year Date Cutoff Slicing
        if years and years > 0 and len(df) > 100:
            cutoff_date = df.index[-1] - pd.Timedelta(days=int(years * 365.25))
            if cutoff_date > df.index[0]:
                df = df[df.index >= cutoff_date]
                
        # Resampling
        if item["resample"]:
            df = resample_ohlcv(df, item["resample"])
            
        # Margin sanity check
        margin_val = item["margin"]
        max_p = df['Close'].max()
        if max_p > cash and margin_val >= 1.0:
            margin_val = min(0.1, cash / max_p)
            
        # Apply parameters
        MultiAssetOpHullStrategy.hull_mode = item["params"]["hull_mode"]
        MultiAssetOpHullStrategy.length = item["params"]["length"]
        MultiAssetOpHullStrategy.weight_threshold = item["params"]["weight_threshold"]
        MultiAssetOpHullStrategy.use_ema_filter = item["params"]["use_ema_filter"]
        MultiAssetOpHullStrategy.trade_direction = item["params"]["trade_direction"]
        
        bt = Backtest(df, MultiAssetOpHullStrategy, cash=cash, margin=margin_val, commission=item["comm"], exclusive_orders=True)
        stats = bt.run()
        
        end_eq = stats['Equity Final [$]']
        ret_pct = stats['Return [%]']
        bh_pct  = stats['Buy & Hold Return [%]']
        wr_pct  = stats['Win Rate [%]']
        pf      = stats['Profit Factor']
        sharpe  = stats['Sharpe Ratio']
        sortino = stats['Sortino Ratio']
        max_dd  = stats['Max. Drawdown [%]']
        trades  = stats['# Trades']
        
        summary_rows.append({
            "Asset / Timeframe": p_name,
            "Window": f"{df.index[0].strftime('%Y/%m')} - {df.index[-1].strftime('%Y/%m')}",
            "Ending Equity": f"${end_eq:,.2f}",
            "Return [%]": f"{ret_pct:+.2f}%",
            "B&H [%]": f"{bh_pct:+.2f}%",
            "Win Rate": f"{wr_pct:.1f}%",
            "PF": f"{pf:.2f}",
            "Sharpe": f"{sharpe:.2f}",
            "Sortino": f"{sortino:.2f}",
            "Max DD": f"{max_dd:.2f}%",
            "Trades": trades
        })
        
        if generate_charts:
            chart_file = item["chart_name"]
            try:
                bt.plot(filename=chart_file, open_browser=False)
                generated_charts.append(os.path.abspath(chart_file))
            except Exception as e:
                pass
                
    summary_df = pd.DataFrame(summary_rows)
    print("\n" + "=" * 108)
    print("                 [+] 3-YEAR MULTI-PRODUCT QUANT BENCHMARK LEADERBOARD ($10,000 STARTING CASH)")
    print("=" * 108)
    print(summary_df.to_string(index=False))
    print("=" * 108)
    
    if generated_charts:
        print("\n[+] Generated Interactive HTML Visual Charts:")
        for cp in generated_charts:
            print(f"    --> {cp}")
            
    return summary_df


if __name__ == "__main__":
    run_all_product_backtests(years=3.0, cash=10000.0, generate_charts=True)
