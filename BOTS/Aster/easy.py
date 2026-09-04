"""
Aster Easy Trading Bot - Simplified trading with bid/ask placement
Adapted from Solana easy.py bot for Aster Exchange
"""

import time
import pandas as pd
import numpy as np
from termcolor import colored, cprint
from datetime import datetime
import os
import json
from dotenv import load_dotenv
import traceback

from aster_api import AsterAPI
from aster_funcs import AsterFuncs

# Load environment variables
load_dotenv()

# Get API keys from environment variables
ASTER_API_KEY = os.getenv('ASTER_API_KEY')
ASTER_API_SECRET = os.getenv('ASTER_API_SECRET')

# Initialize API clients
api = AsterAPI(ASTER_API_KEY, ASTER_API_SECRET)
funcs = AsterFuncs(api)

# ===== CONFIGURATION VARIABLES =====

# Trading Parameters
SYMBOL = 'BTCUSDT'                    # Trading symbol
ACCOUNT_EQUITY_PERCENT = 95           # Percentage of account equity to use as margin (95 = 95%)
LEVERAGE = 30                       # Leverage to use

# Regular Stop Loss/Take Profit (monitored by bot, exits as maker)
REGULAR_TAKE_PROFIT_PERCENT = 45       # Exit as maker at this profit %
REGULAR_STOP_LOSS_PERCENT = -5     # Exit as maker at this loss %

# Emergency Stop Loss/Take Profit (monitored by bot, exits as taker)
EMERGENCY_TAKE_PROFIT_PERCENT = 50     # Emergency exit as taker at this profit %
EMERGENCY_STOP_LOSS_PERCENT = -5.5    # Emergency exit as taker at this loss %

# Trailing Take Profit Settings (Option 4)
TRAILING_TP_ACTIVATION_PERCENT = 5    # Start trailing after reaching this profit % (with leverage)
TRAILING_TP_CALLBACK_PERCENT = 0.5    # Exit when price pulls back this % from peak/low

# Bot Operation Settings
FILL_WAIT_TIME = 10                   # Seconds to wait for order to fill before checking
MAX_POSITION_ATTEMPTS = 300           # Maximum attempts to fill position
MONITORING_INTERVAL = 5                # Seconds between position monitoring checks

def get_account_equity():
    """
    Get current account equity (total balance)
    Returns the USDT balance available for trading
    """
    try:
        account_info = api.get_account_info()

        # Look for USDT balance in assets
        for asset in account_info.get('assets', []):
            if asset.get('asset') == 'USDT':

                # Total equity = wallet balance + unrealized PNL
                # Try different possible field names
                wallet_balance = float(asset.get('walletBalance', asset.get('balance', asset.get('free', 0))))
                unrealized_pnl = float(asset.get('unrealizedProfit', asset.get('unrealizedPnl', 0)))

                # Use availableBalance as the primary source - this is the actual tradeable balance
                if 'availableBalance' in asset:
                    total_equity = float(asset.get('availableBalance'))
                elif 'marginBalance' in asset:
                    total_equity = float(asset.get('marginBalance'))
                else:
                    total_equity = wallet_balance + unrealized_pnl

                print(colored(f"💰 Account Equity: ${total_equity:.2f} (Available Balance)", 'cyan'))

                # Ensure we return positive value
                if total_equity < 0:
                    print(colored(f"⚠️ Warning: Calculated negative equity, checking balance endpoint...", 'yellow'))
                    # Try balance endpoint as fallback
                    balance_info = api.get_balance()
                    for bal in balance_info:
                        if bal.get('asset') == 'USDT':
                            alt_balance = float(bal.get('balance', bal.get('free', 0)))
                            print(colored(f"🔍 Alternative balance: ${alt_balance:.2f}", 'cyan'))
                            if alt_balance > 0:
                                return alt_balance

                return abs(total_equity) if total_equity != 0 else 0

        # Fallback - try balance endpoint
        print(colored("🔍 Trying balance endpoint...", 'yellow'))
        balance_info = api.get_balance()
        for bal in balance_info:
            if bal.get('asset') == 'USDT':
                balance = float(bal.get('balance', bal.get('free', 0)))
                print(colored(f"💰 Account Equity (from balance): ${balance:.2f}", 'cyan'))
                return abs(balance) if balance != 0 else 0

        print(colored("⚠️ Could not find USDT balance", 'yellow'))
        return 0

    except Exception as e:
        print(colored(f"❌ Error fetching account equity: {e}", 'red'))
        print(colored(f"Error details: {str(e)}", 'red'))
        return 0

# Get current equity for display
current_equity = get_account_equity()
margin_to_use = current_equity * (ACCOUNT_EQUITY_PERCENT / 100)

# Menu options
print(colored("""
🌙 Moon Dev's Easy Trading Bot for Aster 🚀
============================================
""", 'cyan'))

print(colored(f"""
Configuration:
- Symbol: {SYMBOL}
- Account Equity: ${current_equity:.2f}
- Margin to Use: {ACCOUNT_EQUITY_PERCENT}% = ${margin_to_use:.2f}
- Leverage: {LEVERAGE}x
- Total Position Value: ${margin_to_use * LEVERAGE:.2f}
- Regular TP/SL: {REGULAR_TAKE_PROFIT_PERCENT}% / {REGULAR_STOP_LOSS_PERCENT}%
- Emergency TP/SL: {EMERGENCY_TAKE_PROFIT_PERCENT}% / {EMERGENCY_STOP_LOSS_PERCENT}%
- Trailing TP Activation: {TRAILING_TP_ACTIVATION_PERCENT}% (starts trailing at this profit)
- Trailing TP Callback: {TRAILING_TP_CALLBACK_PERCENT}% (exits on this pullback from peak)
- Monitor Interval: {MONITORING_INTERVAL} seconds
""", 'yellow'))

