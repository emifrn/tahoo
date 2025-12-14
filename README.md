# Tahoo (ty)

**Terminal Yahoo Finance** - A simple, project-based stock price tracker for your terminal.

## Features

- 📊 Fetch historical stock prices from Yahoo Finance
- 💾 Store data locally in SQLite database
- 📈 Calculate dividend yields
- 🔄 Track stock splits
- 🎨 Beautiful terminal UI with progress bars (powered by [rich](https://github.com/Textualize/rich))
- 📁 Project-based config (like git) - track multiple portfolios

## Installation

### From source

```bash
git clone https://github.com/YOUR_USERNAME/tahoo.git
cd tahoo
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Requirements

- Python 3.11 or later

## Quick Start

### 1. Initialize a project

```bash
mkdir ~/my-stocks
cd ~/my-stocks
ty init
```

This creates `ty.toml` in the current directory.

### 2. Configure your tickers

Edit `ty.toml`:

```toml
[default]
tickers = ["AAPL", "MSFT", "GOOGL", "NVDA"]

[history]
repair = true
auto_adjust = false
```

### 3. Fetch data

```bash
ty -r          # Refresh all default tickers
ty -r TSLA AMD # Refresh specific tickers
```

### 4. Query data

```bash
ty -s                    # Show all history for default tickers
ty -s AAPL MSFT          # Show history for specific tickers
ty -s AAPL -m            # Show last month
ty -s AAPL -y            # Show last year
ty -s -b 2024-01-01      # Show from specific date
ty --yld                 # Show dividend yields
ty -d                    # Show only dividend payments
ty -x                    # Show only stock splits
```

## Project-Based Workflow

Like git, `ty` searches for `ty.toml` in the current directory and parent directories. This lets you organize multiple portfolios:

```
~/stocks/
├── personal/
│   ├── ty.toml
│   ├── ty.db
│   └── ty.updates.csv
└── retirement/
    ├── ty.toml
    ├── ty.db
    └── ty.updates.csv
```

Each directory is independent with its own database and configuration.

## Manual Data Corrections

If Yahoo Finance has bad data, you can add manual corrections to `ty.updates.csv`:

```csv
Date,Ticker,Open,High,Low,Close,Volume,Dividends,Splits
2024-11-08,PFE,27.11,27.15,26.71,26.72,55866600,0.42,0.0
```

These corrections are applied automatically when refreshing data.

## Command Reference

### Global Options

```
-r [TKR ...]       Refresh history from Yahoo Finance (all or specific tickers)
-s [TKR ...]       Select tickers (default: all from config)
-b YYYY-MM-DD      Begin date
-e YYYY-MM-DD      End date
-m                 Last month
-y                 Last year
-d                 Show only dividends
-x                 Show only splits
--yld              Calculate trailing dividend yield
--csv              Output in CSV format
--version          Show version
```

### Commands

```
ty init            Create ty.toml in current directory
```

## Examples

```bash
# Track tech stocks
mkdir ~/stocks/tech
cd ~/stocks/tech
ty init
# Edit ty.toml to add AAPL, MSFT, GOOGL, NVDA
ty -r                           # Fetch all data
ty -s -y                        # Show last year
ty --yld                        # Show dividend yields

# Track dividend stocks in separate project
mkdir ~/stocks/dividends
cd ~/stocks/dividends
ty init
# Edit ty.toml to add KO, PEP, JNJ, PG
ty -r
ty --yld                        # Compare yields

# Export data for analysis
ty -s AAPL -y --csv > aapl.csv
```

## How It Works

1. **Config discovery**: Searches for `ty.toml` starting from current directory, walking up to filesystem root
2. **Data storage**: Stores historical prices in `ty.db` (SQLite) alongside `ty.toml`
3. **Incremental updates**: Only fetches new data since last refresh (skips weekends automatically)
4. **Manual corrections**: Applies fixes from `ty.updates.csv` to handle bad Yahoo data

## License

MIT

## Credits

Built on top of:
- [yfinance](https://github.com/ranaroussi/yfinance) - Yahoo Finance API
- [pandas](https://pandas.pydata.org/) - Data manipulation
- [rich](https://github.com/Textualize/rich) - Terminal formatting
