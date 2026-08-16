"""Tests for GBMSimulator."""

import numpy as np

from app.market.seed_prices import SEED_PRICES
from app.market.simulator import GBMSimulator


class TestGBMSimulator:
    """Unit tests for the GBM price simulator."""

    def test_step_returns_all_tickers(self):
        """Test that step() returns prices for all tickers."""
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        result = sim.step()
        assert set(result.keys()) == {"AAPL", "GOOGL"}

    def test_prices_are_positive(self):
        """GBM prices can never go negative (exp() is always positive)."""
        sim = GBMSimulator(tickers=["AAPL"])
        for _ in range(10_000):
            prices = sim.step()
            assert prices["AAPL"] > 0

    def test_initial_prices_match_seeds(self):
        """Test that initial prices match seed prices."""
        sim = GBMSimulator(tickers=["AAPL"])
        # Before any step, price should be the seed price
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_add_ticker(self):
        """Test adding a ticker dynamically."""
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("TSLA")
        result = sim.step()
        assert "TSLA" in result

    def test_remove_ticker(self):
        """Test removing a ticker."""
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        sim.remove_ticker("GOOGL")
        result = sim.step()
        assert "GOOGL" not in result
        assert "AAPL" in result

    def test_add_duplicate_is_noop(self):
        """Test that adding a duplicate ticker is a no-op."""
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("AAPL")
        assert len(sim._tickers) == 1

    def test_remove_nonexistent_is_noop(self):
        """Test that removing a non-existent ticker is a no-op."""
        sim = GBMSimulator(tickers=["AAPL"])
        sim.remove_ticker("NOPE")  # Should not raise

    def test_unknown_ticker_gets_random_seed_price(self):
        """Test that unknown tickers get random seed prices."""
        sim = GBMSimulator(tickers=["ZZZZ"])
        price = sim.get_price("ZZZZ")
        assert price is not None
        assert 50.0 <= price <= 300.0

    def test_empty_step(self):
        """Test stepping with no tickers."""
        sim = GBMSimulator(tickers=[])
        result = sim.step()
        assert result == {}

    def test_prices_change_over_time(self):
        """After many steps, prices should have drifted from their seeds."""
        sim = GBMSimulator(tickers=["AAPL"])
        initial_price = sim.get_price("AAPL")

        for _ in range(1000):
            sim.step()

        final_price = sim.get_price("AAPL")
        # Price should have changed (extremely unlikely to be exactly the seed)
        assert final_price != initial_price

    def test_cholesky_rebuilds_on_add(self):
        """Test that Cholesky matrix is rebuilt when tickers are added."""
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None  # Only 1 ticker, no correlation matrix
        sim.add_ticker("GOOGL")
        assert sim._cholesky is not None  # Now 2 tickers, matrix exists

    def test_cholesky_none_with_one_ticker(self):
        """Test that Cholesky is None with only one ticker."""
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None

    def test_get_price_returns_none_for_unknown(self):
        """Test that get_price returns None for unknown ticker."""
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("UNKNOWN") is None

    def test_pairwise_correlation_tech_stocks(self):
        """Test that tech stocks have high correlation."""
        corr = GBMSimulator._pairwise_correlation("AAPL", "GOOGL")
        assert corr == 0.6

    def test_pairwise_correlation_finance_stocks(self):
        """Test that finance stocks have moderate correlation."""
        corr = GBMSimulator._pairwise_correlation("JPM", "V")
        assert corr == 0.5

    def test_pairwise_correlation_tsla(self):
        """Test that TSLA has lower correlation with everything."""
        corr = GBMSimulator._pairwise_correlation("TSLA", "AAPL")
        assert corr == 0.3
        corr = GBMSimulator._pairwise_correlation("TSLA", "JPM")
        assert corr == 0.3

    def test_pairwise_correlation_cross_sector(self):
        """Test cross-sector correlation."""
        corr = GBMSimulator._pairwise_correlation("AAPL", "JPM")
        assert corr == 0.3

    def test_default_dt_is_reasonable(self):
        """Test that default dt is a reasonable small value."""
        assert 0 < GBMSimulator.DEFAULT_DT < 0.0001

    def test_prices_rounded_to_two_decimals(self):
        """Test that prices are rounded to 2 decimal places."""
        sim = GBMSimulator(tickers=["AAPL"])
        result = sim.step()
        price_str = str(result["AAPL"])
        # Check that we have at most 2 decimal places
        if "." in price_str:
            decimal_part = price_str.split(".")[1]
            assert len(decimal_part) <= 2

    def test_full_default_ticker_set_cholesky_is_well_behaved(self):
        """The full 10x10 default correlation matrix must decompose cleanly.

        A non-positive-semi-definite correlation matrix raises LinAlgError on
        np.linalg.cholesky; this exercises the full default ticker set (only
        ever manually verified before, per MARKET_DATA_REVIEW.md 3.1) so a
        future change to CORRELATION_GROUPS or the correlation constants
        can't silently break it without CI catching it.
        """
        sim = GBMSimulator(tickers=list(SEED_PRICES.keys()))
        assert sim._cholesky is not None
        for _ in range(100):
            prices = sim.step()
            assert set(prices.keys()) == set(SEED_PRICES.keys())
            assert all(p > 0 for p in prices.values())


