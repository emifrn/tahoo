"""Database connection and management."""

import sqlite3
import pandas as pd
from pathlib import Path
from urllib.request import pathname2url


def connect(db_path: Path) -> sqlite3.Connection:
    """
    Create database connection and initialize schema.

    Args:
        db_path: Path to SQLite database file

    Returns:
        SQLite connection object
    """
    db_uri = f'file:{pathname2url(str(db_path))}?mode=rwc'
    conn = sqlite3.connect(db_uri, uri=True)
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection):
    """
    Initialize database schema.

    Args:
        conn: SQLite connection
    """
    cursor = conn.cursor()
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
    conn.commit()


def insert(conn: sqlite3.Connection, table: str, df: pd.DataFrame):
    """
    Insert DataFrame into database table.

    Args:
        conn: SQLite connection
        table: Table name
        df: DataFrame to insert
    """
    cols = ','.join(df.columns)
    vals = '?' + ',?' * (len(df.columns) - 1)
    sql = f'INSERT OR IGNORE INTO {table}({cols}) VALUES({vals})'
    cursor = conn.cursor()
    cursor.executemany(sql, df.itertuples(index=False, name=None))
    conn.commit()
