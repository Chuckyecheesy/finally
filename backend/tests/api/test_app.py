"""The real app factory and its startup/shutdown sequence."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import DEFAULT_CASH_BALANCE, DEFAULT_WATCHLIST, list_snapshots

from .conftest import FakeMarketSource


def _use_fake_source(monkeypatch) -> list[FakeMarketSource]:
    """Swap the simulator for a fake; returns the list the factory appends to."""
    sources: list[FakeMarketSource] = []

    def fake_factory(price_cache):
        source = FakeMarketSource(price_cache)
        sources.append(source)
        return source

    monkeypatch.setattr(main, "create_market_data_source", fake_factory)
    return sources


@pytest.fixture
def started_app(temp_db, monkeypatch):
    """`create_app()` with the simulator swapped for a fake source."""
    sources = _use_fake_source(monkeypatch)
    app = main.create_app()
    with TestClient(app) as client:
        yield client, app, sources


def test_startup_starts_the_source_on_the_watchlist(started_app):
    client, app, sources = started_app
    (source,) = sources

    assert client.get("/api/health").json() == {"status": "ok"}
    assert source.started
    assert sorted(source.get_tickers()) == sorted(DEFAULT_WATCHLIST)
    assert app.state.market_source is source


def test_startup_records_one_snapshot(started_app):
    (snapshot,) = list_snapshots()
    assert snapshot.total_value == DEFAULT_CASH_BALANCE


def test_shutdown_stops_the_source_and_cancels_the_snapshot_task(temp_db, monkeypatch):
    sources = _use_fake_source(monkeypatch)
    app = main.create_app()
    with TestClient(app):
        pass

    (source,) = sources
    assert source.stopped
    assert app.state.snapshot_task.cancelled()


def test_deferred_source_forwards_to_the_started_source(started_app):
    _, app, sources = started_app
    (source,) = sources

    deferred = main._DeferredMarketSource(app)
    assert deferred.get_tickers() == source.get_tickers()


def test_deferred_source_raises_before_startup(temp_db, monkeypatch):
    _use_fake_source(monkeypatch)
    app = main.create_app()

    with pytest.raises(RuntimeError):
        main._DeferredMarketSource(app).get_tickers()


def test_stream_route_is_mounted(started_app):
    client, app, _ = started_app
    paths = {route.path for route in app.routes}
    assert "/api/stream/prices" in paths
    assert {"/api/portfolio", "/api/portfolio/trade", "/api/watchlist"} <= paths
