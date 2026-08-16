"""Health check endpoint (PLAN.md §8)."""

from __future__ import annotations

from fastapi import APIRouter

from .schemas import HealthOut


def create_health_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["system"])

    @router.get("/health", response_model=HealthOut)
    async def health() -> HealthOut:
        """Liveness probe used by Docker and deployment platforms."""
        return HealthOut(status="ok")

    return router
