# Robinhood Options Chain Downloader

Download complete options chain data from Robinhood for any stock symbol, including all expiration dates with full market data (prices, volume, open interest, implied volatility, and Greeks).

## Features

- 📊 Download complete options chains for any ticker
- 📅 All expiration dates included
- 📈 Full market data: bid/ask, volume, open interest, IV, Greeks (delta, gamma, theta, vega, rho)
- 💾 Incremental CSV writing (data saved as it downloads)
- 🔐 Secure authentication with device token storage
- ⚡ Avoids API timeouts by fetching one expiration at a time

## Installation

1. Install required Python packages:

```bash
pip install robin-stocks pandas python-dotenv
```

2. Create a `.env` file with your Robinhood credentials:

```bash
ROBINHOOD_USERNAME=your_email@example.com
ROBINHOOD_PASSWORD=your_password
```

## Setup (One-time)

Run the authentication setup script to create your device token:

```bash
python setup_auth.py
```

This will:
- Prompt you for your 2FA code (SMS or app)
- Save your device token to `~/.tokens_robinhood.pickle`
- Allow future scripts to run without 2FA prompts

## Usage

Basic usage:

```bash
python download_options_chain.py NVDA
```

Custom output file:

```bash
python download_options_chain.py TSLA --output tsla_options.csv
python download_options_chain.py AAPL -o aapl_data.csv
```

## Output Format

The CSV file contains the following columns:

- `symbol` - Stock ticker
- `expiration_date` - Option expiration date (YYYY-MM-DD)
- `strike_price` - Strike price
- `option_type` - "call" or "put"
- `bid_price` - Current bid price
- `ask_price` - Current ask price
- `mark_price` - Mark price (midpoint)
- `last_trade_price` - Last traded price
- `volume` - Trading volume
- `open_interest` - Open interest
- `implied_volatility` - IV
- `delta` - Delta (Greeks)
- `gamma` - Gamma
- `theta` - Theta
- `vega` - Vega
- `rho` - Rho
- `high_price` - Day's high
- `low_price` - Day's low
- `previous_close` - Previous close price

## Files to Share

To share this with friends, package these files:

1. `setup_auth.py` - One-time authentication setup
2. `download_options_chain.py` - Main downloader script
3. `options_downloader_README.md` - This file (instructions)
4. `.env.example` - Template for credentials (create this)

## Example .env File

Create a file called `.env.example` with this content (for sharing):

```
ROBINHOOD_USERNAME=your_email@example.com
ROBINHOOD_PASSWORD=your_password
```

## Notes

- The downloader writes data incrementally, so you can see progress and won't lose data if interrupted
- Large option chains (like NVDA with 21 expiration dates) may take 5-10 minutes
- Data is saved as each expiration completes
- Rate limiting delays are built in to avoid API issues

## Troubleshooting

**Login fails:**
- Make sure you've run `setup_auth.py` first
- Check your credentials in the `.env` file
- Try logging into Robinhood web/app to verify account status

**No options found:**
- Verify the ticker symbol is correct
- Some stocks may not have options available

**Script interrupted:**
- Data for completed expirations is already saved in the CSV
- You can re-run to get a fresh complete download

## License

Free to use and share. Created for educational and research purposes.
