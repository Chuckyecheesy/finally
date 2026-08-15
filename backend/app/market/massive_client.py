"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource, normalize_ticker

logger = logging.getLogger(__name__)

# Massive trade/quote timestamps are Unix *nanoseconds* (JSON field `t`).
NS_PER_SECOND = 1e9

# The client's LastTrade model maps JSON `t` to `sip_timestamp` — there is no
# `.timestamp` attribute. The participant/TRF variants are checked as fallbacks
# because not every venue populates the SIP field.
_TIMESTAMP_ATTRS = ("sip_timestamp", "participant_timestamp", "trf_timestamp")

# Fallbacks when a snapshot has no last trade (pre-market, or a symbol that
# hasn't traded yet today), in preference order.
_PRICE_FALLBACKS = (("day", "close"), ("prev_day", "close"))


def _positive_number(value: Any) -> float | None:
    """Return value as a float if it's a usable positive number, else None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _extract_price(snap: Any) -> float | None:
    """Pull the current price out of a snapshot.

    Prefers the last trade price. A snapshot may be missing `last_trade`
    entirely (pre-market, or an obscure symbol with no trades yet today), so
    fall back to today's close and then the previous day's close.
    """
    last_trade = getattr(snap, "last_trade", None)
    if last_trade is not None:
        price = _positive_number(getattr(last_trade, "price", None))
        if price is not None:
            return price

    for holder_attr, price_attr in _PRICE_FALLBACKS:
        holder = getattr(snap, holder_attr, None)
        if holder is None:
            continue
        price = _positive_number(getattr(holder, price_attr, None))
        if price is not None:
            return price

    return None


def _extract_timestamp(snap: Any) -> float | None:
    """Pull the trade timestamp out of a snapshot, converted to Unix seconds.

    Returns None when no usable timestamp is present, which lets PriceCache
    stamp the update with the current time rather than discarding a good price.
    """
    last_trade = getattr(snap, "last_trade", None)
    if last_trade is None:
        return None

    for attr in _TIMESTAMP_ATTRS:
        nanoseconds = _positive_number(getattr(last_trade, attr, None))
        if nanoseconds is not None:
            return nanoseconds / NS_PER_SECOND

    return None


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min → poll every 15s (default)
      - Paid tiers: higher limits → poll every 2-5s

    A failed poll never falls back to the simulator (see planning/PLAN.md §5):
    it logs and retries on the next interval, leaving the cache stale.
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = [t for t in (normalize_ticker(t) for t in tickers) if t]

        # Do an immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(self._tickers),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = normalize_ticker(ticker)
        if ticker and ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = normalize_ticker(ticker)
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- Internal ---

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch snapshots, update cache."""
        if not self._tickers or not self._client:
            return

        try:
            # The Massive RESTClient is synchronous — run in a thread to
            # avoid blocking the event loop.
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
        except Exception as e:
            # Don't re-raise — the loop retries on the next interval.
            # Common failures: 401 (bad key), 429 (rate limit), network errors.
            logger.error("Massive poll failed: %s", e)
            return

        processed = 0
        for snap in snapshots or []:
            ticker = normalize_ticker(getattr(snap, "ticker", "") or "")
            if not ticker:
                logger.warning("Skipping snapshot with no ticker symbol")
                continue

            price = _extract_price(snap)
            if price is None:
                # An unknown/delisted symbol, or one that hasn't traded today,
                # comes back without usable price data. Leave it stale.
                logger.warning("Skipping snapshot for %s: no usable price", ticker)
                continue

            self._cache.update(
                ticker=ticker,
                price=price,
                timestamp=_extract_timestamp(snap),
            )
            processed += 1

        logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API. Runs in a thread."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
