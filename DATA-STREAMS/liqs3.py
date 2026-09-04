# ...existing code...
import asyncio
import json
import os
import ssl
import socket
from datetime import datetime
import pytz
from websockets import connect, exceptions as ws_exceptions
from termcolor import cprint

# --- CONFIGURATION ---
# Keep your chosen endpoint; adjust if you need a different Binance environment.
websocket_url = 'wss://dstream.binance.us/ws/!forceOrder@arr'
filename = 'binance_liquidations.csv'

# --- SETUP CSV FILE ---
CSV_HEADERS = [
    'symbol', 'side', 'order_type', 'time_in_force',
    'original_quantity', 'price', 'average_price', 'order_status',
    'order_last_filled_quantity', 'order_filled_accumulated_quantity',
    'order_trade_time', 'usd_size'
]

if not os.path.isfile(filename):
    # Use newline='' for cross-platform CSV writing
    with open(filename, 'w', newline='') as f:
        f.write(",".join(CSV_HEADERS) + "\n")

# --- STREAM HANDLER ---
async def binance_liquidation(uri, filename):
    """Connect to Binance websocket and process liquidation orders robustly."""
    ssl_ctx = ssl.create_default_context()
    backoff = 1

    while True:
        try:
            # ping settings + ssl context reduce handshake/timeouts
            async with connect(uri, ssl=ssl_ctx, ping_interval=20, ping_timeout=10, max_size=None) as websocket:
                backoff = 1
                print("Connected to Binance liquidation stream...")
                while True:
                    raw = await websocket.recv()
                    # Some streams send an array under 'data' or directly an object; guard both.
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        # skip invalid json frames
                        continue

                    # The stream sends an array of forced orders: payload might be {'data': [...]} or a list
                    records = None
                    if isinstance(payload, dict) and 'data' in payload:
                        records = payload['data']
                    elif isinstance(payload, list):
                        records = payload
                    elif isinstance(payload, dict) and 'o' in payload:
                        # single wrapper object
                        records = [payload]
                    else:
                        # unexpected format; skip
                        continue

                    for item in records:
                        # If the stream wraps the order inside 'o', prefer that
                        order_data = item.get('o') if isinstance(item, dict) and 'o' in item else item
                        if not isinstance(order_data, dict):
                            continue

                        # Safely extract fields with defaults
                        symbol_raw = order_data.get('s', '')
                        symbol = symbol_raw.replace('USDT', '').replace('USD', '')
                        side = order_data.get('S', order_data.get('side', 'UNKNOWN'))

                        # Timestamp: try common keys 'T' then 't'
                        timestamp_ms = None
                        for k in ('T', 't', 'time'):
                            if k in order_data:
                                try:
                                    timestamp_ms = int(order_data[k])
                                    break
                                except (ValueError, TypeError):
                                    continue
                        if timestamp_ms is None:
                            # skip if no timestamp
                            continue

                        # Quantity filled: commonly 'z' or 'q' or 'l'
                        filled_qty = None
                        for k in ('z', 'q', 'l'):
                            if k in order_data:
                                try:
                                    filled_qty = float(order_data[k])
                                    break
                                except (ValueError, TypeError):
                                    continue
                        if filled_qty is None:
                            filled_qty = 0.0

                        # Price: commonly 'p'
                        try:
                            price = float(order_data.get('p', order_data.get('price', 0) or 0))
                        except (ValueError, TypeError):
                            price = 0.0

                        usd_size = filled_qty * price

                        # Convert timestamp to Eastern Time (readable)
                        est = pytz.timezone("US/Eastern")
                        time_est = datetime.fromtimestamp(timestamp_ms / 1000, est).strftime('%H:%M:%S')

                        # --- PRINTING LOGIC (for liquidations over $3,000) ---
                        if usd_size > 3000:
                            liquidation_type = 'L LIQ' if side == 'SELL' else 'S LIQ'
                            symbol_display = symbol[:8]  # show up to 8 characters
                            output = f"{liquidation_type} {symbol_display} {time_est} ${usd_size:,.0f}"
                            color = 'green' if side == 'SELL' else 'red'
                            attrs = ['bold'] if usd_size > 10000 else []

                            if usd_size > 250000:
                                stars = '***'
                                # 'blink' may not be supported on all terminals; keep it optional
                                if 'blink' not in attrs:
                                    attrs.append('blink')
                                output = f'{stars} {output}'
                                for _ in range(4):
                                    try:
                                        cprint(output, 'white', f'on_{color}', attrs=attrs)
                                    except Exception:
                                        print(output)
                            elif usd_size > 100000:
                                stars = '*'
                                if 'blink' not in attrs:
                                    attrs.append('blink')
                                output = f'{stars} {output}'
                                for _ in range(2):
                                    try:
                                        cprint(output, 'white', f'on_{color}', attrs=attrs)
                                    except Exception:
                                        print(output)
                            elif usd_size > 25000:
                                try:
                                    cprint(output, 'white', f'on_{color}', attrs=attrs)
                                except Exception:
                                    print(output)

                            print('')  # spacing

                        # --- SAVING TO CSV ---
                        # Map CSV columns to order_data keys (use safe lookups)
                        csv_values = [
                            symbol,
                            side,
                            order_data.get('o', order_data.get('orderType', '')),
                            order_data.get('f', order_data.get('timeInForce', '')),
                            order_data.get('q', order_data.get('origQty', '')),
                            order_data.get('p', order_data.get('price', '')),
                            order_data.get('ap', order_data.get('avgPrice', '')),
                            order_data.get('X', order_data.get('status', '')),
                            order_data.get('l', order_data.get('lastFilledQty', '')),
                            order_data.get('z', order_data.get('accumulatedFilledQty', '')),
                            timestamp_ms,
                            f"{usd_size:.2f}"
                        ]
                        # Convert all to strings and strip commas/newlines
                        csv_line = ",".join([str(v).replace(',', '') for v in csv_values]) + "\n"
                        try:
                            with open(filename, 'a', newline='') as f:
                                f.write(csv_line)
                        except Exception as write_err:
                            print(f"Failed to write CSV: {write_err}")

        except (ws_exceptions.ConnectionClosedError, ws_exceptions.InvalidHandshake, socket.gaierror, ssl.SSLError) as conn_err:
            print(f"An error occurred: {type(conn_err).__name__}: {conn_err}. Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        except Exception as e:
            # Catch-all: log and back off
            print(f"An unexpected error occurred: {type(e).__name__}: {e}. Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue

# --- START THE PROGRAM ---
if __name__ == "__main__":
    try:
        asyncio.run(binance_liquidation(websocket_url, filename))
    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED ---\n{type(e).__name__}: {e}")
    finally:
        print("\n--- Script has finished or crashed. Press Enter to exit. ---")
        try:
            input()
        except Exception:
            pass
# ...existing code...