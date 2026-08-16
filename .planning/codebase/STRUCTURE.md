# Codebase Structure

**Analysis Date:** 2026-08-16

## Directory Layout

```
finally/
├── frontend/                      # Next.js TypeScript project (static export)
│   ├── src/
│   │   ├── app/                   # Next.js App Router — page.tsx, layout.tsx, globals.css
│   │   ├── components/            # Presentational React components (+ colocated *.test.tsx)
│   │   ├── hooks/                 # State/data hooks (usePriceStream, useTerminal) (+ *.test.ts)
│   │   └── lib/                   # api.ts (fetch wrapper), types.ts, format.ts
│   ├── out/                       # Build output of `next build` (static export; gitignored)
│   ├── next.config.ts             # `output: 'export'` static export config
│   ├── vitest.config.ts / vitest.setup.ts   # Frontend unit test config (Vitest + RTL)
│   └── package.json
├── backend/                       # FastAPI uv project (Python)
│   ├── app/
│   │   ├── main.py                # App factory, lifespan, router mounting — entry point
│   │   ├── api/                   # REST routers, Pydantic schemas, error mapping, deps
│   │   ├── db/                    # SQLite schema, seed, and all SQL (one module per domain)
│   │   ├── market/                # Price simulation, Massive client, cache, SSE stream
│   │   └── llm/                   # Chat endpoint, LLM client/mock, trade/watchlist executor
│   ├── tests/                     # pytest — mirrors app/ package structure (api/, db/, market/, llm/)
│   ├── market_data_demo.py        # Standalone Rich terminal demo script
│   └── pyproject.toml             # uv project manifest (hatchling build backend)
├── planning/                      # Project-wide docs for agents
│   ├── PLAN.md                    # Canonical spec (source of truth for behavior)
│   ├── MARKET_DATA_SUMMARY.md     # Completed-subsystem summary
│   └── archive/                   # Historical design docs
├── .planning/                     # GSD workflow state (phases, codebase maps — this directory)
│   └── codebase/                  # Generated codebase map docs (this file lives here)
├── db/                             # Runtime volume mount point; finally.db created here (gitignored)
├── test/                          # Playwright E2E tests + docker-compose.test.yml
│   └── tests/                     # E2E test specs
├── scripts/                       # start/stop scripts (mac + windows)
├── Dockerfile                     # Multi-stage build: Node 20 (frontend) → Python 3.12 (runtime)
├── docker-compose.yml             # Convenience wrapper for local run
└── .env.example                   # Documented env vars (actual .env is gitignored)
```

## Directory Purposes

**`frontend/src/app/`:**
- Purpose: Next.js App Router root — the single page of the SPA
- Contains: `page.tsx` (top-level `Terminal` component), `layout.tsx`, `globals.css`, `icon.svg`
- Key files: `frontend/src/app/page.tsx` composes all hooks/components

**`frontend/src/components/`:**
- Purpose: Presentational, mostly-stateless UI pieces; receive data and callbacks as props from `page.tsx`
- Contains: One `.tsx` per UI element, with a colocated `.test.tsx` for the ones covered by unit tests (`Watchlist`, `Header`, `PositionsTable`, `PriceCell`, `ChatPanel`)
- Key files: `Watchlist.tsx`, `PriceChart.tsx`, `Heatmap.tsx`, `PnlChart.tsx`, `PositionsTable.tsx`, `TradeBar.tsx`, `ChatPanel.tsx`, `Header.tsx`, `PriceCell.tsx`, `Sparkline.tsx`, `Panel.tsx`

**`frontend/src/hooks/`:**
- Purpose: All client-side state and side-effect logic (data fetching, SSE, derived calculations)
- Contains: `usePriceStream.ts` (SSE + tick history for sparklines), `useTerminal.ts` (REST polling for portfolio/watchlist/history, live P&L overlay, trade/watchlist actions)
- Key files: both have colocated `.test.ts`

**`frontend/src/lib/`:**
- Purpose: Framework-agnostic client utilities — leaf dependency for hooks/components
- Contains: `api.ts` (typed fetch wrapper + response normalization + `ApiError`), `types.ts` (shared TS interfaces), `format.ts` (display formatting helpers)

