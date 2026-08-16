"""FastAPI application entrypoint.

Startup is strictly sequential (PLAN.md §7): initialize and seed the database,
then start the market data source, then start the snapshot task. Everything
downstream can therefore assume the schema, the seed rows, and the price cache
already exist.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (
    build_portfolio,
    create_health_router,
    create_portfolio_router,
    create_watchlist_router,
    register_exception_handlers,
)
from app.db import DEFAULT_USER_ID, init_db, list_watchlist, record_snapshot
from app.market import (
    MarketDataSource,
    PriceCache,
    create_market_data_source,
    create_stream_router,
)

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30.0
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _record_snapshot(price_cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> None:
    record_snapshot(total_value=build_portfolio(price_cache, user_id).total_value, user_id=user_id)


async def _snapshot_loop(
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
    interval: float = SNAPSHOT_INTERVAL_SECONDS,
) -> None:
    """Record portfolio value every `interval` seconds until cancelled.

    A failed snapshot is logged and skipped rather than killing the task — the
    P&L chart losing one point matters far less than it losing every later one.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(_record_snapshot, price_cache, user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to record portfolio snapshot")


def create_app(user_id: str = DEFAULT_USER_ID) -> FastAPI:
    price_cache = PriceCache()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(user_id)

        market_source = create_market_data_source(price_cache)
        await market_source.start([entry.ticker for entry in list_watchlist(user_id)])
        app.state.market_source = market_source

        # One snapshot at startup so the P&L chart has a point immediately
        # instead of an empty chart for the first 30 seconds (PLAN.md §7).
        _record_snapshot(price_cache, user_id)
        snapshot_task = asyncio.create_task(_snapshot_loop(price_cache, user_id))
        app.state.snapshot_task = snapshot_task

        try:
            yield
        finally:
            snapshot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await snapshot_task
            await market_source.stop()

    app = FastAPI(title="FinAlly", description="AI Trading Workstation", lifespan=lifespan)
    app.state.price_cache = price_cache
    app.state.market_source = None

    register_exception_handlers(app)

    app.include_router(create_health_router())
    app.include_router(create_portfolio_router(user_id))
    app.include_router(create_watchlist_router(user_id))
    app.include_router(create_stream_router(price_cache))
    _include_chat_router(app, price_cache)

    # Mounted last so it never shadows an /api route. Absent in dev until the
    # Docker build drops the Next.js export here.
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    else:
        logger.warning("Static directory %s not found — serving API only", STATIC_DIR)

    return app


class _DeferredMarketSource(MarketDataSource):
    """Forwards to `app.state.market_source`, which only exists once startup runs.

    Routers are built before the lifespan creates the real source, and the chat
    router captures its source at construction time — so it gets this instead.
    Without the indirection it would capture `None` and the LLM's watchlist
    changes would never reach the simulator.
    """

    def __init__(self, app: FastAPI) -> None:
        self._app = app

    @property
    def _source(self) -> MarketDataSource:
        source = self._app.state.market_source
        if source is None:
            raise RuntimeError("Market data source is not started yet")
        return source

    async def start(self, tickers: list[str]) -> None:
        await self._source.start(tickers)

    async def stop(self) -> None:
        await self._source.stop()

    async def add_ticker(self, ticker: str) -> None:
        await self._source.add_ticker(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        await self._source.remove_ticker(ticker)

    def get_tickers(self) -> list[str]:
        return self._source.get_tickers()


def _include_chat_router(app: FastAPI, price_cache: PriceCache) -> None:
    """Mount POST /api/chat if the LLM subsystem is present.

    It is built in parallel with this module; without it the rest of the API
    still runs, which keeps dev and tests unblocked. Arguments are matched
    against the factory's actual signature so the two can land independently.
    """
    try:
        from app.llm.router import create_chat_router
    except ImportError:
        logger.warning("app.llm.router unavailable — /api/chat is not mounted")
        return

    available = {"price_cache": price_cache, "market_source": _DeferredMarketSource(app)}
    parameters = inspect.signature(create_chat_router).parameters
    app.include_router(create_chat_router(**{k: v for k, v in available.items() if k in parameters}))


app = create_app()
