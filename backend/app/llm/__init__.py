"""LLM chat subsystem: portfolio-aware assistant with auto-executed actions (PLAN.md §9).

The API layer only needs `create_chat_router(price_cache, market_source)`.
"""

from .context import build_history_messages, build_portfolio_context, collect_portfolio_state
from .executor import execute_trades, execute_watchlist_changes
from .router import create_chat_router, mock_mode_enabled
from .schemas import (
    ChatRequest,
    ChatResponse,
    LLMResponseError,
    LLMStructuredResponse,
    TradeAction,
    TradeResult,
    WatchlistChange,
    WatchlistResult,
    parse_structured_response,
)

__all__ = [
    "create_chat_router",
    "mock_mode_enabled",
    "build_portfolio_context",
    "build_history_messages",
    "collect_portfolio_state",
    "execute_trades",
    "execute_watchlist_changes",
    "ChatRequest",
    "ChatResponse",
    "LLMStructuredResponse",
    "LLMResponseError",
    "TradeAction",
    "TradeResult",
    "WatchlistChange",
    "WatchlistResult",
    "parse_structured_response",
]