**`backend/app/api/`:**
- Purpose: HTTP boundary layer — routers, request/response schemas, error-to-status mapping
- Contains: `portfolio.py`, `watchlist.py`, `health.py`, `schemas.py`, `errors.py`, `deps.py`, `__init__.py` (re-exports router factories)

**`backend/app/db/`:**
- Purpose: The only layer permitted to issue SQL; SQLite schema, seeding, and per-domain CRUD
- Contains: `connection.py`, `schema.py`, `init_db.py`, `seed.py`, `profile.py`, `watchlist.py`, `positions.py`, `portfolio.py` (trade execution), `snapshots.py`, `chat.py`, `models.py`, `errors.py`

**`backend/app/market/`:**
- Purpose: Live/simulated price generation, thread-safe caching, SSE delivery
- Contains: `models.py` (`PriceUpdate`), `interface.py` (`MarketDataSource` ABC + `normalize_ticker`), `cache.py` (`PriceCache`), `simulator.py` (GBM simulator), `massive_client.py` (Polygon.io REST poller), `factory.py`, `stream.py`, `seed_prices.py`

**`backend/app/llm/`:**
- Purpose: `/api/chat` endpoint — context building, LLM call (real or mocked), auto-execution of trades/watchlist changes, chat persistence
- Contains: `router.py`, `context.py`, `client.py`, `mock.py`, `executor.py`, `schemas.py`

**`backend/tests/`:**
- Purpose: pytest suite, mirrors `app/` package layout exactly (`tests/api/`, `tests/db/`, `tests/market/`, `tests/llm/`), plus a root `conftest.py`
- Generated: No. Committed: Yes.

**`test/`:**
- Purpose: Playwright E2E tests, run against a Dockerized full-stack container via `docker-compose.test.yml`
- Contains: `tests/` (specs), `playwright-report/` and `test-results/` (generated, gitignored)

**`db/`:**
- Purpose: Runtime volume mount target; `finally.db` (SQLite) is created here by the backend on first request
- Generated: Yes (the `.db` file). Committed: No — only a `.gitkeep` is tracked.

**`planning/`:**
- Purpose: Project-wide agent-facing documentation — `PLAN.md` is the canonical spec referenced from `CLAUDE.md`
- Contains: `PLAN.md`, `MARKET_DATA_SUMMARY.md`, `archive/` (historical/completed design docs)