print(colored("""
Choose an action:
0 - Close position
1 - Long position
2 - Short position
3 - Monitor P&L only (no new entry)
4 - Trailing Take Profit (monitor with trailing)
5 - Exit
""", 'cyan'))

action = int(input('Enter your choice (0-5): '))

# File to store trailing TP data
TRAILING_TP_FILE = 'trailing_tp_data.txt'

def save_trailing_data(symbol, entry_price, is_long, activation_price):
    """
    Save trailing TP data to file for persistence
    """
    data = {
        'symbol': symbol,
        'entry_price': entry_price,
        'is_long': is_long,
        'activation_price': activation_price,
        'highest_price': activation_price if is_long else activation_price,
        'lowest_price': activation_price if not is_long else activation_price,
        'activated': False,
        'timestamp': datetime.now().isoformat()
    }

    with open(TRAILING_TP_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(colored(f"💾 Saved trailing TP data to {TRAILING_TP_FILE}", 'cyan'))
    return data

def load_trailing_data():
    """
    Load trailing TP data from file
    """
    if os.path.exists(TRAILING_TP_FILE):
        try:
            with open(TRAILING_TP_FILE, 'r') as f:
                data = json.load(f)
            return data
        except:
            return None
    return None

def update_trailing_data(data):
    """
    Update trailing TP data file
    """
    with open(TRAILING_TP_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def calculate_trailing_tp_price(entry_price, is_long):
    """
    Calculate the price at which trailing TP should activate
    Based on leveraged P&L percentage
    """
    if is_long:
        # For long: price needs to increase
        # Price change % = TRAILING_TP_ACTIVATION_PERCENT / LEVERAGE
        price_change_pct = TRAILING_TP_ACTIVATION_PERCENT / LEVERAGE
        activation_price = entry_price * (1 + price_change_pct / 100)
    else:
        # For short: price needs to decrease
        price_change_pct = TRAILING_TP_ACTIVATION_PERCENT / LEVERAGE
        activation_price = entry_price * (1 - price_change_pct / 100)

    return round(activation_price, 2)

def monitor_trailing_tp():
    """
    Monitor position with trailing take profit
    Activates after reaching profit target, then trails the peak
    """
    monitor_count = 0

    # Check if we have an existing position
    positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)

    if not im_in_pos:
        print(colored("❌ No position to monitor with trailing TP", 'red'))
        return

    # Get position details
    position_data = positions[0] if positions else {}
    entry_price = position_data.get('entry_price', 0)

    # Calculate activation price
    activation_price = calculate_trailing_tp_price(entry_price, is_long)

    # Initialize or load trailing data
    trailing_data = load_trailing_data()
    if not trailing_data or trailing_data.get('symbol') != SYMBOL:
        trailing_data = save_trailing_data(SYMBOL, entry_price, is_long, activation_price)

    print(colored(f"\n🎯 Trailing TP Configuration:", 'cyan'))
    print(colored(f"  Entry Price: ${entry_price:.2f}", 'white'))
    print(colored(f"  Direction: {'LONG' if is_long else 'SHORT'}", 'white'))
    print(colored(f"  Activation Price: ${activation_price:.2f} ({TRAILING_TP_ACTIVATION_PERCENT}% leveraged profit)", 'yellow'))
    print(colored(f"  Callback: {TRAILING_TP_CALLBACK_PERCENT}% from peak", 'yellow'))

    while True:
        monitor_count += 1

        positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)

        if not im_in_pos:
            print(colored("✅ Position closed", 'yellow'))
            break

        # Get current mark price
        position_data = positions[0] if positions else {}
        mark_price = position_data.get('mark_price', current_price)

        # Calculate leveraged P&L
        if is_long:
            price_change_pct = ((mark_price - entry_price) / entry_price) * 100
            leveraged_pnl = price_change_pct * LEVERAGE
        else:
            price_change_pct = ((entry_price - mark_price) / entry_price) * 100
            leveraged_pnl = price_change_pct * LEVERAGE

        # Display current status
        print(colored(f"\n{'='*60}", 'blue'))
        print(colored(f"📊 Trailing TP Monitor #{monitor_count} - {datetime.now().strftime('%H:%M:%S')}", 'cyan'))
        print(colored(f"{'='*60}", 'blue'))
        print(colored(f"Current Price: ${mark_price:.2f} | P&L: {leveraged_pnl:.3f}%", 'white'))

        # Check if trailing is activated
        if not trailing_data['activated']:
            if is_long:
                if mark_price >= activation_price:
                    trailing_data['activated'] = True
                    trailing_data['highest_price'] = mark_price
                    update_trailing_data(trailing_data)
                    print(colored(f"🔥 TRAILING ACTIVATED at {TRAILING_TP_ACTIVATION_PERCENT}% profit!", 'green', attrs=['bold']))
                    print(colored(f"📝 Now tracking peak and will exit if price drops {TRAILING_TP_CALLBACK_PERCENT}% from peak", 'yellow'))
                else:
                    distance_to_activation = activation_price - mark_price
                    print(colored(f"⏳ Waiting for activation: ${distance_to_activation:.2f} to go (${mark_price:.2f} → ${activation_price:.2f})", 'yellow'))
            else:  # Short
                if mark_price <= activation_price:
                    trailing_data['activated'] = True
                    trailing_data['lowest_price'] = mark_price
                    update_trailing_data(trailing_data)
                    print(colored(f"🔥 TRAILING ACTIVATED at {TRAILING_TP_ACTIVATION_PERCENT}% profit!", 'green', attrs=['bold']))
                    print(colored(f"📝 Now tracking low and will exit if price rises {TRAILING_TP_CALLBACK_PERCENT}% from low", 'yellow'))
                else:
                    distance_to_activation = mark_price - activation_price
                    print(colored(f"⏳ Waiting for activation: ${distance_to_activation:.2f} to go (${mark_price:.2f} → ${activation_price:.2f})", 'yellow'))
        else:
            # Trailing is active - track peak and check for pullback
            if is_long:
                # Update highest price
                if mark_price > trailing_data['highest_price']:
                    trailing_data['highest_price'] = mark_price
                    update_trailing_data(trailing_data)
                    print(colored(f"📈 New peak: ${mark_price:.2f}", 'green'))

                # Calculate pullback from peak
                pullback_pct = ((trailing_data['highest_price'] - mark_price) / trailing_data['highest_price']) * 100

                # Calculate exit price (peak minus callback)
                exit_price = trailing_data['highest_price'] * (1 - TRAILING_TP_CALLBACK_PERCENT / 100)

                print(colored(f"📊 Peak: ${trailing_data['highest_price']:.2f} | Pullback: {pullback_pct:.2f}%", 'cyan'))
                print(colored(f"🎯 Exit if price drops to: ${exit_price:.2f}", 'yellow'))

                # Check if we should exit
                if mark_price <= exit_price:
                    print(colored(f"\n💰 TRAILING TP TRIGGERED! Exiting position at ${mark_price:.2f}", 'green', attrs=['bold']))
                    print(colored(f"   Peak was ${trailing_data['highest_price']:.2f}, pulled back {pullback_pct:.2f}%", 'white'))
                    regular_maker_close(SYMBOL, is_long, abs(pos_size))
                    break
            else:  # Short
                # Update lowest price
                if mark_price < trailing_data['lowest_price']:
                    trailing_data['lowest_price'] = mark_price
                    update_trailing_data(trailing_data)
                    print(colored(f"📉 New low: ${mark_price:.2f}", 'green'))

                # Calculate pullback from low
                pullback_pct = ((mark_price - trailing_data['lowest_price']) / trailing_data['lowest_price']) * 100

                # Calculate exit price (low plus callback)
                exit_price = trailing_data['lowest_price'] * (1 + TRAILING_TP_CALLBACK_PERCENT / 100)

                print(colored(f"📊 Low: ${trailing_data['lowest_price']:.2f} | Pullback: {pullback_pct:.2f}%", 'cyan'))
                print(colored(f"🎯 Exit if price rises to: ${exit_price:.2f}", 'yellow'))

                # Check if we should exit
                if mark_price >= exit_price:
                    print(colored(f"\n💰 TRAILING TP TRIGGERED! Exiting position at ${mark_price:.2f}", 'green', attrs=['bold']))
                    print(colored(f"   Low was ${trailing_data['lowest_price']:.2f}, pulled back {pullback_pct:.2f}%", 'white'))
                    regular_maker_close(SYMBOL, is_long, abs(pos_size))
                    break

        # Also check emergency stop loss
        if leveraged_pnl <= EMERGENCY_STOP_LOSS_PERCENT:
            print(colored(f"\n🚨 EMERGENCY STOP LOSS HIT at {leveraged_pnl:.3f}%!", 'red', attrs=['bold']))
            emergency_market_close(SYMBOL, is_long, abs(pos_size))
            break

        print(colored(f"{'='*60}", 'blue'))
        time.sleep(MONITORING_INTERVAL)

