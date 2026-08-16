"""Request, structured-output, and response models for the chat endpoint (PLAN.md §9).

Three layers of model live here:

1. `ChatRequest` — what the frontend POSTs to `/api/chat`.
2. `LLMStructuredResponse` — the JSON schema the model is asked to emit.
3. `ChatResponse` — what the endpoint returns, which is the model's message plus
   per-action execution results, since trades execute sequentially and a later
   one can fail after an earlier one succeeded.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

Side = Literal["buy", "sell"]
WatchlistAction = Literal["add", "remove"]
ActionStatus = Literal["executed", "failed"]


class LLMResponseError(Exception):
    """The model returned something that is not a valid `LLMStructuredResponse`."""


class ChatRequest(BaseModel):
    message: str


class TradeAction(BaseModel):
    ticker: str
    side: Side
    quantity: float


class WatchlistChange(BaseModel):
    ticker: str
    action: WatchlistAction


class LLMStructuredResponse(BaseModel):
    """The structured output contract. Only `message` is required."""

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


class TradeResult(BaseModel):
    ticker: str
    side: str
    quantity: float
    status: ActionStatus
    error: str | None = None
    trade: dict[str, Any] | None = None


class WatchlistResult(BaseModel):
    ticker: str
    action: str
    status: ActionStatus
    error: str | None = None


class ChatResponse(BaseModel):
    message: str
    trade_results: list[TradeResult] = Field(default_factory=list)
    watchlist_results: list[WatchlistResult] = Field(default_factory=list)


def parse_structured_response(raw: str | None) -> LLMStructuredResponse:
    """Parse the model's raw content into `LLMStructuredResponse`.

    Raises `LLMResponseError` for empty content, non-JSON text, or JSON that
    doesn't match the schema, so callers have one exception type to handle
    rather than three.
    """
    if not raw or not raw.strip():
        raise LLMResponseError("Model returned an empty response")
    try:
        return LLMStructuredResponse.model_validate_json(raw)
    except ValidationError as exc:
        raise LLMResponseError(f"Model response did not match the schema: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Model response was not valid JSON: {exc}") from exc
