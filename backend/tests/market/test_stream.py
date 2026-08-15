"""Tests for the SSE streaming endpoint.

`_generate_events` is driven directly rather than through fastapi's TestClient:
TestClient requires httpx, which isn't a dependency of this project, and the
generator is where all the interesting logic (change detection, disconnect
handling, payload shape) actually lives.
"""

import json

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router

RETRY_EVENT = "retry: 1000\n\n"


class FakeClient:
    host = "127.0.0.1"


class FakeRequest:
    """Stands in for a starlette Request.

    Reports connected for the first `disconnect_after` checks, then drops —
    which is what terminates the generator's loop.
    """

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


@pytest.mark.asyncio
class TestGenerateEvents:
    """Unit tests for the SSE event generator."""

    async def test_first_event_is_retry_directive(self):
        """Browsers need the retry hint so EventSource reconnects promptly."""
        cache = PriceCache()
        events = [e async for e in _generate_events(cache, FakeRequest(0), interval=0.0)]
        assert events[0] == RETRY_EVENT

    async def test_empty_cache_sends_no_data_events(self):
        cache = PriceCache()
        events = [e async for e in _generate_events(cache, FakeRequest(3), interval=0.0)]
        assert events == [RETRY_EVENT]

    async def test_payload_is_keyed_by_ticker(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)

        events = [e async for e in _generate_events(cache, FakeRequest(1), interval=0.0)]

        assert len(events) == 2
        payload = _parse(events[1])
        assert set(payload) == {"AAPL", "GOOGL"}
        assert payload["AAPL"]["price"] == 190.00
        assert payload["AAPL"]["direction"] == "flat"  # First tick never flashes

    async def test_payload_has_full_price_update_shape(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("AAPL", 191.00)

        events = [e async for e in _generate_events(cache, FakeRequest(1), interval=0.0)]
        entry = _parse(events[1])["AAPL"]

        assert set(entry) == {
            "ticker",
            "price",
            "previous_price",
            "timestamp",
            "change",
            "change_percent",
            "direction",
        }
        assert entry["direction"] == "up"
        assert entry["change"] == 1.00

    async def test_unchanged_cache_sends_only_one_event(self):
        """Version-based change detection: no repeat frames while prices hold."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        events = [e async for e in _generate_events(cache, FakeRequest(4), interval=0.0)]

        assert len(events) == 2  # retry + a single data frame

    async def test_new_update_sends_a_new_event(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        gen = _generate_events(cache, FakeRequest(10), interval=0.0)
        try:
            assert await gen.asend(None) == RETRY_EVENT
            assert _parse(await gen.asend(None))["AAPL"]["price"] == 190.00

            cache.update("AAPL", 191.00)
            assert _parse(await gen.asend(None))["AAPL"]["price"] == 191.00
        finally:
            await gen.aclose()

    async def test_stops_when_client_disconnects(self):
        """The generator must terminate, not spin, once the browser goes away."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        events = [e async for e in _generate_events(cache, FakeRequest(0), interval=0.0)]

        assert events == [RETRY_EVENT]

    async def test_handles_request_without_client(self):
        """request.client is None behind some proxies; logging must not blow up."""
        cache = PriceCache()
        request = FakeRequest(1)
        request.client = None

        events = [e async for e in _generate_events(cache, request, interval=0.0)]

        assert events == [RETRY_EVENT]


class TestCreateStreamRouter:
    """Tests for the router factory."""

    def test_registers_prices_route(self):
        router = create_stream_router(PriceCache())
        paths = {route.path for route in router.routes}
        assert paths == {"/api/stream/prices"}

    def test_route_is_a_get(self):
        router = create_stream_router(PriceCache())
        route = router.routes[0]
        assert "GET" in route.methods

    def test_each_call_returns_an_independent_router(self):
        """Regression: a module-level router accumulated a duplicate route per
        call, and every route closed over whichever cache was passed last."""
        first = create_stream_router(PriceCache())
        second = create_stream_router(PriceCache())

        assert first is not second
        assert len(first.routes) == 1
        assert len(second.routes) == 1
