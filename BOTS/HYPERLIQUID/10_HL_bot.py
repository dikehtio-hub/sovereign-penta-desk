############# Coding trading bot #1 - sma bot w/ob data - Hyperliquid Version
import pandas as pd
import numpy as np
import time, schedule
from datetime import datetime, timezone
from eth_account import Account

# HL: Import the Hyperliquid SDK libraries instead of ccxt
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

# HL: Make sure your dontshare_config.py has your wallet's private key
# Example: HL_SECRET_KEY = "0xYOUR_PRIVATE_KEY"
import dontshare_config as ds

# HL: Setup the connection to Hyperliquid
# We use an "account" from our secret key to sign transactions
# "info" is for getting public data (prices, candles)
# "exchange" is for private actions (placing/canceling orders)
print("Connecting to Hyperliquid...")
account = Account.from_key(ds.HL_SECRET_KEY)
info = Info(constants.MAINNET_API_URL, skip_ws=True)
exchange = Exchange(account, constants.MAINNET_API_URL)
print(f"Successfully connected with wallet address: {account.address}")


# HL: Hyperliquid uses simple asset names like 'BTC', 'ETH'
symbol = 'BTC' 
pos_size = 0.001 # HL: Position size is now in terms of the asset (e.g., 0.001 BTC)
target = 8 # Profit target in percentage
max_loss = -9 # Max loss in percentage
vol_decimal = .4


# ask_bid()[0] = ask , [1] = bid
def ask_bid():
    # HL: Get all current market prices from the info object
    all_mids = info.all_mids()
    price = float(all_mids[symbol])
    
    # HL: Hyperliquid doesn't always provide a simple bid/ask spread via API easily.
    # For a simple bot, using the mid-price is a common and effective approach.
    # We will use this mid-price as both the "bid" and "ask" for calculations.
    ask = price
    bid = price
    
    return ask, bid # ask_bid()[0] = ask , [1] = bid


# daily_sma()[0] = df_d # which is the daily sma
def daily_sma():
    print('starting daily indicators...')
    
    # HL: Define timeframe and calculate start time for fetching candles
    timeframe = '1d'
    num_bars = 100
    # Hyperliquid wants time in milliseconds
    start_time_ms = int(time.time() * 1000) - (num_bars * 24 * 60 * 60 * 1000)

    # HL: Fetch candle data (OHLCV) using info.candles_snapshot
    bars = info.candles_snapshot(coin=symbol, interval=timeframe, startTime=start_time_ms, endTime=int(time.time() * 1000))
    
    # HL: The structure is slightly different, so we adjust the DataFrame creation
    df_d = pd.DataFrame(bars)
    df_d['timestamp'] = pd.to_datetime(df_d['t'], unit='ms')
    df_d.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
    df_d[['open', 'high', 'low', 'close']] = df_d[['open', 'high', 'low', 'close']].astype(float)

    # DAILY SMA - 20 day (This logic remains the same)
    df_d['sma20_d'] = df_d.close.rolling(20).mean()
    
    # if bid < the 20 day sma then = BEARISH, if bid > 20 day sma = BULLISH
    bid = ask_bid()[1]
    
    # if sma > bid = SELL, if sma < bid = BUY
    df_d.loc[df_d['sma20_d'] > bid, 'sig'] = 'SELL'
    df_d.loc[df_d['sma20_d'] < bid, 'sig'] = 'BUY'
    
    return df_d


# f15_sma()[0] = df_f which is the 15m sma
def f15_sma():
    print('starting 15 min sma...')
    
    timeframe = '15m'
    num_bars = 100
    start_time_ms = int(time.time() * 1000) - (num_bars * 15 * 60 * 1000)
    
    # HL: Fetch 15m candle data
    bars = info.candles_snapshot(coin=symbol, interval=timeframe, startTime=start_time_ms, endTime=int(time.time() * 1000))

    df_f = pd.DataFrame(bars)
    df_f['timestamp'] = pd.to_datetime(df_f['t'], unit='ms')
    df_f.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
    df_f[['open', 'high', 'low', 'close']] = df_f[['open', 'high', 'low', 'close']].astype(float)
    
    # 15m SMA - 20 period (Logic remains the same)
    df_f['sma20_15'] = df_f.close.rolling(20).mean()
    
    # BUY PRICE 1+2 AND SELL PRICE1+2 (Logic remains the same)
    df_f['bp_1'] = df_f['sma20_15'] * 1.001
    df_f['bp_2'] = df_f['sma20_15'] * 0.997
    df_f['sp_1'] = df_f['sma20_15'] * 0.999
    df_f['sp_2'] = df_f['sma20_15'] * 1.003
    
    return df_f


