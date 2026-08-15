"""Integration tests for SimulatorDataSource."""

import asyncio

import pytest

from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


@pytest.mark.asyncio
class TestSimulatorDataSource:
    """Integration tests for the SimulatorDataSource."""

    async def test_start_populates_cache(self):
        """Test that start() immediately populates the cache."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        # Cache should have seed prices immediately (before first loop tick)
        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None

        await source.stop()

    async def test_prices_update_over_time(self):
        """Test that prices are updated periodically."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])

        initial_version = cache.version
        await asyncio.sleep(0.3)  # Several update cycles

        # Version should have incremented (prices updated)
        assert cache.version > initial_version

        await source.stop()

    async def test_stop_is_clean(self):
        """Test that stop() is clean and idempotent."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])
        await source.stop()
        # Double stop should not raise
        await source.stop()

    async def test_add_ticker(self):
        """Test adding a ticker dynamically."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])

        await source.add_ticker("TSLA")
        assert "TSLA" in source.get_tickers()
        assert cache.get("TSLA") is not None

        await source.stop()

    async def test_remove_ticker(self):
        """Test removing a ticker."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "TSLA"])

        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()
        assert cache.get("TSLA") is None

        await source.stop()

    async def test_get_tickers(self):
        """Test getting the list of active tickers."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        tickers = source.get_tickers()
        assert set(tickers) == {"AAPL", "GOOGL"}

        await source.stop()

    async def test_empty_start(self):
        """Test starting with no tickers."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start([])

        assert len(cache) == 0
        assert source.get_tickers() == []

        await source.stop()

    async def test_exception_resilience(self):
        """Test that simulator continues running after errors."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)

        # Start with a valid ticker
        await source.start(["AAPL"])

        # Wait for some updates
        await asyncio.sleep(0.15)

        # Task should still be running
        assert source._task is not None
        assert not source._task.done()

        await source.stop()

    async def test_custom_update_interval(self):
        """Test using a custom update interval."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.01)
        await source.start(["AAPL"])

        initial_version = cache.version
        await asyncio.sleep(0.05)  # Should get ~5 updates

        # Should have multiple updates with fast interval
        assert cache.version > initial_version + 2

        await source.stop()

    async def test_add_ticker_is_normalized(self):
        """Tickers are uppercased/stripped so cache keys match the Massive source."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])

        await source.add_ticker("  tsla  ")
        assert source.get_tickers() == ["AAPL", "TSLA"]
        assert cache.get("TSLA") is not None
        assert cache.get("tsla") is None

        await source.stop()

    async def test_start_normalizes_tickers(self):
        """A lowercase seed list still produces canonical cache keys."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start([" aapl ", "googl"])

        assert set(source.get_tickers()) == {"AAPL", "GOOGL"}
        assert cache.get("AAPL") is not None

        await source.stop()

    async def test_start_skips_blank_tickers(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "   ", ""])

        assert source.get_tickers() == ["AAPL"]

        await source.stop()

    async def test_remove_ticker_is_normalized(self):
        """Removing with different casing still finds the tracked ticker."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "TSLA"])

        await source.remove_ticker("tsla")
        assert source.get_tickers() == ["AAPL"]
        assert cache.get("TSLA") is None

        await source.stop()

    async def test_add_blank_ticker_is_ignored(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])

        await source.add_ticker("   ")
        assert source.get_tickers() == ["AAPL"]

        await source.stop()

    async def test_unknown_ticker_gets_simulated_price(self):
        """PLAN.md §6: any symbol can be watched; the simulator fabricates a path."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.01)
        await source.start(["AAPL"])

        await source.add_ticker("ZZZZ")
        price = cache.get_price("ZZZZ")
        assert price is not None
        assert 50.0 <= price <= 300.0

        await asyncio.sleep(0.05)
        assert cache.get_price("ZZZZ") is not None  # Keeps ticking

        await source.stop()

    async def test_custom_event_probability(self):
        """Test creating source with custom event probability."""
        cache = PriceCache()
        # Very high event probability for testing
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1, event_probability=1.0)
        await source.start(["AAPL"])

        # Just verify it starts and stops cleanly
        await asyncio.sleep(0.2)
        await source.stop()