def place_regular_tp_sl_orders_OLD(symbol, is_long, entry_price, position_size):
    """
    Place regular TP/SL as LIMIT orders (maker orders on the book)
    These get better fills but may not execute immediately
    """
    try:
        print(colored(f"📝 Placing regular TP/SL limit orders...", 'cyan'))

        # Check for existing orders
        open_orders = api.get_open_orders(symbol)
        has_tp = False
        has_sl = False

        for order in open_orders:
            if 'TP' in str(order.get('clientOrderId', '')).upper() or order.get('type') in ['LIMIT']:
                # Check if it's around our TP/SL prices
                order_price = float(order.get('price', 0))
                if is_long:
                    expected_tp = entry_price * (1 + REGULAR_TAKE_PROFIT_PERCENT / 100)
                    expected_sl = entry_price * (1 + REGULAR_STOP_LOSS_PERCENT / 100)
                    if abs(order_price - expected_tp) / expected_tp < 0.01:  # Within 1%
                        has_tp = True
                    elif abs(order_price - expected_sl) / expected_sl < 0.01:
                        has_sl = True

        if is_long:
            # For long position - TP above entry, SL below entry
            tp_price = round(entry_price * (1 + REGULAR_TAKE_PROFIT_PERCENT / 100), 2)
            sl_price = round(entry_price * (1 + REGULAR_STOP_LOSS_PERCENT / 100), 2)  # Note: SL% is negative
            side = 'SELL'

            print(colored(f"📊 Long position - Entry: ${entry_price:.2f}", 'cyan'))
            print(colored(f"  TP: ${tp_price:.2f} (+{REGULAR_TAKE_PROFIT_PERCENT}%)", 'green'))
            print(colored(f"  SL: ${sl_price:.2f} ({REGULAR_STOP_LOSS_PERCENT}%)", 'red'))
        else:
            # For short position - TP below entry, SL above entry
            tp_price = round(entry_price * (1 - REGULAR_TAKE_PROFIT_PERCENT / 100), 2)
            sl_price = round(entry_price * (1 - REGULAR_STOP_LOSS_PERCENT / 100), 2)  # Note: SL% is negative, double negative = positive
            side = 'BUY'

            print(colored(f"📊 Short position - Entry: ${entry_price:.2f}", 'cyan'))
            print(colored(f"  TP: ${tp_price:.2f} (-{REGULAR_TAKE_PROFIT_PERCENT}%)", 'green'))
            print(colored(f"  SL: ${sl_price:.2f} (+{abs(REGULAR_STOP_LOSS_PERCENT)}%)", 'red'))

        # Check current price vs TP/SL to make sure we don't immediately trigger
        current_price_check = entry_price  # Use entry as approximation
        print(colored(f"⚠️ Current price: ${current_price_check:.2f}", 'yellow'))

        if is_long:
            if current_price_check >= tp_price:
                print(colored(f"⚠️ WARNING: Current price ${current_price_check:.2f} is already at/above TP ${tp_price:.2f}!", 'red'))
            if current_price_check <= sl_price:
                print(colored(f"⚠️ WARNING: Current price ${current_price_check:.2f} is already at/below SL ${sl_price:.2f}!", 'red'))
        else:
            if current_price_check <= tp_price:
                print(colored(f"⚠️ WARNING: Current price ${current_price_check:.2f} is already at/below TP ${tp_price:.2f}!", 'red'))
            if current_price_check >= sl_price:
                print(colored(f"⚠️ WARNING: Current price ${current_price_check:.2f} is already at/above SL ${sl_price:.2f}!", 'red'))

        # Place regular TP as limit order if not exists
        if not has_tp:
            try:
                print(colored(f"📝 Placing TP order: {side} {position_size} @ ${tp_price:.2f}", 'cyan'))
                tp_order = funcs.limit_order(symbol, side, position_size, tp_price, True)
                print(colored(f"✅ Regular TP limit order placed at ${tp_price:.2f} - Order ID: {tp_order.get('orderId', 'Unknown')}", 'green'))
            except Exception as e:
                print(colored(f"⚠️ Failed to place regular TP: {e}", 'yellow'))

        # Wait a moment between orders
        time.sleep(1)

        # Place regular SL as limit order if not exists
        if not has_sl:
            try:
                print(colored(f"📝 Placing SL order: {side} {position_size} @ ${sl_price:.2f}", 'cyan'))
                sl_order = funcs.limit_order(symbol, side, position_size, sl_price, True)
                print(colored(f"✅ Regular SL limit order placed at ${sl_price:.2f} - Order ID: {sl_order.get('orderId', 'Unknown')}", 'green'))
            except Exception as e:
                print(colored(f"⚠️ Failed to place regular SL: {e}", 'yellow'))

        # Brief pause to let orders settle
        time.sleep(2)

        # Check if position still exists after placing orders
        positions_check, still_in_pos, _, _, _, _, _ = funcs.get_position(symbol)
        if not still_in_pos:
            print(colored(f"⚠️ WARNING: Position closed immediately after placing TP/SL orders!", 'red'))
            print(colored(f"This likely means one of the orders executed immediately.", 'red'))

    except Exception as e:
        print(colored(f"❌ Error placing regular orders: {e}", 'red'))

