"""Lazy database initialization.

`init_db()` is the single entry point the FastAPI app calls during startup,
before the market-data and portfolio-snapshot background tasks start. It
creates the file and schema if needed and seeds default data. After it returns,
every table exists and the default profile and watchlist are present, so
background tasks and request handlers can assume a ready database (PLAN.md §7).
"""

from __future__ import annotations

import logging

from .connection import get_connection, get_db_path
from .models import DEFAULT_USER_ID
from .schema import create_schema, missing_tables
from .seed import seed_database

logger = logging.getLogger(__name__)


def init_db(user_id: str = DEFAULT_USER_ID) -> None:
    """Create the schema and seed defaults if they're missing. Idempotent."""
    with get_connection() as conn:
        missing = missing_tables(conn)
        if missing:
            logger.info("Creating database schema at %s (missing: %s)", get_db_path(), missing)
            create_schema(conn)
        seed_database(conn, user_id=user_id)
