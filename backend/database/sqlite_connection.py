"""SQLite connection helper for enterprise persistence repositories."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_sqlite_connection(db_path: str) -> sqlite3.Connection:
    """Create a configured SQLite connection.

    Args:
        db_path: Location of the SQLite database file.

    Returns:
        A thread-shareable SQLite connection with row mapping enabled.
    """
    if db_path == ":memory:":
        connection = sqlite3.connect(db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    if db_path.startswith("file:"):
        connection = sqlite3.connect(db_path, check_same_thread=False, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    resolved = str(Path(db_path).resolve())
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection
