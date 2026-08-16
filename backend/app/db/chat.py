"""Chat message history (PLAN.md §9).

The table is an unbounded append-only log; `list_recent_chat_messages` is what
the LLM layer uses to bound prompt size to the last 20 messages.

`actions` holds the trades and watchlist changes executed for an assistant
turn. It is stored as JSON text and returned already decoded, so callers never
touch the serialization.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .connection import use_connection
from .models import DEFAULT_USER_ID, ChatMessage, utc_now_iso

USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
DEFAULT_HISTORY_LIMIT = 20


def _row_to_message(row: sqlite3.Row) -> ChatMessage:
    raw = row["actions"]
    return ChatMessage(
        id=row["id"],
        user_id=row["user_id"],
        role=row["role"],
        content=row["content"],
        actions=json.loads(raw) if raw is not None else None,
        created_at=row["created_at"],
    )


def add_chat_message(
    role: str,
    content: str,
    actions: Any = None,
    user_id: str = DEFAULT_USER_ID,
    conn: sqlite3.Connection | None = None,
) -> ChatMessage:
    """Append a message and return it.

    `role` is "user" or "assistant" (enforced by a CHECK constraint). `actions`
    is any JSON-serializable value — null for user messages.
    """
    message = ChatMessage(
        id=str(uuid.uuid4()),
        user_id=user_id,
        role=role,
        content=content,
        actions=actions,
        created_at=utc_now_iso(),
    )
    with use_connection(conn) as db:
        db.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                message.id,
                message.user_id,
                message.role,
                message.content,
                None if actions is None else json.dumps(actions),
                message.created_at,
            ),
        )
    return message


def list_recent_chat_messages(
    user_id: str = DEFAULT_USER_ID,
    limit: int = DEFAULT_HISTORY_LIMIT,
    conn: sqlite3.Connection | None = None,
) -> list[ChatMessage]:
    """The most recent `limit` messages, returned oldest-to-newest for prompting."""
    with use_connection(conn) as db:
        rows = db.execute(
            "SELECT * FROM ("
            "  SELECT id, user_id, role, content, actions, created_at, rowid"
            "  FROM chat_messages WHERE user_id = ?"
            "  ORDER BY created_at DESC, rowid DESC LIMIT ?"
            ") ORDER BY created_at, rowid",
            (user_id, limit),
        ).fetchall()
    return [_row_to_message(row) for row in rows]
