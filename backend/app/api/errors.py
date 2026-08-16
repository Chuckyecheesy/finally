"""Maps repository exceptions onto HTTP responses in one place.

`app/db/errors.py` documents the status each error should become; this module
is the single implementation of that mapping, so routes can let errors
propagate instead of repeating try/except.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db import (
    DuplicateTickerError,
    InvalidTickerError,
    InvalidTradeError,
    ProfileNotFoundError,
    RepositoryError,
    TickerNotFoundError,
    UnknownTickerError,
)

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[RepositoryError], int] = {
    DuplicateTickerError: 409,
    TickerNotFoundError: 404,
    UnknownTickerError: 404,
    InvalidTickerError: 400,
    InvalidTradeError: 400,
    ProfileNotFoundError: 500,
}

DEFAULT_STATUS = 500


def status_for(exc: RepositoryError) -> int:
    """Status code for an error, resolved through its MRO so subclasses inherit."""
    for klass in type(exc).__mro__:
        if klass in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[klass]
    return DEFAULT_STATUS


def register_exception_handlers(app: FastAPI) -> None:
    """Translate every `RepositoryError` into `{"detail": ...}` (PLAN.md §8)."""

    @app.exception_handler(RepositoryError)
    async def _handle_repository_error(_request: Request, exc: RepositoryError) -> JSONResponse:
        status = status_for(exc)
        if status >= 500:
            logger.exception("Repository error serving request", exc_info=exc)
        return JSONResponse(status_code=status, content={"detail": str(exc)})