**`.planning/`:**
- Purpose: GSD workflow state — phase plans and generated codebase maps (this document's home: `.planning/codebase/`)

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app factory (`create_app`), module-level `app` instance, lifespan/startup sequencing
- `frontend/src/app/page.tsx`: Top-level React page component

**Configuration:**
- `backend/pyproject.toml`: Python deps, pytest/ruff/coverage config, hatchling build
- `frontend/package.json`, `frontend/next.config.ts`, `frontend/tsconfig.json`: Frontend build/tooling config
- `.env.example` (root): Documented env vars (`OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`)
- `Dockerfile`, `docker-compose.yml`: Container build and local orchestration

**Core Logic:**
- `backend/app/market/simulator.py`: GBM price simulation math
- `backend/app/market/massive_client.py`: Real market data polling
- `backend/app/db/portfolio.py`: Trade execution logic
- `backend/app/llm/executor.py`: Auto-execution of LLM-directed trades/watchlist changes
- `frontend/src/hooks/useTerminal.ts`: Client-side portfolio/watchlist state and live P&L overlay

**Testing:**
- `backend/tests/`: pytest, mirrors `backend/app/` structure 1:1
- `frontend/src/**/*.test.tsx` / `*.test.ts`: Vitest + React Testing Library, colocated with source
- `test/tests/`: Playwright E2E specs (run against the Dockerized app, `LLM_MOCK=true`)

## Naming Conventions

**Files:**
- Backend Python: `snake_case.py`, one module per domain/concern (e.g. `watchlist.py`, `massive_client.py`)
- Backend tests: `test_<module>.py`, mirrors the source module name exactly (e.g. `app/market/cache.py` → `tests/market/test_cache.py`)
- Frontend components: `PascalCase.tsx` matching the exported component name (e.g. `PriceChart.tsx` exports `PriceChart`)
- Frontend hooks: `camelCase.ts` prefixed `use` (e.g. `usePriceStream.ts`, `useTerminal.ts`)
- Frontend tests: `<SourceFile>.test.tsx` / `.test.ts`, colocated in the same directory as the source file (not a separate `__tests__/` tree)
- Frontend lib utilities: `camelCase.ts` (`api.ts`, `format.ts`, `types.ts`)

**Directories:**
- Backend: lowercase, singular-domain names under `app/` (`api`, `db`, `market`, `llm`) — each is a Python package with an `__init__.py` that re-exports its public factory functions/types
- Frontend: lowercase under `src/` (`app`, `components`, `hooks`, `lib`) following Next.js App Router conventions

## Where to Add New Code

**New backend REST endpoint:**
- Router: add a `create_<name>_router()` factory function in a new or existing file under `backend/app/api/`, following the pattern in `backend/app/api/portfolio.py` (factory takes shared state like `PriceCache` as a parameter, returns `APIRouter`)
- Register it: mount via `app.include_router(...)` in `backend/app/main.py`'s `create_app()`
- Schemas: add Pydantic request/response models to `backend/app/api/schemas.py`
- Tests: add `backend/tests/api/test_<name>.py`

**New database operation:**
- Add the function to the relevant domain module in `backend/app/db/` (e.g. new watchlist query → `backend/app/db/watchlist.py`), following the existing signature convention (optional trailing `conn: sqlite3.Connection | None = None`, `user_id: str = DEFAULT_USER_ID`)
- Export it from `backend/app/db/__init__.py`
- Raise a `RepositoryError` subclass from `backend/app/db/errors.py` for domain errors (add a new subclass there if none fits, and document its HTTP status in the docstring)
- Tests: add to `backend/tests/db/test_<domain>.py`

**New market data source:**
- Implement `MarketDataSource` (`backend/app/market/interface.py`) as a new class in `backend/app/market/`
- Wire selection logic into `backend/app/market/factory.py`
- Tests: add `backend/tests/market/test_<name>.py`, plus conformance coverage in `test_interface.py`

**New frontend UI component:**
- Add `frontend/src/components/<Name>.tsx`; keep it presentational (props in, callbacks out) — do not fetch data directly inside components, route data through a hook
- If it needs new state or side effects, add/extend a hook in `frontend/src/hooks/`
- Add types to `frontend/src/lib/types.ts` if the shape is shared across components
- Tests: colocate `<Name>.test.tsx` next to the component using Vitest + React Testing Library

**New API call from frontend:**
- Add a typed function to `frontend/src/lib/api.ts` following the existing pattern (call `request<T>()`, normalize the raw response defensively, return a typed shape)
- Add/extend the corresponding type in `frontend/src/lib/types.ts`

**Utilities:**
- Backend shared helpers: colocate within the relevant package (`app/market/interface.py` for `normalize_ticker`, etc.) rather than a generic `utils.py`
- Frontend shared helpers: `frontend/src/lib/format.ts` for display formatting; `frontend/src/lib/types.ts` for shared type definitions

**New E2E scenario:**
- Add a spec file under `test/tests/`, run against the Dockerized stack with `LLM_MOCK=true` per `docker-compose.test.yml`

## Special Directories

**`frontend/out/`:**
- Purpose: `next build` static export output, copied into the backend's `static/` directory at Docker build time (`Dockerfile` stage 1 → stage 2)
- Generated: Yes. Committed: No (gitignored).

**`backend/static/`** (referenced by `app/main.py`, not present in source tree):
- Purpose: Where the Docker build copies `frontend/out/` so FastAPI can serve it via `StaticFiles`; absent in local dev, so `/api/*` still works without a full frontend build (`main.py` logs a warning and serves API-only)
- Generated: Yes (Docker build only). Committed: No.

**`db/`:**
- Purpose: Docker volume mount target for the SQLite file (`FINALLY_DB_PATH=/app/db/finally.db` in the container)
- Generated: Yes (`finally.db`). Committed: No — only `.gitkeep`.

**`backend/.venv/`, `backend/.pytest_cache/`, `backend/.ruff_cache/`, `frontend/node_modules/`, `frontend/.next/`:**
- Purpose: Local tool/dependency caches and build artifacts
- Generated: Yes. Committed: No.

**`planning/archive/`:**
- Purpose: Historical/superseded design docs (e.g. earlier market-data design iterations), kept for reference but not authoritative
- Generated: No. Committed: Yes.

---

*Structure analysis: 2026-08-16*
