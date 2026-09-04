import asyncio
import json
import os
from datetime import datetime
import pytz
from websockets import connect
from termcolor import cprint

# --- CONFIGURATION ---
# FIX 1: Using the correct Binance.US futures stream endpoint
websocket_url = 'wss://dstream.binance.us/ws/!forceOrder@arr'
filename = 'binance_liquidations.csv'

# --- SETUP CSV FILE ---
# Create the CSV file with the correct headers if it doesn't exist
if not os.path.isfile(filename):
    with open(filename, 'w') as f:
        # FIX 2: Corrected typo 'orrder_type' to 'order_type'
        f.write(",".join([
            'symbol', 'side', 'order_type', 'time_in_force',
            'original_quantity', 'price', 'average_price', 'order_status',
            'order_last_filled_quantity', 'order_filled_accumulated_quantity',
            'order_trade_time', 'usd_size'
        ]) + "\n")

async def binance_liquidation(uri, filename):
    """Connects to the Binance websocket and processes liquidation orders."""
    while True: # Keep running and try to reconnect on error
        try:
            async with connect(uri) as websocket:
                print("Connected to Binance liquidation stream...")
                while True:
                    msg = await websocket.recv()
                    order_data = json.loads(msg)['o']
                    
                    symbol = order_data['s'].replace('USDT', '')
                    side = order_data['S']
                    
                    # FIX 3: Correctly use 'T' for timestamp and 'z' for quantity
                    timestamp = int(order_data['T']) # Use 'T' for the trade time
                    filled_quantity = float(order_data['z']) # Use 'z' for the filled quantity
                    price = float(order_data['p'])
                    usd_size = filled_quantity * price
                    
                    # Convert timestamp to readable Eastern Time
                    est = pytz.timezone("US/Eastern")
                    time_est = datetime.fromtimestamp(timestamp / 1000, est).strftime('%H:%M:%S')
                    
                    # --- PRINTING LOGIC (for liquidations over $3,000) ---
                    if usd_size > 3000:
                        liquidation_type = 'L LIQ' if side == 'SELL' else 'S LIQ'
                        symbol_display = symbol[:4] # Display first 4 letters of the symbol
                        output = f"{liquidation_type} {symbol_display} {time_est} ${usd_size:,.0f}"
                        color = 'green' if side == 'SELL' else 'red'
                        attrs = ['bold'] if usd_size > 10000 else []

                        if usd_size > 250000:
                            stars = '***'
                            attrs.append('blink')
                            output = f'{stars} {output}'
                            # Print multiple times for emphasis
                            for _ in range(4):
                                cprint(output, 'white', f'on_{color}', attrs=attrs)
                        elif usd_size > 100000:
                            # FIX 4: Corrected typo from 'starts' to 'stars'
                            stars = '*'
                            attrs.append('blink')
                            output = f'{stars} {output}'
                            for _ in range(2):
                                cprint(output, 'white', f'on_{color}', attrs=attrs)
                        elif usd_size > 25000:
                            cprint(output, 'white', f'on_{color}', attrs=attrs)
                        
                        # Add a blank line for spacing after a printed liquidation
                        print('') 

                    # --- SAVING TO CSV ---
                    # FIX 5: Correctly get values from the dictionary using square brackets []
                    keys = ['s', 'S', 'o', 'f', 'q', 'p', 'ap', 'X', 'l', 'z', 'T']
                    msg_values = [str(order_data[key]) for key in keys]
                    msg_values.append(str(usd_size))
                    
                    with open(filename, 'a') as f:
                        # FIX 6: Correctly join the values with a comma using '.'
                        trade_info = ",".join(msg_values) + '\n'
                        trade_info = trade_info.replace('USDT', '')
                        f.write(trade_info)

        except Exception as e:
            print(f"An error occurred: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

# --- START THE PROGRAM ---
if __name__ == "__main__":
    try:
        asyncio.run(binance_liquidation(websocket_url, filename))
    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED ---\n{e}")
    finally:
        print("\n--- Script has finished or crashed. Press Enter to exit. ---")
        input()