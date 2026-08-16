"""Portfolio endpoints: valuation, trade execution, and value history."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.db import (
    DEFAULT_USER_ID,
    UnknownTickerError,
    execute_trade,
    get_cash_balance,
    list_positions,
    list_snapshots,
    record_snapshot,
)
from app.market import PriceCache, normalize_ticker

from .deps import get_price_cache
from .schemas import PortfolioOut, PositionOut, SnapshotOut, TradeOut, TradeRequest, TradeResponse


def build_portfolio(price_cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> PortfolioOut:
    """Value the user's account against the latest cached prices.

    A ticker missing from the cache falls back to its average cost, which
    values the position at break-even rather than crashing or dropping it —
    prices can legitimately be absent for a symbol Massive has no data for
    (PLAN.md §8). This fallback is flagged via `stale=True` on the position
    so callers can distinguish it from a genuine break-even.
    """
    cash_balance = get_cash_balance(user_id)
    positions: list[PositionOut] = []

    for position in list_positions(user_id):
        cached_price = price_cache.get_price(position.ticker)
        stale = cached_price is None
        current_price = position.avg_cost if stale else cached_price

        market_value = position.quantity * current_price
        cost_basis = position.quantity * position.avg_cost
        unrealized_pnl = market_value - cost_basis
        positions.append(
            PositionOut(
                ticker=position.ticker,
                quantity=position.quantity,
                avg_cost=position.avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=(
                    (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
                ),
                stale=stale,
            )
        )

    positions_value = sum(p.market_value for p in positions)
    return PortfolioOut(
        cash_balance=cash_balance,
        positions=positions,
        positions_value=positions_value,
        total_value=cash_balance + positions_value,
        total_unrealized_pnl=sum(p.unrealized_pnl for p in positions),
    )


def create_portfolio_router(user_id: str = DEFAULT_USER_ID) -> APIRouter:
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    @router.get("", response_model=PortfolioOut)
    async def get_portfolio(price_cache: PriceCache = Depends(get_price_cache)) -> PortfolioOut:
        """Cash, positions marked to market, and total account value."""
        return build_portfolio(price_cache, user_id)

    @router.post("/trade", response_model=TradeResponse)
    async def post_trade(
        body: TradeRequest,
        price_cache: PriceCache = Depends(get_price_cache),
    ) -> TradeResponse:
        """Execute a market order at the latest cached price and snapshot the result."""
        ticker = normalize_ticker(body.ticker)
        current_price = price_cache.get_price(ticker)
        if current_price is None:
            raise UnknownTickerError(f"No market price available for '{ticker or body.ticker}'")

        trade = execute_trade(
            ticker=ticker,
            side=body.side,
            quantity=body.quantity,
            current_price=current_price,
            user_id=user_id,
        )

        # PLAN.md §7: a snapshot is recorded immediately after every trade so the
        # P&L chart shows the step change instead of waiting for the 30s task.
        portfolio = build_portfolio(price_cache, user_id)
        record_snapshot(total_value=portfolio.total_value, user_id=user_id)

        return TradeResponse(
            trade=TradeOut(
                id=trade.id,
                ticker=trade.ticker,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                executed_at=trade.executed_at,
            ),
            portfolio=portfolio,
        )

    @router.get("/history", response_model=list[SnapshotOut])
    async def get_history() -> list[SnapshotOut]:
        """Portfolio value over time, oldest first, for the P&L chart."""
        return [
            SnapshotOut(total_value=s.total_value, recorded_at=s.recorded_at)
            for s in list_snapshots(user_id)
        ]

    return router