def monitor_position_with_emergency():
    """
    Monitor position with both regular and emergency exits
    Regular = maker exit (better price)
    Emergency = taker exit (immediate)
    """
    monitor_count = 0
    while True:
        monitor_count += 1

        positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)

        if not im_in_pos:
            print(colored("✅ Position closed", 'yellow'))
            break

        # Get detailed position info
        if positions and len(positions) > 0:
            position_data = positions[0]
            entry_price = position_data.get('entry_price', 0)
            mark_price = position_data.get('mark_price', current_price)

            # Calculate leveraged P&L
            if is_long:
                price_change_pct = ((mark_price - entry_price) / entry_price) * 100
                leveraged_pnl = price_change_pct * LEVERAGE
            else:
                price_change_pct = ((entry_price - mark_price) / entry_price) * 100
                leveraged_pnl = price_change_pct * LEVERAGE

            notional_value = abs(pos_size) * current_price
            margin_used = notional_value / LEVERAGE

            side_text = "LONG" if is_long else "SHORT"

            # Display position info
            print(colored(f"\n{'='*60}", 'blue'))
            print(colored(f"📊 Monitor #{monitor_count} - {datetime.now().strftime('%H:%M:%S')}", 'cyan'))
            print(colored(f"{'='*60}", 'blue'))
            print(colored(f"Direction: {side_text} | Size: {abs(pos_size)} units", 'white'))
            print(colored(f"Entry: ${entry_price:.2f} | Mark: ${mark_price:.2f} | Current: ${current_price:.2f}", 'white'))
            print(colored(f"Price Change: {price_change_pct:.3f}% × {LEVERAGE}x leverage", 'white'))
            print(colored(f"Leveraged P&L: {leveraged_pnl:.3f}%", 'yellow' if abs(leveraged_pnl) < 1 else ('green' if leveraged_pnl > 0 else 'red'), attrs=['bold']))

            # Debug: show exact threshold comparisons
            print(colored(f"\n📐 Threshold Check:", 'cyan'))
            print(colored(f"  P&L ({leveraged_pnl:.3f}%) vs Regular SL ({REGULAR_STOP_LOSS_PERCENT}%): {leveraged_pnl <= REGULAR_STOP_LOSS_PERCENT}", 'white'))
            print(colored(f"  P&L ({leveraged_pnl:.3f}%) vs Regular TP ({REGULAR_TAKE_PROFIT_PERCENT}%): {leveraged_pnl >= REGULAR_TAKE_PROFIT_PERCENT}", 'white'))

            # Check REGULAR thresholds first (maker exit - better price)
            if leveraged_pnl >= REGULAR_TAKE_PROFIT_PERCENT:
                print(colored(f"\n✅ REGULAR TAKE PROFIT HIT! Exiting as MAKER at {leveraged_pnl:.3f}%", 'green', attrs=['bold']))
                regular_maker_close(SYMBOL, is_long, abs(pos_size))
                break
            elif leveraged_pnl <= REGULAR_STOP_LOSS_PERCENT:
                print(colored(f"\n🛑 REGULAR STOP LOSS HIT! Exiting as MAKER at {leveraged_pnl:.3f}%", 'red', attrs=['bold']))
                regular_maker_close(SYMBOL, is_long, abs(pos_size))
                break

            # Check EMERGENCY thresholds (taker exit - immediate)
            if leveraged_pnl >= EMERGENCY_TAKE_PROFIT_PERCENT:
                print(colored(f"\n🚨 EMERGENCY TAKE PROFIT HIT! Market closing at {leveraged_pnl:.3f}%", 'green', attrs=['bold']))
                emergency_market_close(SYMBOL, is_long, abs(pos_size))
                break
            elif leveraged_pnl <= EMERGENCY_STOP_LOSS_PERCENT:
                print(colored(f"\n🚨 EMERGENCY STOP LOSS HIT! Market closing at {leveraged_pnl:.3f}%", 'red', attrs=['bold']))
                emergency_market_close(SYMBOL, is_long, abs(pos_size))
                break

            # Show thresholds with distance
            reg_sl_dist = leveraged_pnl - REGULAR_STOP_LOSS_PERCENT
            reg_tp_dist = REGULAR_TAKE_PROFIT_PERCENT - leveraged_pnl
            em_sl_dist = leveraged_pnl - EMERGENCY_STOP_LOSS_PERCENT
            em_tp_dist = EMERGENCY_TAKE_PROFIT_PERCENT - leveraged_pnl

            print(colored(f"\n📊 Thresholds:", 'cyan'))
            print(colored(f"Regular: TP {REGULAR_TAKE_PROFIT_PERCENT}% (needs +{reg_tp_dist:.3f}%) | SL {REGULAR_STOP_LOSS_PERCENT}% (buffer: {reg_sl_dist:.3f}%)", 'white'))
            print(colored(f"Emergency: TP {EMERGENCY_TAKE_PROFIT_PERCENT}% (needs +{em_tp_dist:.3f}%) | SL {EMERGENCY_STOP_LOSS_PERCENT}% (buffer: {em_sl_dist:.3f}%)", 'yellow'))
            print(colored(f"{'='*60}", 'blue'))

        time.sleep(MONITORING_INTERVAL)

