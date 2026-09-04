# moondev day 10 bootcamp  https://www.youtube.com/watch?v=5ln12H3OSMM

# key = 'klhjklhjklhjklhjk' -- this is whats in the dontshareconfig.py

'''
building a bot to trade new altcoins on hyperliquid 
pip install hyperliquid-python-sdk

only way to get access to hyperliquid and 
save huge on fees: https://app.hyperliquid.xyz/join/MOONDEV 

Success
- we can now get bid/ask, change leverage, and make orders

RBI 
R - researching different strategies
B - backtest those strategies
I - implement to bots, small size 30 days, scale if good

ex - https://github.com/hyperliquid-dex/hyperliquid-python-sdk 
docs- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint 
examples - https://github.com/hyperliquid-dex/hyperliquid-python-sdk/tree/master/examples 

todo -
- figure out how to round price per symbol
- cancel only symbols order, one at a time
- get data from HL
'''

from dontshare import key  
# key = 'klhjklhjklhjklhjk' -- this is whats in the dontshareconfig.py (private key, keep safe af)

from eth_account.signers.local import LocalAccount
import eth_account
import json
import time 
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import pandas as pd
from datetime import datetime, timedelta
import schedule 
import requests
import pandas_ta as ta

# ==============================
# CONFIG
# ==============================
symbol = 'SOL' 
timeframe = '15m'
limit = 1000 
max_loss = -1
target = 5
pos_size = 200
leverage = 10
vol_multiplier = 3
rounding = 4

# ==============================
# FUNCTIONS
# ==============================



def ask_bid(symbol):
    '''this gets the ask and bid for any symbol passed in'''
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    orderbook = info.l2_book(symbol)
    bid = float(orderbook['levels'][0][0]['px'])
    ask = float(orderbook['levels'][1][0]['px'])
    return ask, bid, orderbook



def limit_order(coin: str, is_buy: bool, sz: float, limit_px: float, reduce_only: bool = False):
    account = eth_account.Account.from_key(key)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    rounding = get_sz_px_decimals(coin)[0]
    sz = round(sz, rounding)
    print(f'placing limit order for {coin} {sz} @ {limit_px}')
    order_result = exchange.order(coin, is_buy, sz, limit_px, {"limit": {"tif": "Gtc"}}, reduce_only=reduce_only)

    if is_buy:
        print(f"limit BUY order placed, resting: {order_result['response']['data']['statuses'][0]}")
    else:
        print(f"limit SELL order placed, resting: {order_result['response']['data']['statuses'][0]}")

    return order_result



 
def get_sz_px_decimals(symbol):
    '''
    Returns size and price decimals for a symbol.
    '''
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}
    data = {'type': 'meta'}

    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        data = response.json()
        symbols = data['universe']
        symbol_info = next((s for s in symbols if s['name'] == symbol), None)
        if symbol_info:
            sz_decimals = symbol_info['szDecimals']
        else:
            print('Symbol not found')
            sz_decimals = 0
    else:
        print('Error:', response.status_code)
        sz_decimals = 0

    ask = ask_bid(symbol)[0]
    ask_str = str(ask)
    if '.' in ask_str:
        px_decimals = len(ask_str.split('.')[1])
    else:
        px_decimals = 0

    print(f'{symbol} size decimals {sz_decimals}, price decimals {px_decimals}')
    return sz_decimals, px_decimals




def adjust_leverage_size_symbol(symbol, leverage, account):
    '''
    Calculates trade size based on leverage and account balance (95%).
    '''
    account = eth_account.Account.from_key(key)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)

    user_state = info.user_state(account.address)
    acct_value = float(user_state["marginSummary"]["accountValue"])
    acct_val95 = acct_value * 0.95
    
    print(exchange.update_leverage(leverage, symbol))

    price = ask_bid(symbol)[0]
    size = (acct_val95 / price) * leverage
    rounding = get_sz_px_decimals(symbol)[0]
    size = round(size, rounding)

    return leverage, size




def get_ohlcv(symbol, interval, limit):
    '''
    Gets OHLCV candles directly from Hyperliquid.
    '''
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    bars = info.candle_snapshot(symbol, interval, limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    return df




def supply_demand_zones(symbol, timeframe, limit):
    '''
    Calculates supply and demand zones from OHLCV.
    '''
    print('calculating supply and demand zones...')
    df = get_ohlcv(symbol, timeframe, limit)
    supp = df['close'][:-2].min()
    resis = df['close'][:-2].max()
    supp_lo = df['low'][:-2].min()
    res_hi = df['high'][:-2].max()

    sd_df = pd.DataFrame({
        f'{timeframe}_dz': [supp_lo, supp],
        f'{timeframe}_sz': [res_hi, resis]
    })
    print(sd_df)
    return sd_df




def get_position_andmaxpos(symbol, account, max_positions):
    '''
    Gets the current position info.
    '''
    account = eth_account.Account.from_key(key)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    user_state = info.user_state(account.address)
    print(f'account value: {user_state["marginSummary"]["accountValue"]}')

    positions = []
    in_pos = False
    size = 0
    pos_sym = None
    entry_px = 0
    pnl_perc = 0
    long = None

    for position in user_state["assetPositions"]:
        if (position["position"]["coin"] == symbol) and float(position["position"]["szi"]) != 0:
            positions.append(position["position"])
            in_pos = True
            size = float(position["position"]["szi"])
            pos_sym = position["position"]["coin"]
            entry_px = float(position["position"]["entryPx"])
            pnl_perc = float(position["position"]["returnOnEquity"]) * 100
            long = size > 0
            break

    return positions, in_pos, size, pos_sym, entry_px, pnl_perc, long




def cancel_all_orders():
    account = eth_account.Account.from_key(key)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)

    open_orders = info.open_orders(account.address)
    for open_order in open_orders:
        exchange.cancel(open_order['coin'], open_order['oid'])




