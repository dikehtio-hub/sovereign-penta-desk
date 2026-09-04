## HYPERLIQUID POSITIONS MONITOR - Moon Dev
## Tracks HyperLiquid user positions and watches their liquidation levels
## Monitors ALL positions across ALL coins for users in hyperliquidusers.txt 🌙

import time
import os
import threading
from datetime import datetime
import pandas as pd
import numpy as np
from termcolor import cprint, colored
from colorama import Fore, Back, Style, init
import requests

# Initialize colorama
init(autoreset=True)

# Configuration - Moon Dev
MONITOR_INTERVAL = 60  # Monitor positions every 60 seconds
TOP_N_LIQUIDATION = 10  # Show top 10 positions closest to liquidation
PRIORITY_TRACK_COUNT = 20  # Track top 20 longs + 20 shorts (40 total) for priority updates - Moon Dev
MIN_POSITION_VALUE = 200000  # Only show positions >= $50k - Moon Dev
HIGHLIGHT_THRESHOLD = 200000  # Highlight positions over $50k (yellow)
MEGA_THRESHOLD = 2000000  # Highlight BIG positions over $1M (red) - Moon Dev
USERS_FILE = 'hyperliquidusers.txt'  # Input file with wallet addresses
NUM_SCAN_THREADS = 5  # Number of parallel threads for full scan - Moon Dev 🚀

# File paths
DATA_DIR = 'data'
POSITIONS_DIR = os.path.join(DATA_DIR, 'hyperliquid_positions')

# Create directories
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(POSITIONS_DIR, exist_ok=True)

# Cache for open orders - Moon Dev
orders_cache = {}
orders_cache_time = {}
ORDERS_CACHE_TTL = 30  # Cache orders for 30 seconds

# HyperLiquid's own liquidator/strategy addresses - Moon Dev 👑
HL_LIQUIDATOR_ADDRESSES = {
    '0xdfc24b077bc1425ad1dea75bcb6f8158e10df303',
    '0x31ca8395cf837de08b24da3f660e77761dfb974b',
    '0xb0a55f13d22f66e6d495ac98113841b2326e9540',
    '0x010461c14e146ac35fe42271bdc1134ee31c703a',
    '0x2ed5c4484ea3ff8d57d5f2fb152a40d9f2b68308',
    '0x5e177e5e39c0f4e421f5865a6d8beed8d921cb70',
}

# ============================================================================
# ADDRESS LOADING - Moon Dev
# ============================================================================

def load_addresses_from_file():
    """Load wallet addresses from hyperliquidusers.txt - Moon Dev"""
    addresses = []

    if not os.path.exists(USERS_FILE):
        print(f"{Fore.RED}ERROR: {USERS_FILE} not found!{Style.RESET_ALL}")
        return addresses

    with open(USERS_FILE, 'r') as f:
        for line in f:
            address = line.strip()
            if address and address.startswith('0x'):
                addresses.append(address)

    print(f"{Fore.GREEN}✅ Loaded {len(addresses)} wallet addresses from {USERS_FILE}{Style.RESET_ALL}")
    return addresses

# ============================================================================
# OPEN ORDERS FUNCTIONS - Moon Dev
# ============================================================================

def get_user_open_orders(address):
    """Get open orders for a user address - Moon Dev"""
    # Check cache first
    now = time.time()
    if address in orders_cache and (now - orders_cache_time.get(address, 0)) < ORDERS_CACHE_TTL:
        return orders_cache[address]

    try:
        url = "https://api.hyperliquid.xyz/info"
        headers = {'Content-Type': 'application/json'}
        payload = {"type": "openOrders", "user": address}
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            orders = response.json()
            orders_cache[address] = orders
            orders_cache_time[address] = now
            return orders
        else:
            return []
    except Exception as e:
        return []

