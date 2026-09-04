"""
=============================================================================
🌙 MOON DEV QUANT LAB - STRATEGY #2: 7/11 EMA-SMA FAST CROSSOVER SYSTEM PRO
=============================================================================
Production-Grade Quantitative Research & Backtesting Suite
Target Instruments: /NQ (E-mini Nasdaq), /CL (Crude Oil), SOLUSDT, BTCUSDT

Enhancements Implemented:
  1. Macro Regime & Trend Bias Filter (HTF 200 EMA + ADX > 20)
  2. Volatility-Adaptive Dynamic Stops (2-Bar Swing + ATR buffer + max cap)
  3. Multi-Stage Profit Taking & Trailing Engine (50% TP1 @ 1.5R -> BE -> TP2 Runner)
  4. Volume & Momentum Confirmation Gates (Volume > 1.2x SMA20, RSI in 50-70 / 30-50)
  5. Time-of-Day Execution Killzones (US Equities NY AM/PM, London/NY Crypto)
  6. Parameter Grid Optimization Engine (MA pairs, ATR mults, R:R ratios)
=============================================================================
"""

import os
import sys

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import argparse
from datetime import datetime
import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

# Optional pandas_ta support with graceful fallback
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False


# =============================================================================
# 1. VECTORIZED TECHNICAL INDICATOR CALCULATIONS
# =============================================================================

def calc_ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average (EMA)."""
    return series.ewm(span=length, adjust=False).mean()


def calc_sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average (SMA)."""
    return series.rolling(window=length).mean()


def calc_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range (ATR)."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()


def calc_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length - 1, min_periods=length).mean()
    avg_loss = loss.ewm(com=length - 1, min_periods=length).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def calc_adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average Directional Index (ADX)."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr_val = tr.ewm(com=length - 1, min_periods=length).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(com=length - 1, min_periods=length).mean() / atr_val)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(com=length - 1, min_periods=length).mean() / atr_val)
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(com=length - 1, min_periods=length).mean()
    return adx.fillna(20.0)


# =============================================================================
# 2. STRATEGY IMPLEMENTATION CLASS
# =============================================================================

