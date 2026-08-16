"""Chat message repository tests."""

import pytest

from app.db import add_chat_message, list_recent_chat_messages

pytestmark = pytest.mark.usefixtures("temp_db")


def test_empty_by_default():
    assert list_recent_chat_messages() == []


def test_user_message_has_null_actions():
    message = add_chat_message("user", "buy me some AAPL")

    assert message.role == "user"
    assert message.actions is None
    assert list_recent_chat_messages() == [message]


def test_actions_round_trip_as_json():
    actions = {
        "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10, "ok": True}],
        "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
    }
    add_chat_message("assistant", "Bought 10 AAPL.", actions=actions)

    stored = list_recent_chat_messages()[0]
    assert stored.actions == actions


def test_empty_actions_list_survives_round_trip():
    add_chat_message("assistant", "Nothing to do.", actions=[])

    assert list_recent_chat_messages()[0].actions == []


def test_ordered_oldest_to_newest():
    for i in range(4):
        add_chat_message("user", f"message {i}")

    assert [m.content for m in list_recent_chat_messages()] == [
        "message 0",
        "message 1",
        "message 2",
        "message 3",
    ]


def test_limit_keeps_the_most_recent_messages():
    for i in range(25):
        add_chat_message("user", f"message {i}")

    recent = list_recent_chat_messages()
    assert len(recent) == 20
    assert recent[0].content == "message 5"
    assert recent[-1].content == "message 24"


def test_explicit_limit_respected():
    for i in range(10):
        add_chat_message("user", f"message {i}")

    recent = list_recent_chat_messages(limit=3)
    assert [m.content for m in recent] == ["message 7", "message 8", "message 9"]


def test_scoped_per_user():
    add_chat_message("user", "mine")
    add_chat_message("user", "theirs", user_id="other")

    assert [m.content for m in list_recent_chat_messages()] == ["mine"]
    assert [m.content for m in list_recent_chat_messages(user_id="other")] == ["theirs"]


def test_invalid_role_rejected_by_schema():
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        add_chat_message("system", "nope")
