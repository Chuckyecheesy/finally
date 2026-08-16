"""End-to-end coverage of POST /api/chat in mock mode."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_cash_balance, is_watched, list_recent_chat_messages
from app.llm.mock import MOCK_FALLBACK_MESSAGE
from app.llm.router import create_chat_router
from tests.llm.test_executor import RecordingSource


@pytest.fixture
def client(temp_db, price_cache):
    source = RecordingSource()
    app = FastAPI()
    app.include_router(create_chat_router(price_cache, source))
    with TestClient(app) as test_client:
        test_client.market_source = source
        yield test_client


def test_generic_message_returns_fallback_and_no_actions(client):
    body = client.post("/api/chat", json={"message": "hello"}).json()
    assert body["message"] == MOCK_FALLBACK_MESSAGE
    assert body["trade_results"] == []
    assert body["watchlist_results"] == []


def test_trade_request_executes_and_reports_inline(client):
    body = client.post("/api/chat", json={"message": "buy 10 shares of AAPL"}).json()
    assert body["trade_results"] == [
        {
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 10.0,
            "status": "executed",
            "error": None,
            "trade": body["trade_results"][0]["trade"],
        }
    ]
    assert get_cash_balance() == pytest.approx(9000.0)


def test_failed_trade_is_reported_not_a_500(client):
    body = client.post("/api/chat", json={"message": "buy 999 shares of AAPL"}).json()
    assert body["trade_results"][0]["status"] == "failed"
    assert "Insufficient cash" in body["trade_results"][0]["error"]
    assert get_cash_balance() == pytest.approx(10000.0)


def test_watchlist_change_applies_and_syncs_the_source(client):
    body = client.post("/api/chat", json={"message": "watch PYPL"}).json()
    assert body["watchlist_results"][0]["status"] == "executed"
    assert is_watched("PYPL")
    assert client.market_source.added == ["PYPL"]


def test_both_turns_are_persisted_with_actions_on_the_assistant_turn(client):
    client.post("/api/chat", json={"message": "buy 1 AAPL"})
    messages = list_recent_chat_messages()
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].actions is None
    assert messages[1].actions["trade_results"][0]["status"] == "executed"


def test_history_is_available_to_the_next_turn(client):
    client.post("/api/chat", json={"message": "hello"})
    client.post("/api/chat", json={"message": "hello again"})
    assert [m.content for m in list_recent_chat_messages()] == [
        "hello",
        MOCK_FALLBACK_MESSAGE,
        "hello again",
        MOCK_FALLBACK_MESSAGE,
    ]
