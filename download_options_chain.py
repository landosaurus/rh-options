#!/usr/bin/env python3
"""
OPTIMIZED: Download complete options chain data from Robinhood for any stock symbol.
Uses batch API calls to reduce from ~3000+ calls to ~60-80 calls.

Usage:
    python download_options_chain_optimized.py NVDA
    python download_options_chain_optimized.py TSLA
    python download_options_chain_optimized.py AAPL --output my_data.csv
"""

import robin_stocks.robinhood as rh
from robin_stocks.robinhood.helper import request_get
import pandas as pd
from datetime import datetime
import time
import random
import argparse
import sys
import os

# Robinhood API endpoints
MARKETDATA_OPTIONS_URL = 'https://api.robinhood.com/marketdata/options/'
BATCH_SIZE = 50  # Robinhood allows ~50 instruments per batch request
RATE_LIMIT_BASE = 1.0   # Base delay between batch requests (seconds)
RATE_LIMIT_JITTER = 0.5  # Random jitter ± this amount (seconds)


def login():
    """Login to Robinhood using stored credentials."""
    print("Logging in to Robinhood...")
    try:
        rh.login()
        print("Login successful")
        return True
    except Exception as e:
        print(f"Login failed: {e}")
        print("\nMake sure you've run setup_auth.py first to create your credentials")
        return False


def get_all_options_instruments(symbol):
    """
    Get ALL option instruments for a symbol in one paginated call.
    This is much faster than calling per-expiration.

    Returns:
        List of option instrument dictionaries (without market data)
    """
    print(f"Fetching all option instruments for {symbol}...")

    # find_tradable_options without expiration date gets ALL options
    options = rh.options.find_tradable_options(symbol)

    if not options or options == [None]:
        return []

    # Filter out None values
    options = [o for o in options if o is not None]
    print(f"Found {len(options)} option instruments")

    return options


def get_batch_market_data(instrument_urls):
    """
    Fetch market data for multiple instruments in a single API call.
    Robinhood API supports batching ~50 instruments per request.

    Args:
        instrument_urls: List of instrument URLs

    Returns:
        Dictionary mapping instrument URL to market data
    """
    if not instrument_urls:
        return {}

    # Join URLs with comma for batch request
    payload = {
        "instruments": ",".join(instrument_urls)
    }

    try:
        data = request_get(MARKETDATA_OPTIONS_URL, 'results', payload)
        if not data:
            return {}

        # Create mapping from instrument URL to market data
        result = {}
        for item in data:
            if item and 'instrument' in item:
                result[item['instrument']] = item

        return result
    except Exception as e:
        print(f"  Error fetching batch market data: {e}")
        return {}


