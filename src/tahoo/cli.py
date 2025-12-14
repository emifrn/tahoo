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

console = Console(stderr=True)


def check_date(s: str) -> datetime.date:
    """Validate date format for argparse"""
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        msg = f"invalid date format: {s!r}"
        raise argparse.ArgumentTypeError(msg)


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
        elif args.y:
            begin = datetime.date.today() - relativedelta(months=12)
            end = None
        else:
            begin = args.b
            end = args.e

        # Query data
        if args.yld:
            df = db.div_yield(args.s)
        else:
            df = db.history(args.s, begin=begin, end=end, dividends=args.d, splits=args.x)

        # Output results
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
    parser.add_argument("-d", default=False, action='store_true', help="select dividends only")
    parser.add_argument("-x", default=False, action='store_true', help="select splits only")
    parser.add_argument("--yld", default=False, action='store_true', help="show trailing dividend yield")
    parser.add_argument("--csv", default=False, action="store_true", help="output in CSV format")

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
