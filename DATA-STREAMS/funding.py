import asyncio
import json
import os
from datetime import datetime
from websockets import connect
from termcolor import cprint

# --- CONFIGURATION ---
symbols = ['btcusdt', 'ethusdt', 'solusdt', 'avaxusdt', 'xrpusdt', 'taousdt', 'vetusdt', 'linkusdt']
websocket_url_base = 'wss://stream.binance.com/ws/'

# --- STEP 1: CREATE A SHARED WHITEBOARD ---
# This dictionary will hold the latest data for each symbol.
# Our "workers" will update it, and our "manager" will read from it.
latest_funding_rates = {}

# --- STEP 2: WORKERS ONLY UPDATE THE BOARD ---
# This function's only job is to listen for a symbol's data
# and update our shared "whiteboard".
async def binance_funding_stream(symbol):
    websocket_url = f'{websocket_url_base}{symbol}@markPrice'
    while True: # Loop forever to reconnect if the connection drops
        try:
            async with connect(websocket_url) as websocket:
                print(f"Connected to {symbol} stream.")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    # FIX 1: The calculation is now saved to a variable.
                    funding_rate = float(data['r'])
                    yearly_funding_rate = funding_rate * 3 * 365 * 100 # 3 times a day, 365 days, converted to percent

                    # Update the shared dictionary with the new data for this symbol
                    latest_funding_rates[symbol] = yearly_funding_rate

        except Exception as e:
            # This helps you see if something went wrong
            print(f"Error with {symbol}: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

# --- STEP 3: HIRE A MANAGER TO PRINT REPORTS ---
# This function is our "manager". It runs in a loop, clearing the
# screen and printing a neat report of all the data on the "whiteboard".
async def print_funding_rates():
    while True:
        # Clear the terminal screen. 'cls' for Windows, 'clear' for Mac/Linux.
        os.system('cls' if os.name == 'nt' else 'clear')
        
        event_time = datetime.now().strftime("%H:%M:%S")
        print(f"--- Yearly Funding Rates at {event_time} ---")

        # Go through each symbol in our original list to keep the order nice
        for symbol in symbols:
            # Check if we have data for this symbol on our "whiteboard" yet
            if symbol in latest_funding_rates:
                yearly_funding_rate = latest_funding_rates[symbol]
                symbol_display = symbol.replace('usdt', '').upper()

                # Determine colors based on the funding rate value
                if yearly_funding_rate > 50:
                    text_color, back_color = 'white', 'on_red'
                elif yearly_funding_rate > 30:
                    text_color, back_color = 'black', 'on_yellow'
                elif yearly_funding_rate > 5:
                    text_color, back_color = 'black', 'on_cyan'
                elif yearly_funding_rate < -10:
                    text_color, back_color = 'white', 'on_green'
                else:
                    text_color, back_color = 'black', 'on_light_green'

                # Print the formatted line
                cprint(f"{symbol_display:<6} funding: {yearly_funding_rate:>6.2f}%", text_color, back_color)
            else:
                # If we haven't received data for a symbol yet
                cprint(f"{symbol.replace('usdt', '').upper():<6} funding: waiting...", 'white')
        
        # Wait for 1 second before the next report
        await asyncio.sleep(1)

# --- STEP 4: START EVERYONE TOGETHER ---
async def main():
    # Create a list of all our "worker" tasks
    # FIX: The following lines are now correctly indented
    worker_tasks = [binance_funding_stream(symbol) for symbol in symbols]

    # Create the "manager" task
    manager_task = asyncio.create_task(print_funding_rates())

    # Gather and run all tasks together
    await asyncio.gather(*worker_tasks, manager_task)

# This makes sure the script runs when you execute the file
if __name__ == "__main__":
    asyncio.run(main())