def regular_maker_close(symbol, is_long, position_size):
    """
    Regular close as MAKER - places limit orders on the book for better price
    """
    print(colored(f"📝 Executing regular MAKER close...", 'cyan'))

    # Cancel any existing orders
    funcs.cancel_all_orders(symbol)

    # Get orderbook
    ask, bid, _ = funcs.ask_bid(symbol)

    if is_long:
        # Sell at ASK (maker - join the ask)
        close_side = 'SELL'
        close_price = ask
    else:
        # Buy at BID (maker - join the bid)
        close_side = 'BUY'
        close_price = bid

    print(colored(f"Placing {close_side} limit order at ${close_price:.2f} (as maker)", 'cyan'))

    attempts = 0
    max_attempts = 10

    while attempts < max_attempts:
        attempts += 1

        try:
            # Place limit order
            order = funcs.limit_order(symbol, close_side, position_size, close_price, True)
            print(colored(f"✅ Maker close order placed at ${close_price:.2f}", 'green'))

            # Wait for fill
            time.sleep(FILL_WAIT_TIME)

            # Check if closed
            positions, still_in_pos, _, _, _, _, _ = funcs.get_position(symbol)
            if not still_in_pos:
                print(colored(f"✅ Position closed as maker!", 'green'))
                return

            # Update price and try again
            ask, bid, _ = funcs.ask_bid(symbol)
            if is_long:
                close_price = ask
            else:
                close_price = bid

            print(colored(f"Order not filled, updating to new price: ${close_price:.2f}", 'yellow'))

        except Exception as e:
            print(colored(f"❌ Error in regular close: {e}", 'red'))

    # If still not closed after attempts, use emergency close
    print(colored(f"⚠️ Could not close as maker, using emergency close...", 'yellow'))
    emergency_market_close(symbol, is_long, position_size)

def emergency_market_close(symbol, is_long, position_size):
    """
    Emergency market close - crosses the spread immediately
    """
    print(colored(f"🚨 EXECUTING EMERGENCY MARKET CLOSE", 'red', attrs=['bold']))

    # Cancel all open orders first
    funcs.cancel_all_orders(symbol)

    # Get current orderbook
    ask, bid, _ = funcs.ask_bid(symbol)

    if is_long:
        # Sell at bid to close immediately
        close_side = 'SELL'
        close_price = bid
    else:
        # Buy at ask to close immediately
        close_side = 'BUY'
        close_price = ask

    try:
        # Use market-like limit order
        order = funcs.limit_order(symbol, close_side, abs(position_size), close_price, True)
        print(colored(f"✅ Emergency close order placed at ${close_price:.2f}", 'green'))

        # Wait a bit and check
        time.sleep(5)

        # If still in position, try market order
        positions, still_in_pos, _, _, _, _, _ = funcs.get_position(symbol)
        if still_in_pos:
            print(colored(f"⚠️ Position still open, forcing market close...", 'yellow'))
            funcs.kill_switch_mkt(symbol)

    except Exception as e:
        print(colored(f"❌ Error in emergency close: {e}", 'red'))
        print(colored(f"Attempting kill switch...", 'yellow'))
        funcs.kill_switch_mkt(symbol)

