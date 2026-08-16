"""SQLite connection management.

The database file lives at the project-root `db/finally.db` (the Docker volume
mount point described in PLAN.md §4). Override with the `FINALLY_DB_PATH`
environment variable — tests point it at a temp file.

Connections are opened per operation rather than shared. SQLite handles this
cheaply, and it sidesteps every thread-affinity problem that would otherwise
arise from FastAPI request handlers and the market-data / snapshot background
tasks touching the database concurrently. WAL mode lets readers proceed while a
writer holds the write lock; `busy_timeout` makes concurrent writers wait
instead of raising "database is locked".
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DB_PATH_ENV = "FINALLY_DB_PATH"

# app/db/connection.py -> app/db -> app -> backend -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "finally.db"

BUSY_TIMEOUT_MS = 5000


def get_db_path() -> Path:
    """Resolved path of the SQLite file, honoring `FINALLY_DB_PATH`."""
    override = os.getenv(DB_PATH_ENV)
    return Path(override) if override else DEFAULT_DB_PATH


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a connection for one unit of work.

    Commits on clean exit, rolls back on exception, always closes. Rows come
    back as `sqlite3.Row` so callers can index by column name.
    """
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def use_connection(conn: sqlite3.Connection | None) -> Iterator[sqlite3.Connection]:
    """Reuse a caller-supplied connection, or open a fresh one.

    Every repository function accepts an optional `conn`. Passing one lets a
    caller group several writes into a single transaction — trade execution
    debits cash, upserts the position, and appends the trade row, and all three
    must land together or not at all. When `conn` is passed, committing is the
    caller's responsibility.
    """
    if conn is not None:
        yield conn
        return
    with get_connection() as owned:
        yield owned
