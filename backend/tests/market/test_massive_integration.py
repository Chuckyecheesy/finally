"""Integration tests proving one Massive poll cycle feeds both consumers.

`test_massive.py` proves `_poll_once` writes correct values into an isolated
`PriceCache`; `test_stream.py` proves `_generate_events` reads a `PriceCache`
correctly; `test_portfolio.py` proves `build_portfolio` reads a `PriceCache`
correctly. None of those prove all three compose: that a value written by a
real (mocked) Massive poll response is the exact value the SSE stream emits
AND the exact value portfolio valuation marks a position to market with. This
file drives a full poll -> cache -> {stream, portfolio} flow in one test each,
reusing the pinned, proven fake-snapshot contract from `test_massive.py`
rather than reinventing MagicMocks.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.api.portfolio import build_portfolio
from app.db import execute_trade, init_db
from app.db.connection import DB_PATH_ENV
from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource
from app.market.stream import _generate_events
from tests.market.test_massive import FakeSnapshot, _snapshot


class FakeClient:
    host = "127.0.0.1"


class FakeRequest:
    """Stands in for a starlette Request (mirrors test_stream.py's fake)."""

    def __init__(self, disconnect_after: int = 1):
        self.client = FakeClient()
        self._checks = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._checks += 1
        return self._checks > self._disconnect_after


def _parse(event: str) -> dict:
    """Pull the JSON payload out of an SSE `data:` frame."""
    assert event.startswith("data: ")
    assert event.endswith("\n\n")
    return json.loads(event[len("data: ") : -2])


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the repository at a fresh SQLite file and initialize it."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv(DB_PATH_ENV, str(path))
    init_db()
    return path


def _source(cache: PriceCache, tickers: list[str]) -> MassiveDataSource:
    """A source wired up as if start() had run, minus the real REST client."""
    source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
    source._tickers = list(tickers)
    source._client = MagicMock()
    return source


@pytest.mark.asyncio
class TestMassivePollFeedsStreamAndPortfolio:
    """One Massive poll cycle's output must reach the SSE stream and the
    portfolio valuation with identical values, including the degradation
    path when a poll fails to price a held ticker."""

    async def test_poll_result_matches_sse_stream_payload(self):
        cache = PriceCache()
        source = _source(cache, ["AAPL", "GOOGL"])
        mock_snapshots = [_snapshot("AAPL", 190.50), _snapshot("GOOGL", 175.25)]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        events = [e async for e in _generate_events(cache, FakeRequest(1), interval=0.0)]
        payload = _parse(events[1])

        assert payload["AAPL"]["price"] == 190.50
        assert payload["GOOGL"]["price"] == 175.25

    async def test_poll_result_marks_position_to_market(self, temp_db):
        execute_trade(ticker="AAPL", side="buy", quantity=10, current_price=150.0)

        cache = PriceCache()
        source = _source(cache, ["AAPL"])

        with patch.object(source, "_fetch_snapshots", return_value=[_snapshot("AAPL", 190.50)]):
            await source._poll_once()

        portfolio = build_portfolio(cache)
        position = next(p for p in portfolio.positions if p.ticker == "AAPL")

        assert position.current_price == 190.50
        assert position.stale is False
        assert position.unrealized_pnl == pytest.approx(405.0)

    async def test_failed_price_extraction_leaves_position_stale(self, temp_db):
        execute_trade(ticker="AAPL", side="buy", quantity=10, current_price=150.0)

        cache = PriceCache()
        source = _source(cache, ["AAPL"])
        bad_snapshot = FakeSnapshot(ticker="AAPL", last_trade=None, day=None, prev_day=None)

        with patch.object(source, "_fetch_snapshots", return_value=[bad_snapshot]):
            await source._poll_once()

        portfolio = build_portfolio(cache)
        position = next(p for p in portfolio.positions if p.ticker == "AAPL")

        assert position.current_price == 150.0
        assert position.stale is True