def place_emergency_stop_orders(symbol, side, entry_price, position_size):
    """
    Place emergency stop loss and take profit orders on the exchange
    """
    try:
        if side == 'long':
            # For long position
            stop_loss_price = entry_price * (1 + EMERGENCY_STOP_LOSS_PERCENT / 100)
            take_profit_price = entry_price * (1 + EMERGENCY_TAKE_PROFIT_PERCENT / 100)

            # Round prices appropriately
            stop_loss_price = round(stop_loss_price, 2)
            take_profit_price = round(take_profit_price, 2)

            # Place stop loss (STOP_MARKET SELL)
            sl_order = api.place_order(
                symbol=symbol,
                side='SELL',
                order_type='STOP_MARKET',
                quantity=position_size,
                stop_price=stop_loss_price,
                reduce_only=True
            )
            print(colored(f"🛑 Emergency Stop Loss placed at ${stop_loss_price:.2f}", 'yellow'))

            # Place take profit (TAKE_PROFIT_MARKET SELL)
            tp_order = api.place_order(
                symbol=symbol,
                side='SELL',
                order_type='TAKE_PROFIT_MARKET',
                quantity=position_size,
                stop_price=take_profit_price,
                reduce_only=True
            )
            print(colored(f"🎯 Emergency Take Profit placed at ${take_profit_price:.2f}", 'green'))

        else:  # short position
            # For short position (inverse logic)
            stop_loss_price = entry_price * (1 - EMERGENCY_STOP_LOSS_PERCENT / 100)
            take_profit_price = entry_price * (1 - EMERGENCY_TAKE_PROFIT_PERCENT / 100)

            # Round prices appropriately
            stop_loss_price = round(stop_loss_price, 2)
            take_profit_price = round(take_profit_price, 2)

            # Place stop loss (STOP_MARKET BUY)
            sl_order = api.place_order(
                symbol=symbol,
                side='BUY',
                order_type='STOP_MARKET',
                quantity=position_size,
                stop_price=stop_loss_price,
                reduce_only=True
            )
            print(colored(f"🛑 Emergency Stop Loss placed at ${stop_loss_price:.2f}", 'yellow'))

            # Place take profit (TAKE_PROFIT_MARKET BUY)
            tp_order = api.place_order(
                symbol=symbol,
                side='BUY',
                order_type='TAKE_PROFIT_MARKET',
                quantity=position_size,
                stop_price=take_profit_price,
                reduce_only=True
            )
            print(colored(f"🎯 Emergency Take Profit placed at ${take_profit_price:.2f}", 'green'))

        return True

    except Exception as e:
        print(colored(f"⚠️ Error placing emergency orders: {e}", 'red'))
        return False

def fill_position(symbol, side, leverage):
    """
    Fill position by placing orders at bid (for buy) or ask (for sell)
    Uses percentage of account equity for sizing
    """
    # First, set leverage
    print(colored(f"⚙️ Setting leverage to {leverage}x...", 'cyan'))
    api.change_leverage(symbol, leverage)

    # Get fresh account equity
    current_equity = get_account_equity()

    # Safety check for valid equity
    if current_equity <= 0:
        print(colored(f"❌ Invalid account equity: ${current_equity:.2f}", 'red'))
        print(colored("Cannot open position with zero or negative equity", 'red'))
        return False

    margin_usd = abs(current_equity) * (ACCOUNT_EQUITY_PERCENT / 100)

    # Calculate target position value (notional)
    target_notional_usd = margin_usd * leverage
    print(colored(f"💰 Target position: ${target_notional_usd:.2f} notional (${margin_usd:.2f} margin @ {leverage}x)", 'cyan'))
    print(colored(f"   Using {ACCOUNT_EQUITY_PERCENT}% of ${current_equity:.2f} equity", 'white'))

    emergency_orders_placed = False
    current_order_id = None
    attempts = 0

    while attempts < MAX_POSITION_ATTEMPTS:
        attempts += 1

        # Get current position
        positions, im_in_pos, current_size, _, current_price, _, is_long = funcs.get_position(symbol)

        if im_in_pos:
            filled_notional = abs(current_size) * current_price
            filled_margin = filled_notional / leverage
            print(colored(f"📊 Current position: {abs(current_size)} units", 'cyan'))
            print(colored(f"   Notional: ${filled_notional:.2f} | Margin: ${filled_margin:.2f}", 'cyan'))

            # Check if position is filled enough (97% to account for rounding)
            if filled_notional >= (target_notional_usd * 0.97):
                print(colored(f"✅ Position filled: ${filled_notional:.2f} notional (${filled_margin:.2f} margin)", 'green'))
                return True

            # NO ORDERS PLACED - just monitor for exits
            if not emergency_orders_placed:
                print(colored(f"🔔 Position filled! Monitoring for TP/SL thresholds...", 'cyan'))
                print(colored(f"📊 Regular TP: {REGULAR_TAKE_PROFIT_PERCENT}% | SL: {REGULAR_STOP_LOSS_PERCENT}% (as maker)", 'white'))
                print(colored(f"🚨 Emergency TP: {EMERGENCY_TAKE_PROFIT_PERCENT}% | SL: {EMERGENCY_STOP_LOSS_PERCENT}% (as taker)", 'white'))
                emergency_orders_placed = True  # Just using flag to avoid repeat messages

            remaining_notional = target_notional_usd - filled_notional
        else:
            remaining_notional = target_notional_usd

        # Get fresh orderbook
        ask, bid, _ = funcs.ask_bid(symbol)

        # Determine order price - always at bid for buy, ask for sell
        if side == 'BUY':
            order_price = bid
        else:  # SELL
            order_price = ask

        order_price = round(order_price, 2)

        # Calculate order size based on remaining notional value
        order_size = abs(remaining_notional) / order_price

        # Round appropriately based on symbol
        if 'BTC' in symbol:
            order_size = round(order_size, 3)
        elif 'ETH' in symbol:
            order_size = round(order_size, 2)
        else:
            order_size = round(order_size, 1)

        # Cancel previous order if exists
        if current_order_id:
            try:
                api.cancel_order(symbol, order_id=current_order_id)
                print(colored(f"❌ Canceled previous order {current_order_id}", 'yellow'))
                current_order_id = None
            except:
                pass

        # Place new order with emergency stop loss and take profit
        print(colored(f"\n📝 Attempt {attempts}/{MAX_POSITION_ATTEMPTS}:", 'yellow'))
        print(colored(f"  Placing {side} order for {order_size} @ ${order_price:.2f}", 'cyan'))
        print(colored(f"  Current spread: Bid ${bid:.2f} | Ask ${ask:.2f}", 'white'))
        print(colored(f"  Remaining to fill: ${remaining_notional:.2f}", 'white'))

        try:
            # Place the order
            order_result = funcs.limit_order(symbol, side, order_size, order_price, False)

            if order_result:
                current_order_id = order_result.get('orderId')
                print(colored(f"✅ Order placed! ID: {current_order_id}", 'green'))

            if current_order_id:
                # Wait for potential fill
                print(colored(f"⏰ Waiting {FILL_WAIT_TIME} seconds for fill...", 'yellow'))
                time.sleep(FILL_WAIT_TIME)

        except Exception as e:
            print(colored(f"❌ Error placing order: {e}", 'red'))
            time.sleep(2)
            continue

    # Final check
    positions, im_in_pos, final_size, _, final_price, _, _ = funcs.get_position(symbol)
    if im_in_pos:
        final_usd = abs(final_size) * final_price
        if final_usd >= (target_notional_usd * 0.5):  # At least half filled
            print(colored(f"⚠️ Partial fill achieved: ${final_usd:.2f} / ${target_notional_usd:.2f}", 'yellow'))
            return True

    print(colored(f"❌ Failed to fill position after {attempts} attempts", 'red'))
    return False

