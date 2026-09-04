'''
Supply and Demand Zone Bot for hyperliquid
'''

import dontshare as d
import nice_funcs as n
from eth_account.signers.local import LocalAccount
import eth_account
import json
import time
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import ccxt
import pandas as pd
import datetime
import schedule
import requests

# Settings
symbol = 'WIF'
timeframe = '5m'
sma_window = 20
lookback_days = 1
size = 1
max_loss = -10
leverage = 2
max_positions = 1  # ✅ Added this missing variable

secret = d.private_key

acount1 =  LocalAccount.from_key(secret)
n.adjust_leverage_size_signal(symbol, leverage, acount1)
def bot():
    
    pos_size = size
    account1 = LocalAccount.from_key(secret)
    positions1, in_in_pos, mypos_size, pos_sym1, entry_px2, pnl_perc1, long1, num_of_pos = n.get_position(symbol, account1)
    print(f'these are the positions {positions1}')

    if im_in_pos:
        print('in position so check pnl close')
        n.pnl_close(symbol, target, max_loss, account1)
    else:
        print('im not in position so no pnl close')

    # check if in a partial position
    if 0 < mypos_size < pos_size:
        print(f'current size {mypos_size}')
        pos_size = pos_size - mypos_size
        print(f'updated size needed {pos_size}')
        im_in_pos =  False
    else:
        pos_size = size

    latest_sma = n.get_latest_sma(symbol, timeframe, sma_window, 2)

    if latest_sma is not None:
        print(f'lates sma for {symbol} over the{sma_window} intervals: {latest_sma}')
    else:
        print('could not receive sma')

    price = n.ask_bid(symbol)[0]

    if not im_in_pos:
    
        sd_df =n.supply_demand_demand_zones_hl(symbol, timeframe, lookback_days)

        sd_df[f'{timeframe}_dz'] = pd.to_numeric(sd_df['5m_dz'], errors='coerce')
        sd_df[f'{timeframe}_sz'] = pd.to_numeric(sd_df['5m_sz'], errors='coerce')

        print(sd_df)

        buy_price =  sd_df['5m_dz'].mean()
        sell_price =  sd_df['5m_sz'].mean()

        # make buy price and sell price a float
        buy_price = float(buy_price)
        sell_price = float(sell_price)

        print(f'current price {price} buy price{buy_price} sell price {sell_price}')

        #calculate the absolute diff between the current price and buy/sell prices
        diff_to_buy_price =  abs(price - buy_price)
        diff_to_sell_price = abs(price - sell_price)

        #determine whether to buy or sell based on which pricen is closer
        if diff_to_buy_price < diff_to_sell_price:
            n.cancel_all_orders(account1)
            print('canceled all orders..')
            
            #enter the buy price
            n.limit_order(symbol, True, pos_size, buy_price, account1)
            print(f'just placed order for {pos_size} at {buy_price}')

        else:
            #enter sell order
            print('placing sell order')
            n.cancel_all_orders(account1)
            print('just canceled all orders')
            n.limit_order(symbol, False, pos_size, sell_price, account1)
            print(f'just placed order for {pos_size} at {sell_price}')

    else:
        print(f'in {pos_sym1} position size {mypos_size} so not entering')

bot()
schedule.every(30).seconds.do(bot)

while True:
    try:
        schedule.run_pending()
        time.sleep(10)
    except Exception as e:
        print('*** maybe internet connection lost... sleeping 30 and trying again')
        print(e)
        time.sleep(30)
