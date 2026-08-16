"""Trade execution tests — the shared path for REST trades and LLM auto-trades."""

import pytest

from app.db import (
    DEFAULT_CASH_BALANCE,
    InvalidTickerError,
    InvalidTradeError,
    execute_trade,
    get_cash_balance,
    get_position,
    list_positions,
    list_trades,
)

pytestmark = pytest.mark.usefixtures("temp_db")


def test_buy_debits_cash_and_creates_position():
    trade = execute_trade("AAPL", "buy", 10, 100.0)

    assert trade.ticker == "AAPL"
    assert trade.side == "buy"
    assert trade.quantity == 10
    assert trade.price == 100.0
    assert get_cash_balance() == pytest.approx(DEFAULT_CASH_BALANCE - 1000.0)

    position = get_position("AAPL")
    assert position is not None
    assert position.quantity == 10
    assert position.avg_cost == 100.0


def test_buy_normalizes_ticker():
    execute_trade(" aapl ", "BUY", 1, 100.0)

    assert get_position("AAPL") is not None


def test_buy_with_insufficient_cash_raises_and_changes_nothing():
    with pytest.raises(InvalidTradeError, match="Insufficient cash"):
        execute_trade("AAPL", "buy", 1000, 100.0)

    assert get_cash_balance() == DEFAULT_CASH_BALANCE
    assert list_positions() == []
    assert list_trades() == []


def test_buy_spending_entire_balance_succeeds():
    execute_trade("AAPL", "buy", 100, DEFAULT_CASH_BALANCE / 100)

    assert get_cash_balance() == pytest.approx(0.0)


def test_second_buy_recomputes_weighted_avg_cost():
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "buy", 30, 200.0)

    position = get_position("AAPL")
    assert position.quantity == 40
    # (10*100 + 30*200) / 40
    assert position.avg_cost == pytest.approx(175.0)


def test_fractional_shares_supported():
    execute_trade("AAPL", "buy", 0.5, 100.0)

    position = get_position("AAPL")
    assert position.quantity == pytest.approx(0.5)
    assert get_cash_balance() == pytest.approx(DEFAULT_CASH_BALANCE - 50.0)


def test_sell_credits_cash_and_decrements_position():
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "sell", 4, 150.0)

    position = get_position("AAPL")
    assert position.quantity == pytest.approx(6)
    assert get_cash_balance() == pytest.approx(DEFAULT_CASH_BALANCE - 1000.0 + 600.0)


def test_sell_leaves_avg_cost_untouched():
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "sell", 4, 150.0)

    assert get_position("AAPL").avg_cost == pytest.approx(100.0)


def test_selling_entire_position_removes_the_row():
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "sell", 10, 90.0)

    assert get_position("AAPL") is None
    assert list_positions() == []
    assert get_cash_balance() == pytest.approx(DEFAULT_CASH_BALANCE - 100.0)


def test_selling_in_fractional_pieces_clears_the_position():
    execute_trade("AAPL", "buy", 0.3, 100.0)
    execute_trade("AAPL", "sell", 0.1, 100.0)
    execute_trade("AAPL", "sell", 0.2, 100.0)

    assert get_position("AAPL") is None


def test_sell_more_than_held_raises():
    execute_trade("AAPL", "buy", 5, 100.0)

    with pytest.raises(InvalidTradeError, match="Insufficient shares"):
        execute_trade("AAPL", "sell", 6, 100.0)

    assert get_position("AAPL").quantity == 5
    assert len(list_trades()) == 1


def test_sell_without_a_position_raises():
    with pytest.raises(InvalidTradeError, match="Insufficient shares"):
        execute_trade("TSLA", "sell", 1, 100.0)

    assert get_cash_balance() == DEFAULT_CASH_BALANCE


def test_non_positive_quantity_raises():
    for quantity in (0, -5):
        with pytest.raises(InvalidTradeError, match="Quantity"):
            execute_trade("AAPL", "buy", quantity, 100.0)


def test_non_positive_price_raises():
    with pytest.raises(InvalidTradeError, match="market price"):
        execute_trade("AAPL", "buy", 1, 0.0)


def test_unknown_side_raises():
    with pytest.raises(InvalidTradeError, match="Unknown trade side"):
        execute_trade("AAPL", "short", 1, 100.0)


def test_blank_ticker_raises():
    with pytest.raises(InvalidTickerError):
        execute_trade("  ", "buy", 1, 100.0)


def test_trades_are_logged_in_order():
    execute_trade("AAPL", "buy", 1, 100.0)
    execute_trade("TSLA", "buy", 2, 50.0)
    execute_trade("AAPL", "sell", 1, 110.0)

    trades = list_trades()
    assert [(t.ticker, t.side) for t in trades] == [
        ("AAPL", "buy"),
        ("TSLA", "buy"),
        ("AAPL", "sell"),
    ]
    assert [(t.ticker, t.side) for t in list_trades(limit=2)] == [
        ("TSLA", "buy"),
        ("AAPL", "sell"),
    ]


def test_positions_listed_alphabetically():
    execute_trade("TSLA", "buy", 1, 100.0)
    execute_trade("AAPL", "buy", 1, 100.0)

    assert [p.ticker for p in list_positions()] == ["AAPL", "TSLA"]


def test_sequential_trades_see_prior_cash_effects():
    """PLAN.md §9: LLM trades execute in order, each validated against the
    account state left by the previous one."""
    execute_trade("AAPL", "buy", 90, 100.0)  # spends 9000 of 10000

    with pytest.raises(InvalidTradeError, match="Insufficient cash"):
        execute_trade("TSLA", "buy", 20, 100.0)