def close_position(symbol):
    """
    Close position by placing orders at ask (for long) or bid (for short)
    Continuously adjust to current bid/ask if price moves
    """
    # Cancel all emergency orders first
    funcs.cancel_all_orders(symbol)

    current_order_id = None
    attempts = 0

    while attempts < MAX_POSITION_ATTEMPTS:
        attempts += 1

        # Get current position
        positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(symbol)

        if not im_in_pos:
            print(colored("✅ Position closed successfully!", 'green'))
            return True

        remaining_size = abs(pos_size)

        # Get fresh orderbook
        ask, bid, _ = funcs.ask_bid(symbol)

        # Determine close side and price
        # Close as maker - place on the book instead of crossing spread
        # When closing long, we sell at ask (maker)
        # When closing short, we buy at bid (maker)
        if is_long:
            close_side = 'SELL'
            order_price = ask  # Sell at ask as maker
        else:  # Short position
            close_side = 'BUY'
            order_price = bid  # Buy at bid as maker

        order_price = round(order_price, 2)

        # Cancel previous order if exists
        if current_order_id:
            try:
                api.cancel_order(symbol, order_id=current_order_id)
                print(colored(f"❌ Canceled previous order {current_order_id}", 'yellow'))
                current_order_id = None
            except:
                pass

        print(colored(f"\n📝 Close Attempt {attempts}/{MAX_POSITION_ATTEMPTS}:", 'yellow'))
        print(colored(f"  Placing {close_side} order for {remaining_size} @ ${order_price:.2f}", 'cyan'))
        print(colored(f"  Current spread: Bid ${bid:.2f} | Ask ${ask:.2f}", 'white'))
        print(colored(f"  PnL: {pnl_perc:.2f}%", 'white'))

        try:
            # Place reduce-only order
            order_result = funcs.limit_order(symbol, close_side, remaining_size, order_price, True)

            if order_result:
                current_order_id = order_result.get('orderId')
                print(colored(f"✅ Close order placed! ID: {current_order_id}", 'green'))

                # Wait for fill
                print(colored(f"⏰ Waiting {FILL_WAIT_TIME} seconds for fill...", 'yellow'))
                time.sleep(FILL_WAIT_TIME)

        except Exception as e:
            print(colored(f"❌ Error closing: {e}", 'red'))
            time.sleep(2)
            continue

    print(colored(f"⚠️ Could not fully close position after {attempts} attempts", 'yellow'))
    return False

def monitor_position():
    """
    Monitor position with dual-threshold exits
    Regular = maker exit, Emergency = taker exit
    This is just a wrapper for the main monitoring function
    """
    monitor_position_with_emergency()

