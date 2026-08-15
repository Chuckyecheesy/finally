"""Tests for MassiveDataSource (mocked).

Snapshots here are plain classes, deliberately NOT MagicMock. A MagicMock
fabricates any attribute you ask it for, which is precisely how the
`last_trade.timestamp` bug survived the original test suite: the code read an
attribute the real `massive` model does not have, and the mock happily
answered. Plain objects raise/miss on a wrong attribute name, so these tests
actually pin the field contract described in planning/MASSIVE_API.md.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.market.cache import PriceCache
from app.market.massive_client import (
    MassiveDataSource,
    _extract_price,
    _extract_timestamp,
)

# 2024-02-10 16:00:00 UTC, expressed the way Massive sends it: Unix nanoseconds.
TRADE_TS_SECONDS = 1707580800.0
TRADE_TS_NANOS = 1_707_580_800_000_000_000


class FakeLastTrade:
    """Mirrors massive.rest.models.trades.LastTrade.

    Note the JSON field `t` is exposed as `sip_timestamp`; there is no
    `.timestamp` attribute on the real model.
    """

    def __init__(self, price=None, sip_timestamp=None, **extra):
        self.price = price
        self.sip_timestamp = sip_timestamp
        for key, value in extra.items():
            setattr(self, key, value)


class FakeBar:
    """Mirrors a snapshot's day / prev_day OHLC bar."""

    def __init__(self, close=None):
        self.close = close


class FakeSnapshot:
    """Mirrors a single entry of the full-market snapshot response."""

    def __init__(self, ticker=None, last_trade=None, day=None, prev_day=None):
        self.ticker = ticker
        self.last_trade = last_trade
        self.day = day
        self.prev_day = prev_day


def _snapshot(ticker: str, price: float, ts_nanos: int = TRADE_TS_NANOS) -> FakeSnapshot:
    return FakeSnapshot(
        ticker=ticker,
        last_trade=FakeLastTrade(price=price, sip_timestamp=ts_nanos),
    )


def _source(cache: PriceCache, tickers: list[str] | None = None) -> MassiveDataSource:
    """A source wired up as if start() had run, minus the real REST client."""
    source = MassiveDataSource(
        api_key="test-key",
        price_cache=cache,
        poll_interval=60.0,  # Long interval so the loop never auto-polls
    )
    if tickers is not None:
        source._tickers = list(tickers)
        source._client = MagicMock()  # Satisfy the _poll_once guard
    return source


class TestPriceExtraction:
    """Unit tests for _extract_price."""

    def test_prefers_last_trade_price(self):
        snap = FakeSnapshot(
            ticker="AAPL",
            last_trade=FakeLastTrade(price=190.50, sip_timestamp=TRADE_TS_NANOS),
            day=FakeBar(close=185.00),
        )
        assert _extract_price(snap) == 190.50

    def test_falls_back_to_day_close(self):
        """A symbol with no trade yet today still has a usable price."""
        snap = FakeSnapshot(ticker="AAPL", last_trade=None, day=FakeBar(close=185.00))
        assert _extract_price(snap) == 185.00

    def test_falls_back_to_prev_day_close(self):
        """Pre-market: no trade and no day bar, but a previous close exists."""
        snap = FakeSnapshot(
            ticker="AAPL",
            last_trade=None,
            day=FakeBar(close=None),
            prev_day=FakeBar(close=182.25),
        )
        assert _extract_price(snap) == 182.25

    def test_returns_none_when_no_price_anywhere(self):
        assert _extract_price(FakeSnapshot(ticker="AAPL")) is None

    def test_rejects_zero_and_negative_prices(self):
        snap = FakeSnapshot(ticker="AAPL", last_trade=FakeLastTrade(price=0.0))
        assert _extract_price(snap) is None
        snap = FakeSnapshot(ticker="AAPL", last_trade=FakeLastTrade(price=-5.0))
        assert _extract_price(snap) is None

    def test_zero_last_trade_price_falls_through_to_day(self):
        snap = FakeSnapshot(
            ticker="AAPL",
            last_trade=FakeLastTrade(price=0.0),
            day=FakeBar(close=185.00),
        )
        assert _extract_price(snap) == 185.00


