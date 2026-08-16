"""The mock responder must be deterministic and match its documented trigger phrases."""

import pytest

from app.llm.mock import MOCK_FALLBACK_MESSAGE, PORTFOLIO_PREFIX, generate_response


def test_same_input_gives_identical_output():
    first = generate_response("buy 10 shares of AAPL", "ctx", [])
    second = generate_response("buy 10 shares of AAPL", "ctx", [])
    assert first == second


def test_history_is_ignored():
    without = generate_response("hello there", "ctx", [])
    with_history = generate_response(
        "hello there", "ctx", [{"role": "user", "content": "buy 5 AAPL"}]
    )
    assert without == with_history


@pytest.mark.parametrize(
    ("message", "side", "quantity", "ticker"),
    [
        ("buy 10 AAPL", "buy", 10.0, "AAPL"),
        ("buy 10 shares of AAPL", "buy", 10.0, "AAPL"),
        ("sell 2.5 TSLA", "sell", 2.5, "TSLA"),
        ("sell 2.5 shares of tsla", "sell", 2.5, "TSLA"),
        ("Please buy 3 share of NVDA now", "buy", 3.0, "NVDA"),
    ],
)
def test_trade_phrases(message, side, quantity, ticker):
    response = generate_response(message, "ctx", [])
    assert len(response.trades) == 1
    trade = response.trades[0]
    assert (trade.side, trade.quantity, trade.ticker) == (side, quantity, ticker)


def test_multiple_trades_keep_message_order():
    response = generate_response("sell 5 AAPL then buy 2 GOOGL", "ctx", [])
    assert [(t.side, t.ticker) for t in response.trades] == [("sell", "AAPL"), ("buy", "GOOGL")]


@pytest.mark.parametrize(
    "message", ["add NFLX to watchlist", "add NFLX to my watchlist", "watch NFLX"]
)
def test_watchlist_add_phrases(message):
    response = generate_response(message, "ctx", [])
    assert [(c.ticker, c.action) for c in response.watchlist_changes] == [("NFLX", "add")]


@pytest.mark.parametrize(
    "message",
    ["remove NFLX from watchlist", "remove NFLX from my watchlist", "unwatch NFLX"],
)
def test_watchlist_remove_phrases(message):
    response = generate_response(message, "ctx", [])
    assert [(c.ticker, c.action) for c in response.watchlist_changes] == [("NFLX", "remove")]


def test_trade_and_watchlist_in_one_message():
    response = generate_response("buy 1 AAPL and watch NFLX", "ctx", [])
    assert [t.ticker for t in response.trades] == ["AAPL"]
    assert [(c.ticker, c.action) for c in response.watchlist_changes] == [("NFLX", "add")]


@pytest.mark.parametrize(
    "message", ["how is my portfolio doing?", "show my positions", "what's my P&L"]
)
def test_portfolio_questions_return_context_and_no_actions(message):
    response = generate_response(message, "PORTFOLIO CONTEXT BLOCK", [])
    assert response.message.startswith(PORTFOLIO_PREFIX)
    assert "PORTFOLIO CONTEXT BLOCK" in response.message
    assert response.trades == []
    assert response.watchlist_changes == []


def test_fallback():
    response = generate_response("tell me a joke", "ctx", [])
    assert response.message == MOCK_FALLBACK_MESSAGE
    assert response.trades == []
    assert response.watchlist_changes == []
