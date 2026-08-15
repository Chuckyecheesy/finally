"""Tests for PriceCache."""

import threading
import time

from app.market.cache import PriceCache


class TestPriceCache:
    """Unit tests for the PriceCache."""

    def test_update_and_get(self):
        """Test updating and getting a price."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert cache.get("AAPL") == update

    def test_first_update_is_flat(self):
        """Test that the first update has flat direction."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.direction == "flat"
        assert update.previous_price == 190.50

    def test_direction_up(self):
        """Test price update with upward direction."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 191.00)
        assert update.direction == "up"
        assert update.change == 1.00

    def test_direction_down(self):
        """Test price update with downward direction."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 189.00)
        assert update.direction == "down"
        assert update.change == -1.00

    def test_remove(self):
        """Test removing a ticker from cache."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None

    def test_remove_nonexistent(self):
        """Test removing a ticker that doesn't exist."""
        cache = PriceCache()
        cache.remove("AAPL")  # Should not raise

    def test_get_all(self):
        """Test getting all prices."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        all_prices = cache.get_all()
        assert set(all_prices.keys()) == {"AAPL", "GOOGL"}

    def test_version_increments(self):
        """Test that version counter increments."""
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        assert cache.version == v0 + 1
        cache.update("AAPL", 191.00)
        assert cache.version == v0 + 2

    def test_get_price_convenience(self):
        """Test the convenience get_price method."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("NOPE") is None

    def test_len(self):
        """Test __len__ method."""
        cache = PriceCache()
        assert len(cache) == 0
        cache.update("AAPL", 190.00)
        assert len(cache) == 1
        cache.update("GOOGL", 175.00)
        assert len(cache) == 2

    def test_contains(self):
        """Test __contains__ method."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        assert "AAPL" in cache
        assert "GOOGL" not in cache

    def test_custom_timestamp(self):
        """Test updating with a custom timestamp."""
        cache = PriceCache()
        custom_ts = 1234567890.0
        update = cache.update("AAPL", 190.50, timestamp=custom_ts)
        assert update.timestamp == custom_ts

    def test_price_rounding(self):
        """Test that prices are rounded to 2 decimal places."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.12345)
        assert update.price == 190.12

    def test_zero_timestamp_is_preserved(self):
        """0.0 is falsy but still an explicit timestamp — it must not be replaced."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.50, timestamp=0.0)
        assert update.timestamp == 0.0

    def test_omitted_timestamp_uses_wall_clock(self):
        cache = PriceCache()
        before = time.time()
        update = cache.update("AAPL", 190.50)
        assert before <= update.timestamp <= time.time()

    def test_remove_then_update_is_flat_again(self):
        """A re-added ticker starts fresh, with no direction carried over."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("AAPL", 195.00)
        cache.remove("AAPL")

        update = cache.update("AAPL", 100.00)
        assert update.direction == "flat"
        assert update.previous_price == 100.00

    def test_remove_bumps_nothing_but_clears_ticker(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        cache.remove("AAPL")

        assert cache.get_all().keys() == {"GOOGL"}

    def test_get_all_is_a_copy(self):
        """Callers mutating the snapshot must not corrupt the cache."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        snapshot = cache.get_all()
        snapshot.clear()

        assert cache.get("AAPL") is not None

    def test_concurrent_updates_are_all_counted(self):
        """Writes may arrive off the event loop thread (Massive uses to_thread)."""
        cache = PriceCache()
        threads = [
            threading.Thread(
                target=lambda i=i: [cache.update(f"T{i}", 10.0 + j) for j in range(50)]
            )
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(cache) == 8
        assert cache.version == 8 * 50
