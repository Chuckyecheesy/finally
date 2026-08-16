"""Watchlist endpoints.

Every mutation keeps two things in sync: the `watchlist` table and the market
data source's tracked ticker set, which per PLAN.md §6 is exactly the watchlist.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.db import DEFAULT_USER_ID, add_to_watchlist, list_watchlist, remove_from_watchlist
from app.market import MarketDataSource, PriceCache, normalize_ticker

from .deps import get_market_source, get_price_cache
from .schemas import WatchlistAddRequest, WatchlistItemOut


def _item(ticker: str, added_at: str, price_cache: PriceCache) -> WatchlistItemOut:
    update = price_cache.get(ticker)
    if update is None:
        return WatchlistItemOut(ticker=ticker, added_at=added_at)
    return WatchlistItemOut(
        ticker=ticker,
        added_at=added_at,
        price=update.price,
        previous_price=update.previous_price,
        change=update.change,
        change_percent=update.change_percent,
        direction=update.direction,
        timestamp=update.timestamp,
    )


def create_watchlist_router(user_id: str = DEFAULT_USER_ID) -> APIRouter:
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

    @router.get("", response_model=list[WatchlistItemOut])
    async def get_watchlist(
        price_cache: PriceCache = Depends(get_price_cache),
    ) -> list[WatchlistItemOut]:
        """Watched tickers with their latest cached price, oldest addition first."""
        return [_item(e.ticker, e.added_at, price_cache) for e in list_watchlist(user_id)]

    @router.post("", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
    async def post_watchlist(
        body: WatchlistAddRequest,
        price_cache: PriceCache = Depends(get_price_cache),
        market_source: MarketDataSource = Depends(get_market_source),
    ) -> WatchlistItemOut:
        """Add a ticker and start tracking it. 409 if already watched."""
        entry = add_to_watchlist(body.ticker, user_id=user_id)
        await market_source.add_ticker(entry.ticker)
        return _item(entry.ticker, entry.added_at, price_cache)

    @router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_watchlist(
        ticker: str,
        market_source: MarketDataSource = Depends(get_market_source),
    ) -> Response:
        """Remove a ticker and stop tracking it. 404 if not watched."""
        remove_from_watchlist(ticker, user_id=user_id)
        await market_source.remove_ticker(normalize_ticker(ticker))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
