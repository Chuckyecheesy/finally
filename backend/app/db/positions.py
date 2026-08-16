"""Position reads.

Positions are only ever written by `execute_trade` in `app/db/portfolio.py`,
which owns the cash/position/trade-log invariant.
"""

from __future__ import annotations

import sqlite3

from app.market.interface import normalize_ticker

from .connection import use_connection
from .models import DEFAULT_USER_ID, Position

_POSITION_COLUMNS = "id, user_id, ticker, quantity, avg_cost, updated_at"


def row_to_position(row: sqlite3.Row) -> Position:
    return Position(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        quantity=row["quantity"],
        avg_cost=row["avg_cost"],
        updated_at=row["updated_at"],
    )


def list_positions(
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> list[Position]:
    """All open positions for the user, alphabetical by ticker."""
    with use_connection(conn) as db:
        rows = db.execute(
            f"SELECT {_POSITION_COLUMNS} FROM positions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
    return [row_to_position(row) for row in rows]


def get_position(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> Position | None:
    """The user's position in one ticker, or None if they hold none."""
    normalized = normalize_ticker(ticker)
    if not normalized:
        return None
    with use_connection(conn) as db:
        row = db.execute(
            f"SELECT {_POSITION_COLUMNS} FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, normalized),
        ).fetchone()
    return row_to_position(row) if row else None
