"""Database subsystem for FinAlly — the only layer that issues SQL.

Everything downstream (API routes, LLM tool execution, background tasks) goes
through these functions. Each accepts an optional `conn` so several writes can
share one transaction; pass nothing and the call manages its own.

Errors are raised as `RepositoryError` subclasses, each documenting the HTTP
status the API layer should map it to (PLAN.md §8).
"""

from .chat import add_chat_message, list_recent_chat_messages
from .connection import get_connection, get_db_path, use_connection
from .errors import (
    DuplicateTickerError,
    InvalidTickerError,
    InvalidTradeError,
    ProfileNotFoundError,
    RepositoryError,
    TickerNotFoundError,
    UnknownTickerError,
)
from .init_db import init_db
from .models import (
    DEFAULT_USER_ID,
    ChatMessage,
    PortfolioSnapshot,
    Position,
    Trade,
    UserProfile,
    WatchlistEntry,
    utc_now_iso,
)
from .portfolio import execute_trade, list_trades
from .positions import get_position, list_positions
from .profile import get_cash_balance, get_profile, update_cash_balance
from .seed import DEFAULT_CASH_BALANCE, DEFAULT_WATCHLIST
from .snapshots import list_snapshots, record_snapshot
from .watchlist import add_to_watchlist, is_watched, list_watchlist, remove_from_watchlist

__all__ = [
    # Connection / lifecycle
    "init_db",
    "get_connection",
    "use_connection",
    "get_db_path",
    # Models
    "DEFAULT_USER_ID",
    "UserProfile",
    "WatchlistEntry",
    "Position",
    "Trade",
    "PortfolioSnapshot",
    "ChatMessage",
    "utc_now_iso",
    "DEFAULT_CASH_BALANCE",
    "DEFAULT_WATCHLIST",
    # Profile
    "get_profile",
    "get_cash_balance",
    "update_cash_balance",
    # Watchlist
    "list_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "is_watched",
    # Positions & trades
    "list_positions",
    "get_position",
    "execute_trade",
    "list_trades",
    # Snapshots
    "record_snapshot",
    "list_snapshots",
    # Chat
    "add_chat_message",
    "list_recent_chat_messages",
    # Errors
    "RepositoryError",
    "DuplicateTickerError",
    "TickerNotFoundError",
    "UnknownTickerError",
    "InvalidTickerError",
    "InvalidTradeError",
    "ProfileNotFoundError",
]
