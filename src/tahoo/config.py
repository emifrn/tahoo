"""Configuration file finder and loader"""

import os
import tomllib
from pathlib import Path
from typing import Optional, Tuple


CONFIG_FILENAME = "ty.toml"
DATABASE_FILENAME = "ty.db"
UPDATES_FILENAME = "ty.updates.csv"


def find_config_dir(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Walk up directory tree to find ty.toml (like git does).

    Args:
        start_path: Directory to start search from (defaults to current directory)

    Returns:
        Path to directory containing ty.toml, or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_path).resolve()

    current = start_path

    # Walk up until we find ty.toml or hit filesystem root
    while True:
        config_file = current / CONFIG_FILENAME
        if config_file.exists():
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            return None

        current = parent


def load_config(config_dir: Path) -> dict:
    """
    Load configuration from ty.toml

    Args:
        config_dir: Directory containing ty.toml

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If ty.toml doesn't exist
        tomllib.TOMLDecodeError: If ty.toml is invalid
    """
    config_file = config_dir / CONFIG_FILENAME

    with open(config_file, 'rb') as fh:
        settings = tomllib.load(fh)

    # Validate structure
    if 'default' not in settings or 'tickers' not in settings['default']:
        raise ValueError('ty.toml must have [default] section with tickers list')

    if 'history' not in settings:
        settings['history'] = {}

    settings['history'].setdefault('repair', True)
    settings['history'].setdefault('auto_adjust', False)

    return settings


def get_paths(config_dir: Optional[Path] = None) -> Tuple[dict, Path, Path]:
    """
    Find config directory and return settings, database path, and updates path.

    Args:
        config_dir: Optional config directory (if None, searches from current dir)

    Returns:
        Tuple of (settings dict, database path, updates path)

    Raises:
        FileNotFoundError: If no ty.toml found in directory tree
    """
    if config_dir is None:
        config_dir = find_config_dir()

    if config_dir is None:
        raise FileNotFoundError(
            f"No {CONFIG_FILENAME} found in current directory or any parent directory. "
            f"Run 'ty init' to create one."
        )

    settings = load_config(config_dir)
    database = config_dir / DATABASE_FILENAME
    updates = config_dir / UPDATES_FILENAME

    return settings, database, updates


DEFAULT_CONFIG = """# Tahoo (ty) configuration file

[default]
# List your stock tickers here
tickers = []

[history]
# Repair bad data from Yahoo Finance
repair = true
# Auto-adjust prices for splits/dividends
auto_adjust = false
"""


def init_config(directory: Optional[Path] = None) -> Path:
    """
    Initialize a new ty.toml in the specified directory.

    Args:
        directory: Directory to create config in (defaults to current directory)

    Returns:
        Path to created config file

    Raises:
        FileExistsError: If ty.toml already exists
    """
    if directory is None:
        directory = Path.cwd()
    else:
        directory = Path(directory)

    config_file = directory / CONFIG_FILENAME
    updates_file = directory / UPDATES_FILENAME

    if config_file.exists():
        raise FileExistsError(f"{CONFIG_FILENAME} already exists in {directory}")

    # Create ty.toml
    config_file.write_text(DEFAULT_CONFIG)

    # Create empty updates CSV
    if not updates_file.exists():
        updates_file.write_text("Date,Ticker,Open,High,Low,Close,Volume,Dividends,Splits\n")

    return config_file
