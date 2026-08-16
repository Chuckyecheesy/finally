"""Repository exceptions and their intended HTTP mappings (PLAN.md §8).

The API layer catches these and translates them into `{"detail": "..."}`
responses. The repository never imports FastAPI — the status code lives here
only as documentation so the mapping stays in one place.
"""

from __future__ import annotations


class RepositoryError(Exception):
    """Base class for every error this layer raises deliberately."""


class DuplicateTickerError(RepositoryError):
    """Ticker is already on the watchlist. API layer -> HTTP 409."""


class TickerNotFoundError(RepositoryError):
    """Ticker is not on the watchlist, so it can't be removed. API layer -> HTTP 404."""


class UnknownTickerError(RepositoryError):
    """No current price is available for the requested ticker. API layer -> HTTP 404.

    `execute_trade` never raises this — callers resolve `current_price` from the
    market price cache themselves and raise it when the cache has no entry.
    """


class InvalidTickerError(RepositoryError):
    """Ticker symbol is blank after normalization. API layer -> HTTP 400.

    Symbols are not checked against any known-ticker list (PLAN.md §8) — any
    non-empty string is accepted.
    """


class InvalidTradeError(RepositoryError):
    """Trade failed validation: non-positive quantity, insufficient cash, or
    insufficient shares. API layer -> HTTP 400.
    """


class ProfileNotFoundError(RepositoryError):
    """No profile row for this user. API layer -> HTTP 500.

    Startup seeding creates the default profile before any request is served
    (PLAN.md §7), so this indicates a corrupt or uninitialized database rather
    than bad user input.
    """