def volume_spike(df):
    df['MA_Volume'] = df['volume'].rolling(window=20).mean()
    df['MA_Close'] = df['close'].rolling(window=20).mean()
    latest = df.iloc[-1]
    return latest['volume'] > vol_multiplier * latest['MA_Volume'] and latest['MA_Close'] > latest['close']



def kill_switch(symbol):
    positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, long = get_position_andmaxpos(symbol, None, 1)
    while im_in_pos:
        cancel_all_orders()
        ask, bid, _ = ask_bid(pos_sym)
        pos_size = abs(pos_size)
        if long:
            limit_order(pos_sym, False, pos_size, ask)
        else:
            limit_order(pos_sym, True, pos_size, bid)
        time.sleep(5)
        positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, long = get_position_andmaxpos(symbol, None, 1)



def pnl_close(symbol):
    positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, long = get_position_andmaxpos(symbol, None, 1)
    if pnl_perc > target:
        print('closing WIN position')
        kill_switch(pos_sym)
    elif pnl_perc <= max_loss:
        print('closing LOSS position')
        kill_switch(pos_sym)




def close_all_positions(account):
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    user_state = info.user_state(account.address)
    cancel_all_orders()
    for position in user_state["assetPositions"]:
        if float(position["position"]["szi"]) != 0:
            kill_switch(position["position"]["coin"])




def calculate_bollinger_bands(df, length=20, std_dev=2):
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    bb = ta.bbands(df['close'], length=length, std=std_dev)
    bb = bb.iloc[:, :3]
    bb.columns = ['BBL', 'BBM', 'BBU']
    df = pd.concat([df, bb], axis=1)
    df['BandWidth'] = df['BBU'] - df['BBL']
    tight = df['BandWidth'].iloc[-1] <= df['BandWidth'].quantile(0.2)
    wide = df['BandWidth'].iloc[-1] >= df['BandWidth'].quantile(0.8)
    return df, tight, wide



def process_data_to_df(snapshot_data):
    if not snapshot_data:
        return pd.DataFrame()
    data = []
    for snap in snapshot_data:
        timestamp = datetime.fromtimestamp(snap['t'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        data.append([timestamp, snap['o'], snap['h'], snap['l'], snap['c'], snap['v']])
    df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume'])
    if len(df) > 2:
        df['support'] = df[:-2]['close'].min()
        df['resis'] = df[:-2]['close'].max()
    else:
        df['support'] = df['close'].min()
        df['resis'] = df['close'].max()
    return df





def get_ohlcv2(symbol, interval, lookback_days):
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    now = int(datetime.now().timestamp() * 1000)
    start = int((datetime.now() - timedelta(days=lookback_days)).timestamp() * 1000)
    candles = info.candle_snapshot(symbol, interval, 500)
    return candles




def fetch_candle_snapshot(symbol, interval, start_time, end_time):
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}
    data = {
        'type': 'candle_snapshot',
        "req": {
            "coinname": symbol,
            "interval": interval,
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000),
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        snapshot_data = response.json()
        return snapshot_data
    else:
        print(f"Error fetching data for {symbol}: {response.status_code}")
        return None




def calculate_sma(prices, window):
    sma = prices.rolling(window=window).mean()
    return sma.iloc[-1]    # Return the mmost recent SMA value

def get_latest_sma(symbol, timeframe, sma_window, lookback_days=1):
    start_time =  datetime.now() - timedelta(days=lookback_days)
    end_time = datetime.now()

    snapshots =  fetch_candle_snapshot(symbol, timeframe, start_time, end_time)
    if snapshots:
        prices =  pd.Series([float(snapshot['c']) for snapshot in snapshots])
        latest_sma =  calculate_sma(prices, sma_window)
        return latest_sma
    else:
        return None




def supply_demand_zones_hl(symbol, timeframe, limit):

    print('starting moons supply and demand zone calculations..')

    sd_df = pd. DataFrame()

    snapshot_data =  get_ohlcv2(symbol, timeframe, limit)
    df = process_data_to_df(snapshot_data)

    supp =  df.iloc[-1]['support']
    resis =  df.iloc[-1]['resis']
    #print(f'this is moons support fo 1h {supp_1h}) this is resis: {resis_1h}')

    df['supp_lo'] = df[:-2]['low'].max()
    supp_lo = df.iloc[-1]['supp_lo']

    df['res_hi'] = df[:-2]['high'].max()
    res_hi = df.iloc[-1]=['res_hi']

    #print(df)

    sd_df[f'{timeframe}_dz'] =[supp_lo, supp]
    sd_df[f'{timeframe}_sz'] =[res_hi, resis]

    print('here are moons supply and demand zones')
    print(sd_df)

    return sd_df

def calculate_vwap_with_symbol(symbol):
    # Fetch and process data
    snapshot_data = get_ohlcv2(symbol, '15m', 300)
    df = process_data_to_df(snapshot_data)

    # convert the 'timestamp' column to datetime and set as the index
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Ensure all columns used for VWAP calculation are of numeric type
    numeric_columns = ['high', 'low', 'close', 'volume']
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors='coerce')   # 'coerce' will set errors to NaN

    # Drop rpws with NaNs created during type conversion (if any)
    df.dropna(subset=numeric_columns, inplace=True)

    # Ensure the DataFrams is ordered by datetime
    df.sort_index(inplace=True)

    # Calculate VWAP and add it as a new column
    df['VWAP'] = ta.vwap(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'])

    # Retieve the latest VWAP value from the DataFrame
    latest_vwap = df['VWAP'].iloc[-1]

    return df, latest_vwap