def format_orders_compact(orders, filter_coin=None, current_price=None):
    """Format orders compactly - 3 closest to current price - Moon Dev"""
    if not orders:
        return ""

    # Filter to only the relevant coin if specified
    if filter_coin:
        orders = [o for o in orders if o.get('coin', '').upper() == filter_coin.upper()]

    if not orders:
        return ""

    # Sort by distance to current price, show 3 closest
    if current_price and current_price > 0:
        orders = sorted(orders, key=lambda o: abs(float(o.get('limitPx', 0)) - current_price))

    order_strs = []
    for order in orders[:3]:
        sz = float(order.get('sz', 0))
        px = float(order.get('limitPx', 0))
        side = order.get('side', 'B')

        # Format size with sign
        if side == 'B':
            size_str = f"+{sz:.2f}" if sz < 100 else f"+{sz:.0f}"
        else:
            size_str = f"-{sz:.2f}" if sz < 100 else f"-{sz:.0f}"

        # Format price compactly
        if px >= 1000:
            px_str = f"${px:,.0f}"
        elif px >= 1:
            px_str = f"${px:.2f}"
        else:
            px_str = f"${px:.4f}"

        order_strs.append(f"{size_str}@{px_str}")

    return " | ".join(order_strs) if order_strs else ""

# ============================================================================
# POSITION MONITORING FUNCTIONS - Moon Dev
# ============================================================================

def get_spot_position_usd(address):
    """Get USDC spot position for a given address"""
    try:
        url = "https://api.hyperliquid.xyz/info"
        headers = {"Content-Type": "application/json"}
        balance_response = requests.post(url, headers=headers, json={
            "type": "spotClearinghouseState",
            "user": address
        }, timeout=10)
        balance_data = balance_response.json()

        usdc_balance = 0
        for balance in balance_data['balances']:
            if balance['coin'] == 'USDC':
                usdc_balance = float(balance['total'])
                break

        return usdc_balance

    except Exception as e:
        return 0

def get_user_positions(address):
    """Get all positions for a user address"""
    try:
        url = "https://api.hyperliquid.xyz/info"
        headers = {'Content-Type': 'application/json'}

        payload = {
            "type": "clearinghouseState",
            "user": address
        }

        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            positions = []

            if 'assetPositions' in data:
                for asset_pos in data['assetPositions']:
                    pos = asset_pos['position']
                    size = float(pos['szi'])

                    if size != 0:
                        position_info = {
                            'address': address,
                            'coin': pos['coin'],
                            'size': size,
                            'is_long': size > 0,
                            'entry_price': float(pos['entryPx']),
                            'position_value': abs(float(pos['positionValue'])),
                            'unrealized_pnl': float(pos['unrealizedPnl']),
                            'return_on_equity': float(pos.get('returnOnEquity', 0)) * 100,
                            'leverage': float(pos['leverage']['value']),
                            'liquidation_price': float(pos.get('liquidationPx', 0)) if pos.get('liquidationPx') else 0,
                        }
                        positions.append(position_info)

            account_value = 0
            if 'marginSummary' in data:
                account_value = float(data['marginSummary']['accountValue'])

            return positions, account_value
        else:
            return [], 0

    except Exception as e:
        return [], 0

def get_positions_for_addresses(address_list):
    """Get positions for specific list of addresses - Moon Dev"""
    all_positions = []

    for address in address_list:
        positions, account_value = get_user_positions(address)
        if positions:
            all_positions.extend(positions)
        time.sleep(0.1)  # Rate limit

    return all_positions

def get_current_prices():
    """Get current prices for all assets from HyperLiquid with retry - Moon Dev"""
    max_retries = 3
    retry_delay = 3  # seconds

    for attempt in range(max_retries):
        try:
            url = "https://api.hyperliquid.xyz/info"
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json={"type": "metaAndAssetCtxs"}, timeout=10)
            data = response.json()

            prices = {}
            for i, asset in enumerate(data[0]['universe']):
                coin_name = asset['name']
                current_price = float(data[1][i]['markPx'])
                prices[coin_name] = current_price

            return prices

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"{Fore.YELLOW}⚠️  ERROR getting prices (attempt {attempt+1}/{max_retries}): {str(e)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}   Retrying in {retry_delay} seconds...{Style.RESET_ALL}")
                time.sleep(retry_delay)
            else:
                print(f"{Fore.RED}ERROR getting prices after {max_retries} attempts: {str(e)}{Style.RESET_ALL}")
                return {}

