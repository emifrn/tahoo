"""Database operations for stock history"""

import sys
import sqlite3
import datetime
from pathlib import Path
from urllib.request import pathname2url

import numpy as np
import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console(stderr=True)


class StockDatabase:
    """SQLite database for stock price history"""

    def __init__(self, settings: dict, database: Path, updates: Path):
        """
        Initialize database connection.

        Args:
            settings: Configuration dict with default/history sections
            database: Path to SQLite database file
            updates: Path to manual updates CSV file
        """
        # Validate settings structure
        match settings:
            case {
                'default': {'tickers': list()},
                'history': {'repair': bool(), 'auto_adjust': bool()}
            }:
                pass
            case _:
                raise ValueError('settings invalid format')

        self._database = database
        self._updates = updates
        self._repair = settings['history'].get('repair', True)
        self._auto_adjust = settings['history'].get('auto_adjust', False)
        self._default_tickers = settings['default']['tickers']

        # Connect to database
        db_uri = f'file:{pathname2url(str(self._database))}?mode=rwc'
        self._conn = sqlite3.connect(db_uri, uri=True)

        # Create tables
        cursor = self._conn.cursor()
        cursor.executescript("""
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS HistoryTable (
                Ticker      TEXT,
                Date        DATE,
                Open        REAL,
                High        REAL,
                Low         REAL,
                Close       REAL,
                Volume      INTEGER,
                Dividends   REAL,
                Splits      REAL,
                UNIQUE (Ticker, Date) ON CONFLICT IGNORE);
            """)
        self._conn.commit()

    @staticmethod
    def _next_work_day(day: datetime.datetime) -> datetime.date:
        """Get next business day (skip weekends)"""
        day += datetime.timedelta(days=1)
        if day.strftime("%A") == 'Saturday':
            day += datetime.timedelta(days=2)
        elif day.strftime("%A") == 'Sunday':
            day += datetime.timedelta(days=1)
        return day.date()

    def _max_day(
        self,
        table: str,
        column: str,
        ticker: str,
        default: datetime.datetime | None = None
    ) -> datetime.datetime:
        """Get the most recent date for a ticker in the database"""
        if default is None:
            default = datetime.datetime.strptime("2014-12-31", "%Y-%m-%d")

        cursor = self._conn.cursor()
        cursor.execute(f'SELECT max({column}) FROM {table} WHERE Ticker="{ticker}"')
        value = cursor.fetchone()

        if value[0] is None:
            day = default
        else:
            day = datetime.datetime.strptime(value[0], "%Y-%m-%d")

        return day

    def _refresh_history(self, tickers: list[str] | None):
        """Refresh historical prices from Yahoo Finance"""
        console.print("[bold]Refresh historical prices from Yahoo Finance[/bold]")

        data = []
        select = []

        # Find which tickers need updating
        for ticker in self.tickers(tickers):
            refresh_date = self._next_work_day(self._max_day('HistoryTable', 'Date', ticker))
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
                        repair=self._repair,
                        auto_adjust=self._auto_adjust
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
                if self._updates.exists():
                    fix_errors = pd.read_csv(self._updates)
                    df.update(fix_errors)

                console.print(f"[green]Saving to {self._database}[/green]")
                df = df[['Date', 'Ticker', 'Open', 'High', 'Low',
                         'Close', 'Volume', 'Splits', 'Dividends']]
                self.insert('HistoryTable', df)

                # Report any splits
                splits = df[df.Splits > 0]
                splits = splits[["Date", "Ticker", "Splits"]].set_index("Date").sort_index()
                if not splits.empty:
                    console.print("[yellow]Splits detected:[/yellow]")
                    console.print(splits.to_string())

    def tickers(self, tickers: list[str] | None) -> list[str]:
        """Return tickers list or default tickers if None"""
        if not tickers:
            return self._default_tickers
        return tickers

    def insert(self, table: str, df: pd.DataFrame):
        """Insert dataframe into database table"""
        cols = ','.join(df.columns)
        vals = '?' + ',?' * (len(df.columns) - 1)
        sql = f'INSERT OR IGNORE INTO {table}({cols}) VALUES({vals})'
        cursor = self._conn.cursor()
        cursor.executemany(sql, df.itertuples(index=False, name=None))
        self._conn.commit()

    def refresh(self, target: str, names: list[str] | None):
        """Refresh data from specified target"""
        match target:
            case 'history':
                self._refresh_history(names)
            case _:
                raise ValueError(f'Invalid refresh selection "{target}"')

    @staticmethod
    def _select_interval(selection: list[str], begin: str | None, end: str | None) -> list[str]:
        """Add date interval to SQL WHERE clauses"""
        if begin:
            selection.append(f'Date >= date("{begin}")')
        if end:
            selection.append(f'Date < date("{end}")')
        return selection

    @staticmethod
    def _select_divs_splits(selection: list[str], dividends: bool, splits: bool) -> list[str]:
        """Add dividend/split filters to SQL WHERE clauses"""
        if dividends:
            selection.append('Dividends > 0')
        if splits:
            selection.append('Splits != 0')
        return selection

    @staticmethod
    def _select_tickers(selection: list[str], tickers: list[str]) -> list[str]:
        """Add ticker filter to SQL WHERE clauses"""
        ticker_conditions = ' OR '.join(f'ticker="{t}"' for t in tickers)
        selection.append(f'({ticker_conditions})')
        return selection

    def history(
        self,
        tickers: list[str] | None,
        begin: str | None = None,
        end: str | None = None,
        dividends: bool | None = None,
        splits: bool | None = None
    ) -> pd.DataFrame | None:
        """Query historical price data"""
        if tickers is None:
            return None

        selection = []
        self._select_interval(selection, begin, end)
        self._select_divs_splits(selection, dividends, splits)
        self._select_tickers(selection, self.tickers(tickers))

        if selection:
            query = 'SELECT * FROM HistoryTable WHERE ' + ' AND '.join(selection)
        else:
            query = 'SELECT * FROM HistoryTable'

        df = pd.read_sql_query(query, self._conn)
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        df.set_index('Date', inplace=True)

        return df

    def last_close(
        self,
        tickers: list[str],
        begin: str | None,
        end: str | None
    ) -> pd.DataFrame:
        """Get the most recent closing price for each ticker"""
        selection = []

        if ticker_set := set(tickers):
            ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in ticker_set)
            selection.append(f'({ticker_conditions})')
        else:
            raise ValueError('no ticker specified')

        if begin is not None:
            selection.append(f'Date >= date("{begin}")')
        if end is not None:
            selection.append(f'Date < date("{end}")')

        query = f"""
            SELECT max(Date),*
            FROM HistoryTable
            WHERE {' AND '.join(selection)}
            GROUP BY Ticker
            """

        df = pd.read_sql_query(query, self._conn)[['Ticker', 'max(Date)', 'Close']]
        df.set_index('Ticker', drop=True, inplace=True)
        df.rename(columns={'max(Date)': 'CloseDate', 'Close': 'ClosePrice'}, inplace=True)

        return df

    def splits(self, tickers: list[str]) -> pd.DataFrame:
        """Get stock split history for tickers"""
        selection = []

        if ticker_set := set(tickers):
            ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in ticker_set)
            selection.append(f'({ticker_conditions})')
        else:
            raise ValueError('no ticker specified')

        query = f"""
            SELECT Date,Ticker,Splits
            FROM HistoryTable
            WHERE {' AND '.join(selection)}
            AND Splits!=0
            """

        df = pd.read_sql_query(query, self._conn)[['Date', 'Ticker', 'Splits']]
        df["Date"] = pd.to_datetime(df["Date"]).dt.date

        if not df.empty:
            df = df.sort_values(['Ticker', 'Date'], ascending=[True, False])
            df["cumprod(Splits)"] = df.groupby("Ticker").Splits.cumprod()

        return df

    def div_yield(self, tickers: list[str] | None) -> pd.DataFrame:
        """Calculate trailing 12-month dividend yield"""
        df = self.history(tickers, begin=datetime.date.today() - relativedelta(months=12))
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

    def resample(
        self,
        tickers: list[str],
        begin: str | None,
        end: str | None,
        freq: str
    ) -> pd.DataFrame:
        """Resample price data to different frequency"""
        selection = []

        if ticker_set := set(tickers):
            ticker_conditions = ' OR '.join(f'Ticker="{t}"' for t in ticker_set)
            selection.append(f'({ticker_conditions})')
        else:
            raise ValueError('no ticker specified')

        if begin is not None:
            selection.append(f'Date >= date("{begin}")')
        if end is not None:
            selection.append(f'Date < date("{end}")')

        query = f"SELECT * FROM HistoryTable WHERE {' AND '.join(selection)}"
        df = pd.read_sql_query(query, self._conn)[['Ticker', 'Date', 'Close']]
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True, drop=True)

        resampled = []
        for name, group in df.groupby("Ticker"):
            resampled_group = group.resample(freq).last()
            resampled.append(resampled_group)

        return pd.concat(x for x in resampled if not x.empty)
