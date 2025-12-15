"""Command-line interface for tahoo (ty)"""

import sys
import argparse
import datetime
from pathlib import Path

import requests
import tomllib
import sqlite3
from dateutil.relativedelta import relativedelta
from rich.console import Console

from . import __version__
from .config import get_paths, init_config, CONFIG_FILENAME
from .db import StockDatabase
from . import themes

console = Console(stderr=True)


def check_date(s: str) -> datetime.date:
    """Validate date format for argparse"""
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        msg = f"invalid date format: {s!r}"
        raise argparse.ArgumentTypeError(msg)


def display_dataframe(df, title: str | None = None):
    """Display pandas DataFrame with themed table"""
    if df.empty:
        console.print("[yellow]No data available[/yellow]")
        return

    # Prepare data for themed table
    table_data = []
    headers = [str(col) for col in df.columns]

    for _, row in df.iterrows():
        row_data = []
        for col in df.columns:
            value = row[col]
            # Format different types
            if isinstance(value, float):
                row_data.append(f"{value:.2f}")
            elif hasattr(value, 'strftime'):  # datetime object
                row_data.append(value.strftime('%Y-%m-%d'))
            else:
                row_data.append(str(value))
        table_data.append(row_data)

    table = themes.themed_table(title or "", table_data, headers)
    console.print(table)


def display_performance(df, title: str, count: int | None = None):
    """Display performance ranking with themed table"""
    if df.empty:
        console.print(f"[yellow]No data available for {title}[/yellow]")
        return

    # Limit rows if count specified
    if count:
        df = df.head(count)

    # Prepare data for themed table
    table_data = []
    for _, row in df.iterrows():
        # Color code based on performance
        change_pct = row['ChangePercent']
        if change_pct > 0:
            change_style = "green"
            change_str = f"+{row['Change']:.2f}"
            pct_str = f"+{change_pct:.2f}%"
        elif change_pct < 0:
            change_style = "red"
            change_str = f"{row['Change']:.2f}"
            pct_str = f"{change_pct:.2f}%"
        else:
            change_style = "white"
            change_str = f"{row['Change']:.2f}"
            pct_str = f"{change_pct:.2f}%"

        table_data.append([
            row['Ticker'].upper(),
            row['StartDate'],
            row['EndDate'],
            f"[{change_style}]{change_str}[/{change_style}]",
            f"[{change_style}]{pct_str}[/{change_style}]"
        ])

    headers = ["Ticker", "Start", "End", "Change", "Change %"]
    table = themes.themed_table(title, table_data, headers)
    console.print(table)


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new ty.toml in the current directory"""
    try:
        config_file = init_config()
        console.print(f"[green]Created {config_file}[/green]")
        console.print("\nEdit this file to add your stock tickers, then run:")
        console.print("  [bold]ty fetch[/bold]        # Fetch data from Yahoo Finance")
        console.print("  [bold]ty show -y[/bold]      # Show last year of data")
        console.print("  [bold]ty rank --movers 10[/bold]  # See top/bottom performers")
        return 0
    except FileExistsError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch/refresh stock data from Yahoo Finance"""
    try:
        settings, database, updates = get_paths()
        db = StockDatabase(settings, database, updates)
        db.refresh('history', args.tickers)
        return 0

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"\nRun [bold]ty init[/bold] to create a {CONFIG_FILENAME} file")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130


def cmd_show(args: argparse.Namespace) -> int:
    """Show historical price data"""
    try:
        settings, database, updates = get_paths()
        db = StockDatabase(settings, database, updates)

        # Determine date range
        if args.m:
            begin = datetime.date.today() - relativedelta(months=1)
            end = None
        elif args.y:
            begin = datetime.date.today() - relativedelta(months=12)
            end = None
        else:
            begin = args.b
            end = args.e

        # Query data
        df = db.history(args.tickers, begin=begin, end=end, dividends=args.d, splits=args.x)

        # Output results
        if df is not None and not df.empty:
            if args.csv:
                # CSV format (for Excel, spreadsheets)
                print(df.to_csv(index=True))
            else:
                # TSV format (default - for gnuplot, data analysis)
                print(df.to_csv(sep='\t', index=True))
        elif df is not None:
            console.print("[yellow]No data found matching criteria[/yellow]")

        return 0

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"\nRun [bold]ty init[/bold] to create a {CONFIG_FILENAME} file")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130


def cmd_rank(args: argparse.Namespace) -> int:
    """Show performance rankings and momentum"""
    try:
        settings, database, updates = get_paths()
        db = StockDatabase(settings, database, updates)

        # Determine date range (priority: y > day > b/e > m (default))
        if args.y:
            begin = datetime.date.today() - relativedelta(months=12)
            end = None
            period_desc = "Last Year"
        elif args.day:
            begin = datetime.date.today() - relativedelta(days=1)
            end = None
            period_desc = "Last Day"
        elif args.b or args.e:
            begin = args.b
            end = args.e
            if begin and end:
                period_desc = f"{begin} to {end}"
            elif begin:
                period_desc = f"Since {begin}"
            else:
                period_desc = f"Until {end}"
        else:
            # Default to last month
            begin = datetime.date.today() - relativedelta(months=1)
            end = None
            period_desc = "Last Month"

        # Get performance data
        df = db.performance(args.tickers, begin=begin, end=end)

        if df.empty:
            console.print("[yellow]No data available for performance analysis[/yellow]")
            return 0

        # Sort by performance
        df_sorted = df.sort_values('ChangePercent', ascending=False)

        # Display based on options
        if args.movers:
            count = args.movers
            display_performance(df_sorted, f"Top {count} Performers ({period_desc})", count)
            print()
            display_performance(
                df_sorted.iloc[::-1],
                f"Bottom {count} Performers ({period_desc})",
                count
            )
        elif args.top:
            display_performance(df_sorted, f"Top {args.top} Performers ({period_desc})", args.top)
        elif args.bottom:
            df_sorted = df_sorted.iloc[::-1]
            display_performance(df_sorted, f"Bottom {args.bottom} Performers ({period_desc})", args.bottom)
        else:
            # Default: show top 10
            display_performance(df_sorted, f"Top 10 Performers ({period_desc})", 10)

        return 0

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"\nRun [bold]ty init[/bold] to create a {CONFIG_FILENAME} file")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130


