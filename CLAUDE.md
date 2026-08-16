# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory.

The key document is PLAN.md included in full below; the market data component has been completed and is summarized in the file `planning/MARKET_DATA_SUMMARY.md` with more details in the `planning/archive` folder. Consult these docs only when required. The remainder of the platform is still to be developed.

@planning/PLAN.md

<!-- GSD:project-start source:PROJECT.md -->
## Project

**FinAlly — Hardening Pass**

FinAlly is an AI-powered trading workstation (Bloomberg-terminal-style UI, simulated portfolio, LLM chat copilot) built as a capstone project for an agentic AI coding course. The full v1 application — live market data streaming, portfolio/trading, watchlist management, AI chat with auto-executed trades, and the terminal frontend — is already built and passing its test suite (266 backend + 39 frontend tests). This GSD milestone is a **hardening pass**: fixing known fragile areas, closing test coverage gaps, resolving perf nits, and clearing dependency drift — all surfaced by an independent codebase audit (`.planning/codebase/CONCERNS.md`). No new user-facing features are in scope.

**Core Value:** The existing trading-workstation experience must keep working exactly as-is while every specific reliability, coverage, performance, and dependency risk identified in the codebase audit is closed out — without regressing the 305 passing tests.

### Constraints

- **Regression safety**: All 305 existing tests (266 backend + 39 frontend) must continue passing after every change in this milestone; the Playwright E2E suite in `test/` should also be re-run before considering the milestone done.
- **Static export criticality**: `frontend/next.config.ts`'s `output: 'export'` must keep working after the Next.js major-version bump — this is the single point where a regression would silently break the production Docker image, per `.planning/codebase/CONCERNS.md`.
- **No new features**: Changes in this milestone are fixes/hardening only, scoped strictly to the items above.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12+ (backend) - `backend/app/`, `backend/tests/` — targets `py312` per `backend/pyproject.toml`; dev container runs 3.13
- TypeScript 5.7.3 (frontend) - `frontend/src/`
- SQL (embedded in Python strings) - `backend/app/db/schema.py` (SQLite schema/DDL)
- Bash / PowerShell - `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1`
## Runtime
- Python 3.12+ (backend), managed by `uv`
- Node.js 20 (frontend build — `node:20-slim` in `Dockerfile` stage 1; also used by the Playwright test runner in `test/docker-compose.test.yml`)
- Backend: `uv` (`backend/pyproject.toml`, `backend/uv.lock`) — lockfile present, `uv sync --locked` used in Docker build
- Frontend: `npm` (`frontend/package.json`, `frontend/package-lock.json`) — lockfile present, `npm ci` used in Docker build
- E2E tests: `npm` (`test/package.json`, `test/package-lock.json`)
## Frameworks
- FastAPI ≥0.115.0 - `backend/app/main.py` — REST API + SSE streaming + static file serving, single ASGI app
- Uvicorn `[standard]` ≥0.32.0 - ASGI server, entrypoint `uvicorn app.main:app` (see `Dockerfile` CMD)
- Next.js 15.5.23 (App Router) - `frontend/src/app/` — built with `output: "export"` for production (static export), served by FastAPI
- React 19.0.0 / React DOM 19.0.0 - `frontend/src/components/`
- pytest ≥8.3.0 + pytest-asyncio ≥0.24.0 + pytest-cov ≥5.0.0 - `backend/tests/` (config in `backend/pyproject.toml` `[tool.pytest.ini_options]`, `asyncio_mode = "auto"`)
- Vitest 3.2.7 + @testing-library/react 16.2.0 + jsdom 26.0.0 - `frontend/src/**/*.test.tsx` (config: `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`)
- Playwright ^1.62.1 - `test/tests/` E2E suite, config `test/playwright.config.ts`, driven via `test/docker-compose.test.yml`
- Tailwind CSS ^4.3.3 (`@tailwindcss/postcss`) - `frontend/postcss.config.mjs`, `frontend/src/app/globals.css`
- ESLint 9.18.0 (flat config, `eslint-config-next` 15.5.23) - `frontend/eslint.config.mjs`
- Ruff ≥0.7.0 - `backend/pyproject.toml` `[tool.ruff]` (line-length 100, rules `E,F,I,N,W`, target `py312`)
- TypeScript compiler 5.7.3 (noEmit, strict mode) - `frontend/tsconfig.json`
## Key Dependencies
- `litellm` ≥1.96.2 - `backend/app/llm/client.py` — routes chat completions through OpenRouter to Cerebras inference (`openrouter/openai/gpt-oss-120b`, structured output via `response_format`)
- `massive` ≥1.0.0 (Polygon.io Python SDK) - `backend/app/market/massive_client.py` — optional real market-data REST client
- `numpy` ≥2.0.0 - used by the GBM price simulator (`backend/app/market/simulator.py`)
- `pydantic` ≥2.12.5 - request/response schemas (`backend/app/api/schemas.py`, `backend/app/llm/schemas.py`)
- `recharts` 3.10.1 - `frontend/src/components/PnlChart.tsx`, `PriceChart.tsx`, `Heatmap.tsx` — canvas/SVG charting
- `rich` ≥13.0.0 - `backend/market_data_demo.py` (terminal dashboard demo, not part of the served app)
- Python stdlib `sqlite3` - `backend/app/db/connection.py` — no ORM; hand-written SQL via `sqlite3.Row`
## Configuration
- `.env` file at project root (gitignored; `.env.example` committed) — loaded via `--env-file .env` in `docker-compose.yml` and the start scripts
- Variables: `OPENROUTER_API_KEY` (required for live LLM chat), `MASSIVE_API_KEY` (optional — presence toggles real market data vs. simulator, see `backend/app/market/factory.py`), `LLM_MOCK` (optional, `"true"` enables deterministic mock chat responses)
- `FINALLY_DB_PATH` env var overrides the SQLite file location (`backend/app/db/connection.py`); defaults to `<repo>/db/finally.db`, and is set to `/app/db/finally.db` inside the Docker image
- `.env` file existence noted only — contents not read/quoted here per security policy
- `frontend/next.config.ts` — conditional config: dev mode adds an `/api/*` rewrite proxy to `http://localhost:8000`; non-dev (build) mode sets `output: "export"` for the static export FastAPI serves
- `backend/pyproject.toml` — project metadata, dependency groups (`dev` extra), Ruff/pytest/coverage config
- `Dockerfile` — multi-stage build: Stage 1 `node:20-slim` builds the Next.js static export (`npm ci && npm run build`); Stage 2 `python:3.12-slim` installs backend deps via `uv sync --locked`, copies the frontend export into `/app/static`, exposes port 8000
## Platform Requirements
- Python 3.12+ with `uv` installed; run `uv sync --extra dev` in `backend/`
- Node 20+ with `npm` in `frontend/`
- Docker (for full-stack container build/run and E2E tests)
- Single Docker container, single port (8000), per `docker-compose.yml`
- SQLite database persisted via Docker named volume mounted at `/app/db` (host `./db/`)
- Deployable to any container platform (App Runner, Render, etc.) — no external service dependencies beyond OpenRouter/Massive APIs
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Backend (Python): `snake_case.py`, one module per concern inside a package (`app/db/portfolio.py`, `app/market/simulator.py`). Test files mirror source module names: `tests/db/test_portfolio.py` for `app/db/portfolio.py`.
- Frontend (TypeScript/React): `PascalCase.tsx` for components (`Watchlist.tsx`, `PriceCell.tsx`), `camelCase.ts` for hooks/libs (`usePriceStream.ts`, `format.ts`, `api.ts`). Test files are co-located and suffixed `.test.tsx`/`.test.ts` (`PriceCell.test.tsx` next to `PriceCell.tsx`).
- Python: `snake_case`, verb-first (`execute_trade`, `get_cash_balance`, `list_positions`, `build_portfolio`). Factory functions prefixed `create_` (`create_portfolio_router`, `create_market_data_source`, `create_chat_router`).
- TypeScript: `camelCase`, verb-first for actions/fetchers (`fetchPortfolio`, `sendChat`, `executeTrade`), `use` prefix for hooks (`usePriceStream`, `useTerminal`).
- Python: `snake_case` throughout, including SQL-adjacent identifiers (`current_price`, `avg_cost`, `cost_basis`).
- TypeScript: `camelCase` for locals, `SCREAMING_SNAKE_CASE` for module-level constants (`MAX_HISTORY`, `DEFAULT_WATCHLIST`).
- Python: Pydantic models and dataclasses use `PascalCase` with an `Out`/`Request`/`Response` suffix convention for API schemas (`PositionOut`, `TradeRequest`, `TradeResponse`, `PortfolioOut`) — see `backend/app/api/schemas.py`. Domain dataclasses have no suffix (`Trade`, `PriceUpdate`).
- TypeScript: `PascalCase` interfaces/types in `frontend/src/lib/types.ts`, imported with `import type { ... }`.
## Code Style
- No explicit Python formatter configured (no `black`/`ruff format` section in `backend/pyproject.toml`); `ruff` is lint-only. Line length is 100 (`[tool.ruff] line-length = 100`), and `E501` (line-too-long) is explicitly ignored, implying formatting discipline is manual/convention-based rather than enforced by a formatter.
- Frontend has no dedicated Prettier config file; formatting follows ESLint's `next/core-web-vitals` + `next/typescript` presets (`frontend/eslint.config.mjs`).
- Backend: `ruff` with `select = ["E", "F", "I", "N", "W"]` (pycodestyle errors/warnings, pyflakes, isort, pep8-naming) — see `backend/pyproject.toml`. Run via `uv run --extra dev ruff check app/ tests/` (documented in `backend/CLAUDE.md`).
- Frontend: ESLint flat config (`frontend/eslint.config.mjs`) extending `next/core-web-vitals` and `next/typescript` via `FlatCompat`. Run via `npm run lint` (`frontend/package.json`).
## Import Organization
- Ruff's `I` (isort) rule enforces this ordering automatically.
- External/library imports first, then local imports using the `@/` path alias (`@/lib/format`, `@/lib/types`), then relative imports for same-directory files (`./PriceCell`).
- `import type { ... }` used for type-only imports (see `frontend/src/hooks/usePriceStream.ts`, `frontend/src/lib/api.ts`).
- Frontend: `@/*` maps to `src/*` (`frontend/tsconfig.json` `paths`, mirrored in `frontend/vitest.config.ts` `resolve.alias`).
- Backend: no path aliases; the `app` package is imported absolutely (`from app.db import ...`, `from app.market import ...`) after `uv sync` installs the project in editable mode.
## Error Handling
- The repository layer (`backend/app/db/`) defines one custom exception hierarchy rooted at `RepositoryError` (`backend/app/db/errors.py`). Each subclass's docstring documents the HTTP status it should map to (`DuplicateTickerError` -> 409, `TickerNotFoundError`/`UnknownTickerError` -> 404, `InvalidTickerError`/`InvalidTradeError` -> 400, `ProfileNotFoundError` -> 500). The repository layer never imports FastAPI.
- A single mapping module, `backend/app/api/errors.py`, converts `RepositoryError` -> HTTP response via `register_exception_handlers(app)` and a `STATUS_BY_ERROR` dict resolved through the exception's MRO (so subclasses inherit their parent's status). Routes let errors propagate — no per-route `try/except`.
- All API errors return `{"detail": "human-readable message"}` (per `planning/PLAN.md` §8). 5xx errors are logged with `logger.exception`; 4xx errors are not.
- Validation lives in exactly one place per concern: `execute_trade()` in `backend/app/db/portfolio.py` is documented as "the single writer of cash, positions, and the trade log" so both the REST endpoint and the LLM's auto-executed trades share identical validation and can't drift apart.
- A small floating-point epsilon (`EPSILON = 1e-9`) is used throughout money/share comparisons in `backend/app/db/portfolio.py` to avoid residue like `1e-16` shares or off-by-a-fraction-of-a-cent cash mismatches — follow this pattern for any new money-math code.
- `app/llm/client.py` never raises: a failed or malformed LLM completion degrades to an apology message with no executed actions, rather than propagating an exception to the chat endpoint (documented in `backend/CLAUDE.md`).
- `frontend/src/lib/api.ts` defines a single `ApiError extends Error` class carrying `status`; the shared `request<T>()` helper throws it for any non-OK response, extracting `detail` from the JSON body when present, else falling back to a generic `Request failed (${status})` message.
- All API response shapes are defensively normalized (never trust the wire format blindly): helper functions like `normalizePosition`, `num()`, and the watchlist/history parsers coerce `unknown` JSON into typed values, tolerating both bare-array and wrapped-object response shapes. Follow this "coerce, don't assume" pattern for new API consumers.
- `frontend/src/hooks/usePriceStream.ts`'s `coerce()`/`parsePriceEvent()` functions apply the same defensive-parsing pattern to SSE payloads — malformed or partial data degrades to being skipped, not to throwing.
## Comments
- Module-level docstrings (Python) and JSDoc-style block comments (TypeScript) explain *why*, not *what* — e.g. `backend/app/db/portfolio.py`'s module docstring explains why `execute_trade` is the single writer, and `frontend/src/components/PriceCell.tsx` explains why the flashing span is remounted with a fresh `key`.
- Inline comments call out non-obvious tradeoffs and reference `PLAN.md` sections directly, e.g. `# PLAN.md §7: a snapshot is recorded immediately after every trade...` in `backend/app/api/portfolio.py`, and `// PLAN §2` in `frontend/src/hooks/usePriceStream.ts`. New code touching spec-driven behavior should cite the relevant `PLAN.md` section the same way.
- Test files often carry a one-line module docstring/comment describing the test file's overall guarantee (e.g. `backend/tests/llm/test_mock.py`: `"""The mock responder must be deterministic and match its documented trigger phrases."""`).
- Used selectively on exported functions/hooks/components to document behavior and edge cases, not on every function (see `usePriceStream`, `PriceCell`, `parsePriceEvent` in `frontend/src/`). Not enforced by a lint rule.
- Every public function and module in `backend/app/` has a docstring; docstrings on exceptions in `backend/app/db/errors.py` double as the source of truth for HTTP-status mapping.
## Function Design
- Python repository functions consistently accept `user_id: str = DEFAULT_USER_ID` and an optional trailing `conn: sqlite3.Connection | None = None` so callers can group multiple writes into a single transaction, or let the call manage its own connection (documented pattern in `backend/CLAUDE.md` and used throughout `backend/app/db/`).
- Router-factory functions accept dependencies as parameters and return an `APIRouter` (`create_portfolio_router(user_id=...)`, `create_chat_router(price_cache, market_source)`) rather than using global routers — enables isolated test apps (see `backend/tests/api/conftest.py`).
- Backend repository functions return typed dataclasses/Pydantic models, never raw SQLite rows.
- Frontend API functions always return normalized, typed values (never raw `unknown` JSON) — normalization happens once, at the boundary in `frontend/src/lib/api.ts`.
## Module Design
- Backend: each subpackage (`app/db`, `app/market`, `app/llm`, `app/api`) has an `__init__.py` that re-exports its public surface, so consumers import from the package root (`from app.db import execute_trade, DuplicateTickerError`) instead of reaching into submodules. This is the documented, expected import style (`backend/CLAUDE.md`).
- Frontend: no barrel files observed; components/hooks/lib modules are imported directly by path (`@/lib/format`, `@/components/PriceCell`).
- Used on the backend (via `__init__.py` re-exports) but not on the frontend.
- The market-data layer defines an abstract `MarketDataSource` interface (`backend/app/market/interface.py`) implemented by both `SimulatorDataSource` and `MassiveDataSource`; a `create_market_data_source()` factory selects the implementation based on `MASSIVE_API_KEY`. New market-data-like subsystems should follow this same interface + factory pattern, as recommended by `planning/PLAN.md` §6.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- Strategy pattern for market data: `MarketDataSource` ABC with two interchangeable implementations selected at startup by an env var (`market/factory.py`)
- Single shared mutable cache (`PriceCache`) is the only coupling point between the market-data background task and both the SSE stream and portfolio valuation — producers/consumers never talk directly
- Router-factory pattern throughout the backend: every FastAPI router is built by a `create_*_router(...)` function that closes over its dependencies (price cache, market source, user_id) rather than using module-level globals, so state can be constructed once in `create_app()` and passed down explicit
- Repository-style `app/db` layer: no ORM, raw `sqlite3`, one function per operation, domain-specific exception types instead of generic DB errors
- Frontend state is split into two independent hooks by data-transport: `usePriceStream` (push, SSE, high-frequency) vs `useTerminal` (pull, REST polling every 15s, low-frequency), composed together only in `page.tsx`
## Layers
- Purpose: Render UI, dumb w.r.t. business logic — receive data/callbacks as props
- Location: `frontend/src/components/*.tsx`
- Contains: `Watchlist`, `PriceChart`, `Heatmap`, `PnlChart`, `PositionsTable`, `TradeBar`, `ChatPanel`, `Header`, `PriceCell`, `Sparkline`, `Panel`
- Depends on: hooks (via props passed from `page.tsx`), `lib/types.ts` for shapes
- Used by: `frontend/src/app/page.tsx`
- Purpose: Own all client-side state and side effects (SSE subscription, REST polling, derived calculations like live P&L)
- Location: `frontend/src/hooks/usePriceStream.ts`, `frontend/src/hooks/useTerminal.ts`
- Contains: `EventSource` lifecycle, `useState`/`useEffect`/`useMemo` state machines
- Depends on: `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
- Used by: `frontend/src/app/page.tsx`
- Purpose: Typed fetch wrapper + response normalization (`api.ts`), shared TS types (`types.ts`), display formatting (`format.ts`)
- Location: `frontend/src/lib/*.ts`
- Depends on: nothing internal (leaf layer)
- Used by: hooks and components
- Purpose: HTTP boundary — request validation (Pydantic), routing, error-to-status-code mapping
- Location: `backend/app/api/*.py`
- Contains: `portfolio.py` (portfolio + trade endpoints), `watchlist.py`, `health.py`, `schemas.py` (Pydantic models), `errors.py` (exception handlers), `deps.py` (FastAPI `Depends` providers)
- Depends on: `app.db`, `app.market`
- Used by: `app/main.py`
- Purpose: Produce and cache live/simulated prices, expose them over SSE
- Location: `backend/app/market/*.py`
- Contains: `models.py` (`PriceUpdate`), `interface.py` (ABC + `normalize_ticker`), `cache.py` (`PriceCache`), `simulator.py` (GBM), `massive_client.py` (Polygon poller), `factory.py`, `stream.py`, `seed_prices.py`
- Depends on: `numpy`, `massive` SDK
- Used by: `app/main.py`, `app/api/portfolio.py` (for valuation), `app/llm` (for chat context)
- Purpose: Sole owner of all SQL; SQLite schema, seeding, and CRUD per domain
- Location: `backend/app/db/*.py`
- Contains: `connection.py`, `schema.py`, `init_db.py`, `seed.py`, `profile.py`, `watchlist.py`, `positions.py`, `portfolio.py` (trade execution), `snapshots.py`, `chat.py`, `models.py` (dataclasses), `errors.py` (`RepositoryError` subclasses)
- Depends on: stdlib `sqlite3` only
- Used by: `app/api/*`, `app/llm/executor.py`, `app/main.py` (snapshot loop, lifespan init)
- Purpose: Build portfolio+history context, call the LLM (or mock), auto-execute returned trades/watchlist changes, persist the conversation
- Location: `backend/app/llm/*.py`
- Contains: `router.py` (`/api/chat`), `context.py`, `client.py` (LiteLLM→OpenRouter→Cerebras), `mock.py` (`LLM_MOCK=true` responder), `executor.py`, `schemas.py`
- Depends on: `app.db`, `app.market` (`PriceCache`, `MarketDataSource`)
- Used by: `app/main.py` (mounted conditionally via `_include_chat_router`, so `/api/chat` degrades gracefully if the module is absent)
## Data Flow
### Live price streaming (SSE)
### Trade execution (manual, via Trade Bar)
### Chat / AI trade execution
- Server: two mutable stores — `PriceCache` (in-memory, ephemeral, per-process) and SQLite (`db/finally.db`, durable, volume-mounted). No caching layer between SQLite and the API; each request reads fresh.
- Client: React local component state only, split by transport (SSE vs REST) across `usePriceStream` and `useTerminal`; no global store (Redux/Zustand) — `page.tsx` is the sole composition point.
## Key Abstractions
- Purpose: Uniform lifecycle contract (`start`, `stop`, `add_ticker`, `remove_ticker`, `get_tickers`) so downstream code (SSE stream, chat executor, portfolio valuation) never needs to know whether prices are simulated or real
- Examples: `backend/app/market/interface.py`, `backend/app/market/simulator.py` (`SimulatorDataSource`), `backend/app/market/massive_client.py` (`MassiveDataSource`), `backend/app/main.py` (`_DeferredMarketSource` — a lazy forwarding proxy used only because routers are constructed before the lifespan starts the real source)
- Pattern: Strategy + a deferred-proxy adapter for the ordering problem between router construction and app startup
- Purpose: Immutable value object for one ticker's latest price state (ticker, price, previous_price, timestamp, derived `change`/`change_percent`/`direction`)
- Examples: `backend/app/market/models.py`
- Pattern: Value object, `to_dict()` for JSON/SSE serialization
- Purpose: Domain-specific exceptions from `app/db` (e.g. `DuplicateTickerError`, `UnknownTickerError`, `InvalidTradeError`) each documenting the HTTP status the API layer should map it to
- Examples: `backend/app/db/errors.py`, mapped centrally in `backend/app/api/errors.py`
- Pattern: Exception-carries-intent — the persistence layer decides the HTTP semantics, the API layer just translates
- Purpose: Every FastAPI router (`create_health_router`, `create_portfolio_router`, `create_watchlist_router`, `create_stream_router`, `create_chat_router`) is a function returning an `APIRouter`, parameterized by the shared state it needs
- Examples: `backend/app/api/portfolio.py:65`, `backend/app/market/stream.py`, `backend/app/llm/router.py:30`
- Pattern: Avoids module-level singletons; all shared state (`PriceCache`, `MarketDataSource`) is constructed once in `create_app()` (`backend/app/main.py:66`) and threaded through explicitly — important for tests, which build isolated app instances
## Entry Points
- Location: `backend/app/main.py` (module-level `app = create_app()` at line 166, run via `uvicorn app.main:app`)
- Triggers: Docker `CMD` / `uv run uvicorn app.main:app` in dev
- Responsibilities: Sequential startup (init DB → seed → start market source → start snapshot loop), router mounting, static file mounting for the Next.js export
- Location: `frontend/src/app/page.tsx` (`Terminal` component, Next.js App Router root page)
- Triggers: Browser navigation to `/`
- Responsibilities: Compose hooks and components into the trading terminal layout; owns `selected` ticker and `chatCollapsed` UI state
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
### Frontend response shape defensiveness
## Error Handling
- Persistence layer owns error *semantics* (which HTTP status), API layer only translates (`backend/app/db/errors.py` docstrings name the mapped status per error type)
- Chat trade/watchlist execution is non-atomic and per-item: `execute_trades`/`execute_watchlist_changes` (`backend/app/llm/executor.py`) report per-action `status`/`error` rather than failing the whole request
- Frontend surfaces API errors via `ApiError` (`frontend/src/lib/api.ts:10`), caught in `useTerminal`'s `run()` wrapper (`frontend/src/hooks/useTerminal.ts:54`) and shown/dismissed via `TradeBar`'s error prop
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| cerebras-inference | Use this to write code to call an LLM using LiteLLM and OpenRouter with the Cerebras inference provider | `.claude/skills/cerebras/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
