#moondev day 10 bootcamp  https://www.youtube.com/watch?v=5ln12H3OSMM

#key = 'klhjklhjklhjklhjk' -- this is whats in the dontshareconfig.py


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
- cancel only symbols order, one at at atime
- get data from HL
'''


from dontshare import key  
#key = 'klhjklhjklhjklhjk' -- this is whats in the dontshareconfig.py (private key, keep safe af)


from eth_account.signers.local import LocalAccount
import eth_account
import json
import time 
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import schedule 
import requests
import pandas_ta as ta


symbol = 'SOL' 
timeframe = '15m'
limit = 1000 
max_loss = -1
target = 5
pos_size = 200
leverage = 10
vol_multiplier = 3
rounding = 4


cb_symbol = symbol + '/USDT' #BTC/USD


def ask_bid(symbol):
    '''this gets the ask and bid for any symbol passed in'''

    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}


    data = {
        'type': 'l2Book',
        'coin': symbol
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    l2_data = response.json()
    l2_data = l2_data['levels']
    #print(l2_data)

    # get bid and ask 
    bid = float(l2_data[0][0]['px'])
    ask = float(l2_data[1][0]['px'])

    return ask, bid, l2_data

def limit_order(coin: str, is_buy: bool, sz: float, limit_px: float, reduce_only: bool = False):
    account: LocalAccount = eth_account.Account.from_key(key)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    rounding = get_sz_px_decimals(coin)[0]
    sz = round(sz,rounding)
    # limit_px = round(limit_px,rounding)
    print(f'placing limit order for {coin} {sz} @ {limit_px}')
    order_result = exchange.order(coin, is_buy, sz, limit_px, {"limit": {"tif": "Gtc"}}, reduce_only=reduce_only)


    if is_buy == True:
        print(f"limit BUY order placed thanks moon, resting: {order_result['response']['data']['statuses'][0]}")
    else:
        print(f"limit SELL order placed thanks moon, resting: {order_result['response']['data']['statuses'][0]}")


    return order_result


def get_sz_px_decimals(symbol):

    '''
    this is succesfully returns Size decimals and Price decimals


    this outputs the size decimals for a given symbol
    which is - the SIZE you can buy or sell at
    ex. if sz decimal == 1 then you can buy/sell 1.4
    if sz decimal == 2 then you can buy/sell 1.45
    if sz decimal == 3 then you can buy/sell 1.456


    if size isnt right, we get this error. to avoid it use the sz decimal func
    {'error': 'Invalid order size'}
    '''

    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}
    data = {'type': 'meta'}


    response = requests.post(url, headers=headers, data=json.dumps(data))


    if response.status_code == 200:
        # Success
        data = response.json()
        #print(data)
        symbols = data['universe']
        symbol_info = next((s for s in symbols if s['name'] == symbol), None)
        if symbol_info:
            sz_decimals = symbol_info['szDecimals']
            
        else:
            print('Symbol not found')
    else:
        # Error
        print('Error:', response.status_code)


    ask = ask_bid(symbol)[0]
    #print(f'this is the ask {ask}')


    # Compute the number of decimal points in the ask price
    ask_str = str(ask)
    if '.' in ask_str:
        px_decimals = len(ask_str.split('.')[1])
    else:
        px_decimals = 0


    print(f'{symbol} this is the price {sz_decimals} decimal(s)')


    return sz_decimals, px_decimals


def adjust_leverage_size_symbol(symbol, leverage, account):
    '''
    this calculates size based off what we want.
    95% of balance
    '''

    print('leverage:', leverage)

    account = LocalAccount = eth_account.Account.from_key(key)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)

    #Get the user state and print out leverage information for ETH 
    user_state = info.user_state(account.address)
    acct_value = user_state["marginSummary"]["accountValue"]
    print(acct_value)
    acct_val95 = acct_value * 0.95
    
    print(exchange.update_leverage(leverage, symbol))

    price =  ask_bid(symbol)[0]

    #size == balance / price * leverage
    # INJ 6.95 ... at 10x lev... 10 ink = $cost 6.95
    size =(acct_val95 / price) * leverage
    size = float(size)
    rounding = get_sz_px_decimals(symbol)[0]
    size = round(size,rounding)
    #print(f'this is the size we can use 95% of acct val {size}')

    user_state = info,user_state(account.address)

    return leverage,size



def get_ohclv(cb_symbol, timeframe, limit):


    coinbase = ccxt.kraken()


    ohlcv = coinbase.fetch_ohlcv(cb_symbol, timeframe, limit)
    #print(ohlcv)


    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')


    df = df.tail(limit)


    df['support'] = df[:-2]['close'].min()
    df['resis'] = df[:-2]['close'].max()


    # Save the dataframe to a CSV file
    df.to_csv('ohlcv_data.csv', index=False)


    return df 




def supply_demand_zones(symbol, timeframe, limit):


    print('starting moons supply and demand zone calculations..')


    sd_df = pd.DataFrame()


    df = get_ohclv(cb_symbol, timeframe, limit)
    #print(df)


    supp = df.iloc[-1]['support']
    resis = df.iloc[-1]['resis']
    #print(f'this is moons support for 1h {supp_1h} this is resis: {resis_1h}')


    df['supp_lo'] = df[:-2]['low'].min()
    supp_lo = df.iloc[-1]['supp_lo']


    df['res_hi'] = df[:-2]['high'].max()
    res_hi = df.iloc[-1]['res_hi']


    sd_df[f'{timeframe}_dz'] = [supp_lo, supp]
    sd_df[f'{timeframe}_sz'] = [res_hi, resis]


    print('here are moons supply and demand zones')
    print(sd_df)


    return sd_df 


def get_position_and_maxpos(symbol,account, max_positions):

    '''
    gets the current position info, like size etc. 
    '''


    account = LocalAccount = eth_account.Account.from_key(key)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    user_state = info.user_state(account.address)
    print(f'this is current account value: {user_state["marginSummary"]["accountValue"]}')
    positions = []
    for position in user_state["assetPositions"]:
        if (position["position"]["coin"] == symbol) and float(position["position"]["szi"]) != 0:
            positions.append(position["position"])
            in_pos = True 
            size = float(position["position"]["szi"])
            pos_sym = position["position"]["coin"]
            entry_px = float(position["position"]["entryPx"])
            pnl_perc = float(position["position"]["returnOnEquity"])*100
            print(f'this is the pnl perc {pnl_perc}')
            break 
    else:
        in_pos = False 
        size = 0 
        pos_sym = None 
        entry_px = 0 
        pnl_perc = 0


    if size > 0:
        long = True 
    elif size < 0:
        long = False 
    else:
        long = None 


    return positions, in_pos, size, pos_sym, entry_px, pnl_perc, long 




def cancel_all_orders():
    # this cancels all open orders
    account = LocalAccount = eth_account.Account.from_key(key)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)


    open_orders = info.open_orders(account.address)
    #print(open_orders)


    print('above are the open orders... need to cancel any...')
    for open_order in open_orders:
        #print(f'cancelling order {open_order}')
        exchange.cancel(open_order['coin'], open_order['oid'])


def volume_spike(df):
    # A volume spike would be significantly larger than the current moving average of volume
    df['MA_Volume'] = df['volume'].rolling(window=20).mean()


    # A downward trend can be seen when the current close price is below the moving average of close price
    df['MA_Close'] = df['close'].rolling(window=20).mean()
    # print(df['MA_Volume'])
    # print(df['MA_Close'])


    latest_data = df.iloc[-1]
    volume_spike_and_price_downtrend = latest_data['volume'] > vol_multiplier * latest_data['MA_Volume'] and latest_data['MA_Close'] > latest_data['close']


    return volume_spike_and_price_downtrend


def kill_switch(symbol):


    positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, long = get_position(symbol)


    while im_in_pos == True:


        cancel_all_orders()


        # get bid_ask
        askbid = ask_bid(pos_sym)
        ask = askbid[0]
        bid = askbid[1]


        pos_size = abs(pos_size)


        if long == True:
            limit_order(pos_sym, False, pos_size, ask)
            print('kill switch - SELL TO CLOSE SUBMITTED ')
            time.sleep(5)
        elif long == False:
            limit_order(pos_sym, True, pos_size, bid)
            print('kill switch - BUY TO CLOSE SUBMITTED ')
            time.sleep(5)
        
        positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, long = get_position(symbol)


    print('position successfully closed in kill switch')


def pnl_close(symbol):


    print('entering pnl close')
    positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, long = get_position(symbol)


    if pnl_perc > target:
        print(f'pnl gain is {pnl_perc} and target is {target}... closing position WIN')
        kill_switch(pos_sym)
    elif pnl_perc <= max_loss:
        print(f'pnl loss is {pnl_perc} and max loss is {max_loss}... closing position LOSS')
        kill_switch(pos_sym)
    else:
        print(f'pnl loss is {pnl_perc} and max loss is {max_loss} and target {target}... not closing position')
    print('finished with pnl close')

pnl_close()

    #snapshot_data =  n.get_ohlcv2('BTC', '1m', 500)
    #df = n.process_data_to_df(snapshot_data)
    #bbdf = n.calculate_bollinger_bands(df)
    
    #bollinger_bands_tight = n.calculate_bollinger_bands(df)

def close_all_positions(account):
        
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    user_state = info.user_state(account.address)
    print(f'this is current account value: {user_state["marginSummary"]["accountValue"]}')
    positions = []
    open_positions = []
    print(f'this is the symbol {symbol}')
    print(user_state["assetPositions"])

    # cancel all orders
    cancel_all_orders()
    print('all orders have been cancelled')

    #CHECKING MAX POSTIONS FIRST
    # Iterate over each position in the assetPositions list
    for position in user_state["assetPositions"]:
        # Check if the position size ('szi') is not zero, indicating an open position
        if float(position["position"]["szi"]) != 0:
            # If it's an open position, add the coijn symbol to the open_positions list
            open_positions.append(position["position"]["coin"])

        
    # for position in positions we need to call the kill switch
    for position in open_positions:
        kill_switch(position, account)

    print('all orders have been closed')

def calculate_bollinger_bands(df, length=20, std_dev=2):
    """
    Calculate Bollinger Bands for a given DataFrame and classify the bands as 'tight' or 'wide'.

    Parameters:
    - df: DataFrame with a 'close' column.
    - length: The period over which the SMA is calculated. Default is 20.
    - std_dev: The nummber standard deviations to plot above and below the SMA. Default is 2.

    Returns:
    - df: Dataframe with Bollinger Bands and classifications for 'tight' and 'wide' bands.
    -  tight: Boolean indicating if the bands are currently tight.
    - wide: Boolean indicating if the bands are currently wide.
    """

    # Ensure 'close' is numeric
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Calculate Bollinger Bands using pandas_ta
    bollinger_bands = ta.bbands(df['close'], length=length, std=std_dev)

    # Select only the Bollinger Bands columns (ignoring additional columns like bandwith and percent bandwidth)
    bollinger_bands = bollinger_bands.iloc[:, [0, 1, 2]] # Assuming the first three columns are BBL, BBM, and BBU
    bollinger_bands.columns = ['BBL', 'BBM', 'BBU']

    # Merge the Bollinger Bands with the original DataFrame
    df = pd.concat([df, bollinger_bands], axis=1)

    # Calculate Band Width
    df['BandWidth'] = df['BBU'] - df['BBL']

    # Determine thresholds for 'tight' and 'wide' bands
    tight_threshold = df['BandWidth'].quantile(0.2)
    wide_threshold = df['BandWidth'].quantile(0.8)

    #Classify the current state of the bands
    current_band_width = df['BandWidth'].iloc[-1]
    tight = current_band_width <= tight_threshold
    wide = current_band_width >= wide_threshold

    return df, tight, wide


def process_data_to_df(snapshot_data):
    if snapshot_data:
        # Assuming the response contains a list of candlestick data
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        data = []
        for snapshot in snapshot_data:
            timestamp = datetime.fromtimetamp(snapshot['t'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            open_price = snapshot['o']
            high_price = snapshot['h']
            low_price = snapshot['l']
            close_price = snapshot['c']
            volume = snapshot['v']
            data.append([timestamp, open_price, high_price, low_price, close_price, volume])

        df = pd.DataFrame(data, columns=columns)

        # Calculate support and resistance, excluding the last two rows fdor the calculation
        if len(df) > 2:      # CHeck if DataFrame has more than 2 rows to avoid errors
            df['support'] = df[:-2]['close'].min()
            df['resis'] = df[:-2]['close'].max()
        else: # If DataFrame has 2 or fewer rows, use the available 'close' prices for calculation
            df['support'] = df['close'].min()
            df['resis'] = df['close'].max()

        return df
    else:
        return pd.DataFrame()  # Return an empty DataFrame if no data is available

def get_ohlcv2(symbol, interval, lookback_days):
    end_time = datetime.now()
    start_time = end_time - timedelta(days=lookback_days)
    
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}
    data =  {
        "type": "canddleSnapshot",
        "req": {
            "coin": symbol,
            "interval": interval,
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000)
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        snapshot_data = response.json()
        return snapshot_data
    else:
        print(f"Error fetching data for {symbol}: {response.status_code}")
        return None

# # df = get_ohclv(cb_symbol, timeframe, limit)
# # print(volume_spike(df))
# # time.sleep(876)


# #kill_switch(symbol)


# cancel_all_orders()
# askbid = ask_bid(symbol)
# bid = askbid[1]
# ask = askbid[0]
# l2_data = askbid[2]
# #print(l2_data)


# #limit_order(symbol, True, pos_size, bid) # buy order
# #limit_order(symbol, False, pos_size, ask) # sell order


# time.sleep(7)


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


