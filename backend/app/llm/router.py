"""`POST /api/chat` — the chat endpoint (PLAN.md §9).

One round trip: store the user message, build context, call the model (or the
mock), auto-execute whatever it asked for, store the assistant turn with its
actions, and return the whole thing as a single JSON payload. No streaming —
structured output has to be complete before it can be parsed anyway.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter

from app.db import DEFAULT_USER_ID, add_chat_message
from app.market import MarketDataSource, PriceCache

from . import client, mock
from .context import build_history_messages, build_portfolio_context
from .executor import execute_trades, execute_watchlist_changes
from .schemas import ChatRequest, ChatResponse


def mock_mode_enabled() -> bool:
    """Whether `LLM_MOCK` selects the offline responder. Read per request so tests can toggle it."""
    return os.getenv(mock.MOCK_ENV_VAR, "").strip().lower() == "true"


def create_chat_router(
    price_cache: PriceCache,
    market_source: MarketDataSource | None = None,
) -> APIRouter:
    """Build the chat router bound to the shared price cache and market data source.

    `market_source` is optional only so the endpoint stays usable in tests
    without a running data source; in the app it should always be passed, since
    watchlist changes made through chat need it to start and stop price tracking.
    """
    router = APIRouter(prefix="/api", tags=["chat"])

    @router.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        user_id = DEFAULT_USER_ID

        history = build_history_messages(user_id=user_id)
        add_chat_message("user", request.message, user_id=user_id)

        portfolio_context = build_portfolio_context(price_cache, user_id=user_id)
        responder = mock if mock_mode_enabled() else client
        # The completion call is blocking; off the event loop so it can't stall SSE.
        llm_response = await asyncio.to_thread(
            responder.generate_response, request.message, portfolio_context, history
        )

        trade_results = execute_trades(llm_response, price_cache, user_id=user_id)
        watchlist_results = await execute_watchlist_changes(
            llm_response, market_source, user_id=user_id
        )

        response = ChatResponse(
            message=llm_response.message,
            trade_results=trade_results,
            watchlist_results=watchlist_results,
        )
        add_chat_message(
            "assistant",
            response.message,
            actions=response.model_dump(exclude={"message"}),
            user_id=user_id,
        )
        return response

    return router
