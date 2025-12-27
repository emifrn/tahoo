"""Database query functions for stock price data."""

import sqlite3
import datetime
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta


def get_max_date(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    ticker: str,
    default: datetime.datetime | None = None
) -> datetime.datetime:
    """
    Get the most recent date for a ticker in the database.

    Args:
        conn: SQLite connection
        table: Table name
        column: Column name to find max date
        ticker: Ticker symbol
        default: Default date if no data found

    Returns:
        Most recent datetime for ticker
    """
    if default is None:
        default = datetime.datetime.strptime("2014-12-31", "%Y-%m-%d")

    cursor = conn.cursor()
    cursor.execute(f'SELECT max({column}) FROM {table} WHERE Ticker="{ticker}"')
    value = cursor.fetchone()

    if value[0] is None:
        return default
    else:
        return datetime.datetime.strptime(value[0], "%Y-%m-%d")


def get_prices(
    conn: sqlite3.Connection,
    tickers: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    dividends: bool | None = None,
    splits: bool | None = None
) -> pd.DataFrame:
    """
    Query historical price data.

    Args:
        conn: SQLite connection
        tickers: List of ticker symbols
        start_date: Start date (inclusive) in YYYY-MM-DD format
        end_date: End date (exclusive) in YYYY-MM-DD format
        dividends: If True, only return rows with dividends > 0
        splits: If True, only return rows with splits != 0

    Returns:
        DataFrame with columns: Ticker, Date (index), Open, High, Low, Close, Volume, Dividends, Splits
    """
    selection = []

    # Date filters
    if start_date:
        selection.append(f'Date >= date("{start_date}")')
    if end_date:
        selection.append(f'Date < date("{end_date}")')

    # Dividend/split filters
    if dividends:
        selection.append('Dividends > 0')
    if splits:
        selection.append('Splits != 0')

    # Ticker filter
    ticker_conditions = ' OR '.join(f'ticker="{t}"' for t in tickers)
    selection.append(f'({ticker_conditions})')

    # Build query
    if selection:
        query = 'SELECT * FROM HistoryTable WHERE ' + ' AND '.join(selection)
    else:
        query = 'SELECT * FROM HistoryTable'

    df = pd.read_sql_query(query, conn)

    if df.empty:
        return df

    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
    df.set_index('Date', inplace=True)

    return df


def get_latest_close(
    conn: sqlite3.Connection,
    tickers: list[str],
    start_date: str | None = None,
    end_date: str | None = None
) -> pd.DataFrame:
    """
    Get the most recent closing price for each ticker.

    Args:
        conn: SQLite connection
        tickers: List of ticker symbols
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        DataFrame with index: Ticker, columns: CloseDate, ClosePrice
    """
    if not tickers:
        raise ValueError('no ticker specified')

    selection = []

    # Ticker filter
    ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in tickers)
    selection.append(f'({ticker_conditions})')

    # Date filters
    if start_date is not None:
        selection.append(f'Date >= date("{start_date}")')
    if end_date is not None:
        selection.append(f'Date < date("{end_date}")')

    query = f"""
        SELECT max(Date),*
        FROM HistoryTable
        WHERE {' AND '.join(selection)}
        GROUP BY Ticker
        """

    df = pd.read_sql_query(query, conn)[['Ticker', 'max(Date)', 'Close']]
    df.set_index('Ticker', drop=True, inplace=True)
    df.rename(columns={'max(Date)': 'CloseDate', 'Close': 'ClosePrice'}, inplace=True)

    return df


def get_splits(conn: sqlite3.Connection, tickers: list[str]) -> pd.DataFrame:
    """
    Get stock split history for tickers.

    Args:
        conn: SQLite connection
        tickers: List of ticker symbols

    Returns:
        DataFrame with columns: Date, Ticker, Splits, cumprod(Splits)
    """
    if not tickers:
        raise ValueError('no ticker specified')

    ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in tickers)

    query = f"""
        SELECT Date,Ticker,Splits
        FROM HistoryTable
        WHERE ({ticker_conditions})
        AND Splits!=0
        """

    df = pd.read_sql_query(query, conn)[['Date', 'Ticker', 'Splits']]
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    if not df.empty:
        df = df.sort_values(['Ticker', 'Date'], ascending=[True, False])
        df["cumprod(Splits)"] = df.groupby("Ticker").Splits.cumprod()

    return df


