# Tahoo (ty)

**Terminal Yahoo Finance** - A simple, project-based stock price tracker for your terminal.

## Features

- Fetch historical stock prices from Yahoo Finance
- Store data locally in SQLite database
- Performance rankings and momentum analysis
- Calculate dividend yields
- Track stock splits
- Beautiful terminal UI with themed tables (powered by [rich](https://github.com/Textualize/rich))
- Project-based config (like git) - track multiple portfolios

## Installation

### From source

```bash
git clone https://github.com/emifrn/tahoo.git
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

# Optional: Specify custom paths for database and updates file
# [paths]
# database = "ty.db"              # Can be absolute or relative to ty.toml
# updates = "ty.updates.csv"
```

### 3. Fetch data

```bash
ty fetch              # Fetch all default tickers
ty fetch AAPL MSFT   # Fetch specific tickers
```

### 4. Analyze your portfolio

```bash
ty show AAPL -m            # Show AAPL last month
ty show -y                 # Show all tickers last year
ty rank --movers 10 -y     # Top/bottom 10 performers
ty yield                   # Show dividend yields
```

## Commands

### `ty init`
Initialize `ty.toml` in current directory

```bash
ty init
```

### `ty fetch`
Fetch/refresh stock data from Yahoo Finance

```bash
ty fetch              # All tickers from config
ty fetch AAPL MSFT   # Specific tickers only
```

### `ty show`
Show historical price data

```bash
ty show                      # All history
ty show AAPL MSFT           # Specific tickers
ty show AAPL -m             # Last month
ty show -y                  # Last year
ty show -b 2024-01-01       # From specific date
ty show -d                  # Dividends only
ty show -x                  # Splits only
ty show --csv               # CSV output
```

**Options:**
- `-m` - Last month
- `-y` - Last year
- `-b YYYY-MM-DD` - Begin date
- `-e YYYY-MM-DD` - End date
- `-d` - Dividends only
- `-x` - Splits only
- `--csv` - CSV format

### `ty rank`
Performance rankings and momentum analysis

```bash
ty rank                      # Top 10 performers (default: last month)
ty rank --movers 10 -y      # Top & bottom 10 last year
ty rank --top 5 -m          # Top 5 last month
ty rank --bottom 10         # Bottom 10 performers
ty rank AAPL MSFT --movers 3  # Compare specific tickers
```

**Options:**
- `--top N` - Show top N performers
- `--bottom N` - Show bottom N performers
- `--movers N` - Show top N and bottom N
- `-m` - Last month (default)
- `-y` - Last year
- `--day` - Last day
- `-b YYYY-MM-DD` - Begin date
- `-e YYYY-MM-DD` - End date

### `ty yield`
Dividend yield analysis

```bash
ty yield              # All tickers
ty yield JNJ KO PG   # Specific tickers
ty yield --csv       # CSV output
```

### `ty splits`
Stock split history

```bash
ty splits            # All splits
ty splits AAPL NVDA # Specific tickers
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

These corrections are applied automatically when fetching data.

## Examples

### Track tech stocks

```bash
mkdir ~/stocks/tech
cd ~/stocks/tech
ty init
# Edit ty.toml to add AAPL, MSFT, GOOGL, NVDA
ty fetch                    # Fetch all data
ty show -y                  # Show last year
ty rank --movers 5 -y      # See top/bottom performers
```

### Track dividend stocks

```bash
mkdir ~/stocks/dividends
cd ~/stocks/dividends
ty init
# Edit ty.toml to add KO, PEP, JNJ, PG
ty fetch
ty yield                   # Compare yields
```

### Find momentum

```bash
ty rank --movers 10 -m     # Monthly movers
ty rank --top 20 -y        # Yearly winners
ty rank AAPL MSFT GOOGL --movers 2  # Compare big tech
```

### Export data

```bash
ty show AAPL -y --csv > aapl.csv
ty yield --csv > yields.csv
```

## Theming

Tahoo uses the same theme system as [edgar-pipes](https://github.com/emifrn/edgar-pipes) for consistent visual output.

**Default theme:** `nobox-minimal-dark` (clean, no borders, subtle zebra striping)

**Customize:**
```bash
export TAHOO_THEME=financial    # More colorful
export NO_COLOR=1               # Disable colors
```

**Available themes:**
- `default` (nobox-minimal-dark)
- `minimal`
- `financial`
- `nobox`

## How It Works

1. **Config discovery**: Searches for `ty.toml` starting from current directory, walking up to filesystem root
2. **Data storage**: Stores historical prices in `ty.db` (SQLite) and manual corrections in `ty.updates.csv`. By default, both files are stored alongside `ty.toml`, but you can specify custom paths (absolute or relative) in the `[paths]` section of `ty.toml`
3. **Incremental updates**: Only fetches new data since last refresh (skips weekends automatically)
4. **Manual corrections**: Applies fixes from `ty.updates.csv` to handle bad Yahoo data
5. **Performance analysis**: Compares first and last prices over period to calculate momentum

## License

MIT

## Credits

Built on top of:
- [yfinance](https://github.com/ranaroussi/yfinance) - Yahoo Finance API
- [pandas](https://pandas.pydata.org/) - Data manipulation
- [rich](https://github.com/Textualize/rich) - Terminal formatting
