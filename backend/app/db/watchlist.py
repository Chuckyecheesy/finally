"""Watchlist reads and writes.

Tickers are normalized with the same `normalize_ticker` the market data
sources use, so a watchlist row and its price-cache key are always the same
string no matter how the user typed it.
"""

from __future__ import annotations

import sqlite3
import uuid

from app.market.interface import normalize_ticker

from .connection import use_connection
from .errors import DuplicateTickerError, InvalidTickerError, TickerNotFoundError
from .models import DEFAULT_USER_ID, WatchlistEntry, utc_now_iso


def _row_to_entry(row: sqlite3.Row) -> WatchlistEntry:
    return WatchlistEntry(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        added_at=row["added_at"],
    )


def _require_ticker(ticker: str) -> str:
    normalized = normalize_ticker(ticker)
    if not normalized:
        raise InvalidTickerError("Ticker symbol must not be blank")
    return normalized


def list_watchlist(
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> list[WatchlistEntry]:
    """Watchlist entries for the user, oldest addition first."""
    with use_connection(conn) as db:
        rows = db.execute(
            "SELECT id, user_id, ticker, added_at FROM watchlist"
            " WHERE user_id = ? ORDER BY added_at, ticker",
            (user_id,),
        ).fetchall()
    return [_row_to_entry(row) for row in rows]


def is_watched(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Whether the ticker is currently on the user's watchlist."""
    normalized = normalize_ticker(ticker)
    if not normalized:
        return False
    with use_connection(conn) as db:
        row = db.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, normalized),
        ).fetchone()
    return row is not None


def add_to_watchlist(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> WatchlistEntry:
    """Add a ticker and return the created entry.

    Raises `DuplicateTickerError` if it is already watched, `InvalidTickerError`
    if the symbol is blank.
    """
    normalized = _require_ticker(ticker)
    entry = WatchlistEntry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=normalized,
        added_at=utc_now_iso(),
    )
    with use_connection(conn) as db:
        try:
            db.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (entry.id, entry.user_id, entry.ticker, entry.added_at),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTickerError(f"{normalized} is already on the watchlist") from exc
    return entry


def remove_from_watchlist(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Remove a ticker. Raises `TickerNotFoundError` if it isn't watched."""
    normalized = _require_ticker(ticker)
    with use_connection(conn) as db:
        cursor = db.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, normalized),
        )
        if cursor.rowcount == 0:
            raise TickerNotFoundError(f"{normalized} is not on the watchlist")
