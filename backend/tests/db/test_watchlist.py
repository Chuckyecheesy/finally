"""Watchlist repository tests."""

import pytest

from app.db import (
    DEFAULT_WATCHLIST,
    DuplicateTickerError,
    InvalidTickerError,
    TickerNotFoundError,
    add_to_watchlist,
    is_watched,
    list_watchlist,
    remove_from_watchlist,
)

pytestmark = pytest.mark.usefixtures("temp_db")


def test_seeded_watchlist_has_default_tickers():
    tickers = {entry.ticker for entry in list_watchlist()}
    assert tickers == set(DEFAULT_WATCHLIST)


def test_add_returns_entry_and_persists():
    entry = add_to_watchlist("PYPL")

    assert entry.ticker == "PYPL"
    assert entry.id
    assert is_watched("PYPL")
    assert "PYPL" in {e.ticker for e in list_watchlist()}


def test_add_normalizes_ticker():
    entry = add_to_watchlist("  pypl ")

    assert entry.ticker == "PYPL"
    assert is_watched("pypl")


def test_add_duplicate_raises():
    with pytest.raises(DuplicateTickerError):
        add_to_watchlist("AAPL")


def test_add_duplicate_is_case_insensitive():
    with pytest.raises(DuplicateTickerError):
        add_to_watchlist("aapl")


def test_add_blank_ticker_raises():
    with pytest.raises(InvalidTickerError):
        add_to_watchlist("   ")


def test_remove_deletes_entry():
    remove_from_watchlist("aapl")

    assert not is_watched("AAPL")
    assert "AAPL" not in {e.ticker for e in list_watchlist()}


def test_remove_unknown_ticker_raises():
    with pytest.raises(TickerNotFoundError):
        remove_from_watchlist("ZZZZ")


def test_remove_then_add_succeeds():
    remove_from_watchlist("AAPL")
    entry = add_to_watchlist("AAPL")

    assert entry.ticker == "AAPL"


def test_watchlist_is_scoped_per_user():
    add_to_watchlist("PYPL", user_id="other")

    assert [e.ticker for e in list_watchlist(user_id="other")] == ["PYPL"]
    assert not is_watched("PYPL")
