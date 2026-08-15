"""Tests for the MarketDataSource contract and ticker normalization.

planning/PLAN.md §12 calls for verifying that "both implementations conform to
the abstract interface" — these tests assert that structurally, so a future
third data source can't quietly drift from the contract.
"""

import inspect

import pytest

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource, normalize_ticker
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource

IMPLEMENTATIONS = [SimulatorDataSource, MassiveDataSource]

ASYNC_METHODS = ["start", "stop", "add_ticker", "remove_ticker"]
SYNC_METHODS = ["get_tickers"]


def _build(cls) -> MarketDataSource:
    cache = PriceCache()
    if cls is MassiveDataSource:
        return cls(api_key="test-key", price_cache=cache)
    return cls(price_cache=cache)


class TestNormalizeTicker:
    """Unit tests for normalize_ticker."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("AAPL", "AAPL"),
            ("aapl", "AAPL"),
            ("  aapl  ", "AAPL"),
            ("AaPl", "AAPL"),
            ("brk.b", "BRK.B"),
            ("", ""),
            ("   ", ""),
            ("\taapl\n", "AAPL"),
        ],
    )
    def test_normalization(self, raw, expected):
        assert normalize_ticker(raw) == expected

    def test_is_idempotent(self):
        assert normalize_ticker(normalize_ticker(" aapl ")) == "AAPL"


class TestInterfaceConformance:
    """Both data sources must satisfy the same contract."""

    def test_abstract_base_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            MarketDataSource()

    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    def test_is_a_market_data_source(self, cls):
        assert issubclass(cls, MarketDataSource)
        assert isinstance(_build(cls), MarketDataSource)

    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    def test_implements_every_abstract_method(self, cls):
        for name in ASYNC_METHODS + SYNC_METHODS:
            assert getattr(cls, name) is not getattr(MarketDataSource, name), (
                f"{cls.__name__} does not override {name}()"
            )

    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    def test_async_methods_are_coroutines(self, cls):
        for name in ASYNC_METHODS:
            assert inspect.iscoroutinefunction(getattr(cls, name)), f"{name} must be async"

    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    def test_get_tickers_is_synchronous(self, cls):
        assert not inspect.iscoroutinefunction(cls.get_tickers)

    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    def test_get_tickers_empty_before_start(self, cls):
        assert _build(cls).get_tickers() == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    async def test_stop_before_start_is_safe(self, cls):
        """stop() is documented as safe to call repeatedly, including early."""
        source = _build(cls)
        await source.stop()
        await source.stop()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", IMPLEMENTATIONS)
    async def test_get_tickers_returns_a_copy(self, cls):
        """Mutating the returned list must not reach into the source's state."""
        source = _build(cls)
        if cls is SimulatorDataSource:
            await source.start(["AAPL"])
        else:
            # Pre-seed the tracked list without constructing a real REST client
            source._tickers = ["AAPL"]

        tickers = source.get_tickers()
        tickers.append("HACK")

        assert source.get_tickers() == ["AAPL"]

        await source.stop()
