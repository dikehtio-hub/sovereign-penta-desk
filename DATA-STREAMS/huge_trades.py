import asyncio
import json
import os
from datetime import datetime
import pytz
from websockets import connect
from termcolor import cprint

# List of symbols you want to track
symbols = ['btcusdt', 'ethusdt', 'solusdt', 'avaxusdt', 'xrpusdt', 'taousdt', 'vetusdt', 'linkusdt']
websocket_url_base = 'wss://stream.binance.com/ws/' # Corrected the stream URL
trade_filename = 'binance_trades.csv'

# Check if the csv file exists
# FIX 1: Corrected variable name from trades_filename to trade_filename
if not os.path.isfile(trade_filename):
    with open(trade_filename, 'w') as f:
        f.write('Event Time, Symbol, Aggregate Trade ID, Price, Quantity, First Trade ID, Trade Time, Is Buyer Maker\n')

class TradeAggregator:
    # FIX 2: Corrected constructor from _init_ to __init__
    def __init__(self):
        self.trade_buckets = {}

    async def add_trade(self, symbol, second, usd_size, is_buyer_maker):
        trade_key = (symbol, second, is_buyer_maker)
        self.trade_buckets[trade_key] = self.trade_buckets.get(trade_key, 0) + usd_size

    # FIX 3: Changed parameter from 's' to 'self'
    async def check_and_print_trades(self):
        # Using integer seconds is more reliable for comparison than string time
        current_second = int(datetime.now().timestamp())
        deletions = []
        for trade_key, usd_size in self.trade_buckets.items():
            symbol, trade_timestamp, is_buyer_maker = trade_key
            
            # Process trades from previous seconds that are large enough
            if trade_timestamp < current_second and usd_size > 500000:
                attrs = ['bold']
                back_color = 'on_blue' if not is_buyer_maker else 'on_magenta'
                trade_type = "BUY" if not is_buyer_maker else 'SELL'
                
                trade_time_readable = datetime.fromtimestamp(trade_timestamp).strftime("%H:%M:%S")

                if usd_size > 3000000:
                    usd_size_formatted = usd_size / 1000000
                    # Added a blinking effect for huge trades
                    cprint(f"\033[5m{trade_type} {symbol} {trade_time_readable} ${usd_size_formatted:.2f}m\033[0m", 'white', back_color, attrs=attrs)
                else:
                    # FIX 5: Corrected formatting for trades > 500k and < 3m
                    usd_size_formatted = usd_size / 1000
                    # FIX 4: Corrected typo from crpint to cprint
                    cprint(f"{trade_type} {symbol} {trade_time_readable} ${usd_size_formatted:.1f}k", 'white', back_color, attrs=attrs)
                
                deletions.append(trade_key)

        for key in deletions:
            if key in self.trade_buckets:
                del self.trade_buckets[key]

trade_aggregator = TradeAggregator()

async def binance_trade_stream(uri, symbol, aggregator):
    while True: # Add a loop to auto-reconnect on disconnect
        try:
            async with connect(uri) as websocket:
                print(f"Connected to {symbol} stream.")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Handles potential errors if data format is unexpected
                    if 'p' in data and 'q' in data:
                        usd_size = float(data['p']) * float(data['q'])
                        # Use integer timestamp for more reliable aggregation
                        trade_timestamp = int(data['T'] / 1000)
                        
                        await aggregator.add_trade(symbol.upper().replace('USDT',''), trade_timestamp, usd_size, data['m'])

        except Exception as e:
            # Improvement: Print the actual error for better debugging
            print(f"Error with {symbol} stream: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

# FIX 6: De-indented this function to be in the global scope
async def print_aggregated_trades_every_second(aggregator):
    while True:
        await asyncio.sleep(1)
        await aggregator.check_and_print_trades()