#!/usr/bin/env python3
"""
Post-process options chain CSV to create analytics and formatted Excel report.

Generates an Excel file with:
- Sheet 1: Summary with analytics (put/call ratios, max pain, unusual activity)
- Sheet 2: All calls data
- Sheet 3: All puts data

Usage:
    python analyze_options_chain.py NVDA_options_chain_20231119_123456.csv
    python analyze_options_chain.py data.csv --output analysis.xlsx
"""

import pandas as pd
import argparse
import sys
from datetime import datetime
import os

def calculate_put_call_ratios(df):
    """
    Calculate put/call ratios by expiration and overall.

    Returns:
        DataFrame with expiration, put/call volume ratio, and OI ratio
    """
    ratios = []

    for exp_date in sorted(df['expiration_date'].unique()):
        exp_data = df[df['expiration_date'] == exp_date]

        calls = exp_data[exp_data['option_type'] == 'call']
        puts = exp_data[exp_data['option_type'] == 'put']

        # Volume ratios
        call_volume = calls['volume'].sum()
        put_volume = puts['volume'].sum()
        volume_ratio = put_volume / call_volume if call_volume > 0 else 0

        # Open interest ratios
        call_oi = calls['open_interest'].sum()
        put_oi = puts['open_interest'].sum()
        oi_ratio = put_oi / call_oi if call_oi > 0 else 0

        ratios.append({
            'expiration_date': exp_date,
            'call_volume': int(call_volume),
            'put_volume': int(put_volume),
            'put_call_volume_ratio': round(volume_ratio, 2),
            'call_oi': int(call_oi),
            'put_oi': int(put_oi),
            'put_call_oi_ratio': round(oi_ratio, 2)
        })

    return pd.DataFrame(ratios)

def calculate_max_pain(df, exp_date):
    """
    Calculate max pain for a specific expiration.
    Max pain is the strike where option holders would lose the most money.

    Args:
        df: DataFrame with option data
        exp_date: Expiration date to calculate for

    Returns:
        Strike price with maximum pain
    """
    exp_data = df[df['expiration_date'] == exp_date].copy()

    if len(exp_data) == 0:
        return None

    # Get all unique strikes
    strikes = sorted(exp_data['strike_price'].unique())

    max_pain_strike = None
    min_total_value = float('inf')

    for strike in strikes:
        total_value = 0

        # Calculate value of all calls at this strike
        calls = exp_data[exp_data['option_type'] == 'call']
        for _, call in calls.iterrows():
            if call['strike_price'] < strike:
                # ITM call
                intrinsic_value = strike - call['strike_price']
                total_value += intrinsic_value * call['open_interest'] * 100

        # Calculate value of all puts at this strike
        puts = exp_data[exp_data['option_type'] == 'put']
        for _, put in puts.iterrows():
            if put['strike_price'] > strike:
                # ITM put
                intrinsic_value = put['strike_price'] - strike
                total_value += intrinsic_value * put['open_interest'] * 100

        # Track minimum total value (max pain)
        if total_value < min_total_value:
            min_total_value = total_value
            max_pain_strike = strike

    return max_pain_strike

def detect_unusual_activity(df):
    """
    Detect unusual option activity based on volume and open interest.

    Flags options where:
    - Volume is significantly higher than average
    - Volume/OI ratio is very high (new positions being opened)

    Returns:
        DataFrame with unusual activity
    """
    # Calculate statistics
    df = df.copy()
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
    df['open_interest'] = pd.to_numeric(df['open_interest'], errors='coerce').fillna(0)

    # Filter out zero volume
    active_options = df[df['volume'] > 0].copy()

    if len(active_options) == 0:
        return pd.DataFrame()

    # Calculate volume/OI ratio
    active_options['volume_oi_ratio'] = active_options.apply(
        lambda x: x['volume'] / x['open_interest'] if x['open_interest'] > 0 else 0,
        axis=1
    )

    # Calculate percentiles for unusual activity
    volume_mean = active_options['volume'].mean()
    volume_std = active_options['volume'].std()
    volume_threshold = volume_mean + (2 * volume_std)  # 2 standard deviations

    # Flag unusual activity
    unusual = active_options[
        (active_options['volume'] >= volume_threshold) |  # High volume
        (active_options['volume_oi_ratio'] >= 0.5)  # Volume is 50%+ of OI
    ].copy()

    # Sort by volume descending
    unusual = unusual.sort_values('volume', ascending=False)

    # Select relevant columns
    unusual = unusual[[
        'expiration_date', 'strike_price', 'option_type',
        'volume', 'open_interest', 'volume_oi_ratio',
        'last_trade_price', 'implied_volatility'
    ]].copy()

    unusual['volume_oi_ratio'] = unusual['volume_oi_ratio'].round(2)

    return unusual.head(50)  # Top 50 unusual activities

