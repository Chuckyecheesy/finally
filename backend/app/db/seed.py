"""Default seed data (PLAN.md §7).

Seeding is per-table and conditional: an existing profile or a non-empty
watchlist is left alone, so a restart against a persisted volume never
resurrects tickers the user deliberately removed.
"""

from __future__ import annotations

import sqlite3
import uuid

from .models import DEFAULT_USER_ID, utc_now_iso

DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_WATCHLIST = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)


def seed_database(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> None:
    """Insert the default profile and watchlist if they aren't there yet."""
    now = utc_now_iso()

    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (user_id, DEFAULT_CASH_BALANCE, now),
    )

    (watchlist_count,) = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (user_id,)
    ).fetchone()
    if watchlist_count == 0:
        conn.executemany(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            [(str(uuid.uuid4()), user_id, ticker, now) for ticker in DEFAULT_WATCHLIST],
        )
