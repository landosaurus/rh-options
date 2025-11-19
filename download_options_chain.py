#!/usr/bin/env python3
"""
Download complete options chain data from Robinhood for any stock symbol.
Fetches all available expiration dates with full market data including Greeks.

Usage:
    python download_options_chain.py NVDA
    python download_options_chain.py TSLA
    python download_options_chain.py AAPL --output my_data.csv

    # Resume interrupted download:
    python download_options_chain.py NVDA --continue --csv NVDA_options_chain_20231119_123456.csv
"""

import robin_stocks.robinhood as rh
import pandas as pd
from datetime import datetime
import time
import argparse
import sys
import os
import json

def login():
    """Login to Robinhood using stored credentials."""
    print("🔐 Logging in to Robinhood...")
    try:
        rh.login()
        print("✅ Login successful")
        return True
    except Exception as e:
        print(f"❌ Login failed: {e}")
        print("\n💡 Make sure you've run setup_auth.py first to create your credentials")
        return False

def get_expiration_dates(symbol):
    """Get all available expiration dates for a symbol."""
    try:
        chains = rh.options.get_chains(symbol=symbol)
        if chains and 'expiration_dates' in chains:
            return chains['expiration_dates']
        return []
    except Exception as e:
        print(f"❌ Error getting expiration dates: {e}")
        return []

def get_completed_expirations(csv_file):
    """
    Get list of expiration dates already in the CSV file.
    Since we only write to CSV after fully fetching an expiration,
    any expiration in the file is complete.

    Args:
        csv_file: Path to existing CSV file

    Returns:
        Set of expiration dates in the file
    """
    if not os.path.exists(csv_file):
        return set()

    try:
        df = pd.read_csv(csv_file)
        if 'expiration_date' in df.columns:
            return set(df['expiration_date'].unique())
        return set()
    except Exception as e:
        print(f"⚠️  Warning: Could not read existing CSV: {e}")
        return set()

def fetch_options_for_expiration(symbol, exp_date):
    """
    Fetch ALL options for a single expiration date.
    Data is kept in memory and only returned after complete fetch.

    Args:
        symbol: Stock ticker
        exp_date: Expiration date (YYYY-MM-DD)

    Returns:
        List of option records, or None if error
    """
    try:
        # Get options for this expiration
        options = rh.options.find_options_by_expiration(
            inputSymbols=symbol,
            expirationDate=exp_date,
            optionType=None  # Both calls and puts
        )

        if not options:
            return []

        batch_options = []

        # Get market data for each option - keep in memory until all complete
        for option in options:
            try:
                strike = float(option['strike_price'])
                option_type = option['type']

                # Get market data
                market_data = rh.options.get_option_market_data_by_id(option['id'])

                if market_data:
                    record = {
                        'symbol': symbol,
                        'expiration_date': exp_date,
                        'strike_price': strike,
                        'option_type': option_type,
                        'bid_price': market_data[0].get('bid_price', ''),
                        'ask_price': market_data[0].get('ask_price', ''),
                        'mark_price': market_data[0].get('mark_price', ''),
                        'last_trade_price': market_data[0].get('last_trade_price', ''),
                        'volume': market_data[0].get('volume', 0),
                        'open_interest': market_data[0].get('open_interest', 0),
                        'implied_volatility': market_data[0].get('implied_volatility', ''),
                        'delta': market_data[0].get('delta', ''),
                        'gamma': market_data[0].get('gamma', ''),
                        'theta': market_data[0].get('theta', ''),
                        'vega': market_data[0].get('vega', ''),
                        'rho': market_data[0].get('rho', ''),
                        'high_price': market_data[0].get('high_price', ''),
                        'low_price': market_data[0].get('low_price', ''),
                        'previous_close': market_data[0].get('previous_close_price', ''),
                    }
                    batch_options.append(record)
            except Exception as e:
                # Skip individual options that fail
                continue

        # Return all options only after complete fetch
        return batch_options

    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return None

