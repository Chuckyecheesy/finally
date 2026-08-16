# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import (
    PriceCache,
    PriceUpdate,
    MarketDataSource,
    normalize_ticker,
    create_market_data_source,
)
```

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `timestamp`, plus properties `change`, `change_percent`, `direction` ("up"/"down"/"flat"), and `to_dict()` for JSON serialization.

- **`PriceCache`** — Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None) -> PriceUpdate`
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `remove(ticker)`
  - `version` property — monotonic counter, increments on every update (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`normalize_ticker(ticker)`** — Canonical symbol form: stripped and uppercased, `""` for blank input. Both data sources apply it, so cache keys are always canonical. Use it in the watchlist/trade endpoints too, so user input matches cache keys.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
```

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Database API

`app/db/` is the only layer that issues SQL. Import everything from the package:

```python
from app.db import execute_trade, list_positions, DuplicateTickerError
```

Every function takes an optional trailing `conn: sqlite3.Connection | None = None` so
callers can group writes into one transaction; omit it and the call manages its own.
`user_id` defaults to `DEFAULT_USER_ID` ("default") everywhere.

- **Lifecycle** — `init_db()` at FastAPI startup (creates schema + seeds; idempotent).
- **Profile** — `get_profile()`, `get_cash_balance()`, `update_cash_balance(user_id, new_balance)`.
- **Watchlist** — `list_watchlist()`, `add_to_watchlist(ticker)`, `remove_from_watchlist(ticker)`, `is_watched(ticker)`.
- **Positions** — `list_positions()`, `get_position(ticker)`.
- **Trades** — `execute_trade(ticker, side, quantity, current_price)`, `list_trades(limit=None)`.
  Callers resolve `current_price` from `PriceCache.get_price` first; a `None` price is a
  404 (`UnknownTickerError`) raised by the caller, not by this function.
- **Snapshots** — `record_snapshot(total_value)`, `list_snapshots(since=None, limit=None)`.
- **Chat** — `add_chat_message(role, content, actions=None)`, `list_recent_chat_messages(limit=20)`.

Errors are `RepositoryError` subclasses; each docstring names the HTTP status the API
layer should map it to: `DuplicateTickerError` 409, `TickerNotFoundError` /
`UnknownTickerError` 404, `InvalidTradeError` / `InvalidTickerError` 400,
`ProfileNotFoundError` 500.

Tests point at a temp database via the `FINALLY_DB_PATH` env var — see the `temp_db`
fixture in `tests/db/conftest.py`.

## LLM Chat API

`app/llm/` owns `POST /api/chat`. The API layer needs one import:

```python
from app.llm import create_chat_router

router = create_chat_router(price_cache, market_source)  # market_source optional but expected
```

The router needs `market_source` so watchlist changes made through chat start/stop
price tracking, mirroring what the REST watchlist endpoints do.

- **`schemas.py`** — `ChatRequest`, `LLMStructuredResponse` (the structured output
  contract), `ChatResponse` (message + `trade_results` / `watchlist_results`, each
  entry `status` "executed" or "failed" with an `error` string).
- **`client.py`** — LiteLLM -> OpenRouter -> Cerebras, `openrouter/openai/gpt-oss-120b`.
  Never raises; a failed or malformed completion degrades to an apology with no actions.
- **`mock.py`** — offline responder used when `LLM_MOCK=true`. Its module docstring is
  the authoritative list of supported trigger phrases (E2E tests depend on them verbatim).
- **`executor.py`** — runs trades sequentially through `app.db.execute_trade`; not
  atomic, each action reports its own outcome.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
