"""
Moon Dev Quant Lab - Comparative Backtester
Compares Baseline OP Hull Suite Ribbon vs. Upgraded Strategy Pro Architecture.
"""

import os
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import warnings
warnings.filterwarnings('ignore')

# -----------------------------------------------------------------------------
# INDICATORS
# -----------------------------------------------------------------------------

def calc_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda w: np.dot(w, weights) / weights.sum(), raw=True)

def calc_thma(series, length):
    third_len = max(1, length // 3)
    half_len  = max(1, length // 2)
    w_third = calc_wma(series, third_len)
    w_half  = calc_wma(series, half_len)
    w_full  = calc_wma(series, length)
    diff = 3 * w_third - w_half - w_full
    return calc_wma(diff, length).to_numpy()

def calc_hma(series, length):
    half_len = max(1, length // 2)
    sqrt_len = max(1, int(np.round(np.sqrt(length))))
    w_half = calc_wma(series, half_len)
    w_full = calc_wma(series, length)
    diff = 2 * w_half - w_full
    return calc_wma(diff, sqrt_len).to_numpy()

def calc_atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean().to_numpy()

def compute_epoch_weight(mhull, shift=2):
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

def calc_adx(high, low, close, length=14):
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


# -----------------------------------------------------------------------------
# STRATEGY DEFINITION
# -----------------------------------------------------------------------------

class ModularOpHullStrategy(Strategy):
    hull_mode        = "THMA"
    length           = 21
    shift            = 2
    weight_threshold = 20.0
    use_ema_filter   = True
    use_adx_filter   = False   # Set True for Upgraded Pro version
    adx_threshold    = 18.0
    ema_len          = 200
    trade_direction  = "long"
    
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


# -----------------------------------------------------------------------------
# DATA LOADERS & BENCHMARK HARNESS
# -----------------------------------------------------------------------------

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


def run_comparative_benchmark():
    print("=" * 115)
    print(">>> MOON DEV QUANT LAB - HEAD-TO-HEAD STRATEGY UPGRADE BENCHMARK ($10,000 STARTING CAPITAL) <<<")
    print("Version 1 (Baseline Hull Ribbon)  vs.  Version 2 (Strategy Pro with ADX Expansion & Tuned Conviction)")
    print("=" * 115)
    
    test_suite = [
        {
            "asset": "SOL-USD (1H)",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv",
            "resample": "1h",
            "cash": 10000.0,
            "margin": 1.0,
            "comm": 0.0006,
            "v1_params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 20.0, "use_ema_filter": True, "use_adx_filter": False},
            "v2_params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 20.0, "use_ema_filter": True, "use_adx_filter": True, "adx_threshold": 18.0}
        },
        {
            "asset": "SOL-USD (4H)",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv",
            "resample": "4h",
            "cash": 10000.0,
            "margin": 1.0,
            "comm": 0.0006,
            "v1_params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 30.0, "use_ema_filter": False, "use_adx_filter": False},
            "v2_params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 30.0, "use_ema_filter": False, "use_adx_filter": True, "adx_threshold": 18.0}
        },
        {
            "asset": "ETH-USD (1H)",
            "file": r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2024-02-02_RSI_and_Bollinger_Bands_Retracement_ETH-USD-5m-2022-1-01T00_00.csv",
            "resample": "1h",
            "cash": 10000.0,
            "margin": 1.0,
            "comm": 0.0006,
            "v1_params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 25.0, "use_ema_filter": True, "use_adx_filter": False},
            "v2_params": {"hull_mode": "THMA", "length": 21, "weight_threshold": 25.0, "use_ema_filter": True, "use_adx_filter": True, "adx_threshold": 18.0}
        },
        {
            "asset": "/NQ Futures (1H)",
            "file": "synthetic",
            "resample": "1h",
            "cash": 10000.0,
            "margin": 0.1,
            "comm": 0.0002,
            "v1_params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 50.0, "use_ema_filter": True, "use_adx_filter": False},
            "v2_params": {"hull_mode": "THMA", "length": 34, "weight_threshold": 50.0, "use_ema_filter": True, "use_adx_filter": True, "adx_threshold": 18.0}
        }
    ]
    
    comparisons = []
    
    for item in test_suite:
        asset_name = item["asset"]
        if item["file"] == "synthetic":
            df = get_synthetic_nq(10000)
        else:
            df = load_clean_ohlcv(item["file"])
            
        if item["resample"]:
            df = resample_ohlcv(df, item["resample"])
            
        # 1. Run Baseline (V1)
        ModularOpHullStrategy.hull_mode = item["v1_params"]["hull_mode"]
        ModularOpHullStrategy.length = item["v1_params"]["length"]
        ModularOpHullStrategy.weight_threshold = item["v1_params"]["weight_threshold"]
        ModularOpHullStrategy.use_ema_filter = item["v1_params"]["use_ema_filter"]
        ModularOpHullStrategy.use_adx_filter = item["v1_params"]["use_adx_filter"]
        
        bt_v1 = Backtest(df, ModularOpHullStrategy, cash=item["cash"], margin=item["margin"], commission=item["comm"], exclusive_orders=True)
        s1 = bt_v1.run()
        
        # 2. Run Strategy Pro (V2)
        ModularOpHullStrategy.hull_mode = item["v2_params"]["hull_mode"]
        ModularOpHullStrategy.length = item["v2_params"]["length"]
        ModularOpHullStrategy.weight_threshold = item["v2_params"]["weight_threshold"]
        ModularOpHullStrategy.use_ema_filter = item["v2_params"]["use_ema_filter"]
        ModularOpHullStrategy.use_adx_filter = item["v2_params"]["use_adx_filter"]
        ModularOpHullStrategy.adx_threshold = item["v2_params"]["adx_threshold"]
        
        bt_v2 = Backtest(df, ModularOpHullStrategy, cash=item["cash"], margin=item["margin"], commission=item["comm"], exclusive_orders=True)
        s2 = bt_v2.run()
        
        ret_diff = s2['Return [%]'] - s1['Return [%]']
        pf_diff  = s2['Profit Factor'] - s1['Profit Factor']
        dd_diff  = s2['Max. Drawdown [%]'] - s1['Max. Drawdown [%]']
        
        comparisons.append({
            "Asset": asset_name,
            "V1 Net Ret": f"{s1['Return [%]']:+.2f}%",
            "V2 Pro Ret": f"{s2['Return [%]']:+.2f}%",
            "Delta Ret": f"{ret_diff:+.2f}%",
            "V1 WR": f"{s1['Win Rate [%]']:.1f}%",
            "V2 WR": f"{s2['Win Rate [%]']:.1f}%",
            "V1 PF": f"{s1['Profit Factor']:.2f}",
            "V2 PF": f"{s2['Profit Factor']:.2f}",
            "V1 Sortino": f"{s1['Sortino Ratio']:.2f}",
            "V2 Sortino": f"{s2['Sortino Ratio']:.2f}",
            "V1 MaxDD": f"{s1['Max. Drawdown [%]']:.1f}%",
            "V2 MaxDD": f"{s2['Max. Drawdown [%]']:.1f}%",
            "V1 Trades": s1['# Trades'],
            "V2 Trades": s2['# Trades']
        })
        
    comp_df = pd.DataFrame(comparisons)
    print("\n" + "=" * 115)
    print("                     [+] HEAD-TO-HEAD PERFORMANCE COMPARISON TABLE")
    print("=" * 115)
    print(comp_df.to_string(index=False))
    print("=" * 115)
    return comp_df

if __name__ == "__main__":
    run_comparative_benchmark()
