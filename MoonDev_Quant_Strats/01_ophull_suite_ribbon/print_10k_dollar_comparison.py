import pandas as pd
import numpy as np
from backtesting import Backtest
from run_comparative_backtest import ModularOpHullStrategy, load_clean_ohlcv, get_synthetic_nq

test_suite = [
    {
        'asset': 'SOL-USD (4H)',
        'file': r'C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv',
        'resample': '4h',
        'margin': 1.0,
        'comm': 0.0006,
        'v1': {'hull_mode': 'THMA', 'length': 34, 'weight_threshold': 30.0, 'use_ema_filter': False, 'use_adx_filter': False},
        'v2': {'hull_mode': 'THMA', 'length': 34, 'weight_threshold': 30.0, 'use_ema_filter': False, 'use_adx_filter': True, 'adx_threshold': 18.0}
    },
    {
        'asset': 'SOL-USD (1H)',
        'file': r'C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2026-08-19_Bearish_Harami_Cross_Strategy_storage_SOL-USD15m24.csv',
        'resample': '1h',
        'margin': 1.0,
        'comm': 0.0006,
        'v1': {'hull_mode': 'THMA', 'length': 21, 'weight_threshold': 20.0, 'use_ema_filter': True, 'use_adx_filter': False},
        'v2': {'hull_mode': 'THMA', 'length': 21, 'weight_threshold': 20.0, 'use_ema_filter': True, 'use_adx_filter': True, 'adx_threshold': 18.0}
    },
    {
        'asset': '/NQ Futures (1H)',
        'file': 'synthetic',
        'resample': '1h',
        'margin': 0.1,
        'comm': 0.0002,
        'v1': {'hull_mode': 'THMA', 'length': 34, 'weight_threshold': 50.0, 'use_ema_filter': True, 'use_adx_filter': False},
        'v2': {'hull_mode': 'THMA', 'length': 34, 'weight_threshold': 50.0, 'use_ema_filter': True, 'use_adx_filter': True, 'adx_threshold': 18.0}
    },
    {
        'asset': 'ETH-USD (1H)',
        'file': r'C:\Users\ixis1\Desktop\MoonDev_Quant_Elite_Code\2024-02-02_RSI_and_Bollinger_Bands_Retracement_ETH-USD-5m-2022-1-01T00_00.csv',
        'resample': '1h',
        'margin': 1.0,
        'comm': 0.0006,
        'v1': {'hull_mode': 'THMA', 'length': 21, 'weight_threshold': 25.0, 'use_ema_filter': True, 'use_adx_filter': False},
        'v2': {'hull_mode': 'THMA', 'length': 21, 'weight_threshold': 25.0, 'use_ema_filter': True, 'use_adx_filter': True, 'adx_threshold': 18.0}
    }
]

rows = []
for item in test_suite:
    if item['file'] == 'synthetic':
        df = get_synthetic_nq(10000)
    else:
        df = load_clean_ohlcv(item['file'])
    if item['resample']:
        df = df.resample(item['resample']).agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        
    # V1
    for k, v in item['v1'].items():
        setattr(ModularOpHullStrategy, k, v)
    bt1 = Backtest(df, ModularOpHullStrategy, cash=10000.0, margin=item['margin'], commission=item['comm'], exclusive_orders=True)
    s1 = bt1.run()
    
    # V2
    for k, v in item['v2'].items():
        setattr(ModularOpHullStrategy, k, v)
    bt2 = Backtest(df, ModularOpHullStrategy, cash=10000.0, margin=item['margin'], commission=item['comm'], exclusive_orders=True)
    s2 = bt2.run()
    
    v1_profit = s1['Equity Final [$]'] - 10000.0
    v2_profit = s2['Equity Final [$]'] - 10000.0
    delta_profit = v2_profit - v1_profit
    
    rows.append({
        'Asset': item['asset'],
        'Start Cash': '$10,000.00',
        'V1 Final Eq': f"${s1['Equity Final [$]']:,.2f}",
        'V2 Final Eq': f"${s2['Equity Final [$]']:,.2f}",
        'V1 Net Profit': f"${v1_profit:+,.2f}",
        'V2 Net Profit': f"${v2_profit:+,.2f}",
        'Profit Delta': f"${delta_profit:+,.2f}",
        'V2 Net Ret': f"{s2['Return [%]']:+.2f}%",
        'V2 WR': f"{s2['Win Rate [%]']:.1f}%",
        'V2 PF': f"{s2['Profit Factor']:.2f}"
    })

res_df = pd.DataFrame(rows)
print("\n" + "=" * 120)
print("            [+] EXACT DOLLAR GROWTH COMPARISON ON A $10,000.00 STARTING ACCOUNT")
print("=" * 120)
print(res_df.to_string(index=False))
print("=" * 120)