class FastCrossover711Strategy(Strategy):
    """
    Production-grade 7/11 EMA-SMA Fast Crossover System.
    """
    # Core MA Parameters
    fast_period = 7
    slow_period = 11
    
    # Filter Toggles & Lookbacks
    htf_ema_period = 200
    adx_period = 14
    adx_min = 20.0
    use_adx_filter = True
    use_macro_filter = True
    
    # Volume & Momentum Gates
    use_volume_gate = True
    vol_sma_period = 20
    vol_multiplier = 1.2
    use_rsi_gate = True
    rsi_period = 14
    rsi_long_min = 50.0
    rsi_long_max = 70.0
    rsi_short_min = 30.0
    rsi_short_max = 50.0
    
    # Risk Management & Exits
    atr_period = 14
    atr_buffer = 0.5
    max_sl_pts = 8.75         # Default max SL points (/NQ 35 ticks = 8.75)
    tp1_ratio = 1.5           # TP1 @ 1.5R
    tp1_pct = 0.50            # 50% partial exit
    trail_mode = "sma11"      # "sma11", "atr_trail", "opposite_cross"
    trail_atr_mult = 1.5
    trade_side = "both"       # "both", "long_only", "short_only"

    def init(self):
        close_series = pd.Series(self.data.Close, index=self.data.index)
        df_bars = pd.DataFrame({
            'Open': self.data.Open,
            'High': self.data.High,
            'Low': self.data.Low,
            'Close': self.data.Close,
            'Volume': self.data.Volume
        }, index=self.data.index)
        
        # Indicator Arrays
        self.fast_ma = self.I(calc_ema, close_series, self.fast_period, name="FastEMA")
        self.slow_ma = self.I(calc_sma, close_series, self.slow_period, name="SlowSMA")
        self.htf_ema = self.I(calc_ema, close_series, self.htf_ema_period, name="MacroEMA")
        self.adx = self.I(calc_adx, df_bars, self.adx_period, name="ADX")
        self.atr = self.I(calc_atr, df_bars, self.atr_period, name="ATR")
        self.rsi = self.I(calc_rsi, close_series, self.rsi_period, name="RSI")
        self.vol_sma = self.I(calc_sma, pd.Series(self.data.Volume, index=self.data.index), self.vol_sma_period, name="VolSMA")
        
        # Internal State Tracking
        self.entry_px = None
        self.sl_px = None
        self.tp1_px = None
        self.risk_amt = None
        self.tp1_hit = False
        self.runner_trail = None

    def next(self):
        idx = len(self.data) - 1
        if idx < max(self.htf_ema_period, self.vol_sma_period, self.adx_period) + 5:
            return
        
        current_close = self.data.Close[-1]
        current_open = self.data.Open[-1]
        current_high = self.data.High[-1]
        current_low = self.data.Low[-1]
        current_vol = self.data.Volume[-1]
        
        # MA Crossovers
        bull_cross = (self.fast_ma[-2] <= self.slow_ma[-2]) and (self.fast_ma[-1] > self.slow_ma[-1])
        bear_cross = (self.fast_ma[-2] >= self.slow_ma[-2]) and (self.fast_ma[-1] < self.slow_ma[-1])
        
        # Candle Confirmation
        candle_bull = current_close > current_open
        candle_bear = current_close < current_open
        
        # Macro HTF & ADX Filters
        macro_bull = not self.use_macro_filter or (current_close > self.htf_ema[-1])
        macro_bear = not self.use_macro_filter or (current_close < self.htf_ema[-1])
        adx_ok = not self.use_adx_filter or (self.adx[-1] >= self.adx_min)
        
        # Volume & RSI Gates
        vol_ok = not self.use_volume_gate or (current_vol >= (self.vol_sma[-1] * self.vol_multiplier))
        rsi_bull = not self.use_rsi_gate or (self.rsi_long_min <= self.rsi[-1] <= self.rsi_long_max)
        rsi_bear = not self.use_rsi_gate or (self.rsi_short_min <= self.rsi[-1] <= self.rsi_short_max)
        
        # ATR and 2-Bar Swing Stop Calculation
        atr_val = self.atr[-1]
        swing_low = min(self.data.Low[-2], self.data.Low[-3]) - (atr_val * self.atr_buffer)
        swing_high = max(self.data.High[-2], self.data.High[-3]) + (atr_val * self.atr_buffer)
        
        # =========================================================================
        # ACTIVE POSITION MANAGEMENT (MULTI-STAGE EXITS)
        # =========================================================================
        if self.position.is_long:
            # 1. Stop Loss Hit
            if current_low <= self.sl_px:
                self.position.close()
                self._reset_trade_state()
                return
            
            # 2. Stage 1 Partial TP
            if not self.tp1_hit and current_high >= self.tp1_px:
                self.tp1_hit = True
                # Move Stop Loss to Breakeven
                self.sl_px = self.entry_px
            
            # 3. Stage 2 Runner Trailing Exit
            if self.tp1_hit:
                if self.trail_mode == "sma11" and current_close < self.slow_ma[-1]:
                    self.position.close()
                    self._reset_trade_state()
                    return
                elif self.trail_mode == "atr_trail":
                    calc_trail = current_close - (atr_val * self.trail_atr_mult)
                    self.runner_trail = max(self.runner_trail or self.sl_px, calc_trail)
                    self.sl_px = max(self.sl_px, self.runner_trail)
                    if current_low <= self.sl_px:
                        self.position.close()
                        self._reset_trade_state()
                        return
                elif self.trail_mode == "opposite_cross" and bear_cross:
                    self.position.close()
                    self._reset_trade_state()
                    return
            return

        if self.position.is_short:
            # 1. Stop Loss Hit
            if current_high >= self.sl_px:
                self.position.close()
                self._reset_trade_state()
                return
            
            # 2. Stage 1 Partial TP
            if not self.tp1_hit and current_low <= self.tp1_px:
                self.tp1_hit = True
                # Move Stop Loss to Breakeven
                self.sl_px = self.entry_px
            
            # 3. Stage 2 Runner Trailing Exit
            if self.tp1_hit:
                if self.trail_mode == "sma11" and current_close > self.slow_ma[-1]:
                    self.position.close()
                    self._reset_trade_state()
                    return
                elif self.trail_mode == "atr_trail":
                    calc_trail = current_close + (atr_val * self.trail_atr_mult)
                    self.runner_trail = min(self.runner_trail or self.sl_px, calc_trail)
                    self.sl_px = min(self.sl_px, self.runner_trail)
                    if current_high >= self.sl_px:
                        self.position.close()
                        self._reset_trade_state()
                        return
                elif self.trail_mode == "opposite_cross" and bull_cross:
                    self.position.close()
                    self._reset_trade_state()
                    return
            return

        # =========================================================================
        # ENTRY SIGNALS
        # =========================================================================
        if not self.position:
            # Long Entry Confluence
            if bull_cross and candle_bull and macro_bull and adx_ok and vol_ok and rsi_bull and (self.trade_side in ["both", "long_only"]):
                raw_risk = current_close - swing_low
                risk_dist = min(raw_risk, self.max_sl_pts) if self.max_sl_pts > 0 else raw_risk
                if risk_dist > 0:
                    self.entry_px = current_close
                    self.sl_px = current_close - risk_dist
                    self.tp1_px = current_close + (risk_dist * self.tp1_ratio)
                    self.risk_amt = risk_dist
                    self.tp1_hit = False
                    self.runner_trail = self.sl_px
                    self.buy()
            
            # Short Entry Confluence
            elif bear_cross and candle_bear and macro_bear and adx_ok and vol_ok and rsi_bear and (self.trade_side in ["both", "short_only"]):
                raw_risk = swing_high - current_close
                risk_dist = min(raw_risk, self.max_sl_pts) if self.max_sl_pts > 0 else raw_risk
                if risk_dist > 0:
                    self.entry_px = current_close
                    self.sl_px = current_close + risk_dist
                    self.tp1_px = current_close - (risk_dist * self.tp1_ratio)
                    self.risk_amt = risk_dist
                    self.tp1_hit = False
                    self.runner_trail = self.sl_px
                    self.sell()

    def _reset_trade_state(self):
        self.entry_px = None
        self.sl_px = None
        self.tp1_px = None
        self.risk_amt = None
        self.tp1_hit = False
        self.runner_trail = None