class TestGBMSimulatorAtScale:
    """The Cholesky/correlation math has only ever been exercised at the default
    10-ticker scale. A correlation-constant change, or a future large custom
    watchlist, could raise LinAlgError (non-positive-semi-definite matrix) with
    no test catching it before production — these tests exercise a 60-ticker,
    non-default watchlist (10 default sector tickers + 50 synthetic unknowns)
    to close that gap.
    """

    SYNTHETIC_TICKERS = [f"SYN{i:03d}" for i in range(50)]

    def _large_watchlist(self) -> list[str]:
        return list(SEED_PRICES.keys()) + list(self.SYNTHETIC_TICKERS)

    def _expected_correlation_matrix(self, tickers: list[str]) -> np.ndarray:
        n = len(tickers)
        expected = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = GBMSimulator._pairwise_correlation(tickers[i], tickers[j])
                expected[i, j] = rho
                expected[j, i] = rho
        return expected

    def test_large_non_default_watchlist_cholesky_is_well_behaved(self):
        """A 60-ticker, non-default watchlist must produce a Cholesky factor that
        truly reconstructs the intended correlation matrix, not merely "not raise".
        """
        tickers = self._large_watchlist()
        assert len(tickers) == 60
        assert set(tickers) != set(SEED_PRICES.keys())

        sim = GBMSimulator(tickers=tickers)
        assert sim._cholesky is not None
        assert sim._cholesky.shape == (60, 60)

        expected_corr = self._expected_correlation_matrix(sim._tickers)

        # The Cholesky factor must reconstruct the intended correlation matrix.
        reconstructed = sim._cholesky @ sim._cholesky.T
        assert np.allclose(reconstructed, expected_corr, atol=1e-8)

        # Independent well-behaved check: the correlation matrix must be
        # positive semi-definite (no negative eigenvalues beyond float noise).
        eigenvalues = np.linalg.eigvalsh(expected_corr)
        assert np.all(eigenvalues > -1e-8)

    def test_large_watchlist_prices_stay_positive_over_many_steps(self):
        """Prices must stay strictly positive across many steps for a large,
        non-default watchlist (GBM's exp() guarantees this mathematically, but
        this proves it holds at scale with correlated draws too)."""
        sim = GBMSimulator(tickers=self._large_watchlist())
        tracked = set(sim.get_tickers())

        for _ in range(500):
            prices = sim.step()
            assert set(prices.keys()) == tracked
            assert all(p > 0 for p in prices.values())

    def test_cholesky_stable_after_add_remove_churn_at_scale(self):
        """Cholesky must remain well-behaved after add/remove churn at scale."""
        sim = GBMSimulator(tickers=self._large_watchlist())

        for i in range(50, 55):
            sim.add_ticker(f"SYN{i:03d}")

        for i in range(0, 5):
            sim.remove_ticker(f"SYN{i:03d}")

        remaining = sim.get_tickers()
        assert len(remaining) == 60

        assert sim._cholesky is not None
        assert sim._cholesky.shape == (len(remaining), len(remaining))

        prices = sim.step()
        assert set(prices.keys()) == set(remaining)
        assert all(p > 0 for p in prices.values())
