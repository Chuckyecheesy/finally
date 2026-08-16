"""Row types returned by the repository.

Frozen dataclasses rather than raw `sqlite3.Row` so downstream code gets
attribute access and type hints. `dataclasses.asdict()` converts any of them to
a JSON-serializable dict for API responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

DEFAULT_USER_ID = "default"


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string — the format every timestamp column stores."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class UserProfile:
    id: str
    cash_balance: float
    created_at: str


@dataclass(frozen=True)
class WatchlistEntry:
    id: str
    user_id: str
    ticker: str
    added_at: str


@dataclass(frozen=True)
class Position:
    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


@dataclass(frozen=True)
class Trade:
    id: str
    user_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str


@dataclass(frozen=True)
class PortfolioSnapshot:
    id: str
    user_id: str
    total_value: float
    recorded_at: str


@dataclass(frozen=True)
class ChatMessage:
    id: str
    user_id: str
    role: str
    content: str
    actions: Any
    created_at: str
