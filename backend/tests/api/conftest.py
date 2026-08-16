"""Fixtures for API tests.

Routes are mounted onto a bare app with a hand-populated `PriceCache` and a
fake market source, so no simulator background loop runs and prices are
deterministic. `app/main.py`'s real lifespan is exercised separately in
`test_app.py`.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import (
    create_health_router,
    create_portfolio_router,
    create_watchlist_router,
    register_exception_handlers,
)
from app.db import init_db
from app.db.connection import DB_PATH_ENV
from app.market import MarketDataSource, PriceCache

SEEDED_PRICES = {"AAPL": 100.0, "MSFT": 200.0}


class FakeMarketSource(MarketDataSource):
    """Records lifecycle calls instead of producing prices."""

    def __init__(self, price_cache: PriceCache) -> None:
        self.price_cache = price_cache
        self.tickers: list[str] = []
        self.started = False
        self.stopped = False

    async def start(self, tickers: list[str]) -> None:
        self.tickers = list(tickers)
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def add_ticker(self, ticker: str) -> None:
        if ticker not in self.tickers:
            self.tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if ticker in self.tickers:
            self.tickers.remove(ticker)
        self.price_cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self.tickers)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh, seeded SQLite file for one test."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv(DB_PATH_ENV, str(path))
    init_db()
    return path


@pytest.fixture
def price_cache():
    cache = PriceCache()
    for ticker, price in SEEDED_PRICES.items():
        cache.update(ticker, price)
    return cache


@pytest.fixture
def market_source(price_cache):
    return FakeMarketSource(price_cache)


@pytest.fixture
def client(temp_db, price_cache, market_source):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(create_health_router())
    app.include_router(create_portfolio_router())
    app.include_router(create_watchlist_router())
    app.state.price_cache = price_cache
    app.state.market_source = market_source
    with TestClient(app) as test_client:
        yield test_client