def display_liquidation_risk(df):
    """Display positions closest to liquidation across ALL coins - Moon Dev style"""
    if df is None or df.empty:
        print(f"{Fore.YELLOW}No positions data available{Style.RESET_ALL}")
        return

   #print(f"\n{Fore.CYAN}DEBUG: Total positions found: {len(df)}{Style.RESET_ALL}")

    # Get unique coins
    coins = df['coin'].unique()
    print(f"{Fore.CYAN}DEBUG: Coins with positions: {', '.join(sorted(coins))}{Style.RESET_ALL}")

    # Filter valid liquidation prices
    risk_df = df[df['liquidation_price'] > 0].copy()

    #print(f"{Fore.CYAN}DEBUG: Positions with liq prices: {len(risk_df)}{Style.RESET_ALL}")

    if risk_df.empty:
        print(f"{Fore.YELLOW}No positions with liquidation prices found!{Style.RESET_ALL}")
        return

    # Get current prices for all coins
    current_prices = get_current_prices()

    if not current_prices:
        print(f"{Fore.RED}ERROR: Could not fetch current prices{Style.RESET_ALL}")
        return

    # Add current price to each position
    risk_df['current_price'] = risk_df['coin'].map(current_prices)

    # Remove positions where we couldn't get price
    risk_df = risk_df[risk_df['current_price'].notna()]

    # Calculate distance to liquidation
    risk_df['distance_to_liq_pct'] = np.where(
        risk_df['is_long'],
        abs((risk_df['current_price'] - risk_df['liquidation_price']) / risk_df['current_price'] * 100),
        abs((risk_df['liquidation_price'] - risk_df['current_price']) / risk_df['current_price'] * 100)
    )

    # Sort by distance to liquidation
    risk_df = risk_df.sort_values('distance_to_liq_pct')

    # Split into longs and shorts
    risky_longs = risk_df[risk_df['is_long']].sort_values('distance_to_liq_pct')
    risky_shorts = risk_df[~risk_df['is_long']].sort_values('distance_to_liq_pct')

    # Filter to only show positions >= $50k - Moon Dev
    risky_longs = risky_longs[risky_longs['position_value'].abs() >= MIN_POSITION_VALUE]
    risky_shorts = risky_shorts[risky_shorts['position_value'].abs() >= MIN_POSITION_VALUE]

    # ============================================================================
    # HYPERLIQUID LIQUIDATOR POSITIONS SECTION - Moon Dev 👑
    # ============================================================================
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}👑 HYPERLIQUID LIQUIDATOR POSITIONS (Top 3 per address) 👑")
    print(f"{Fore.YELLOW}{'-'*100}")

    hl_positions = risk_df[risk_df['address'].str.lower().isin(HL_LIQUIDATOR_ADDRESSES)]

    if len(hl_positions) > 0:
        for hl_addr in HL_LIQUIDATOR_ADDRESSES:
            addr_positions = hl_positions[hl_positions['address'].str.lower() == hl_addr].copy()
            if len(addr_positions) == 0:
                continue

            addr_positions = addr_positions.sort_values('position_value', ascending=False).head(3)
            orders = get_user_open_orders(hl_addr)

            print(f"{Fore.YELLOW}👑 {hl_addr}")
            for _, row in addr_positions.iterrows():
                direction = "LONG" if row['is_long'] else "SHORT"
                dir_color = Fore.GREEN if row['is_long'] else Fore.RED

                pos_line = f"   {dir_color}{direction} {Fore.WHITE}{row['coin']} {Fore.CYAN}${row['position_value']:,.0f} " + \
                          f"{Fore.BLUE}| Entry: ${row['entry_price']:,.2f} " + \
                          f"{Fore.RED}| Liq: ${row['liquidation_price']:,.2f} " + \
                          f"{Fore.MAGENTA}| Dist: {row['distance_to_liq_pct']:.1f}% " + \
                          f"{Fore.CYAN}| {row['leverage']:.1f}x"

                orders_str = format_orders_compact(orders, filter_coin=row['coin'], current_price=row['current_price'])
                if orders_str:
                    pos_line += f" {Fore.WHITE}| {orders_str}"

                print(pos_line)
        print()
    else:
        print(f"{Fore.YELLOW}No HL liquidator positions in current data{Style.RESET_ALL}\n")

    # Display long positions
    print(f"\n{Fore.GREEN}{Style.BRIGHT}🚀 TOP {TOP_N_LIQUIDATION} LONG POSITIONS CLOSEST TO LIQUIDATION (ALL COINS) 📈")
    print(f"{Fore.GREEN}{'-'*100}")

    if len(risky_longs) > 0:
        for i, (_, row) in enumerate(risky_longs.head(TOP_N_LIQUIDATION).iterrows(), 1):
            # Get USDC balance for top 2 positions
            usdc_balance = get_spot_position_usd(row['address']) if i <= 2 else 0

            display_text = f"{Fore.GREEN}#{i} {Fore.YELLOW}{row['coin']} {Fore.GREEN}${row['position_value']:,.0f} " + \
                           f"{Fore.BLUE}| Entry: ${row['entry_price']:,.2f} " + \
                           f"{Fore.RED}| Liq: ${row['liquidation_price']:,.2f} " + \
                           f"{Fore.MAGENTA}| Current: ${row['current_price']:,.2f} " + \
                           f"{Fore.MAGENTA}| Distance: {row['distance_to_liq_pct']:.2f}% " + \
                           f"{Fore.CYAN}| Leverage: {row['leverage']:.1f}x"

            if i <= 2:
                display_text += f" {Fore.MAGENTA}| 💰 USDC: ${usdc_balance:,.0f}"

            # Highlight BIG positions >= $1M in RED - Moon Dev
            if row['position_value'] >= MEGA_THRESHOLD:
                display_text = colored(f"#{i} {row['coin']} ${row['position_value']:,.0f} " + \
                               f"| Entry: ${row['entry_price']:,.2f} " + \
                               f"| Liq: ${row['liquidation_price']:,.2f} " + \
                               f"| Current: ${row['current_price']:,.2f} " + \
                               f"| Distance: {row['distance_to_liq_pct']:.2f}% " + \
                               f"| Leverage: {row['leverage']:.1f}x" + \
                               (f" | 💰 USDC: ${usdc_balance:,.0f}" if i <= 2 else ""), 'white', 'on_red')
            # Highlight positions >= $50k in YELLOW - Moon Dev
            elif row['position_value'] > HIGHLIGHT_THRESHOLD:
                display_text = colored(f"#{i} {row['coin']} ${row['position_value']:,.0f} " + \
                               f"| Entry: ${row['entry_price']:,.2f} " + \
                               f"| Liq: ${row['liquidation_price']:,.2f} " + \
                               f"| Current: ${row['current_price']:,.2f} " + \
                               f"| Distance: {row['distance_to_liq_pct']:.2f}% " + \
                               f"| Leverage: {row['leverage']:.1f}x" + \
                               (f" | 💰 USDC: ${usdc_balance:,.0f}" if i <= 2 else ""), 'black', 'on_yellow')

            print(display_text)

            # Get open orders and display with address - Moon Dev
            orders = get_user_open_orders(row['address'])
            orders_str = format_orders_compact(orders, filter_coin=row['coin'], current_price=row['current_price'])
            hl_crown = "👑 " if row['address'].lower() in HL_LIQUIDATOR_ADDRESSES else ""
            if orders_str:
                print(f"{Fore.CYAN}   {hl_crown}{row['address']} {Fore.WHITE}| {row['coin']}: {orders_str}")
            else:
                print(f"{Fore.CYAN}   {hl_crown}{row['address']}")
    else:
        print(f"{Fore.YELLOW}No long positions >= ${MIN_POSITION_VALUE:,} found!")

    # Display short positions
    print(f"\n{Fore.RED}{Style.BRIGHT}💥 TOP {TOP_N_LIQUIDATION} SHORT POSITIONS CLOSEST TO LIQUIDATION (ALL COINS) 📉")
    print(f"{Fore.RED}{'-'*100}")

    if len(risky_shorts) > 0:
        for i, (_, row) in enumerate(risky_shorts.head(TOP_N_LIQUIDATION).iterrows(), 1):
            # Get USDC balance for top 2 positions
            usdc_balance = get_spot_position_usd(row['address']) if i <= 2 else 0

            display_text = f"{Fore.RED}#{i} {Fore.YELLOW}{row['coin']} {Fore.RED}${row['position_value']:,.0f} " + \
                           f"{Fore.BLUE}| Entry: ${row['entry_price']:,.2f} " + \
                           f"{Fore.RED}| Liq: ${row['liquidation_price']:,.2f} " + \
                           f"{Fore.MAGENTA}| Current: ${row['current_price']:,.2f} " + \
                           f"{Fore.MAGENTA}| Distance: {row['distance_to_liq_pct']:.2f}% " + \
                           f"{Fore.CYAN}| Leverage: {row['leverage']:.1f}x"

            if i <= 2:
                display_text += f" {Fore.MAGENTA}| 💰 USDC: ${usdc_balance:,.0f}"

            # Highlight BIG positions >= $1M in RED - Moon Dev
            if row['position_value'] >= MEGA_THRESHOLD:
                display_text = colored(f"#{i} {row['coin']} ${row['position_value']:,.0f} " + \
                               f"| Entry: ${row['entry_price']:,.2f} " + \
                               f"| Liq: ${row['liquidation_price']:,.2f} " + \
                               f"| Current: ${row['current_price']:,.2f} " + \
                               f"| Distance: {row['distance_to_liq_pct']:.2f}% " + \
                               f"| Leverage: {row['leverage']:.1f}x" + \
                               (f" | 💰 USDC: ${usdc_balance:,.0f}" if i <= 2 else ""), 'white', 'on_red')
            # Highlight positions >= $50k in YELLOW - Moon Dev
            elif row['position_value'] > HIGHLIGHT_THRESHOLD:
                display_text = colored(f"#{i} {row['coin']} ${row['position_value']:,.0f} " + \
                               f"| Entry: ${row['entry_price']:,.2f} " + \
                               f"| Liq: ${row['liquidation_price']:,.2f} " + \
                               f"| Current: ${row['current_price']:,.2f} " + \
                               f"| Distance: {row['distance_to_liq_pct']:.2f}% " + \
                               f"| Leverage: {row['leverage']:.1f}x" + \
                               (f" | 💰 USDC: ${usdc_balance:,.0f}" if i <= 2 else ""), 'black', 'on_yellow')

            print(display_text)

            # Get open orders and display with address - Moon Dev
            orders = get_user_open_orders(row['address'])
            orders_str = format_orders_compact(orders, filter_coin=row['coin'], current_price=row['current_price'])
            hl_crown = "👑 " if row['address'].lower() in HL_LIQUIDATOR_ADDRESSES else ""
            if orders_str:
                print(f"{Fore.CYAN}   {hl_crown}{row['address']} {Fore.WHITE}| {row['coin']}: {orders_str}")
            else:
                print(f"{Fore.CYAN}   {hl_crown}{row['address']}")
    else:
        print(f"{Fore.YELLOW}No short positions >= ${MIN_POSITION_VALUE:,} found!")

    # Save liquidation data to CSV for AI agents - Moon Dev
    try:
        if len(risky_longs) > 0:
            longs_file = os.path.join(POSITIONS_DIR, "all_long_liquidation_risk.csv")
            risky_longs.head(PRIORITY_TRACK_COUNT).to_csv(longs_file, index=False)

        if len(risky_shorts) > 0:
            shorts_file = os.path.join(POSITIONS_DIR, "all_short_liquidation_risk.csv")
            risky_shorts.head(PRIORITY_TRACK_COUNT).to_csv(shorts_file, index=False)

        # Save combined file for AI agents
        if len(risky_longs) > 0 or len(risky_shorts) > 0:
            combined = pd.concat([
                risky_longs.head(PRIORITY_TRACK_COUNT),
                risky_shorts.head(PRIORITY_TRACK_COUNT)
            ]).sort_values('distance_to_liq_pct')

            combined_file = os.path.join(POSITIONS_DIR, "all_liquidation_risk.csv")
            combined.to_csv(combined_file, index=False)
    except Exception as e:
        print(f"{Fore.RED}Error saving CSV files: {str(e)}{Style.RESET_ALL}")

