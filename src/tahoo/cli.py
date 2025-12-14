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
        console.print("  [bold]ty -r[/bold]  # Refresh data from Yahoo Finance")
        console.print("  [bold]ty -s[/bold]  # Show all historical data")
        return 0
    except FileExistsError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


def cmd_history(args: argparse.Namespace) -> int:
    """Main command for querying/refreshing stock history"""
    try:
        settings, database, updates = get_paths()
        db = StockDatabase(settings, database, updates)

        # Refresh data if requested
        if args.r is not None:
            db.refresh('history', args.r)

        # Determine date range
        if args.m:
            begin = datetime.date.today() - relativedelta(months=1)
            end = None
            period_desc = "Last Month"
        elif args.y:
            begin = datetime.date.today() - relativedelta(months=12)
            end = None
            period_desc = "Last Year"
        elif args.d_period:
            begin = datetime.date.today() - relativedelta(days=1)
            end = None
            period_desc = "Last Day"
        else:
            begin = args.b
            end = args.e
            if begin and end:
                period_desc = f"{begin} to {end}"
            elif begin:
                period_desc = f"Since {begin}"
            else:
                period_desc = "All Time"

        # Handle performance rankings
        if args.top or args.bottom or args.movers:
            df = db.performance(args.s, begin=begin, end=end)

            if df.empty:
                console.print("[yellow]No data available for performance analysis[/yellow]")
                return 0

            # Sort by performance
            df_sorted = df.sort_values('ChangePercent', ascending=False)

            if args.movers:
                # Show both top and bottom
                count = args.movers
                display_performance(df_sorted, f"Top {count} Performers ({period_desc})", count)
                print()  # Blank line between tables
                display_performance(
                    df_sorted.iloc[::-1],  # Reverse for bottom
                    f"Bottom {count} Performers ({period_desc})",
                    count
                )
            elif args.top:
                display_performance(df_sorted, f"Top {args.top} Performers ({period_desc})", args.top)
            elif args.bottom:
                # Reverse sort for bottom performers
                df_sorted = df_sorted.iloc[::-1]
                display_performance(df_sorted, f"Bottom {args.bottom} Performers ({period_desc})", args.bottom)

        # Query data
        elif args.yld:
            df = db.div_yield(args.s)
            if df is not None and not df.empty:
                if args.csv:
                    print(df.to_csv())
                else:
                    print(df.to_string())
            elif df is not None:
                console.print("[yellow]No data found matching criteria[/yellow]")
        else:
            df = db.history(args.s, begin=begin, end=end, dividends=args.d, splits=args.x)
            if df is not None and not df.empty:
                if args.csv:
                    print(df.to_csv())
                else:
                    print(df.to_string())
            elif df is not None:
                console.print("[yellow]No data found matching criteria[/yellow]")

        return 0

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"\nRun [bold]ty init[/bold] to create a {CONFIG_FILENAME} file")
        return 1
    except requests.exceptions.HTTPError as e:
        console.print(f"[red]HTTPError: {e}[/red]")
        return 1
    except tomllib.TOMLDecodeError as e:
        console.print(f"[red]TOMLDecodeError: {e}[/red]")
        return 1
    except sqlite3.OperationalError as e:
        console.print(f"[red]sqlite3.OperationalError: {e}[/red]")
        return 1
    except ValueError as e:
        console.print(f"[red]ValueError: {e}[/red]")
        return 1
    except KeyError as e:
        console.print(f"[red]KeyError: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        prog='ty',
        description='Tahoo - Terminal Yahoo Finance stock tracker'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize ty.toml in current directory')
    init_parser.set_defaults(func=cmd_init)

    # Main command (default) - handle stock queries
    parser.add_argument("-r", metavar='TKR', nargs='*', help="refresh history from Yahoo Finance")
    parser.add_argument("-s", metavar='TKR', nargs='*', help="select specific tickers")
    parser.add_argument("-b", metavar='YYYY-MM-DD', type=check_date, help="select begin date")
    parser.add_argument("-e", metavar='YYYY-MM-DD', type=check_date, help="select end date")
    parser.add_argument("-m", default=False, action='store_true', help="select last month")
    parser.add_argument("-y", default=False, action='store_true', help="select last year")
    parser.add_argument("--day", dest='d_period', default=False, action='store_true', help="select last day")
    parser.add_argument("-d", default=False, action='store_true', help="select dividends only")
    parser.add_argument("-x", default=False, action='store_true', help="select splits only")
    parser.add_argument("--yld", default=False, action='store_true', help="show trailing dividend yield")
    parser.add_argument("--csv", default=False, action="store_true", help="output in CSV format")

    # Performance rankings
    parser.add_argument("--top", type=int, metavar='N', help="show top N performers")
    parser.add_argument("--bottom", type=int, metavar='N', help="show bottom N performers")
    parser.add_argument("--movers", type=int, metavar='N', help="show top N and bottom N performers")

    parser.set_defaults(func=cmd_history)

    return parser


def main():
    """Main entry point for ty command"""
    parser = create_parser()
    args = parser.parse_args()

    # Handle subcommands
    if args.command == 'init':
        sys.exit(cmd_init(args))
    else:
        sys.exit(cmd_history(args))


if __name__ == '__main__':
    main()