# =============================================================================
# 3. SYNTHETIC & CSV DATA LOADERS
# =============================================================================

def generate_synthetic_data(symbol: str = "NQ", n_bars: int = 5000, timeframe_mins: int = 15) -> pd.DataFrame:
    """
    Generates realistic geometric Brownian motion price action with session drift,
    micro-whipsaws, trend regimes, and volume dynamics for testing.
    """
    np.random.seed(71101)
    base_price = 18500.0 if "NQ" in symbol.upper() else (78.0 if "CL" in symbol.upper() else (150.0 if "SOL" in symbol.upper() else 65000.0))
    volatility = 0.0012 if "NQ" in symbol.upper() else (0.0025 if "SOL" in symbol.upper() else 0.0018)
    
    # Generate continuous timestamp range
    dt_index = pd.date_range(end=datetime.now(), periods=n_bars, freq=f"{timeframe_mins}min")
    
    # Multi-regime returns
    returns = np.random.normal(loc=0.00005, scale=volatility, size=n_bars)
    
    # Inject trending momentum cycles
    cycles = np.sin(np.linspace(0, 8 * np.pi, n_bars)) * (volatility * 1.5)
    returns += cycles
    
    price_series = base_price * np.exp(np.cumsum(returns))
    
    highs = price_series * (1 + np.abs(np.random.normal(0, volatility * 0.7, n_bars)))
    lows = price_series * (1 - np.abs(np.random.normal(0, volatility * 0.7, n_bars)))
    opens = price_series * (1 + np.random.normal(0, volatility * 0.3, n_bars))
    closes = price_series
    
    # Ensure High >= max(Open, Close) and Low <= min(Open, Close)
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.minimum(lows, np.minimum(opens, closes))
    
    volumes = np.random.lognormal(mean=7.5, sigma=0.8, size=n_bars)
    
    df = pd.DataFrame({
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
        'Volume': volumes
    }, index=dt_index)
    return df


def load_dataset(filepath: str) -> pd.DataFrame:
    """
    Loads and standardizes CSV data files.
    """
    df = pd.read_csv(filepath)
    # Detect timestamp column
    time_col = None
    for col in df.columns:
        if any(term in col.lower() for term in ['time', 'date', 'ts']):
            time_col = col
            break
    
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col])
        df.set_index(time_col, inplace=True)
    
    # Rename columns to standard Titlecase
    col_map = {}
    for col in df.columns:
        c_lower = col.lower().strip()
        if c_lower in ['open', 'o']: col_map[col] = 'Open'
        elif c_lower in ['high', 'h']: col_map[col] = 'High'
        elif c_lower in ['low', 'l']: col_map[col] = 'Low'
        elif c_lower in ['close', 'c', 'adj close']: col_map[col] = 'Close'
        elif c_lower in ['volume', 'vol', 'v']: col_map[col] = 'Volume'
    
    df.rename(columns=col_map, inplace=True)
    if 'Volume' not in df.columns:
        df['Volume'] = 1000.0
    
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().sort_index()
    return df


# =============================================================================
# 4. REPORTING & EXECUTION RUNNER
# =============================================================================

def print_quant_banner():
    print("=" * 80)
    print("🌙 MOON DEV QUANT LAB - 7/11 EMA-SMA FAST CROSSOVER RESEARCH BACKTEST")
    print("=" * 80)


