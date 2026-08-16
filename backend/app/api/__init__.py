"""REST API layer: request/response models, routers, and error mapping.

Routers are created by factories so they can be mounted onto an app that owns
the shared `PriceCache` and `MarketDataSource` on `app.state`.
"""

from .errors import register_exception_handlers
from .health import create_health_router
from .portfolio import build_portfolio, create_portfolio_router
from .watchlist import create_watchlist_router

__all__ = [
    "register_exception_handlers",
    "create_health_router",
    "create_portfolio_router",
    "create_watchlist_router",
    "build_portfolio",
]