class TestTimestampExtraction:
    """Unit tests for _extract_timestamp — the regression surface for the bug."""

    def test_reads_sip_timestamp_in_nanoseconds(self):
        snap = _snapshot("AAPL", 190.50)
        assert _extract_timestamp(snap) == TRADE_TS_SECONDS

    def test_ignores_nonexistent_timestamp_attribute(self):
        """The real model has no `.timestamp`; nothing should depend on it."""
        assert not hasattr(FakeLastTrade(), "timestamp")

    def test_falls_back_to_participant_timestamp(self):
        snap = FakeSnapshot(
            ticker="AAPL",
            last_trade=FakeLastTrade(
                price=190.50,
                sip_timestamp=None,
                participant_timestamp=TRADE_TS_NANOS,
            ),
        )
        assert _extract_timestamp(snap) == TRADE_TS_SECONDS

    def test_returns_none_without_last_trade(self):
        assert _extract_timestamp(FakeSnapshot(ticker="AAPL")) is None

    def test_returns_none_without_any_timestamp(self):
        snap = FakeSnapshot(ticker="AAPL", last_trade=FakeLastTrade(price=190.50))
        assert _extract_timestamp(snap) is None


@pytest.mark.asyncio
class TestMassiveDataSource:
    """Unit tests for MassiveDataSource with mocked API."""

    async def test_poll_updates_cache(self):
        """Test that polling updates the cache."""
        cache = PriceCache()
        source = _source(cache, ["AAPL", "GOOGL"])

        mock_snapshots = [_snapshot("AAPL", 190.50), _snapshot("GOOGL", 175.25)]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_timestamp_converted_from_nanoseconds(self):
        """Massive sends Unix nanoseconds; the cache stores Unix seconds.

        Regression test: the client previously read `last_trade.timestamp`
        (nonexistent) and divided by 1000 (wrong unit), so no real snapshot
        ever reached the cache.
        """
        cache = PriceCache()
        source = _source(cache, ["AAPL"])

        with patch.object(source, "_fetch_snapshots", return_value=[_snapshot("AAPL", 190.50)]):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        assert update.timestamp == TRADE_TS_SECONDS

    async def test_missing_timestamp_still_caches_price(self):
        """A good price is never discarded just because the timestamp is absent."""
        cache = PriceCache()
        source = _source(cache, ["AAPL"])
        snap = FakeSnapshot(ticker="AAPL", last_trade=FakeLastTrade(price=190.50))

        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        assert update.price == 190.50
        assert update.timestamp > 0  # Stamped with wall-clock time instead

    async def test_snapshot_without_trade_uses_prev_close(self):
        """Pre-market snapshots have no last trade but do have a prior close."""
        cache = PriceCache()
        source = _source(cache, ["AAPL"])
        snap = FakeSnapshot(ticker="AAPL", last_trade=None, prev_day=FakeBar(close=182.25))

        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 182.25

    async def test_malformed_snapshot_skipped(self):
        """Test that malformed snapshots are skipped gracefully."""
        cache = PriceCache()
        source = _source(cache, ["AAPL", "BAD"])

        good_snap = _snapshot("AAPL", 190.50)
        bad_snap = FakeSnapshot(ticker="BAD", last_trade=None)  # No price anywhere

        with patch.object(source, "_fetch_snapshots", return_value=[good_snap, bad_snap]):
            await source._poll_once()

        # Good ticker processed, bad one skipped
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None

    async def test_snapshot_without_ticker_skipped(self):
        """A snapshot with no symbol can't be keyed into the cache."""
        cache = PriceCache()
        source = _source(cache, ["AAPL"])
        snap = FakeSnapshot(ticker=None, last_trade=FakeLastTrade(price=190.50))

        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        assert len(cache) == 0

    async def test_snapshot_ticker_is_normalized(self):
        """Cache keys are uppercase regardless of what the API returns."""
        cache = PriceCache()
        source = _source(cache, ["AAPL"])
        snap = FakeSnapshot(ticker=" aapl ", last_trade=FakeLastTrade(price=190.50))

        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50

    async def test_api_error_does_not_crash(self):
        """Test that API errors don't crash the poller."""
        cache = PriceCache()
        source = _source(cache, ["AAPL"])

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()  # Should not raise

        assert cache.get_price("AAPL") is None  # No update happened

    async def test_stale_cache_survives_failed_poll(self):
        """Per PLAN.md §5: a failed poll leaves prices stale, never falls back."""
        cache = PriceCache()
        source = _source(cache, ["AAPL"])

        with patch.object(source, "_fetch_snapshots", return_value=[_snapshot("AAPL", 190.50)]):
            await source._poll_once()
        with patch.object(source, "_fetch_snapshots", side_effect=Exception("429 rate limit")):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50  # Stale, but intact

    async def test_empty_response_is_handled(self):
        """An unknown symbol is simply absent from the response array."""
        cache = PriceCache()
        source = _source(cache, ["NOPE"])

        with patch.object(source, "_fetch_snapshots", return_value=[]):
            await source._poll_once()

        assert len(cache) == 0

    async def test_add_ticker(self):
        """Test adding a ticker."""
        cache = PriceCache()
        source = _source(cache)

        await source.add_ticker("AAPL")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_uppercase_normalization(self):
        """Test that tickers are normalized to uppercase."""
        cache = PriceCache()
        source = _source(cache)

        await source.add_ticker("aapl")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_strips_whitespace(self):
        """Test that ticker whitespace is stripped."""
        cache = PriceCache()
        source = _source(cache)

        await source.add_ticker("  AAPL  ")
        assert "AAPL" in source.get_tickers()

    async def test_add_duplicate_ticker_is_noop(self):
        cache = PriceCache()
        source = _source(cache)

        await source.add_ticker("AAPL")
        await source.add_ticker("aapl")
        assert source.get_tickers() == ["AAPL"]

    async def test_add_blank_ticker_is_ignored(self):
        cache = PriceCache()
        source = _source(cache)

        await source.add_ticker("   ")
        assert source.get_tickers() == []

    async def test_remove_ticker(self):
        """Test removing a ticker."""
        cache = PriceCache()
        source = _source(cache, ["AAPL", "GOOGL"])
        cache.update("AAPL", 190.00)

        await source.remove_ticker("AAPL")
        assert "AAPL" not in source.get_tickers()
        assert cache.get("AAPL") is None

    async def test_remove_ticker_normalizes(self):
        cache = PriceCache()
        source = _source(cache, ["AAPL"])
        cache.update("AAPL", 190.00)

        await source.remove_ticker("aapl")
        assert source.get_tickers() == []
        assert cache.get("AAPL") is None

    async def test_get_tickers(self):
        """Test getting the list of active tickers."""
        cache = PriceCache()
        source = _source(cache, ["AAPL", "GOOGL"])

        assert source.get_tickers() == ["AAPL", "GOOGL"]

    async def test_empty_tickers_skips_poll(self):
        """Test that polling is skipped when there are no tickers."""
        cache = PriceCache()
        source = _source(cache)
        source._tickers = []

        # Should not call _fetch_snapshots
        with patch.object(source, "_fetch_snapshots") as mock_fetch:
            await source._poll_once()
            mock_fetch.assert_not_called()

    async def test_stop_is_idempotent(self):
        """Test that stop() can be called multiple times."""
        cache = PriceCache()
        source = _source(cache)

        await source.stop()
        await source.stop()  # Should not raise

    async def test_stop_cancels_task(self):
        """Test that stop() cancels the polling task."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=10.0)

        # Mock the client and start
        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[]):
                await source.start(["AAPL"])

        # Verify task is running
        assert source._task is not None
        assert not source._task.done()

        # Stop and verify task is cancelled
        await source.stop()
        assert source._task is None

    async def test_start_immediate_poll(self):
        """Test that start() does an immediate poll before starting the loop."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[_snapshot("AAPL", 190.50)]):
                await source.start(["AAPL"])

        # Cache should have data immediately from the first poll
        assert cache.get_price("AAPL") == 190.50

        await source.stop()

    async def test_start_normalizes_tickers(self):
        """Tickers passed to start() are normalized before the first poll."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[]):
                await source.start([" aapl ", "googl", "  "])

        assert source.get_tickers() == ["AAPL", "GOOGL"]

        await source.stop()
