"""Yahoo Finance data fetching and updates."""

import sqlite3
import datetime
import pandas as pd
import yfinance as yf
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from . import store, queries

console = Console(stderr=True)


def next_work_day(day: datetime.datetime) -> datetime.date:
    """
    Get next business day (skip weekends).

    Args:
        day: Current datetime

    Returns:
        Next business day as date
    """
    day += datetime.timedelta(days=1)
    if day.strftime("%A") == 'Saturday':
        day += datetime.timedelta(days=2)
    elif day.strftime("%A") == 'Sunday':
        day += datetime.timedelta(days=1)
    return day.date()


def refresh_history(
    conn: sqlite3.Connection,
    settings: dict,
    updates_path: Path,
    tickers: list[str] | None
):
    """
    Refresh historical prices from Yahoo Finance.

    Args:
        conn: SQLite connection
        settings: Configuration dict with history section (repair, auto_adjust)
        updates_path: Path to manual updates CSV file
        tickers: List of tickers to refresh, or None for default tickers
    """
    console.print("[bold]Refresh historical prices from Yahoo Finance[/bold]")

    # Get settings
    repair = settings['history'].get('repair', True)
    auto_adjust = settings['history'].get('auto_adjust', False)
    default_tickers = settings['default']['tickers']

    # Determine which tickers to fetch
    ticker_list = tickers if tickers else default_tickers

    data = []
    select = []

    # Find which tickers need updating
    for ticker in ticker_list:
        refresh_date = next_work_day(queries.get_max_date(conn, 'HistoryTable', 'Date', ticker))
        if datetime.date.today() >= refresh_date:
            select.append((ticker, refresh_date))

    if not select:
        console.print("Nothing to do - all tickers are up to date")
        return

    # Fetch data with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Fetching from Yahoo...", total=len(select))

        for ticker, refresh_date in select:
            progress.update(task, description=f"Fetching {ticker} from {refresh_date}")

            try:
                stock = yf.Ticker(ticker)
                df = stock.history(
                    start=refresh_date,
                    repair=repair,
                    auto_adjust=auto_adjust
                )

                if not df.empty:
                    df = df.round(2)
                    df.reset_index(inplace=True)
                    df['Ticker'] = ticker
                    df.rename(columns={'Stock Splits': 'Splits'}, inplace=True)
                    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
                    data.append(df)

            except Exception as e:
                console.print(f"[yellow]Warning: Failed to fetch {ticker}: {e}[/yellow]")

            progress.advance(task)

    # Save to database
    if data:
        df = pd.concat(data)

        if not df.empty:
            # Apply manual corrections
            if updates_path.exists():
                fix_errors = pd.read_csv(updates_path)
                df.update(fix_errors)

            console.print(f"[green]Saving to database[/green]")
            df = df[['Date', 'Ticker', 'Open', 'High', 'Low',
                     'Close', 'Volume', 'Splits', 'Dividends']]
            store.insert(conn, 'HistoryTable', df)

            # Report any splits
            splits = df[df.Splits > 0]
            splits = splits[["Date", "Ticker", "Splits"]].set_index("Date").sort_index()
            if not splits.empty:
                console.print("[yellow]Splits detected:[/yellow]")
                console.print(splits.to_string())