def download_full_chain(symbol, output_file=None, continue_mode=False):
    """
    Download complete options chain for a symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'NVDA', 'TSLA')
        output_file: Optional custom output filename
        continue_mode: If True, resume from existing CSV file

    Returns:
        Path to the created CSV file, or None if failed
    """
    symbol = symbol.upper()

    print(f"\n📊 Downloading options chain for {symbol}")
    print("=" * 60)

    # Get expiration dates
    print("📅 Fetching available expiration dates...")
    expiration_dates = get_expiration_dates(symbol)

    if not expiration_dates:
        print(f"❌ No expiration dates found for {symbol}")
        return None

    print(f"✅ Found {len(expiration_dates)} expiration dates")
    print(f"   Range: {expiration_dates[0]} to {expiration_dates[-1]}")
    print()

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'{symbol}_options_chain_{timestamp}.csv'

    # Check for existing progress
    completed_expirations = set()
    is_first_write = True

    if continue_mode and os.path.exists(output_file):
        print(f"🔍 Checking existing file for completed expirations...")
        completed_expirations = get_completed_expirations(output_file)

        if completed_expirations:
            is_first_write = False
            print(f"🔄 Resuming download from existing file: {output_file}")
            print(f"✅ Already completed: {len(completed_expirations)} expiration dates")
            print(f"⏳ Remaining: {len(expiration_dates) - len(completed_expirations)} expiration dates")
            print()
    elif os.path.exists(output_file) and not continue_mode:
        print(f"⚠️  Warning: File {output_file} already exists")
        print(f"   Use --continue to resume, or specify a different output file")
        return None

    print(f"💾 Output file: {output_file}")
    print(f"⏳ Starting download (this may take several minutes)...")
    print()

    total_options = 0
    skipped = 0
    fetched = 0

    for i, exp_date in enumerate(expiration_dates, 1):
        # Skip already completed expirations
        if exp_date in completed_expirations:
            skipped += 1
            print(f"[{i}/{len(expiration_dates)}] {exp_date} ⏭️  (already downloaded)")
            continue

        print(f"[{i}/{len(expiration_dates)}] Fetching {exp_date}...", end=' ', flush=True)

        # Fetch all options for this expiration (kept in memory)
        options_data = fetch_options_for_expiration(symbol, exp_date)

        # Only write to CSV if fetch was successful and complete
        if options_data is not None and len(options_data) > 0:
            # Create DataFrame and sort
            df = pd.DataFrame(options_data)
            df = df.sort_values(['option_type', 'strike_price'])

            # Write to CSV (header only on first write)
            mode = 'w' if is_first_write else 'a'
            header = is_first_write
            df.to_csv(output_file, mode=mode, header=header, index=False)

            # Update counters
            count = len(options_data)
            total_options += count
            fetched += 1
            is_first_write = False

            print(f"✓ {count} options (Session total: {total_options})")
        elif options_data is not None:
            print("(no data)")
        else:
            print("❌ (fetch failed, will retry on resume)")

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    print()
    print("=" * 60)

    if os.path.exists(output_file):
        # Read final CSV to get summary stats
        df = pd.read_csv(output_file)

        print(f"✅ Download complete!")
        print(f"📁 File: {output_file}")
        print(f"📊 Total options in file: {len(df)}")
        print(f"   Calls: {len(df[df['option_type'] == 'call'])}")
        print(f"   Puts: {len(df[df['option_type'] == 'put'])}")
        print(f"   Date range: {df['expiration_date'].min()} to {df['expiration_date'].max()}")
        print(f"   Strike range: ${df['strike_price'].min():.2f} to ${df['strike_price'].max():.2f}")

        if continue_mode:
            print(f"\n📈 Session stats:")
            print(f"   Fetched this session: {fetched} expiration dates")
            print(f"   Skipped (already had): {skipped} expiration dates")
            print(f"   New options added: {total_options}")

        return output_file
    else:
        print("❌ No options data retrieved")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Download complete options chain data from Robinhood',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fresh download:
  python download_options_chain.py NVDA
  python download_options_chain.py TSLA --output tsla_options.csv
  python download_options_chain.py AAPL -o aapl_data.csv

  # Resume interrupted download:
  python download_options_chain.py NVDA --continue --csv NVDA_options_chain_20231119_123456.csv

Note: You must run setup_auth.py first to authenticate with Robinhood.
        """
    )

    parser.add_argument('symbol',
                       help='Stock ticker symbol (e.g., NVDA, TSLA, AAPL)')
    parser.add_argument('-o', '--output', '--csv',
                       dest='output',
                       help='Output CSV filename (default: auto-generated with timestamp)')
    parser.add_argument('--continue', '--resume',
                       dest='continue_mode',
                       action='store_true',
                       help='Resume from existing CSV file (requires --csv to specify the file)')

    args = parser.parse_args()

    # Validate continue mode
    if args.continue_mode and not args.output:
        print("❌ Error: --continue requires --csv to specify the file to resume")
        print("   Example: python download_options_chain.py NVDA --continue --csv NVDA_options_chain_20231119_123456.csv")
        sys.exit(1)

    # Login first
    if not login():
        sys.exit(1)

    # Download the data
    try:
        output_file = download_full_chain(args.symbol, args.output, args.continue_mode)

        if output_file:
            print(f"\n🎉 Success! Data saved to {output_file}")
            if args.continue_mode:
                print(f"💡 Tip: Data was appended to existing file")
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        if args.output:
            print(f"💾 Partial data saved to: {args.output}")
            print(f"🔄 Resume with: python download_options_chain.py {args.symbol} --continue --csv {args.output}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        # Logout
        try:
            rh.logout()
        except:
            pass

if __name__ == "__main__":
    main()