# open_positions() openpos_bool, openpos_size, long
def open_positions():
    # HL: Get the user's entire account state
    user_state = info.user_state(account.address)
    openpos_bool = False
    openpos_size = 0.0
    long = None

    # HL: Loop through asset positions to find our symbol
    for position in user_state.get('assetPositions', []):
        if position['position']['coin'] == symbol:
            # szi is the size of the position
            size = float(position['position']['szi'])
            if abs(size) > 0: # If size is not zero, we have a position
                openpos_bool = True
                openpos_size = size
                long = True if size > 0 else False
            break # Exit loop once we find our position

    return openpos_bool, openpos_size, long

def kill_switch():
    print('starting the kill switch')
    openposi, kill_size, long = open_positions()

    print(f'openposi {openposi}, long {long}, size {kill_size}')
    
    # HL: Cancel any existing open orders for the symbol first
    open_orders = info.open_orders(account.address)
    for order in open_orders:
        if order['coin'] == symbol:
            print(f"Canceling opening order {order['oid']} to prepare for closing...")
            try:
                exchange.cancel(symbol, order['oid'])
                time.sleep(0.2) # Small delay
            except Exception as e:
                print(f"Could not cancel order {order['oid']}: {e}")

    # Loop until the position is confirmed closed
    while openposi:
        print('starting kill switch loop til limit fill..')
        
        # HL: Get current price for closing
        ask, bid = ask_bid()
        price_to_close = bid if long else ask
        
        # HL: Hyperliquid wants a boolean for buy/sell
        is_buy = not long # If long, we sell to close (is_buy=False). If short, we buy to close (is_buy=True).
        
        # HL: Order size must be positive
        order_size = abs(kill_size)

        try:
            # HL: Place a "reduceOnly" order. This ensures it only closes a position, never opens a new one.
            print(f"Placing {'BUY' if is_buy else 'SELL'} to CLOSE order of {order_size} {symbol} at ${price_to_close}")
            exchange.order(symbol, is_buy, order_size, price_to_close, {"limit": {"tif": "Gtc"}, "reduceOnly": True})
            
            print('Sleeping for 30 seconds to see if it fills..')
            time.sleep(30)

        except Exception as e:
            print(f"An error occurred placing the closing order: {e}")
            print("Retrying in 10 seconds...")
            time.sleep(10)
            
        # HL: Check if the position is closed
        openposi, kill_size, long = open_positions()

    print("Position successfully closed. Kill switch complete.")


def sleep_on_close():
    # HL: This function is complex to replicate exactly as Hyperliquid's user fills history is different.
    # For simplicity, we will implement a simpler logic: if we just closed a trade, wait.
    # A more robust implementation would involve tracking trade state within the bot.
    # We will skip implementing this for now to keep the migration simple.
    print('Sleep on close function skipped for Hyperliquid version (can be added later).')
    pass


def ob():
    # HL: Order book logic is also different. Hyperliquid's websocket is better for this.
    # For a REST API bot, we will simulate this by checking price volatility.
    # This function's goal was to see if the market was one-sided. We will simplify this.
    # For now, we will return False so it doesn't block the pnl_close logic.
    print("OB volume check function simplified for Hyperliquid version.")
    vol_under_dec = False
    return vol_under_dec


# pnl_close() [0] in_pos [1] size [2] long
def pnl_close():
    print('checking to see if its time to exit... ')
    in_pos, size, long = open_positions()
    
    if not in_pos:
        print('we are not in position')
        return in_pos, size, long

    # HL: Get user state again for PNL information
    user_state = info.user_state(account.address)
    unrealized_pnl = 0.0
    entry_price = 0.0

    for pos in user_state.get('assetPositions', []):
        if pos['position']['coin'] == symbol:
            unrealized_pnl = float(pos['position']['unrealizedPnl'])
            entry_price = float(pos['position']['entryPx'])
            break
            
    if entry_price == 0:
        print("Could not find entry price, cannot calculate PNL%.")
        return in_pos, size, long

    # HL: Calculate PNL Percentage
    # PNL % = (Unrealized PNL / (Position Size * Entry Price)) * 100
    position_value = abs(size) * entry_price
    perc = (unrealized_pnl / position_value) * 100 if position_value != 0 else 0
    
    print(f'Entry: ${entry_price:.2f} | Size: {size} {symbol} | uPNL: ${unrealized_pnl:.2f} | PNL %: {perc:.2f}%')

    if perc > target:
        print(f":) :) Profit target of {target}% hit! Current PNL is {perc:.2f}%.")
        # vol_under_dec = ob() # Simplified and returns False
        # if vol_under_dec:
        #     print(f'Volume check positive... holding position. Sleeping 30s.')
        #     time.sleep(30)
        # else:
        print(f':) :) :) Starting the kill switch because we hit our target!')
        kill_switch()
        in_pos = False # Update state after closing
        
    elif perc < max_loss:
        print(f"STOP LOSS! PNL ({perc:.2f}%) is below max loss ({max_loss}%)! Starting kill switch.")
        kill_switch()
        in_pos = False # Update state after closing
    else:
        print(f'Holding position. PNL {perc:.2f}% is between target ({target}%) and stop loss ({max_loss}%).')

    print('just finished checking PNL close..')
    return in_pos, size, long


