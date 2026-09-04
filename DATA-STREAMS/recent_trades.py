import asyncio
import json
import os
from datetime import datetime
import pytz
from websockets import connect
from termcolor import cprint

# --------------------------------------------
# Binance.US Compatible Stream Configuration
# --------------------------------------------
symbols = [
    'btcusdt', 'ethusdt', 'solusdt', 'avaxusdt', 'xrpusdt',
    'linkusdt', 'ltcusdt', 'dogeusdt'
]
# Note: Binance.US does NOT support all Binance.com pairs (taousdt, vetusdt removed)

websocket_url_base = 'wss://stream.binance.us:9443/ws/'
trades_filename = 'binanceus_trades.csv'

# --------------------------------------------
# Initialize CSV Log
# --------------------------------------------
if not os.path.isfile(trades_filename):
    with open(trades_filename, 'w') as f:
        f.write('Event Time,Symbol,Aggregate Trade ID,Price,Quantity,Trade Time,Is Buyer Maker\n')


# --------------------------------------------
# Binance.US WebSocket Stream Function
# --------------------------------------------
async def binance_trade_stream(uri, symbol, filename):
    async with connect(uri) as websocket:
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                # Extract fields safely
                event_time = int(data['E'])
                agg_trade_id = data['a']
                price = float(data['p'])
                quantity = float(data['q'])
                trade_time = int(data['T'])
                is_buyer_maker = data['m']

                # Calculate USD trade size
                usd_size = price * quantity

                # Convert to readable Eastern time
                est = pytz.timezone('US/Eastern')
                readable_trade_time = datetime.fromtimestamp(trade_time / 1000, est).strftime('%H:%M:%S')
                display_symbol = symbol.upper().replace('USDT', '')

                # Filter large trades
                if usd_size > 1499:
                    trade_type = 'SELL' if is_buyer_maker else 'BUY'
                    color = 'red' if trade_type == 'SELL' else 'green'
                    attrs = ['bold'] if usd_size >= 50000 else []

                    stars = ''
                    repeat_count = 1
                    if usd_size >= 500000:
                        stars = '**'
                        color = 'magenta' if trade_type == 'SELL' else 'blue'
                    elif usd_size >= 100000:
                        stars = '*'

                    output = f"{stars} {trade_type} {display_symbol} {readable_trade_time} ${usd_size:,.0f}"
                    for _ in range(repeat_count):
                        cprint(output, 'white', f'on_{color}', attrs=attrs)

                    # Append trade log to CSV
                    with open(filename, 'a') as f:
                        f.write(f"{event_time},{symbol.upper()},{agg_trade_id},{price},{quantity},{trade_time},{is_buyer_maker}\n")

            except Exception as e:
                cprint(f"Error in {symbol}: {e}", "red")
                await asyncio.sleep(5)


# --------------------------------------------
# Main Execution Entry
# --------------------------------------------
async def main():
    filename = trades_filename
    tasks = []

    # Create WebSocket tasks for each symbol
    for symbol in symbols:
        stream_url = f"{websocket_url_base}{symbol}@aggTrade"
        tasks.append(binance_trade_stream(stream_url, symbol, filename))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
