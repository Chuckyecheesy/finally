"""Portfolio value snapshots for the P&L chart (PLAN.md §7)."""

from __future__ import annotations

import sqlite3
import uuid

from .connection import use_connection
from .models import DEFAULT_USER_ID, PortfolioSnapshot, utc_now_iso


def _row_to_snapshot(row: sqlite3.Row) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        id=row["id"],
        user_id=row["user_id"],
        total_value=row["total_value"],
        recorded_at=row["recorded_at"],
    )


def record_snapshot(
    total_value: float,
    user_id: str = DEFAULT_USER_ID,
    recorded_at: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> PortfolioSnapshot:
    """Append a portfolio-value snapshot and return it.

    Written at startup, every 30 seconds by a background task, and immediately
    after each trade.
    """
    snapshot = PortfolioSnapshot(
        id=str(uuid.uuid4()),
        user_id=user_id,
        total_value=total_value,
        recorded_at=recorded_at or utc_now_iso(),
    )
    with use_connection(conn) as db:
        db.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)"
            " VALUES (?, ?, ?, ?)",
            (snapshot.id, snapshot.user_id, snapshot.total_value, snapshot.recorded_at),
        )
    return snapshot


def list_snapshots(
    user_id: str = DEFAULT_USER_ID,
    since: str | None = None,
    limit: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[PortfolioSnapshot]:
    """Snapshots ordered oldest to newest, ready to plot.

    `since` is an inclusive ISO-8601 lower bound on `recorded_at`. `limit`
    keeps the most *recent* N while preserving oldest-first ordering.
    """
    columns = "id, user_id, total_value, recorded_at"
    where = "WHERE user_id = ?"
    params: list[object] = [user_id]
    if since is not None:
        where += " AND recorded_at >= ?"
        params.append(since)

    with use_connection(conn) as db:
        if limit is None:
            rows = db.execute(
                f"SELECT {columns} FROM portfolio_snapshots {where}"
                " ORDER BY recorded_at, rowid",
                params,
            ).fetchall()
        else:
            rows = db.execute(
                f"SELECT * FROM (SELECT {columns}, rowid FROM portfolio_snapshots {where}"
                " ORDER BY recorded_at DESC, rowid DESC LIMIT ?) ORDER BY recorded_at, rowid",
                [*params, limit],
            ).fetchall()
    return [_row_to_snapshot(row) for row in rows]