def cmd_yield(args: argparse.Namespace) -> int:
    """Show dividend yield analysis"""
    try:
        settings, database, updates = get_paths()
        db = StockDatabase(settings, database, updates)

        df = db.div_yield(args.tickers)

        if df is not None and not df.empty:
            if args.csv:
                print(df.to_csv())
            else:
                df_display = df.reset_index()
                display_dataframe(df_display, "Dividend Yields")
        elif df is not None:
            console.print("[yellow]No data found[/yellow]")

        return 0

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"\nRun [bold]ty init[/bold] to create a {CONFIG_FILENAME} file")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130


def cmd_splits(args: argparse.Namespace) -> int:
    """Show stock split history"""
    try:
        settings, database, updates = get_paths()
        db = StockDatabase(settings, database, updates)

        # Get tickers or use defaults
        tickers = args.tickers if args.tickers else None
        if tickers is None:
            tickers = settings['default']['tickers']

        df = db.splits(tickers)

        if not df.empty:
            display_dataframe(df, "Stock Splits")
        else:
            console.print("[yellow]No splits found[/yellow]")

        return 0

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"\nRun [bold]ty init[/bold] to create a {CONFIG_FILENAME} file")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130




def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with subcommands"""
    parser = argparse.ArgumentParser(
        prog='ty',
        description='Tahoo - Terminal Yahoo Finance stock tracker'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands', required=True)

    # =========================================================================
    # init - Initialize project
    # =========================================================================
    init_parser = subparsers.add_parser(
        'init',
        help='Initialize ty.toml in current directory'
    )
    init_parser.set_defaults(func=cmd_init)

    # =========================================================================
    # fetch - Fetch/refresh data
    # =========================================================================
    fetch_parser = subparsers.add_parser(
        'fetch',
        help='Fetch/refresh stock data from Yahoo Finance'
    )
    fetch_parser.add_argument(
        'tickers',
        nargs='*',
        help='Tickers to fetch (default: all from config)'
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # =========================================================================
    # show - Show historical data
    # =========================================================================
    show_parser = subparsers.add_parser(
        'show',
        help='Show historical price data'
    )
    show_parser.add_argument(
        'tickers',
        nargs='*',
        help='Tickers to show (default: all from config)'
    )
    show_parser.add_argument('-b', metavar='YYYY-MM-DD', type=check_date, help='Begin date')
    show_parser.add_argument('-e', metavar='YYYY-MM-DD', type=check_date, help='End date')
    show_parser.add_argument('-m', action='store_true', help='Last month')
    show_parser.add_argument('-y', action='store_true', help='Last year')
    show_parser.add_argument('-d', action='store_true', help='Dividends only')
    show_parser.add_argument('-x', action='store_true', help='Splits only')
    show_parser.add_argument('--csv', action='store_true', help='Output CSV format')
    show_parser.set_defaults(func=cmd_show)

    # =========================================================================
    # rank - Performance rankings
    # =========================================================================
    rank_parser = subparsers.add_parser(
        'rank',
        help='Show performance rankings and momentum'
    )
    rank_parser.add_argument(
        'tickers',
        nargs='*',
        help='Tickers to rank (default: all from config)'
    )
    rank_parser.add_argument('--top', type=int, metavar='N', help='Show top N performers')
    rank_parser.add_argument('--bottom', type=int, metavar='N', help='Show bottom N performers')
    rank_parser.add_argument('--movers', type=int, metavar='N', help='Show top N and bottom N')
    rank_parser.add_argument('-b', metavar='YYYY-MM-DD', type=check_date, help='Begin date')
    rank_parser.add_argument('-e', metavar='YYYY-MM-DD', type=check_date, help='End date')
    rank_parser.add_argument('-m', action='store_true', help='Last month (default)')
    rank_parser.add_argument('-y', action='store_true', help='Last year')
    rank_parser.add_argument('--day', action='store_true', help='Last day')
    rank_parser.set_defaults(func=cmd_rank)

    # =========================================================================
    # yield - Dividend yield
    # =========================================================================
    yield_parser = subparsers.add_parser(
        'yield',
        help='Show dividend yield analysis'
    )
    yield_parser.add_argument(
        'tickers',
        nargs='*',
        help='Tickers to analyze (default: all from config)'
    )
    yield_parser.add_argument('--csv', action='store_true', help='Output CSV format')
    yield_parser.set_defaults(func=cmd_yield)

    # =========================================================================
    # splits - Stock splits
    # =========================================================================
    splits_parser = subparsers.add_parser(
        'splits',
        help='Show stock split history'
    )
    splits_parser.add_argument(
        'tickers',
        nargs='*',
        help='Tickers to show (default: all from config)'
    )
    splits_parser.set_defaults(func=cmd_splits)

    return parser


def main():
    """Main entry point for ty command"""
    parser = create_parser()
    args = parser.parse_args()

    # Execute the command's function
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
