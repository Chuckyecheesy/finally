"""Trade execution — the single writer of cash, positions, and the trade log.

`execute_trade` is deliberately the *only* place trade validation lives. Both
the REST `POST /api/portfolio/trade` endpoint and the LLM's auto-executed
trades (PLAN.md §9) call it, so the two paths cannot drift apart on what
counts as a valid order.

Callers resolve `current_price` themselves, from the market price cache
(`PriceCache.get_price`). A `None` price means the ticker has no market data;
the caller raises `UnknownTickerError` (HTTP 404) rather than calling this.
"""

from __future__ import annotations

import sqlite3
import uuid

from app.market.interface import normalize_ticker

from .connection import use_connection
from .errors import InvalidTickerError, InvalidTradeError
from .models import DEFAULT_USER_ID, Trade, utc_now_iso
from .positions import get_position
from .profile import get_profile, update_cash_balance

BUY = "buy"
SELL = "sell"

# Floating-point slack for money and share comparisons. Without it, selling a
# position in two halves can leave a residue like 1e-16 shares behind, and
# "spend exactly all my cash" can fail by a fraction of a cent.
EPSILON = 1e-9


def execute_trade(
    ticker: str,
    side: str,
    quantity: float,
    current_price: float,
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> Trade:
    """Execute a market order at `current_price` and return the recorded trade.

    Cash movement, the position upsert, and the trade-log append happen in one
    transaction — either all three land or none do.

    Buys debit cash and blend the new shares into `avg_cost` as a
    quantity-weighted average. Sells credit cash, decrement the quantity, and
    leave `avg_cost` untouched (realized P&L is derived from the trade log, not
    stored); a position that reaches zero shares is deleted.

    Raises `InvalidTickerError` (HTTP 400) for a blank symbol and
    `InvalidTradeError` (HTTP 400) for an unknown side, a non-positive quantity
    or price, insufficient cash on a buy, or insufficient shares on a sell.
    """
    normalized = normalize_ticker(ticker)
    if not normalized:
        raise InvalidTickerError("Ticker symbol must not be blank")

    side = side.strip().lower()
    if side not in (BUY, SELL):
        raise InvalidTradeError(f"Unknown trade side '{side}' — expected 'buy' or 'sell'")

    if quantity <= 0:
        raise InvalidTradeError("Quantity must be greater than zero")

    if current_price <= 0:
        raise InvalidTradeError(f"No valid market price available for {normalized}")

    notional = quantity * current_price

    with use_connection(conn) as db:
        profile = get_profile(user_id, conn=db)
        position = get_position(normalized, user_id=user_id, conn=db)
        now = utc_now_iso()

        if side == BUY:
            if profile.cash_balance + EPSILON < notional:
                raise InvalidTradeError(
                    f"Insufficient cash: {notional:.2f} required, "
                    f"{profile.cash_balance:.2f} available"
                )
            update_cash_balance(user_id, profile.cash_balance - notional, conn=db)

            if position is None:
                db.execute(
                    "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), user_id, normalized, quantity, current_price, now),
                )
            else:
                new_quantity = position.quantity + quantity
                new_avg_cost = (
                    position.quantity * position.avg_cost + notional
                ) / new_quantity
                db.execute(
                    "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ?"
                    " WHERE id = ?",
                    (new_quantity, new_avg_cost, now, position.id),
                )
        else:
            held = position.quantity if position else 0.0
            if quantity > held + EPSILON:
                raise InvalidTradeError(
                    f"Insufficient shares: {quantity} requested, {held} held in {normalized}"
                )
            update_cash_balance(user_id, profile.cash_balance + notional, conn=db)

            remaining = held - quantity
            if remaining <= EPSILON:
                db.execute("DELETE FROM positions WHERE id = ?", (position.id,))
            else:
                db.execute(
                    "UPDATE positions SET quantity = ?, updated_at = ? WHERE id = ?",
                    (remaining, now, position.id),
                )

        trade = Trade(
            id=str(uuid.uuid4()),
            user_id=user_id,
            ticker=normalized,
            side=side,
            quantity=quantity,
            price=current_price,
            executed_at=now,
        )
        db.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                trade.id,
                trade.user_id,
                trade.ticker,
                trade.side,
                trade.quantity,
                trade.price,
                trade.executed_at,
            ),
        )

    return trade


def list_trades(
    user_id: str = DEFAULT_USER_ID,
    limit: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[Trade]:
    """Trade history, oldest first. `limit` keeps the most *recent* N trades."""
    with use_connection(conn) as db:
        if limit is None:
            rows = db.execute(
                "SELECT id, user_id, ticker, side, quantity, price, executed_at FROM trades"
                " WHERE user_id = ? ORDER BY executed_at, rowid",
                (user_id,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM ("
                "  SELECT id, user_id, ticker, side, quantity, price, executed_at, rowid"
                "  FROM trades WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC LIMIT ?"
                ") ORDER BY executed_at, rowid",
                (user_id, limit),
            ).fetchall()
    return [
        Trade(
            id=row["id"],
            user_id=row["user_id"],
            ticker=row["ticker"],
            side=row["side"],
            quantity=row["quantity"],
            price=row["price"],
            executed_at=row["executed_at"],
        )
        for row in rows
    ]
