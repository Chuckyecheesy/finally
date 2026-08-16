"""Executor behavior: per-action reporting, sequential-not-atomic trades, watchlist sync."""

import pytest

from app.db import get_cash_balance, get_position, is_watched
from app.llm.executor import execute_trades, execute_watchlist_changes
from app.llm.schemas import LLMStructuredResponse, TradeAction, WatchlistChange
from app.market import MarketDataSource


class RecordingSource(MarketDataSource):
    """Captures add/remove calls so tests can assert the tracked set stayed in sync."""

    def __init__(self, fail: bool = False):
        self.added: list[str] = []
        self.removed: list[str] = []
        self.fail = fail

    async def start(self, tickers):
        pass

    async def stop(self):
        pass

    async def add_ticker(self, ticker):
        if self.fail:
            raise RuntimeError("source unavailable")
        self.added.append(ticker)

    async def remove_ticker(self, ticker):
        if self.fail:
            raise RuntimeError("source unavailable")
        self.removed.append(ticker)

    def get_tickers(self):
        return self.added


def response(trades=(), changes=()):
    return LLMStructuredResponse(
        message="m", trades=list(trades), watchlist_changes=list(changes)
    )


def test_successful_trade_updates_position_and_cash(temp_db, price_cache):
    results = execute_trades(
        response(trades=[TradeAction(ticker="aapl", side="buy", quantity=10)]), price_cache
    )
    assert [r.status for r in results] == ["executed"]
    assert results[0].ticker == "AAPL"
    assert results[0].trade["price"] == 100.0
    assert get_cash_balance() == pytest.approx(9000.0)
    assert get_position("AAPL").quantity == 10


def test_trades_execute_sequentially_and_are_not_atomic(temp_db, price_cache):
    """Trade 1 spends the whole balance, so trade 2 must fail on insufficient cash."""
    results = execute_trades(
        response(
            trades=[
                TradeAction(ticker="AAPL", side="buy", quantity=100),  # $10,000 — all of it
                TradeAction(ticker="GOOGL", side="buy", quantity=1),  # $200 — no cash left
            ]
        ),
        price_cache,
    )
    assert [r.status for r in results] == ["executed", "failed"]
    assert "Insufficient cash" in results[1].error
    assert get_position("AAPL") is not None
    assert get_position("GOOGL") is None


def test_later_trade_can_succeed_after_an_earlier_failure(temp_db, price_cache):
    results = execute_trades(
        response(
            trades=[
                TradeAction(ticker="AAPL", side="sell", quantity=5),  # nothing held
                TradeAction(ticker="GOOGL", side="buy", quantity=1),
            ]
        ),
        price_cache,
    )
    assert [r.status for r in results] == ["failed", "executed"]
    assert "Insufficient shares" in results[0].error


def test_trade_without_a_cached_price_fails_without_touching_the_account(temp_db, price_cache):
    results = execute_trades(
        response(trades=[TradeAction(ticker="ZZZZ", side="buy", quantity=1)]), price_cache
    )
    assert results[0].status == "failed"
    assert "No market price available for ZZZZ" in results[0].error
    assert get_cash_balance() == pytest.approx(10000.0)


def test_non_positive_quantity_is_reported_not_raised(temp_db, price_cache):
    results = execute_trades(
        response(trades=[TradeAction(ticker="AAPL", side="buy", quantity=0)]), price_cache
    )
    assert results[0].status == "failed"
    assert "greater than zero" in results[0].error


async def test_watchlist_add_and_remove_sync_the_market_source(temp_db):
    source = RecordingSource()
    results = await execute_watchlist_changes(
        response(
            changes=[
                WatchlistChange(ticker="pypl", action="add"),
                WatchlistChange(ticker="AAPL", action="remove"),
            ]
        ),
        source,
    )
    assert [r.status for r in results] == ["executed", "executed"]
    assert is_watched("PYPL")
    assert not is_watched("AAPL")
    assert source.added == ["PYPL"]
    assert source.removed == ["AAPL"]


async def test_duplicate_add_and_missing_remove_are_reported(temp_db):
    source = RecordingSource()
    results = await execute_watchlist_changes(
        response(
            changes=[
                WatchlistChange(ticker="AAPL", action="add"),  # already seeded
                WatchlistChange(ticker="ZZZZ", action="remove"),  # not watched
            ]
        ),
        source,
    )
    assert [r.status for r in results] == ["failed", "failed"]
    assert "already on the watchlist" in results[0].error
    assert "not on the watchlist" in results[1].error
    assert source.added == []


async def test_market_source_failure_does_not_fail_the_watchlist_change(temp_db):
    results = await execute_watchlist_changes(
        response(changes=[WatchlistChange(ticker="PYPL", action="add")]),
        RecordingSource(fail=True),
    )
    assert results[0].status == "executed"
    assert is_watched("PYPL")


async def test_market_source_is_optional(temp_db):
    results = await execute_watchlist_changes(
        response(changes=[WatchlistChange(ticker="PYPL", action="add")]), None
    )
    assert results[0].status == "executed"
