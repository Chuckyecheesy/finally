"""Portfolio context and conversation history assembly for the LLM prompt (PLAN.md §9).

Prices come from the shared `PriceCache`, never from a fresh market call — a
ticker with no cached price yet is reported as unknown rather than guessed at,
so the model never reasons about a fabricated number.
"""

from __future__ import annotations

from typing import Any

from app.db import (
    DEFAULT_USER_ID,
    get_profile,
    list_positions,
    list_recent_chat_messages,
    list_watchlist,
)
from app.market import PriceCache

HISTORY_LIMIT = 20


def collect_portfolio_state(
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """Cash, positions marked to market, watchlist prices, and total value."""
    cash = get_profile(user_id).cash_balance

    positions: list[dict[str, Any]] = []
    positions_value = 0.0
    for position in list_positions(user_id):
        price = price_cache.get_price(position.ticker)
        entry: dict[str, Any] = {
            "ticker": position.ticker,
            "quantity": position.quantity,
            "avg_cost": position.avg_cost,
            "current_price": price,
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_percent": None,
        }
        if price is not None:
            market_value = position.quantity * price
            cost_basis = position.quantity * position.avg_cost
            positions_value += market_value
            entry["market_value"] = market_value
            entry["unrealized_pnl"] = market_value - cost_basis
            if cost_basis:
                entry["unrealized_pnl_percent"] = (market_value - cost_basis) / cost_basis * 100
        positions.append(entry)

    watchlist = []
    for watched in list_watchlist(user_id):
        update = price_cache.get(watched.ticker)
        watchlist.append(
            {
                "ticker": watched.ticker,
                "price": update.price if update else None,
                "change_percent": update.change_percent if update else None,
            }
        )

    return {
        "cash_balance": cash,
        "positions": positions,
        "positions_value": positions_value,
        "total_value": cash + positions_value,
        "watchlist": watchlist,
    }


def build_portfolio_context(
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
) -> str:
    """Render the portfolio state as the plain-text block injected into the prompt."""
    state = collect_portfolio_state(price_cache, user_id)
    lines = [
        "CURRENT PORTFOLIO",
        f"Cash balance: ${state['cash_balance']:,.2f}",
        f"Positions value: ${state['positions_value']:,.2f}",
        f"Total portfolio value: ${state['total_value']:,.2f}",
        "",
        "POSITIONS",
    ]

    if not state["positions"]:
        lines.append("(none — the portfolio is all cash)")
    for position in state["positions"]:
        price = position["current_price"]
        if price is None:
            lines.append(
                f"{position['ticker']}: {position['quantity']:g} shares @ avg cost "
                f"${position['avg_cost']:,.2f} — no current price available"
            )
        else:
            lines.append(
                f"{position['ticker']}: {position['quantity']:g} shares @ avg cost "
                f"${position['avg_cost']:,.2f}, current ${price:,.2f}, "
                f"value ${position['market_value']:,.2f}, "
                f"unrealized P&L ${position['unrealized_pnl']:,.2f} "
                f"({position['unrealized_pnl_percent'] or 0.0:+.2f}%)"
            )

    lines += ["", "WATCHLIST"]
    if not state["watchlist"]:
        lines.append("(empty)")
    for watched in state["watchlist"]:
        if watched["price"] is None:
            lines.append(f"{watched['ticker']}: no price data yet")
        else:
            lines.append(
                f"{watched['ticker']}: ${watched['price']:,.2f} "
                f"({watched['change_percent']:+.2f}%)"
            )

    return "\n".join(lines)


def build_history_messages(
    user_id: str = DEFAULT_USER_ID,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, str]]:
    """Recent conversation as chat-completion role/content pairs, oldest first."""
    return [
        {"role": message.role, "content": message.content}
        for message in list_recent_chat_messages(user_id=user_id, limit=limit)
    ]
