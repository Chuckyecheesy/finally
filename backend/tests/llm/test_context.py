"""Portfolio context assembly: P&L math and missing-price handling."""

import pytest

from app.db import add_chat_message, execute_trade
from app.llm.context import build_history_messages, build_portfolio_context, collect_portfolio_state


def test_all_cash_portfolio(temp_db, price_cache):
    state = collect_portfolio_state(price_cache)
    assert state["cash_balance"] == pytest.approx(10000.0)
    assert state["positions"] == []
    assert state["total_value"] == pytest.approx(10000.0)
    assert {w["ticker"] for w in state["watchlist"]} >= {"AAPL", "GOOGL", "TSLA"}


def test_unrealized_pnl_uses_the_live_price(temp_db, price_cache):
    execute_trade("AAPL", "buy", 10, 100.0)
    price_cache.update("AAPL", 110.0)

    position = next(p for p in collect_portfolio_state(price_cache)["positions"])
    assert position["market_value"] == pytest.approx(1100.0)
    assert position["unrealized_pnl"] == pytest.approx(100.0)
    assert position["unrealized_pnl_percent"] == pytest.approx(10.0)


def test_total_value_is_cash_plus_positions(temp_db, price_cache):
    execute_trade("AAPL", "buy", 10, 100.0)
    price_cache.update("AAPL", 110.0)

    state = collect_portfolio_state(price_cache)
    assert state["cash_balance"] == pytest.approx(9000.0)
    assert state["total_value"] == pytest.approx(10100.0)


def test_position_without_a_cached_price_is_marked_unknown(temp_db, price_cache):
    execute_trade("ZZZZ", "buy", 1, 10.0)

    position = next(
        p for p in collect_portfolio_state(price_cache)["positions"] if p["ticker"] == "ZZZZ"
    )
    assert position["current_price"] is None
    assert position["unrealized_pnl"] is None
    assert "no current price available" in build_portfolio_context(price_cache)


def test_context_string_reports_cash_and_holdings(temp_db, price_cache):
    execute_trade("AAPL", "buy", 10, 100.0)
    context = build_portfolio_context(price_cache)
    assert "Cash balance: $9,000.00" in context
    assert "AAPL: 10 shares" in context
    assert "WATCHLIST" in context


def test_history_is_role_content_pairs_oldest_first(temp_db):
    add_chat_message("user", "first")
    add_chat_message("assistant", "second", actions={"trade_results": []})
    assert build_history_messages() == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
    ]