def main():
    """
    Main bot execution
    """
    try:
        if action == 0:  # Close position
            print(colored(f"\n🔄 Closing position for {SYMBOL}...", 'yellow'))
            positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)
            if im_in_pos:
                print(colored(f"📊 Current PnL: {pnl_perc:.2f}%", 'cyan'))
                close_position(SYMBOL)
            else:
                print(colored("No position to close", 'yellow'))

        elif action == 1:  # Long position
            print(colored(f"\n📈 Opening LONG position for {SYMBOL}...", 'green'))

            # Check if already in position
            positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)

            if im_in_pos:
                pos_usd = abs(pos_size) * current_price
                margin_used = pos_usd / LEVERAGE
                print(colored(f"Already in position: ${pos_usd:.2f} notional (${margin_used:.2f} margin) | PnL: {pnl_perc:.2f}%", 'yellow'))

                # Check if emergency orders exist
                print(colored(f"🔍 Checking for existing emergency orders...", 'cyan'))
                open_orders = api.get_open_orders(SYMBOL)
                has_sl = False
                has_tp = False

                for order in open_orders:
                    if order.get('type') == 'STOP_MARKET':
                        has_sl = True
                        print(colored(f"✅ Found existing Stop Loss order", 'green'))
                    elif order.get('type') == 'TAKE_PROFIT_MARKET':
                        has_tp = True
                        print(colored(f"✅ Found existing Take Profit order", 'green'))

                # Place emergency orders if missing
                if not has_sl or not has_tp:
                    print(colored(f"⚠️ Missing emergency orders, placing them now...", 'yellow'))

                    # Calculate stop prices based on current price
                    if is_long:
                        stop_loss_price = round(current_price * (1 + EMERGENCY_STOP_LOSS_PERCENT / 100), 2)
                        take_profit_price = round(current_price * (1 + EMERGENCY_TAKE_PROFIT_PERCENT / 100), 2)
                        stop_side = 'SELL'
                    else:
                        stop_loss_price = round(current_price * (1 - EMERGENCY_STOP_LOSS_PERCENT / 100), 2)
                        take_profit_price = round(current_price * (1 - EMERGENCY_TAKE_PROFIT_PERCENT / 100), 2)
                        stop_side = 'BUY'

                    if not has_sl:
                        try:
                            sl_order = api.place_order(
                                symbol=SYMBOL,
                                side=stop_side,
                                order_type='STOP_MARKET',
                                quantity=abs(pos_size),
                                stop_price=stop_loss_price,
                                reduce_only=True
                            )
                            print(colored(f"✅ Stop Loss placed at ${stop_loss_price:.2f}", 'green'))
                        except Exception as e:
                            print(colored(f"❌ Failed to place stop loss: {e}", 'red'))

                    if not has_tp:
                        try:
                            tp_order = api.place_order(
                                symbol=SYMBOL,
                                side=stop_side,
                                order_type='TAKE_PROFIT_MARKET',
                                quantity=abs(pos_size),
                                stop_price=take_profit_price,
                                reduce_only=True
                            )
                            print(colored(f"✅ Take Profit placed at ${take_profit_price:.2f}", 'green'))
                        except Exception as e:
                            print(colored(f"❌ Failed to place take profit: {e}", 'red'))

                monitor_position()
            else:
                success = fill_position(SYMBOL, 'BUY', LEVERAGE)
                if success:
                    print(colored("Starting position monitoring...", 'cyan'))
                    monitor_position()

        elif action == 2:  # Short position
            print(colored(f"\n📉 Opening SHORT position for {SYMBOL}...", 'red'))

            # Check if already in position
            positions, im_in_pos, pos_size, _, current_price, pnl_perc, _ = funcs.get_position(SYMBOL)

            if im_in_pos:
                pos_usd = abs(pos_size) * current_price
                margin_used = pos_usd / LEVERAGE
                print(colored(f"Already in position: ${pos_usd:.2f} notional (${margin_used:.2f} margin) | PnL: {pnl_perc:.2f}%", 'yellow'))
                monitor_position()
            else:
                success = fill_position(SYMBOL, 'SELL', LEVERAGE)
                if success:
                    print(colored("Starting position monitoring...", 'cyan'))
                    monitor_position()

        elif action == 3:  # Monitor P&L only
            print(colored(f"\n📊 Monitoring P&L for {SYMBOL}...", 'cyan'))

            # Check if in position
            positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)

            if not im_in_pos:
                print(colored("❌ No position to monitor", 'red'))
            else:
                pos_usd = abs(pos_size) * current_price
                margin_used = pos_usd / LEVERAGE

                # Calculate leveraged P&L
                if is_long:
                    leveraged_pnl = pnl_perc * LEVERAGE
                else:
                    leveraged_pnl = pnl_perc * LEVERAGE

                print(colored(f"Found position: ${pos_usd:.2f} notional (${margin_used:.2f} margin)", 'green'))
                print(colored(f"Current P&L: {leveraged_pnl:.2f}% (leveraged)", 'yellow'))

                # Show thresholds
                print(colored(f"\n📊 Exit Thresholds:", 'cyan'))
                print(colored(f"Regular TP: {REGULAR_TAKE_PROFIT_PERCENT}% | SL: {REGULAR_STOP_LOSS_PERCENT}% (as maker)", 'white'))
                print(colored(f"Emergency TP: {EMERGENCY_TAKE_PROFIT_PERCENT}% | SL: {EMERGENCY_STOP_LOSS_PERCENT}% (as taker)", 'white'))

                # Start monitoring - NO ORDERS PLACED
                print(colored(f"\n🔍 Starting position monitoring (no orders placed)...", 'cyan'))
                monitor_position_with_emergency()

        elif action == 4:  # Trailing Take Profit
            print(colored(f"\n📈 Starting Trailing Take Profit for {SYMBOL}...", 'cyan'))

            # Check if in position
            positions, im_in_pos, pos_size, _, current_price, pnl_perc, is_long = funcs.get_position(SYMBOL)

            if not im_in_pos:
                print(colored("❌ No position to monitor with trailing TP", 'red'))
                print(colored("Please open a position first (option 1 or 2)", 'yellow'))
            else:
                pos_usd = abs(pos_size) * current_price
                margin_used = pos_usd / LEVERAGE

                # Calculate leveraged P&L
                leveraged_pnl = pnl_perc * LEVERAGE

                side_text = "LONG" if is_long else "SHORT"
                print(colored(f"Found {side_text} position: ${pos_usd:.2f} notional (${margin_used:.2f} margin)", 'green'))
                print(colored(f"Current P&L: {leveraged_pnl:.2f}% (leveraged)", 'yellow'))

                # Show trailing configuration
                print(colored(f"\n🎯 Trailing Configuration:", 'cyan'))
                print(colored(f"  Activation: {TRAILING_TP_ACTIVATION_PERCENT}% leveraged profit", 'white'))
                print(colored(f"  Callback: {TRAILING_TP_CALLBACK_PERCENT}% from peak/low", 'white'))
                print(colored(f"  Emergency SL: {EMERGENCY_STOP_LOSS_PERCENT}%", 'white'))

                # Start trailing TP monitor
                monitor_trailing_tp()

        elif action == 5:  # Exit
            print(colored("\n👋 Exiting... Thanks for using Moon Dev Easy Bot!", 'cyan'))

        else:
            print(colored("❌ Invalid action selected", 'red'))

    except KeyboardInterrupt:
        print(colored("\n⚠️ Bot interrupted by user", 'yellow'))
        print(colored("Checking for open positions...", 'cyan'))
        positions, im_in_pos, _, _, _, _, _ = funcs.get_position(SYMBOL)
        if im_in_pos:
            response = input("Close position before exiting? (y/n): ")
            if response.lower() == 'y':
                close_position(SYMBOL)
    except Exception as e:
        print(colored(f"❌ Error in bot: {e}", 'red'))
        print(traceback.format_exc())

if __name__ == "__main__":
    print(colored("""
    ============================================
    🌙 Moon Dev Easy Bot for Aster Exchange 🚀
    ============================================
    """, 'cyan'))

    main()

    print(colored("\n✨ Thanks for using Moon Dev Trading Bot! ✨", 'cyan'))