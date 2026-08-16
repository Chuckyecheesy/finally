"""Watchlist endpoints and their effect on the market data source."""

from app.db import DEFAULT_WATCHLIST


def test_get_returns_seeded_watchlist_with_prices(client):
    items = client.get("/api/watchlist").json()
    assert [item["ticker"] for item in items] == sorted(DEFAULT_WATCHLIST)

    by_ticker = {item["ticker"]: item for item in items}
    assert by_ticker["AAPL"]["price"] == 100.0
    assert by_ticker["AAPL"]["direction"] == "flat"
    # No cached price yet for a ticker the fake source never published.
    assert by_ticker["NFLX"]["price"] is None


def test_add_ticker_tracks_it_on_the_market_source(client, market_source):
    response = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert response.status_code == 201
    assert response.json()["ticker"] == "PYPL"
    assert response.json()["price"] is None
    assert "PYPL" in market_source.get_tickers()
    assert "PYPL" in [item["ticker"] for item in client.get("/api/watchlist").json()]


def test_add_duplicate_ticker_is_409(client):
    response = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert response.status_code == 409
    assert "AAPL" in response.json()["detail"]


def test_add_blank_ticker_is_rejected(client):
    assert client.post("/api/watchlist", json={"ticker": "   "}).status_code == 400
    assert client.post("/api/watchlist", json={"ticker": ""}).status_code == 422


def test_remove_ticker_untracks_it_and_drops_the_price(client, market_source, price_cache):
    market_source.tickers = list(DEFAULT_WATCHLIST)

    response = client.delete("/api/watchlist/aapl")
    assert response.status_code == 204
    assert "AAPL" not in market_source.get_tickers()
    assert price_cache.get("AAPL") is None
    assert "AAPL" not in [item["ticker"] for item in client.get("/api/watchlist").json()]


def test_remove_unwatched_ticker_is_404(client):
    response = client.delete("/api/watchlist/ZZZZ")
    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]
