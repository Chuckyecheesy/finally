"""Auto-execution of the actions the model asked for (PLAN.md §9).

Execution is sequential, not atomic. Each trade is validated against the
account state *left by the previous one*, so trade 2 can fail on insufficient
cash because trade 1 spent it. Every action reports its own success or failure
and nothing is rolled back.

Trades go through `app.db.execute_trade` — the same function the REST trade
endpoint calls — so the manual and AI paths can never disagree about what a
valid order is.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from app.db import (
    DEFAULT_USER_ID,
    RepositoryError,
    add_to_watchlist,
    execute_trade,
    remove_from_watchlist,
)
from app.market import MarketDataSource, PriceCache, normalize_ticker

from .schemas import LLMStructuredResponse, TradeResult, WatchlistResult

logger = logging.getLogger(__name__)


def execute_trades(
    response: LLMStructuredResponse,
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
) -> list[TradeResult]:
    """Run each requested trade in array order, reporting per-trade outcomes."""
    results: list[TradeResult] = []
    for action in response.trades:
        ticker = normalize_ticker(action.ticker)
        price = price_cache.get_price(ticker)
        if price is None:
            results.append(
                TradeResult(
                    ticker=ticker,
                    side=action.side,
                    quantity=action.quantity,
                    status="failed",
                    error=f"No market price available for {ticker or action.ticker}",
                )
            )
            continue
        try:
            trade = execute_trade(ticker, action.side, action.quantity, price, user_id=user_id)
        except RepositoryError as exc:
            results.append(
                TradeResult(
                    ticker=ticker,
                    side=action.side,
                    quantity=action.quantity,
                    status="failed",
                    error=str(exc),
                )
            )
        else:
            results.append(
                TradeResult(
                    ticker=trade.ticker,
                    side=trade.side,
                    quantity=trade.quantity,
                    status="executed",
                    trade=asdict(trade),
                )
            )
    return results


async def execute_watchlist_changes(
    response: LLMStructuredResponse,
    market_source: MarketDataSource | None,
    user_id: str = DEFAULT_USER_ID,
) -> list[WatchlistResult]:
    """Apply watchlist changes and keep the market data source's tracked set in sync.

    The database write is authoritative: if it succeeds but the market source
    call fails, the change still counts as executed and the ticker simply has no
    price until the next restart re-seeds the source from the watchlist.
    """
    results: list[WatchlistResult] = []
    for change in response.watchlist_changes:
        ticker = normalize_ticker(change.ticker)
        try:
            if change.action == "add":
                add_to_watchlist(ticker, user_id=user_id)
            else:
                remove_from_watchlist(ticker, user_id=user_id)
        except RepositoryError as exc:
            results.append(
                WatchlistResult(
                    ticker=ticker, action=change.action, status="failed", error=str(exc)
                )
            )
            continue

        if market_source is not None:
            try:
                if change.action == "add":
                    await market_source.add_ticker(ticker)
                else:
                    await market_source.remove_ticker(ticker)
            except Exception:
                logger.exception("Failed to sync %s with the market data source", ticker)

        results.append(WatchlistResult(ticker=ticker, action=change.action, status="executed"))
    return results
