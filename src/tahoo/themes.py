"""
themes.py - Rich-based table theming for Tahoo CLI

Provides configurable visual themes using Rich library with zebra striping
and financial data awareness. Compatible with edgar-pipes theme system.
"""

import os
import sys
from typing import Any
from io import StringIO

from rich.console import Console
from rich.table import Table


def should_use_color() -> bool:
    """Determine if color output should be used."""
    # Don't use color if output is redirected
    if not sys.stdout.isatty():
        return False

    # Respect NO_COLOR environment variable
    if os.environ.get('NO_COLOR'):
        return False

    # Check for explicit color preference
    force_color = os.environ.get('FORCE_COLOR')
    if force_color:
        return True

    # Default: use color in interactive terminals
    return True


class BaseTheme:
    """Base theme class for Rich table formatting."""

    def __init__(self):
        self.use_color = should_use_color()
        self.console = Console(force_terminal=self.use_color)

    @property
    def show_header(self) -> bool:
        return True

    @property
    def show_lines(self) -> bool:
        return False

    @property
    def show_edge(self) -> bool:
        return True

    @property
    def padding(self) -> tuple[int, int]:
        return (0, 1)  # (vertical, horizontal)

    @property
    def header_style(self) -> str:
        return "bold"

    @property
    def row_styles(self) -> list[str]:
        return ["", ""]  # No zebra striping by default

    @property
    def box_style(self) -> str | None:
        """Box style for Rich table. None removes all borders."""
        return "default"

    def get_column_style(self, column_name: str) -> str:
        """Get Rich style string for a column."""
        return ""


class MinimalDarkTheme(BaseTheme):
    """Clean minimal theme for dark terminals (edgar-pipes default)."""

    @property
    def header_style(self) -> str:
        return "bold bright_white"

    @property
    def row_styles(self) -> list[str]:
        return ["", "dim"]

    def get_column_style(self, column_name: str) -> str:
        if column_name.lower() in ['ticker', 'symbol']:
            return 'bold bright_white'
        return ''


class NoBoxMinimalDarkTheme(MinimalDarkTheme):
    """Minimal dark theme with no borders (edgar-pipes default)."""

    @property
    def box_style(self) -> str | None:
        return None


class FinancialDarkTheme(BaseTheme):
    """Financial data theme for dark terminals."""

    @property
    def header_style(self) -> str:
        return "bold bright_cyan"

    @property
    def row_styles(self) -> list[str]:
        return ["", "on grey15"]  # Zebra striping

    def get_column_style(self, column_name: str) -> str:
        name_lower = column_name.lower()
        if name_lower in ['ticker', 'symbol']:
            return 'bold bright_blue'
        elif 'date' in name_lower:
            return 'bright_green'
        elif 'change' in name_lower and '%' in column_name:
            return 'yellow'
        return ''


class NoBoxFinancialDarkTheme(FinancialDarkTheme):
    """Financial dark theme with no borders."""

    @property
    def box_style(self) -> str | None:
        return None


# Theme registry
THEMES = {
    "default": NoBoxMinimalDarkTheme,
    "minimal": MinimalDarkTheme,
    "minimal-dark": MinimalDarkTheme,
    "nobox": NoBoxFinancialDarkTheme,
    "nobox-minimal": NoBoxMinimalDarkTheme,
    "nobox-minimal-dark": NoBoxMinimalDarkTheme,
    "financial": FinancialDarkTheme,
    "financial-dark": FinancialDarkTheme,
    "nobox-dark": NoBoxFinancialDarkTheme,
}


def get_theme(theme_name: str = "default") -> BaseTheme:
    """Get theme instance by name."""
    theme_class = THEMES.get(theme_name, NoBoxMinimalDarkTheme)
    return theme_class()


def get_default_theme() -> str:
    """
    Get default theme name with precedence:
    1. Environment variable TAHOO_THEME (highest)
    2. Built-in default: 'nobox-minimal-dark' (lowest)
    """
    env_theme = os.environ.get('TAHOO_THEME')
    if env_theme:
        return env_theme

    return 'nobox-minimal-dark'


def themed_table(
    title: str,
    data: list[dict],
    headers: list[str],
    theme_name: str | None = None
) -> Table:
    """Generate themed table using Rich."""
    if theme_name is None:
        theme_name = get_default_theme()

    theme = get_theme(theme_name)

    # Create Rich table with theme-specific box style
    table_kwargs = {
        "title": title,
        "show_header": theme.show_header,
        "header_style": theme.header_style,
        "show_lines": theme.show_lines,
        "show_edge": theme.show_edge,
        "padding": theme.padding,
        "row_styles": theme.row_styles
    }

    # Add box parameter if theme specifies it
    if hasattr(theme, 'box_style'):
        if theme.box_style is not None and theme.box_style != "default":
            table_kwargs["box"] = theme.box_style
        elif theme.box_style is None:
            table_kwargs["box"] = None  # Remove all borders

    table = Table(**table_kwargs)

    # Add columns with appropriate styling
    for header in headers:
        column_style = theme.get_column_style(header)
        justify = "right" if header != "Ticker" else "left"
        table.add_column(header, style=column_style, justify=justify)

    # Add rows
    for row_data in data:
        table.add_row(*row_data)

    return table