def create_summary_sheet(df):
    """
    Create summary analytics sheet.

    Returns:
        List of DataFrames to write to summary sheet
    """
    summary_data = []

    # Overall statistics
    total_calls = len(df[df['option_type'] == 'call'])
    total_puts = len(df[df['option_type'] == 'put'])
    total_call_volume = df[df['option_type'] == 'call']['volume'].sum()
    total_put_volume = df[df['option_type'] == 'put']['volume'].sum()
    total_call_oi = df[df['option_type'] == 'call']['open_interest'].sum()
    total_put_oi = df[df['option_type'] == 'put']['open_interest'].sum()

    overall_stats = pd.DataFrame([
        {'Metric': 'Total Call Options', 'Value': total_calls},
        {'Metric': 'Total Put Options', 'Value': total_puts},
        {'Metric': 'Total Call Volume', 'Value': int(total_call_volume)},
        {'Metric': 'Total Put Volume', 'Value': int(total_put_volume)},
        {'Metric': 'Total Call Open Interest', 'Value': int(total_call_oi)},
        {'Metric': 'Total Put Open Interest', 'Value': int(total_put_oi)},
        {'Metric': 'Overall P/C Volume Ratio', 'Value': round(total_put_volume / total_call_volume if total_call_volume > 0 else 0, 2)},
        {'Metric': 'Overall P/C OI Ratio', 'Value': round(total_put_oi / total_call_oi if total_call_oi > 0 else 0, 2)},
    ])

    summary_data.append(('OVERALL STATISTICS', overall_stats))

    # Put/Call ratios by expiration
    pc_ratios = calculate_put_call_ratios(df)
    summary_data.append(('PUT/CALL RATIOS BY EXPIRATION', pc_ratios))

    # Max pain by expiration
    max_pain_data = []
    for exp_date in sorted(df['expiration_date'].unique()):
        max_pain = calculate_max_pain(df, exp_date)
        if max_pain:
            max_pain_data.append({
                'expiration_date': exp_date,
                'max_pain_strike': f'${max_pain:.2f}'
            })

    max_pain_df = pd.DataFrame(max_pain_data)
    summary_data.append(('MAX PAIN BY EXPIRATION', max_pain_df))

    # Unusual activity
    unusual = detect_unusual_activity(df)
    if len(unusual) > 0:
        summary_data.append(('UNUSUAL OPTION ACTIVITY (Top 50)', unusual))

    return summary_data

def analyze_options_chain(csv_file, output_file=None):
    """
    Analyze options chain CSV and create Excel report.

    Args:
        csv_file: Path to input CSV file
        output_file: Optional output Excel filename

    Returns:
        Path to created Excel file, or None if failed
    """
    print(f"\n📊 Analyzing options chain data...")
    print("=" * 60)

    # Read CSV
    try:
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} options from {csv_file}")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return None

    # Validate required columns
    required_cols = ['expiration_date', 'strike_price', 'option_type', 'volume', 'open_interest']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing required columns: {missing_cols}")
        return None

    # Generate output filename
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(csv_file))[0]
        output_file = f'{base_name}_analysis.xlsx'

    print(f"📈 Calculating analytics...")

    # Separate calls and puts
    calls_df = df[df['option_type'] == 'call'].copy()
    puts_df = df[df['option_type'] == 'put'].copy()

    print(f"   Calls: {len(calls_df)}")
    print(f"   Puts: {len(puts_df)}")

    # Create summary data
    print(f"📊 Generating summary statistics...")
    summary_data = create_summary_sheet(df)

    # Write to Excel
    print(f"💾 Writing to Excel: {output_file}")

    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Sheet 1: Summary
            current_row = 0
            for title, data in summary_data:
                # Write title
                title_df = pd.DataFrame([[title]])
                title_df.to_excel(writer, sheet_name='Summary', startrow=current_row,
                                 header=False, index=False)
                current_row += 2

                # Write data
                data.to_excel(writer, sheet_name='Summary', startrow=current_row, index=False)
                current_row += len(data) + 3

            # Sheet 2: Calls
            calls_df.to_excel(writer, sheet_name='Calls', index=False)

            # Sheet 3: Puts
            puts_df.to_excel(writer, sheet_name='Puts', index=False)

        print()
        print("=" * 60)
        print(f"✅ Analysis complete!")
        print(f"📁 Output file: {output_file}")
        print(f"📊 Sheets created:")
        print(f"   1. Summary (analytics)")
        print(f"   2. Calls ({len(calls_df)} options)")
        print(f"   3. Puts ({len(puts_df)} options)")

        return output_file

    except Exception as e:
        print(f"❌ Error writing Excel file: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Analyze options chain CSV and create Excel report with analytics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_options_chain.py NVDA_options_chain_20231119_123456.csv
  python analyze_options_chain.py data.csv --output my_analysis.xlsx

The output Excel file will contain:
- Sheet 1: Summary with put/call ratios, max pain, and unusual activity
- Sheet 2: All calls data
- Sheet 3: All puts data
        """
    )

    parser.add_argument('csv_file',
                       help='Input CSV file with options chain data')
    parser.add_argument('-o', '--output',
                       help='Output Excel filename (default: auto-generated)')

    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.csv_file):
        print(f"❌ Error: File not found: {args.csv_file}")
        sys.exit(1)

    # Analyze the data
    try:
        output_file = analyze_options_chain(args.csv_file, args.output)

        if output_file:
            print(f"\n🎉 Success! Analysis saved to {output_file}")
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
