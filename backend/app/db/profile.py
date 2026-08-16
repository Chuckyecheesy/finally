"""User profile reads and writes (cash balance)."""

from __future__ import annotations

import sqlite3

from .connection import use_connection
from .errors import ProfileNotFoundError
from .models import DEFAULT_USER_ID, UserProfile


def _row_to_profile(row: sqlite3.Row) -> UserProfile:
    return UserProfile(
        id=row["id"],
        cash_balance=row["cash_balance"],
        created_at=row["created_at"],
    )


def get_profile(
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> UserProfile:
    """Return the user's profile. Raises `ProfileNotFoundError` if absent."""
    with use_connection(conn) as db:
        row = db.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise ProfileNotFoundError(f"No profile for user '{user_id}'")
    return _row_to_profile(row)


def get_cash_balance(
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> float:
    """Convenience accessor for just the cash balance."""
    return get_profile(user_id, conn=conn).cash_balance


def update_cash_balance(
    user_id: str = DEFAULT_USER_ID,
    new_balance: float = 0.0,
    conn: sqlite3.Connection | None = None,
) -> UserProfile:
    """Set the cash balance to an absolute value and return the updated profile.

    Pass `conn` to fold this into a caller-owned transaction — `execute_trade`
    does exactly that so the debit and the position update commit together.
    """
    with use_connection(conn) as db:
        cursor = db.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_balance, user_id),
        )
        if cursor.rowcount == 0:
            raise ProfileNotFoundError(f"No profile for user '{user_id}'")
        return get_profile(user_id, conn=db)
