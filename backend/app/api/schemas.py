"""Pydantic request and response models for the REST API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PositionOut(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float


class PortfolioOut(BaseModel):
    cash_balance: float
    positions: list[PositionOut]
    positions_value: float
    total_value: float
    total_unrealized_pnl: float


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]


class TradeOut(BaseModel):
    id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str


class TradeResponse(BaseModel):
    trade: TradeOut
    portfolio: PortfolioOut


class SnapshotOut(BaseModel):
    total_value: float
    recorded_at: str


class WatchlistItemOut(BaseModel):
    ticker: str
    added_at: str
    price: float | None = None
    previous_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    direction: str | None = None
    timestamp: float | None = None


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(min_length=1)


class HealthOut(BaseModel):
    status: str
