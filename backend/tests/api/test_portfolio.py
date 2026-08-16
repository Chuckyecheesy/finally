"""Portfolio endpoints: valuation, trades, and history."""

import pytest

from app.db import DEFAULT_CASH_BALANCE


def buy(client, ticker="AAPL", quantity=10):
    return client.post(
        "/api/portfolio/trade",
        json={"ticker": ticker, "quantity": quantity, "side": "buy"},
    )


def test_fresh_portfolio_is_all_cash(client):
    body = client.get("/api/portfolio").json()
    assert body["cash_balance"] == DEFAULT_CASH_BALANCE
    assert body["positions"] == []
    assert body["positions_value"] == 0
    assert body["total_value"] == DEFAULT_CASH_BALANCE
    assert body["total_unrealized_pnl"] == 0


def test_buy_debits_cash_and_opens_position(client):
    response = buy(client, "AAPL", 10)
    assert response.status_code == 200

    trade = response.json()["trade"]
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10
    assert trade["price"] == 100.0

    portfolio = response.json()["portfolio"]
    assert portfolio["cash_balance"] == DEFAULT_CASH_BALANCE - 1000.0
    assert portfolio["total_value"] == DEFAULT_CASH_BALANCE
    (position,) = portfolio["positions"]
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == 10
    assert position["avg_cost"] == 100.0
    assert position["current_price"] == 100.0
    assert position["unrealized_pnl"] == 0
    assert position["unrealized_pnl_percent"] == 0


def test_position_marks_to_market(client, price_cache):
    buy(client, "AAPL", 10)
    price_cache.update("AAPL", 110.0)

    (position,) = client.get("/api/portfolio").json()["positions"]
    assert position["current_price"] == 110.0
    assert position["market_value"] == pytest.approx(1100.0)
    assert position["unrealized_pnl"] == pytest.approx(100.0)
    assert position["unrealized_pnl_percent"] == pytest.approx(10.0)


def test_sell_credits_cash_and_closes_position(client):
    buy(client, "AAPL", 10)
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "sell"},
    )
    assert response.status_code == 200
    portfolio = response.json()["portfolio"]
    assert portfolio["positions"] == []
    assert portfolio["cash_balance"] == pytest.approx(DEFAULT_CASH_BALANCE)


def test_ticker_is_normalized(client):
    response = buy(client, "  aapl  ", 1)
    assert response.status_code == 200
    assert response.json()["trade"]["ticker"] == "AAPL"


def test_missing_price_falls_back_to_avg_cost(client, price_cache):
    buy(client, "AAPL", 10)
    price_cache.remove("AAPL")

    (position,) = client.get("/api/portfolio").json()["positions"]
    assert position["current_price"] == 100.0
    assert position["unrealized_pnl"] == 0


def test_buy_without_enough_cash_is_400(client):
    response = buy(client, "AAPL", 1000)
    assert response.status_code == 400
    assert "Insufficient cash" in response.json()["detail"]


def test_sell_without_enough_shares_is_400(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
    )
    assert response.status_code == 400
    assert "Insufficient shares" in response.json()["detail"]


def test_non_positive_quantity_is_400(client):
    response = buy(client, "AAPL", 0)
    assert response.status_code == 400
    assert "detail" in response.json()


def test_trade_in_unpriced_ticker_is_404(client):
    response = buy(client, "ZZZZ", 1)
    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]


def test_unknown_side_is_rejected(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "hold"},
    )
    assert response.status_code == 422


def test_history_starts_empty_and_grows_with_each_trade(client):
    assert client.get("/api/portfolio/history").json() == []

    buy(client, "AAPL", 1)
    buy(client, "MSFT", 1)

    history = client.get("/api/portfolio/history").json()
    assert len(history) == 2
    assert all(point["total_value"] == pytest.approx(DEFAULT_CASH_BALANCE) for point in history)
    assert [point["recorded_at"] for point in history] == sorted(
        point["recorded_at"] for point in history
    )


def test_position_is_not_stale_when_price_is_cached(client):
    buy(client, "AAPL", 10)

    (position,) = client.get("/api/portfolio").json()["positions"]
    assert position["stale"] is False


def test_position_is_stale_when_price_cache_has_no_price(client, price_cache):
    buy(client, "AAPL", 10)
    price_cache.remove("AAPL")

    (position,) = client.get("/api/portfolio").json()["positions"]
    assert position["stale"] is True
    assert position["current_price"] == pytest.approx(position["avg_cost"])
    assert position["unrealized_pnl"] == pytest.approx(0.0)


def test_break_even_position_is_not_stale(client, price_cache):
    buy(client, "AAPL", 10)
    price_cache.update("AAPL", 100.0)

    (position,) = client.get("/api/portfolio").json()["positions"]
    assert position["stale"] is False
    assert position["unrealized_pnl"] == pytest.approx(0.0)


def test_trade_response_portfolio_carries_stale(client):
    response = buy(client, "AAPL", 10)
    (position,) = response.json()["portfolio"]["positions"]
    assert "stale" in position