def place_opening_orders(side, price1, price2, size):
    # HL: Cancel any old opening orders before placing new ones.
    open_orders = info.open_orders(account.address)
    for order in open_orders:
        if order['coin'] == symbol:
            try:
                print(f"Clearing old opening order {order['oid']}...")
                exchange.cancel(symbol, order['oid'])
                time.sleep(0.2)
            except Exception as e:
                print(f"Could not cancel order {order['oid']}: {e}")

    # HL: This function places the two opening orders
    is_buy = True if side == 'BUY' else False
    try:
        print(f"Placing new opening order 1: {side} {size} {symbol} at ${price1:.2f}")
        exchange.order(symbol, is_buy, size, price1, {"limit": {"tif": "Gtc"}})
        time.sleep(0.2) # Small delay between orders
        
        print(f"Placing new opening order 2: {side} {size} {symbol} at ${price2:.2f}")
        exchange.order(symbol, is_buy, size, price2, {"limit": {"tif": "Gtc"}})
        
        print('Just made opening orders, going to sleep for 2 mins..')
        time.sleep(120)

    except Exception as e:
        print(f"!!!!!!!! ERROR placing opening orders: {e}")
        time.sleep(10)


def bot():
    print(f"\n--- Running Bot Cycle at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC ---")
    
    # 1. Check PNL and manage existing positions first.
    in_pos, curr_size, _ = pnl_close()
    
    # If kill_switch was triggered inside pnl_close, in_pos will be False.
    if in_pos:
        print('We are in a position, so not placing new orders. Waiting for next cycle.')
        return # Exit the function for this cycle

    # 2. If not in a position, check for new signals.
    print("Not in a position. Looking for a new entry.")
    
    try:
        df_d = daily_sma() # Determines LONG/SHORT
        df_f = f15_sma() # Provides entry prices
    except Exception as e:
        print(f"Could not fetch market data: {e}")
        return

    # 3. Get signal and prices
    sig = df_d.iloc[-1]['sig']
    last_sma15 = df_f.iloc[-1]['sma20_15']
    curr_p = ask_bid()[1] # Current price (bid)
    
    print(f"Daily Signal: {sig} | 15m SMA: ${last_sma15:.2f} | Current Price: ${curr_p:.2f}")
    
    # 4. Decide whether to place orders
    open_size = pos_size / 2

    if (sig == 'BUY') and (curr_p < last_sma15):
        print('Signal is BUY and price is below 15m SMA. Favorable entry.')
        bp_1 = df_f.iloc[-1]['bp_1']
        bp_2 = df_f.iloc[-1]['bp_2']
        place_opening_orders('BUY', bp_1, bp_2, open_size)
        
    elif (sig == 'SELL') and (curr_p > last_sma15):
        print('Signal is SELL and price is above 15m SMA. Favorable entry.')
        sp_1 = df_f.iloc[-1]['sp_1']
        sp_2 = df_f.iloc[-1]['sp_2']
        place_opening_orders('SELL', sp_1, sp_2, open_size)
        
    else:
        print('Signal and price condition not met for a new entry. Waiting...')
        # HL: Cancel any lingering orders if conditions aren't met
        open_orders = info.open_orders(account.address)
        if any(o['coin'] == symbol for o in open_orders):
             print("Conditions not met, cancelling resting opening orders.")
             for order in open_orders:
                if order['coin'] == symbol:
                    try:
                        exchange.cancel(symbol, order['oid'])
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"Could not cancel order {order['oid']}: {e}")
        else:
            print("No resting orders to cancel.")


# --- Main Loop ---
if __name__ == '__main__':
    # Run once at the start
    bot()

    # Schedule to run every 28 seconds
    schedule.every(28).seconds.do(bot)

    while True:
        try:
            schedule.run_pending()
            time.sleep(1) # sleep to prevent cpu spinning
        except Exception as e:
            print(f'+++++ An unexpected error occurred in the main loop: {e}')
            print('Restarting in 30 seconds...')
            time.sleep(30)