def calculate_div_yield(
    conn: sqlite3.Connection,
    tickers: list[str],
    lookback_months: int = 12
) -> pd.DataFrame:
    """
    Calculate trailing dividend yield.

    Args:
        conn: SQLite connection
        tickers: List of ticker symbols
        lookback_months: Number of months to look back for dividends

    Returns:
        DataFrame with columns: Ticker (index), Date, Close, Dividends, Last, Count, Yield
    """
    start_date = (datetime.date.today() - relativedelta(months=lookback_months)).isoformat()

    df = get_prices(conn, tickers, start_date=start_date)

    if df.empty:
        return df

    df = df.reset_index().groupby("Ticker").agg({
        "Date": lambda x: x[x.notnull()].iloc[-1] if x.notnull().any() else np.nan,
        "Close": lambda x: x[x.notnull()].iloc[-1] if x.notnull().any() else np.nan,
        "Dividends": [
            ("sum", "sum"),
            ("last", lambda x: x[x > 0].iloc[-1] if (x > 0).any() else np.nan),
            ("count", lambda x: (x > 0).sum())]})
    df.columns = ["Date", "Close", "Dividends", "Last", "Count"]
    df["Yield"] = (df.Dividends * 100 / df.Close).round(2)

    return df


def resample_prices(
    conn: sqlite3.Connection,
    tickers: list[str],
    freq: str,
    start_date: str | None = None,
    end_date: str | None = None
) -> pd.DataFrame:
    """
    Resample price data to different frequency.

    Args:
        conn: SQLite connection
        tickers: List of ticker symbols
        freq: Pandas frequency string (e.g., 'M' for monthly, 'W' for weekly)
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)

    Returns:
        DataFrame with resampled prices
    """
    if not tickers:
        raise ValueError('no ticker specified')

    selection = []

    # Ticker filter
    ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in tickers)
    selection.append(f'({ticker_conditions})')

    # Date filters
    if start_date is not None:
        selection.append(f'Date >= date("{start_date}")')
    if end_date is not None:
        selection.append(f'Date < date("{end_date}")')

    query = f"SELECT * FROM HistoryTable WHERE {' AND '.join(selection)}"
    df = pd.read_sql_query(query, conn)[['Ticker', 'Date', 'Close']]
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True, drop=True)

    resampled = []
    for name, group in df.groupby("Ticker"):
        resampled_group = group.resample(freq).last()
        resampled.append(resampled_group)

    return pd.concat(x for x in resampled if not x.empty)


def calculate_performance(
    conn: sqlite3.Connection,
    tickers: list[str],
    start_date: str | None = None,
    end_date: str | None = None
) -> pd.DataFrame:
    """
    Calculate performance (price change) for each ticker over a period.

    Args:
        conn: SQLite connection
        tickers: List of ticker symbols
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)

    Returns:
        DataFrame with columns:
            - Ticker: Stock symbol
            - StartDate: First date in period
            - StartPrice: Opening price
            - EndDate: Last date in period
            - EndPrice: Closing price
            - Change: Absolute price change
            - ChangePercent: Percentage change
    """
    selection = []

    # Ticker filter
    if tickers:
        ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in tickers)
        selection.append(f'({ticker_conditions})')

    # Date filters
    if start_date is not None:
        selection.append(f'Date >= date("{start_date}")')
    if end_date is not None:
        selection.append(f'Date < date("{end_date}")')

    where_clause = ' AND '.join(selection) if selection else '1=1'

    # Get first and last price for each ticker in the period
    query = f"""
        WITH FirstPrices AS (
            SELECT
                Ticker,
                MIN(Date) as StartDate,
                Close as StartPrice
            FROM HistoryTable
            WHERE {where_clause}
            GROUP BY Ticker
        ),
        LastPrices AS (
            SELECT
                Ticker,
                MAX(Date) as EndDate,
                Close as EndPrice
            FROM HistoryTable
            WHERE {where_clause}
            GROUP BY Ticker
        )
        SELECT
            f.Ticker,
            f.StartDate,
            f.StartPrice,
            l.EndDate,
            l.EndPrice
        FROM FirstPrices f
        JOIN LastPrices l ON f.Ticker = l.Ticker
        WHERE f.StartDate < l.EndDate
    """

    df = pd.read_sql_query(query, conn)

    if df.empty:
        return df

    # Calculate changes
    df['Change'] = df['EndPrice'] - df['StartPrice']
    df['ChangePercent'] = (df['Change'] / df['StartPrice'] * 100).round(2)

    # Round prices
    df['StartPrice'] = df['StartPrice'].round(2)
    df['EndPrice'] = df['EndPrice'].round(2)
    df['Change'] = df['Change'].round(2)

    return df
