<!-- refreshed: 2026-08-16 -->
# Architecture

**Analysis Date:** 2026-08-16

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│              Browser — Next.js static export (served by FastAPI)     │
│  `frontend/src/app/page.tsx` — Terminal (top-level page component)   │
├───────────────────┬───────────────────┬──────────────────────────────┤
│  usePriceStream    │   useTerminal      │  ChatPanel                  │
│  `hooks/usePriceStream.ts` (SSE)       │  `components/ChatPanel.tsx`  │
│  `hooks/useTerminal.ts` (REST polling) │  (REST /api/chat)            │
└─────────┬─────────────────┬────────────┴──────────┬───────────────────┘
          │ EventSource        │ fetch()              │ fetch()
          ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FastAPI app — `backend/app/main.py`                 │
│  ┌───────────────┬────────────────┬────────────────┬──────────────┐ │
│  │ /api/stream/*  │ /api/portfolio │ /api/watchlist  │ /api/chat    │ │
│  │ `market/stream`│ `api/portfolio`│ `api/watchlist` │ `llm/router` │ │
│  └───────┬────────┴────────┬───────┴────────┬────────┴──────┬──────┘ │
└──────────┼─────────────────┼────────────────┼───────────────┼────────┘
           │                 │                 │               │
           ▼                 ▼                 ▼               ▼
┌────────────────────┐ ┌───────────────────────────┐ ┌──────────────────┐
│  PriceCache          │ │  app/db (SQLite, sqlite3) │ │  app/llm          │
│  `market/cache.py`   │ │  positions, trades, cash, │ │  client/mock +    │
│  in-memory, thread-  │ │  watchlist, snapshots,    │ │  executor (calls  │
│  safe, versioned     │ │  chat_messages            │ │  db + market)     │
└─────────▲────────────┘ └───────────────────────────┘ └──────────────────┘
          │
┌─────────┴────────────────────────────────────────────┐
│  MarketDataSource (ABC) — `market/interface.py`       │
│  ├── SimulatorDataSource  (`market/simulator.py`)      │
│  └── MassiveDataSource    (`market/massive_client.py`) │
│  selected by `market/factory.py` via MASSIVE_API_KEY   │
└────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Terminal (page) | Top-level layout composition, selected-ticker state | `frontend/src/app/page.tsx` |
| usePriceStream | Owns the SSE `EventSource` connection, accumulates per-ticker tick history for sparklines, exposes connection status | `frontend/src/hooks/usePriceStream.ts` |
| useTerminal | Owns REST-derived state (portfolio, watchlist, snapshot history), overlays live prices onto positions, exposes trade/watchlist actions | `frontend/src/hooks/useTerminal.ts` |
| api.ts | Typed fetch wrapper, response normalization, `ApiError` | `frontend/src/lib/api.ts` |
| FastAPI app factory | Wires lifespan (DB init → market source start → snapshot loop), mounts routers, mounts static export | `backend/app/main.py` |
| PriceCache | Thread-safe in-memory latest-price store with a version counter for SSE change detection | `backend/app/market/cache.py` |
| MarketDataSource (ABC) | Defines `start/stop/add_ticker/remove_ticker/get_tickers`; both concrete sources conform | `backend/app/market/interface.py` |
| SimulatorDataSource | GBM-based simulated price generator (default), writes into `PriceCache` | `backend/app/market/simulator.py` |
| MassiveDataSource | Polygon.io REST poller (used when `MASSIVE_API_KEY` set) | `backend/app/market/massive_client.py` |
| create_stream_router | SSE endpoint factory (`/api/stream/prices`), version-based diffing against `PriceCache` | `backend/app/market/stream.py` |
| app/db package | Sole SQL-issuing layer; one module per table/domain, functions take optional `conn` for transaction grouping | `backend/app/db/*.py` |
| app/api package | REST routers (`portfolio`, `watchlist`, `health`), Pydantic request/response schemas, exception→HTTP mapping | `backend/app/api/*.py` |
| app/llm package | Chat request handling: builds context, calls LiteLLM (or mock), executes trades/watchlist changes, persists chat history | `backend/app/llm/*.py` |

## Pattern Overview

**Overall:** Layered service architecture within a single FastAPI process — presentation (routers) → domain services (market, llm) → persistence (db) — fronting a statically-exported SPA. Backend and frontend are fully decoupled codebases connected only by the `/api/*` HTTP/SSE contract; the frontend is bundled into the backend's static directory at Docker build time so the whole app runs as one process on one port.

**Key Characteristics:**
- Strategy pattern for market data: `MarketDataSource` ABC with two interchangeable implementations selected at startup by an env var (`market/factory.py`)
- Single shared mutable cache (`PriceCache`) is the only coupling point between the market-data background task and both the SSE stream and portfolio valuation — producers/consumers never talk directly
- Router-factory pattern throughout the backend: every FastAPI router is built by a `create_*_router(...)` function that closes over its dependencies (price cache, market source, user_id) rather than using module-level globals, so state can be constructed once in `create_app()` and passed down explicit
- Repository-style `app/db` layer: no ORM, raw `sqlite3`, one function per operation, domain-specific exception types instead of generic DB errors
- Frontend state is split into two independent hooks by data-transport: `usePriceStream` (push, SSE, high-frequency) vs `useTerminal` (pull, REST polling every 15s, low-frequency), composed together only in `page.tsx`

## Layers

**Frontend — Presentation (`frontend/src/components/`):**
- Purpose: Render UI, dumb w.r.t. business logic — receive data/callbacks as props
- Location: `frontend/src/components/*.tsx`
- Contains: `Watchlist`, `PriceChart`, `Heatmap`, `PnlChart`, `PositionsTable`, `TradeBar`, `ChatPanel`, `Header`, `PriceCell`, `Sparkline`, `Panel`
- Depends on: hooks (via props passed from `page.tsx`), `lib/types.ts` for shapes
- Used by: `frontend/src/app/page.tsx`

**Frontend — State/Data (`frontend/src/hooks/`):**
- Purpose: Own all client-side state and side effects (SSE subscription, REST polling, derived calculations like live P&L)
- Location: `frontend/src/hooks/usePriceStream.ts`, `frontend/src/hooks/useTerminal.ts`
- Contains: `EventSource` lifecycle, `useState`/`useEffect`/`useMemo` state machines
- Depends on: `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
- Used by: `frontend/src/app/page.tsx`

**Frontend — Client Utilities (`frontend/src/lib/`):**
- Purpose: Typed fetch wrapper + response normalization (`api.ts`), shared TS types (`types.ts`), display formatting (`format.ts`)
- Location: `frontend/src/lib/*.ts`
- Depends on: nothing internal (leaf layer)
- Used by: hooks and components

**Backend — API/Presentation (`backend/app/api/`):**
- Purpose: HTTP boundary — request validation (Pydantic), routing, error-to-status-code mapping
- Location: `backend/app/api/*.py`
- Contains: `portfolio.py` (portfolio + trade endpoints), `watchlist.py`, `health.py`, `schemas.py` (Pydantic models), `errors.py` (exception handlers), `deps.py` (FastAPI `Depends` providers)
- Depends on: `app.db`, `app.market`
- Used by: `app/main.py`

**Backend — Market Data (`backend/app/market/`):**
- Purpose: Produce and cache live/simulated prices, expose them over SSE
- Location: `backend/app/market/*.py`
- Contains: `models.py` (`PriceUpdate`), `interface.py` (ABC + `normalize_ticker`), `cache.py` (`PriceCache`), `simulator.py` (GBM), `massive_client.py` (Polygon poller), `factory.py`, `stream.py`, `seed_prices.py`
- Depends on: `numpy`, `massive` SDK
- Used by: `app/main.py`, `app/api/portfolio.py` (for valuation), `app/llm` (for chat context)

**Backend — Persistence (`backend/app/db/`):**
- Purpose: Sole owner of all SQL; SQLite schema, seeding, and CRUD per domain
- Location: `backend/app/db/*.py`
- Contains: `connection.py`, `schema.py`, `init_db.py`, `seed.py`, `profile.py`, `watchlist.py`, `positions.py`, `portfolio.py` (trade execution), `snapshots.py`, `chat.py`, `models.py` (dataclasses), `errors.py` (`RepositoryError` subclasses)
- Depends on: stdlib `sqlite3` only
- Used by: `app/api/*`, `app/llm/executor.py`, `app/main.py` (snapshot loop, lifespan init)

**Backend — LLM/Chat (`backend/app/llm/`):**
- Purpose: Build portfolio+history context, call the LLM (or mock), auto-execute returned trades/watchlist changes, persist the conversation
- Location: `backend/app/llm/*.py`
- Contains: `router.py` (`/api/chat`), `context.py`, `client.py` (LiteLLM→OpenRouter→Cerebras), `mock.py` (`LLM_MOCK=true` responder), `executor.py`, `schemas.py`
- Depends on: `app.db`, `app.market` (`PriceCache`, `MarketDataSource`)
- Used by: `app/main.py` (mounted conditionally via `_include_chat_router`, so `/api/chat` degrades gracefully if the module is absent)

## Data Flow

### Live price streaming (SSE)

1. Client opens `EventSource('/api/stream/prices')` (`frontend/src/hooks/usePriceStream.ts`)
2. `create_stream_router` (`backend/app/market/stream.py`) polls `PriceCache.version` and yields new/changed `PriceUpdate`s as SSE events
3. Background task (`SimulatorDataSource` or `MassiveDataSource`) writes into the same `PriceCache` roughly every 500ms (simulator) or on each poll cycle (Massive)
4. `usePriceStream` parses each event, updates `prices` state (keyed by ticker) and appends to per-ticker `history` arrays for sparklines/charts
5. `page.tsx` / `useTerminal` overlay `prices` onto the last fetched portfolio positions (`livePositions()` in `frontend/src/hooks/useTerminal.ts:13`) so P&L and total value tick live between REST refreshes

### Trade execution (manual, via Trade Bar)

1. `TradeBar` calls `terminal.trade(ticker, qty, side)` (`frontend/src/hooks/useTerminal.ts:92`)
2. `api.executeTrade` → `POST /api/portfolio/trade` (`frontend/src/lib/api.ts:123`)
3. `create_portfolio_router` handler (`backend/app/api/portfolio.py:73`) resolves the current price from `PriceCache`, calls `app.db.execute_trade`, then immediately calls `build_portfolio` + `record_snapshot` so the P&L chart shows the step change without waiting for the 30s loop
4. Response returns the executed `trade` and freshly valued `portfolio`; frontend calls `refresh()` to pull the latest state from `/api/portfolio`, `/api/watchlist`, `/api/portfolio/history`

### Chat / AI trade execution

1. `ChatPanel` → `api.sendChat(message)` → `POST /api/chat` (`backend/app/llm/router.py:42`)
2. Handler stores the user message, builds portfolio context (`context.build_portfolio_context`) and recent history (`context.build_history_messages`, capped at 20 messages)
3. Calls `client.generate_response` (real LiteLLM/OpenRouter/Cerebras call) or `mock.generate_response` if `LLM_MOCK=true`, off the event loop via `asyncio.to_thread`
4. `execute_trades` (`app/llm/executor.py`) runs any returned trades sequentially through `app.db.execute_trade`, not atomic — each trade validated against post-prior-trade state, per-trade success/failure reported
5. `execute_watchlist_changes` applies add/remove against `app.db.watchlist` and the live `MarketDataSource` (via `_DeferredMarketSource` indirection in `main.py:113`, since the router is built before the lifespan starts the real source)
6. Assistant turn + `trade_results`/`watchlist_results` persisted to `chat_messages`; full `ChatResponse` returned as one JSON payload (no streaming)

**State Management:**
- Server: two mutable stores — `PriceCache` (in-memory, ephemeral, per-process) and SQLite (`db/finally.db`, durable, volume-mounted). No caching layer between SQLite and the API; each request reads fresh.
- Client: React local component state only, split by transport (SSE vs REST) across `usePriceStream` and `useTerminal`; no global store (Redux/Zustand) — `page.tsx` is the sole composition point.

## Key Abstractions

**MarketDataSource (ABC):**
- Purpose: Uniform lifecycle contract (`start`, `stop`, `add_ticker`, `remove_ticker`, `get_tickers`) so downstream code (SSE stream, chat executor, portfolio valuation) never needs to know whether prices are simulated or real
- Examples: `backend/app/market/interface.py`, `backend/app/market/simulator.py` (`SimulatorDataSource`), `backend/app/market/massive_client.py` (`MassiveDataSource`), `backend/app/main.py` (`_DeferredMarketSource` — a lazy forwarding proxy used only because routers are constructed before the lifespan starts the real source)
- Pattern: Strategy + a deferred-proxy adapter for the ordering problem between router construction and app startup

**PriceUpdate (frozen dataclass):**
- Purpose: Immutable value object for one ticker's latest price state (ticker, price, previous_price, timestamp, derived `change`/`change_percent`/`direction`)
- Examples: `backend/app/market/models.py`
- Pattern: Value object, `to_dict()` for JSON/SSE serialization

**RepositoryError hierarchy:**
- Purpose: Domain-specific exceptions from `app/db` (e.g. `DuplicateTickerError`, `UnknownTickerError`, `InvalidTradeError`) each documenting the HTTP status the API layer should map it to
- Examples: `backend/app/db/errors.py`, mapped centrally in `backend/app/api/errors.py`
- Pattern: Exception-carries-intent — the persistence layer decides the HTTP semantics, the API layer just translates

**Router factories:**
- Purpose: Every FastAPI router (`create_health_router`, `create_portfolio_router`, `create_watchlist_router`, `create_stream_router`, `create_chat_router`) is a function returning an `APIRouter`, parameterized by the shared state it needs
- Examples: `backend/app/api/portfolio.py:65`, `backend/app/market/stream.py`, `backend/app/llm/router.py:30`
- Pattern: Avoids module-level singletons; all shared state (`PriceCache`, `MarketDataSource`) is constructed once in `create_app()` (`backend/app/main.py:66`) and threaded through explicitly — important for tests, which build isolated app instances

## Entry Points

**Backend process:**
- Location: `backend/app/main.py` (module-level `app = create_app()` at line 166, run via `uvicorn app.main:app`)
- Triggers: Docker `CMD` / `uv run uvicorn app.main:app` in dev
- Responsibilities: Sequential startup (init DB → seed → start market source → start snapshot loop), router mounting, static file mounting for the Next.js export

**Frontend page:**
- Location: `frontend/src/app/page.tsx` (`Terminal` component, Next.js App Router root page)
- Triggers: Browser navigation to `/`
- Responsibilities: Compose hooks and components into the trading terminal layout; owns `selected` ticker and `chatCollapsed` UI state

**SSE stream:**
- Location: `backend/app/market/stream.py` (`create_stream_router`), mounted in `main.py:100`
- Triggers: Browser `EventSource` connection to `GET /api/stream/prices`
- Responsibilities: Long-lived connection pushing `PriceUpdate` diffs based on `PriceCache.version`

## Architectural Constraints

- **Threading:** Backend is a single asyncio event loop (uvicorn). Blocking work (LLM calls, DB snapshot writes) is explicitly pushed off-loop via `asyncio.to_thread` (`backend/app/llm/router.py:52`, `backend/app/main.py:59`). `PriceCache` (`backend/app/market/cache.py`) is documented as thread-safe (lock-protected) specifically because the Massive/simulator background task and the snapshot thread-pool calls can touch it concurrently with the event loop.
- **Global state:** Module-level `app = create_app()` singleton in `backend/app/main.py:166` is the only true module-level global; all other shared state (`PriceCache`, `MarketDataSource`) lives on `app.state` and is threaded through router factories rather than imported as globals.
- **Startup ordering:** Strictly sequential and load-bearing — DB init/seed must complete before the market source starts, which must complete before the snapshot loop starts, which must complete before the app accepts requests (documented in `main.py` module docstring and PLAN.md §7). Router construction happens *before* the market source exists, which is why `_DeferredMarketSource` (`main.py:113`) exists as a forwarding proxy — a real architectural workaround for that ordering constraint, not incidental complexity.
- **No streaming for chat:** `/api/chat` returns one complete JSON payload; deliberately not SSE/streamed, since structured-output parsing needs the full response anyway (PLAN.md §9).
- **Single-user hardcoded:** Every DB table and helper function defaults `user_id="default"`; there is no auth layer. This is a deliberate simplification, not an oversight — do not add multi-user logic without a corresponding schema/API review.

## Anti-Patterns

### Deferred market-source proxy (intentional, not a bug)

**What happens:** `_DeferredMarketSource` (`backend/app/main.py:113`) implements the full `MarketDataSource` ABC but every method just forwards to `app.state.market_source`, raising `RuntimeError` if called before startup completes.

**Why it's wrong (superficially):** Looks like an unnecessary indirection layer over a simple object reference.

**Do this instead:** Understand it's required — the chat router is built by `create_chat_router` before `create_app()`'s lifespan has started the real `MarketDataSource`. Do not "simplify" this by passing `market_source` directly into `create_chat_router` at router-construction time; that would silently capture `None` and break LLM-driven watchlist changes. Any future refactor touching router wiring order must preserve this indirection or restructure startup ordering deliberately.

### Frontend response shape defensiveness

**What happens:** `frontend/src/lib/api.ts` normalizes API responses defensively — e.g. `fetchWatchlist()` accepts either a bare array or `{ watchlist: [...] }`, and every numeric field goes through a `num()` guard that coerces non-finite/non-number values to `0`.

**Why it's a smell:** This suggests the backend response shape has been unstable or under-specified during development; new frontend code may be tempted to keep adding fallback branches instead of tightening the actual API contract.

**Do this instead:** When touching `app/api/schemas.py`, treat it as the single source of truth for response shape and update `frontend/src/lib/types.ts` + `api.ts` normalization to match exactly, removing now-unnecessary fallback branches rather than adding new ones.

## Error Handling

**Strategy:** Backend raises domain-specific exceptions from `app/db` (`RepositoryError` subclasses); `backend/app/api/errors.py` registers FastAPI exception handlers that map them to `{"detail": "..."}` JSON with the status codes documented in PLAN.md §8 (400 invalid trade, 404 unknown ticker, 409 duplicate ticker). The LLM client (`app/llm/client.py`) never raises — a failed/malformed completion degrades to an apology message with no actions, so a broken LLM call cannot 500 the chat endpoint.

**Patterns:**
- Persistence layer owns error *semantics* (which HTTP status), API layer only translates (`backend/app/db/errors.py` docstrings name the mapped status per error type)
- Chat trade/watchlist execution is non-atomic and per-item: `execute_trades`/`execute_watchlist_changes` (`backend/app/llm/executor.py`) report per-action `status`/`error` rather than failing the whole request
- Frontend surfaces API errors via `ApiError` (`frontend/src/lib/api.ts:10`), caught in `useTerminal`'s `run()` wrapper (`frontend/src/hooks/useTerminal.ts:54`) and shown/dismissed via `TradeBar`'s error prop

## Cross-Cutting Concerns

**Logging:** Standard library `logging` module, one logger per module (`logger = logging.getLogger(__name__)`); notable use in `main.py` snapshot loop (catches and logs exceptions without killing the background task) and static-dir-missing warning.

**Validation:** Pydantic models for all request/response bodies (`backend/app/api/schemas.py`, `backend/app/llm/schemas.py`); `normalize_ticker()` (`backend/app/market/interface.py`) is the single shared ticker-canonicalization function applied at both the market-data layer and API layer so cache keys and DB rows stay consistent regardless of input casing.

**Authentication:** None. Single hardcoded `user_id="default"` throughout, by design (PLAN.md §7).

---

*Architecture analysis: 2026-08-16*
