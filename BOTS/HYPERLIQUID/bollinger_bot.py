# SZ  =  supply and demand bot DONT NOT RUN YET  MOONDEV d10 bollinger band bot https://www.youtube.com/watch?v=5ln12H3OSMM
'''
bollinger band bot
Do not run without making your own strategy
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

symbol =  'WIF'
timeframe = '15m'
sma_window = 20
lookback_days = 1
size = 1
max_loss = -10
leverage = 2
max_positions = 1

secret = d.private_key

def bot():

    account1 = eth_account.Account.from_key(secret)

    positions1, im_in_pos, mypos_size, pos_sym1, entry_px2, pnl_perc1, long1, num_of_pos = n.get_position_and_maxpos(symbol, account1, max_positions)

    print(f'these are position for {symbol} {positions1}')

    lev, pos_size = n.adjust_leverage_size_signal(symbol, leverage, account1)

    # dividing poition by 2
    pos_size = pos_size / 2

    if im_in_pos:
        n.cancel_all_orders(account1)
        print('in position so check pnl close')
        n.pnl_close(symbol)
    else:
        print('not in position so no pnl close')

    #get price
    ask, bid, l2_data = n.ask_bid(symbol)

    print(f'ask: {ask} bid: {bid}')

    bid11 = float(l2_data[0][10]['px'])
    ask11 = float(l2_data[1][10]['px'])

    print(f'ask11: {ask11} bid11: {bid11}')

    snapshot_data =  n.get_ohlclv2('BTC', '1m', 500)
    df = n.process_data_to_df(snapshot_data)
    bbdf = n.calculate_bollinger_bands(df)
    bollinger_bands_tight = n.calculate_bollinger_bands(df)

    print(f'bollinger bands are tight: {bollinger_bands_tight}')

    #  ONLY ENTER IF BOLLINGER BANDS ARE TIGHT
    if not im_in_pos and bollinger_bands_tight:
        print('bollinger bands are tight and we dont have a position so entering')
        print(f'not in position we are quoteing a sell at {ask} and buy at {bid}')
        # cancel all orders
        n.cancel_all_orders(account1)

        print('just canceled all orders')

        # ENTER BUY ORDER
        n.limit_order(symbol, True, pos_size, bid11, False, account1)
        print(f'just placed an order for {pos_size} at {bid}')

        # ENTER SELL ORDER
        n.lmit_order(symbol, False, pos_size, ask11, False, account1)    
        print(f'just placed an order for {pos_size} at {ask}')

    elif bollinger_bands_tight ==  False:
            n.cancel_aLL_orders(account1)
            n.close_all_positions(account1)
    else:
        print(f'our position is {im_in_pos} bollinger bands may not be tight')

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
