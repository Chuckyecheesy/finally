"""Accessors for the shared state the app puts on `app.state` at startup.

The price cache and market data source are created once in the lifespan and
read from `request.app.state`, so routers stay free of module globals and tests
can attach their own fakes.
"""

from __future__ import annotations

from fastapi import Request

from app.market import MarketDataSource, PriceCache


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache


def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