def get_priority_addresses():
    """Get addresses from current top 10 longs and shorts - Moon Dev"""
    priority_addresses = set()

    try:
        # Load longs CSV
        longs_file = os.path.join(POSITIONS_DIR, "all_long_liquidation_risk.csv")
        if os.path.exists(longs_file):
            longs_df = pd.read_csv(longs_file)
            if not longs_df.empty and 'address' in longs_df.columns:
                priority_addresses.update(longs_df['address'].tolist())

        # Load shorts CSV
        shorts_file = os.path.join(POSITIONS_DIR, "all_short_liquidation_risk.csv")
        if os.path.exists(shorts_file):
            shorts_df = pd.read_csv(shorts_file)
            if not shorts_df.empty and 'address' in shorts_df.columns:
                priority_addresses.update(shorts_df['address'].tolist())
    except Exception as e:
        print(f"{Fore.YELLOW}Could not load priority addresses: {str(e)}{Style.RESET_ALL}")

    return list(priority_addresses)

def priority_update_worker(all_addresses):
    """Fast worker that continuously updates top 40 traders - Moon Dev"""
    # Wait for initial full scan
    time.sleep(30)

    PRIORITY_UPDATE_INTERVAL = 60  # Update top 40 every 60 seconds

    while True:
        try:
            priority_addresses = get_priority_addresses()

            if priority_addresses:
                print(f"{Fore.CYAN}⚡ Priority: Updating {len(priority_addresses)} top traders...{Style.RESET_ALL}")
                priority_positions = get_positions_for_addresses(priority_addresses)

                if priority_positions:
                    df = pd.DataFrame(priority_positions)

                    # Clear screen
                    os.system('clear' if os.name == 'posix' else 'cls')

                    # Display header
                    print(f"\n{Back.BLUE}{Fore.WHITE}{'='*100}{Style.RESET_ALL}")
                    print(f"{Back.BLUE}{Fore.WHITE}🌙 MOON DEV'S HYPERLIQUID POSITIONS MONITOR 🌙{Style.RESET_ALL}")
                    print(f"{Back.BLUE}{Fore.WHITE}{'='*100}{Style.RESET_ALL}")

                    print(f"\n{Fore.GREEN}⚡ PRIORITY UPDATE (Top {len(priority_addresses)} traders - updates every {PRIORITY_UPDATE_INTERVAL}s)")
                    print(f"{Fore.CYAN}📊 Tracking {len(all_addresses)} total HyperLiquid users | {len(priority_positions)} priority positions")
                    print(f"{Fore.CYAN}⏰ Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"{Fore.YELLOW}🔄 Full scan running in background...{Style.RESET_ALL}")

                    # Display liquidation risk
                    display_liquidation_risk(df)

            time.sleep(PRIORITY_UPDATE_INTERVAL)

        except Exception as e:
            print(f"{Fore.RED}Priority worker ERROR: {str(e)}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            time.sleep(10)

def scan_address_chunk(addresses_chunk, thread_id, results_list):
    """Scan a chunk of addresses in a separate thread - Moon Dev"""
    chunk_positions = []

    for i, address in enumerate(addresses_chunk):
        positions, account_value = get_user_positions(address)
        if positions:
            chunk_positions.extend(positions)
        time.sleep(0.1)  # Rate limit

        # Progress update every 100 addresses
        # if (i + 1) % 100 == 0:
        #     #print(f"{Fore.CYAN}   Thread {thread_id}: Processed {i+1}/{len(addresses_chunk)} addresses...{Style.RESET_ALL}")
        #     continue 

    results_list.append(chunk_positions)
    #print(f"{Fore.GREEN}   ✅ Thread {thread_id}: Complete! Found {len(chunk_positions)} positions{Style.RESET_ALL}")

def full_scan_worker(all_addresses):
    """Background worker that scans all users with multi-threading - Moon Dev"""
    #print(f"{Fore.GREEN}📡 Full scan worker: Starting comprehensive scan loop with {NUM_SCAN_THREADS} threads...{Style.RESET_ALL}")

    while True:
        try:
            print(f"{Fore.CYAN}📡 Full scan: Checking all {len(all_addresses)} users across {NUM_SCAN_THREADS} threads...{Style.RESET_ALL}")
            start_time = time.time()

            # Split addresses into chunks for parallel processing - Moon Dev
            chunk_size = len(all_addresses) // NUM_SCAN_THREADS
            address_chunks = []

            for i in range(NUM_SCAN_THREADS):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size if i < NUM_SCAN_THREADS - 1 else len(all_addresses)
                address_chunks.append(all_addresses[start_idx:end_idx])

            #print(f"{Fore.CYAN}   Split into {NUM_SCAN_THREADS} chunks of ~{chunk_size} addresses each{Style.RESET_ALL}")

            # Launch threads - Moon Dev
            results_list = []
            threads = []

            for i, chunk in enumerate(address_chunks):
                thread = threading.Thread(target=scan_address_chunk, args=(chunk, i+1, results_list))
                thread.start()
                threads.append(thread)

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Combine results from all threads - Moon Dev
            all_positions = []
            for chunk_results in results_list:
                all_positions.extend(chunk_results)

            elapsed = time.time() - start_time
            print(f"{Fore.CYAN}✅ Full scan complete: {len(all_positions)} positions in {elapsed:.1f}s (~{len(all_addresses)/elapsed:.1f} addresses/sec){Style.RESET_ALL}")

            if all_positions:
                df = pd.DataFrame(all_positions)

                # Clear screen
                os.system('clear' if os.name == 'posix' else 'cls')

                # Display header
                print(f"\n{Back.BLUE}{Fore.WHITE}{'='*100}{Style.RESET_ALL}")
                print(f"{Back.BLUE}{Fore.WHITE}🌙 MOON DEV'S HYPERLIQUID POSITIONS MONITOR 🌙{Style.RESET_ALL}")
                print(f"{Back.BLUE}{Fore.WHITE}{'='*100}{Style.RESET_ALL}")

                print(f"\n{Fore.GREEN}✅ FULL SCAN COMPLETE (Scanned all {len(all_addresses)} users)")
                print(f"{Fore.CYAN}📊 {len(all_positions)} total positions")
                print(f"{Fore.CYAN}⏰ Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{Fore.CYAN}⏱️  Scan took: {elapsed:.1f} seconds")

                # Display liquidation risk
                display_liquidation_risk(df)

                # Save to CSV
                latest_file = os.path.join(POSITIONS_DIR, "hyperliquid_positions_latest.csv")
                df.to_csv(latest_file, index=False)

            # Sleep before next full scan
            time.sleep(MONITOR_INTERVAL)

        except Exception as e:
            print(f"{Fore.RED}Full scan worker ERROR: {str(e)}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            time.sleep(10)

# ============================================================================
# MAIN - Moon Dev
# ============================================================================

def main():
    """Main function - runs priority worker + full scan worker - Moon Dev"""
    print(f"\n{Back.BLUE}{Fore.WHITE}{'='*100}{Style.RESET_ALL}")
    print(f"{Back.BLUE}{Fore.WHITE}🌙 MOON DEV'S HYPERLIQUID POSITIONS MONITOR - STARTING UP 🌙{Style.RESET_ALL}")
    print(f"{Back.BLUE}{Fore.WHITE}{'='*100}{Style.RESET_ALL}\n")

    # Load addresses from file
    all_addresses = load_addresses_from_file()

    if not all_addresses:
        print(f"{Fore.RED}ERROR: No addresses loaded! Exiting...{Style.RESET_ALL}")
        return

    print(f"{Fore.CYAN}Starting PRIORITY update worker (fast updates every 60s for top 40)...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Starting FULL SCAN worker ({NUM_SCAN_THREADS} parallel threads scanning all {len(all_addresses)} users)...{Style.RESET_ALL}\n")

    # Start priority update worker (fast, updates top 40 every 60 seconds)
    priority_thread = threading.Thread(target=priority_update_worker, args=(all_addresses,), daemon=True)
    priority_thread.start()

    # Start full scan worker (scans all users)
    fullscan_thread = threading.Thread(target=full_scan_worker, args=(all_addresses,), daemon=True)
    fullscan_thread.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Back.RED}{Fore.WHITE}🛑 Moon Dev says: Shutting down...{Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()