def download_full_chain_optimized(symbol, output_file=None):
    """
    Download complete options chain using optimized batch API calls.

    Args:
        symbol: Stock ticker symbol (e.g., 'NVDA', 'TSLA')
        output_file: Optional custom output filename

    Returns:
        Path to the created CSV file, or None if failed
    """
    symbol = symbol.upper()

    print(f"\nDownloading options chain for {symbol} (OPTIMIZED)")
    print("=" * 60)

    # Step 1: Get all option instruments at once
    all_options = get_all_options_instruments(symbol)

    if not all_options:
        print(f"No options found for {symbol}")
        return None

    # Count unique expirations
    expirations = set(o.get('expiration_date') for o in all_options if o.get('expiration_date'))
    print(f"Options span {len(expirations)} expiration dates")

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'{symbol}_options_chain_{timestamp}.csv'

    print(f"Output file: {output_file}")
    print(f"Fetching market data in batches of {BATCH_SIZE}...")
    print()

    # Step 2: Collect all instrument URLs
    instrument_urls = []
    url_to_option = {}

    for option in all_options:
        url = option.get('url')
        if url:
            instrument_urls.append(url)
            url_to_option[url] = option

    print(f"Total instruments to fetch market data: {len(instrument_urls)}")

    # Step 3: Fetch market data in batches
    total_batches = (len(instrument_urls) + BATCH_SIZE - 1) // BATCH_SIZE
    all_market_data = {}

    for i in range(0, len(instrument_urls), BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        batch_urls = instrument_urls[i:i + BATCH_SIZE]

        print(f"[Batch {batch_num}/{total_batches}] Fetching {len(batch_urls)} instruments...", end=' ', flush=True)

        batch_data = get_batch_market_data(batch_urls)
        all_market_data.update(batch_data)

        print(f"Got {len(batch_data)} results")

        # Rate limit with jitter: random delay to mimic human behavior
        if batch_num < total_batches:
            delay = RATE_LIMIT_BASE + random.uniform(-RATE_LIMIT_JITTER, RATE_LIMIT_JITTER)
            time.sleep(max(0.5, delay))  # Never go below 0.5s

    print()
    print(f"Successfully fetched market data for {len(all_market_data)} options")

    # Step 4: Merge instrument data with market data and build records
    print("Merging data and building records...")

    records = []
    for url, option in url_to_option.items():
        market_data = all_market_data.get(url, {})

        record = {
            'symbol': symbol,
            'expiration_date': option.get('expiration_date', ''),
            'strike_price': float(option.get('strike_price', 0)),
            'option_type': option.get('type', ''),
            # Market data fields
            'bid_price': market_data.get('bid_price', ''),
            'ask_price': market_data.get('ask_price', ''),
            'mark_price': market_data.get('mark_price', ''),
            'last_trade_price': market_data.get('last_trade_price', ''),
            'volume': market_data.get('volume', 0),
            'open_interest': market_data.get('open_interest', 0),
            'implied_volatility': market_data.get('implied_volatility', ''),
            'delta': market_data.get('delta', ''),
            'gamma': market_data.get('gamma', ''),
            'theta': market_data.get('theta', ''),
            'vega': market_data.get('vega', ''),
            'rho': market_data.get('rho', ''),
            'high_price': market_data.get('high_price', ''),
            'low_price': market_data.get('low_price', ''),
            'previous_close': market_data.get('previous_close_price', ''),
        }
        records.append(record)

    # Step 5: Create DataFrame and save
    df = pd.DataFrame(records)
    df = df.sort_values(['expiration_date', 'option_type', 'strike_price'])
    df.to_csv(output_file, index=False)

    print()
    print("=" * 60)
    print(f"Download complete!")
    print(f"File: {output_file}")
    print(f"Total options: {len(df)}")
    print(f"  Calls: {len(df[df['option_type'] == 'call'])}")
    print(f"  Puts: {len(df[df['option_type'] == 'put'])}")
    print(f"  Date range: {df['expiration_date'].min()} to {df['expiration_date'].max()}")
    print(f"  Strike range: ${df['strike_price'].min():.2f} to ${df['strike_price'].max():.2f}")
    print()
    print(f"API calls made: ~{total_batches + 2} (vs ~{len(all_options)} with old method)")

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description='Download complete options chain data from Robinhood (OPTIMIZED)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_options_chain_optimized.py NVDA
  python download_options_chain_optimized.py TSLA --output tsla_options.csv

Note: You must run setup_auth.py first to authenticate with Robinhood.
        """
    )

    parser.add_argument('symbol',
                       help='Stock ticker symbol (e.g., NVDA, TSLA, AAPL)')
    parser.add_argument('-o', '--output',
                       dest='output',
                       help='Output CSV filename (default: auto-generated with timestamp)')

    args = parser.parse_args()

    # Login first
    if not login():
        sys.exit(1)

    # Download the data
    try:
        start_time = time.time()
        output_file = download_full_chain_optimized(args.symbol, args.output)
        elapsed = time.time() - start_time

        if output_file:
            print(f"Success! Data saved to {output_file}")
            print(f"Total time: {elapsed:.1f} seconds")
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Logout
        try:
            rh.logout()
        except:
            pass


if __name__ == "__main__":
    main()