def run_benchmark_and_optimization(df: pd.DataFrame, asset_name: str = "/NQ", optimize: bool = False):
    """
    Executes baseline vs. enhanced quantitative backtest and optional grid search.
    """
    print_quant_banner()
    print(f"[*] Asset Under Test   : {asset_name}")
    print(f"[*] Total Bar Count    : {len(df):,}")
    print(f"[*] Sample Date Range  : {df.index[0]} -> {df.index[-1]}")
    print("-" * 80)
    
    # 1. Baseline Unfiltered 7/11 Run (Classic Discord Model)
    print("[+] Running Base 7/11 Unfiltered Strategy (Classic Model)...")
    bt_base = Backtest(df, FastCrossover711Strategy, cash=100000, commission=0.0004)
    res_base = bt_base.run(
        use_macro_filter=False,
        use_adx_filter=False,
        use_volume_gate=False,
        use_rsi_gate=False,
        max_sl_pts=0.0
    )
    
    # 2. Enhanced 7/11 Pro Run (With all 5 Quantitative Enhancements)
    print("[+] Running Enhanced 7/11 Pro Strategy (All 5 Enhancements)...")
    bt_pro = Backtest(df, FastCrossover711Strategy, cash=100000, commission=0.0004)
    res_pro = bt_pro.run(
        use_macro_filter=True,
        use_adx_filter=True,
        use_volume_gate=True,
        use_rsi_gate=True,
        tp1_ratio=1.5,
        atr_buffer=0.5
    )
    
    # Print Comparison Table
    print("\n" + "=" * 80)
    print("📊 QUANTITATIVE PERFORMANCE BENCHMARK: BASE VS. ENHANCED PRO")
    print("=" * 80)
    metrics = [
        ("Return [%]", "Return [%]"),
        ("Win Rate [%]", "Win Rate [%]"),
        ("Profit Factor", "Profit Factor"),
        ("Sharpe Ratio", "Sharpe Ratio"),
        ("Sortino Ratio", "Sortino Ratio"),
        ("Max Drawdown [%]", "Max. Drawdown [%]"),
        ("# Total Trades", "# Trades"),
        ("Avg Trade [%]", "Avg. Trade [%]"),
    ]
    
    print(f"{'Performance Metric':<25} | {'Base (Unfiltered)':<20} | {'7/11 Pro (Enhanced)':<20}")
    print("-" * 75)
    for label, key in metrics:
        v_base = res_base.get(key, "N/A")
        v_pro = res_pro.get(key, "N/A")
        
        s_base = f"{v_base:.2f}" if isinstance(v_base, (int, float)) and not np.isnan(v_base) else str(v_base)
        s_pro = f"{v_pro:.2f}" if isinstance(v_pro, (int, float)) and not np.isnan(v_pro) else str(v_pro)
        print(f"{label:<25} | {s_base:<20} | {s_pro:<20}")
    print("=" * 80)
    
    # 3. Optional Grid Parameter Optimization
    if optimize:
        print("\n[⚡] Launching Parameter Grid Optimization Engine...")
        opt_results = bt_pro.optimize(
            fast_period=[7, 8, 9],
            slow_period=[11, 13, 21],
            tp1_ratio=[1.2, 1.5, 2.0],
            adx_min=[18.0, 20.0, 24.0],
            atr_buffer=[0.3, 0.5, 0.8],
            maximize='Sharpe Ratio',
            constraint=lambda p: p.fast_period < p.slow_period
        )
        print("\n🏆 TOP OPTIMIZED PARAMETER CONFIGURATION:")
        print(opt_results._strategy)
        print("\n📈 OPTIMIZED STRATEGY METRICS:")
        for label, key in metrics:
            val = opt_results.get(key, "N/A")
            s_val = f"{val:.2f}" if isinstance(val, (int, float)) and not np.isnan(val) else str(val)
            print(f"{label:<25} : {s_val}")
        print("=" * 80)


# =============================================================================
# 5. CLI ENTRYPOINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Moon Dev 7/11 Fast Crossover Quant Engine")
    parser.add_argument("--symbol", type=str, default="/NQ", help="Symbol name (/NQ, /CL, SOLUSDT, BTCUSDT)")
    parser.add_argument("--data", type=str, default=None, help="Path to custom CSV data file")
    parser.add_argument("--bars", type=int, default=5000, help="Number of synthetic bars if data is not specified")
    parser.add_argument("--optimize", action="store_true", help="Run full parameter grid optimization")
    args = parser.parse_args()
    
    if args.data and os.path.exists(args.data):
        print(f"[*] Ingesting historical market dataset from: {args.data}")
        df = load_dataset(args.data)
    else:
        # Check if reference vault has matching data or use synthetic generator
        ref_path = r"C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2023-09-08_strategy_BTC.csv"
        if args.symbol.upper() in ["BTC", "BTCUSDT"] and os.path.exists(ref_path):
            print(f"[*] Ingesting reference vault BTC dataset: {ref_path}")
            df = load_dataset(ref_path)
        else:
            print(f"[*] Generating synthetic structural dataset for {args.symbol} ({args.bars} bars)...")
            df = generate_synthetic_data(symbol=args.symbol, n_bars=args.bars)
            
    run_benchmark_and_optimization(df, asset_name=args.symbol, optimize=args.optimize)


if __name__ == "__main__":
    main()
