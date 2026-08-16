# Coding Conventions

**Analysis Date:** 2026-08-16

## Naming Patterns

**Files:**
- Backend (Python): `snake_case.py`, one module per concern inside a package (`app/db/portfolio.py`, `app/market/simulator.py`). Test files mirror source module names: `tests/db/test_portfolio.py` for `app/db/portfolio.py`.
- Frontend (TypeScript/React): `PascalCase.tsx` for components (`Watchlist.tsx`, `PriceCell.tsx`), `camelCase.ts` for hooks/libs (`usePriceStream.ts`, `format.ts`, `api.ts`). Test files are co-located and suffixed `.test.tsx`/`.test.ts` (`PriceCell.test.tsx` next to `PriceCell.tsx`).

**Functions:**
- Python: `snake_case`, verb-first (`execute_trade`, `get_cash_balance`, `list_positions`, `build_portfolio`). Factory functions prefixed `create_` (`create_portfolio_router`, `create_market_data_source`, `create_chat_router`).
- TypeScript: `camelCase`, verb-first for actions/fetchers (`fetchPortfolio`, `sendChat`, `executeTrade`), `use` prefix for hooks (`usePriceStream`, `useTerminal`).

**Variables:**
- Python: `snake_case` throughout, including SQL-adjacent identifiers (`current_price`, `avg_cost`, `cost_basis`).
- TypeScript: `camelCase` for locals, `SCREAMING_SNAKE_CASE` for module-level constants (`MAX_HISTORY`, `DEFAULT_WATCHLIST`).

**Types:**
- Python: Pydantic models and dataclasses use `PascalCase` with an `Out`/`Request`/`Response` suffix convention for API schemas (`PositionOut`, `TradeRequest`, `TradeResponse`, `PortfolioOut`) — see `backend/app/api/schemas.py`. Domain dataclasses have no suffix (`Trade`, `PriceUpdate`).
- TypeScript: `PascalCase` interfaces/types in `frontend/src/lib/types.ts`, imported with `import type { ... }`.

## Code Style

**Formatting:**
- No explicit Python formatter configured (no `black`/`ruff format` section in `backend/pyproject.toml`); `ruff` is lint-only. Line length is 100 (`[tool.ruff] line-length = 100`), and `E501` (line-too-long) is explicitly ignored, implying formatting discipline is manual/convention-based rather than enforced by a formatter.
- Frontend has no dedicated Prettier config file; formatting follows ESLint's `next/core-web-vitals` + `next/typescript` presets (`frontend/eslint.config.mjs`).

**Linting:**
- Backend: `ruff` with `select = ["E", "F", "I", "N", "W"]` (pycodestyle errors/warnings, pyflakes, isort, pep8-naming) — see `backend/pyproject.toml`. Run via `uv run --extra dev ruff check app/ tests/` (documented in `backend/CLAUDE.md`).
- Frontend: ESLint flat config (`frontend/eslint.config.mjs`) extending `next/core-web-vitals` and `next/typescript` via `FlatCompat`. Run via `npm run lint` (`frontend/package.json`).

## Import Organization

**Python:**
1. `from __future__ import annotations` first (present at the top of nearly every backend module — `app/api/portfolio.py`, `app/db/portfolio.py`, `app/api/errors.py`, `app/db/errors.py`).
2. Standard library imports (`sqlite3`, `uuid`, `logging`).
3. Third-party imports (`fastapi`, `pydantic`).
4. Local/relative imports, often via package `__init__.py` re-exports rather than deep paths — e.g. `from app.db import (DEFAULT_USER_ID, UnknownTickerError, execute_trade, ...)` in `backend/app/api/portfolio.py`, not `from app.db.portfolio import execute_trade`.
- Ruff's `I` (isort) rule enforces this ordering automatically.

**TypeScript:**
- External/library imports first, then local imports using the `@/` path alias (`@/lib/format`, `@/lib/types`), then relative imports for same-directory files (`./PriceCell`).
- `import type { ... }` used for type-only imports (see `frontend/src/hooks/usePriceStream.ts`, `frontend/src/lib/api.ts`).

**Path Aliases:**
- Frontend: `@/*` maps to `src/*` (`frontend/tsconfig.json` `paths`, mirrored in `frontend/vitest.config.ts` `resolve.alias`).
- Backend: no path aliases; the `app` package is imported absolutely (`from app.db import ...`, `from app.market import ...`) after `uv sync` installs the project in editable mode.

## Error Handling

**Backend — layered exception translation:**
- The repository layer (`backend/app/db/`) defines one custom exception hierarchy rooted at `RepositoryError` (`backend/app/db/errors.py`). Each subclass's docstring documents the HTTP status it should map to (`DuplicateTickerError` -> 409, `TickerNotFoundError`/`UnknownTickerError` -> 404, `InvalidTickerError`/`InvalidTradeError` -> 400, `ProfileNotFoundError` -> 500). The repository layer never imports FastAPI.
- A single mapping module, `backend/app/api/errors.py`, converts `RepositoryError` -> HTTP response via `register_exception_handlers(app)` and a `STATUS_BY_ERROR` dict resolved through the exception's MRO (so subclasses inherit their parent's status). Routes let errors propagate — no per-route `try/except`.
- All API errors return `{"detail": "human-readable message"}` (per `planning/PLAN.md` §8). 5xx errors are logged with `logger.exception`; 4xx errors are not.
- Validation lives in exactly one place per concern: `execute_trade()` in `backend/app/db/portfolio.py` is documented as "the single writer of cash, positions, and the trade log" so both the REST endpoint and the LLM's auto-executed trades share identical validation and can't drift apart.
- A small floating-point epsilon (`EPSILON = 1e-9`) is used throughout money/share comparisons in `backend/app/db/portfolio.py` to avoid residue like `1e-16` shares or off-by-a-fraction-of-a-cent cash mismatches — follow this pattern for any new money-math code.
- `app/llm/client.py` never raises: a failed or malformed LLM completion degrades to an apology message with no executed actions, rather than propagating an exception to the chat endpoint (documented in `backend/CLAUDE.md`).

**Frontend — defensive parsing at the API boundary:**
- `frontend/src/lib/api.ts` defines a single `ApiError extends Error` class carrying `status`; the shared `request<T>()` helper throws it for any non-OK response, extracting `detail` from the JSON body when present, else falling back to a generic `Request failed (${status})` message.
- All API response shapes are defensively normalized (never trust the wire format blindly): helper functions like `normalizePosition`, `num()`, and the watchlist/history parsers coerce `unknown` JSON into typed values, tolerating both bare-array and wrapped-object response shapes. Follow this "coerce, don't assume" pattern for new API consumers.
- `frontend/src/hooks/usePriceStream.ts`'s `coerce()`/`parsePriceEvent()` functions apply the same defensive-parsing pattern to SSE payloads — malformed or partial data degrades to being skipped, not to throwing.

## Comments

**When to Comment:**
- Module-level docstrings (Python) and JSDoc-style block comments (TypeScript) explain *why*, not *what* — e.g. `backend/app/db/portfolio.py`'s module docstring explains why `execute_trade` is the single writer, and `frontend/src/components/PriceCell.tsx` explains why the flashing span is remounted with a fresh `key`.
- Inline comments call out non-obvious tradeoffs and reference `PLAN.md` sections directly, e.g. `# PLAN.md §7: a snapshot is recorded immediately after every trade...` in `backend/app/api/portfolio.py`, and `// PLAN §2` in `frontend/src/hooks/usePriceStream.ts`. New code touching spec-driven behavior should cite the relevant `PLAN.md` section the same way.
- Test files often carry a one-line module docstring/comment describing the test file's overall guarantee (e.g. `backend/tests/llm/test_mock.py`: `"""The mock responder must be deterministic and match its documented trigger phrases."""`).

**JSDoc/TSDoc:**
- Used selectively on exported functions/hooks/components to document behavior and edge cases, not on every function (see `usePriceStream`, `PriceCell`, `parsePriceEvent` in `frontend/src/`). Not enforced by a lint rule.

**Docstrings (Python):**
- Every public function and module in `backend/app/` has a docstring; docstrings on exceptions in `backend/app/db/errors.py` double as the source of truth for HTTP-status mapping.

## Function Design

**Size:** Functions are kept small and single-purpose; larger flows (e.g. trade execution) are still one function but broken into clearly commented sections (validate -> resolve state -> branch by side -> persist -> return).

**Parameters:**
- Python repository functions consistently accept `user_id: str = DEFAULT_USER_ID` and an optional trailing `conn: sqlite3.Connection | None = None` so callers can group multiple writes into a single transaction, or let the call manage its own connection (documented pattern in `backend/CLAUDE.md` and used throughout `backend/app/db/`).
- Router-factory functions accept dependencies as parameters and return an `APIRouter` (`create_portfolio_router(user_id=...)`, `create_chat_router(price_cache, market_source)`) rather than using global routers — enables isolated test apps (see `backend/tests/api/conftest.py`).

**Return Values:**
- Backend repository functions return typed dataclasses/Pydantic models, never raw SQLite rows.
- Frontend API functions always return normalized, typed values (never raw `unknown` JSON) — normalization happens once, at the boundary in `frontend/src/lib/api.ts`.

## Module Design

**Exports:**
- Backend: each subpackage (`app/db`, `app/market`, `app/llm`, `app/api`) has an `__init__.py` that re-exports its public surface, so consumers import from the package root (`from app.db import execute_trade, DuplicateTickerError`) instead of reaching into submodules. This is the documented, expected import style (`backend/CLAUDE.md`).
- Frontend: no barrel files observed; components/hooks/lib modules are imported directly by path (`@/lib/format`, `@/components/PriceCell`).

**Barrel Files:**
- Used on the backend (via `__init__.py` re-exports) but not on the frontend.

**Interfaces over implementations:**
- The market-data layer defines an abstract `MarketDataSource` interface (`backend/app/market/interface.py`) implemented by both `SimulatorDataSource` and `MassiveDataSource`; a `create_market_data_source()` factory selects the implementation based on `MASSIVE_API_KEY`. New market-data-like subsystems should follow this same interface + factory pattern, as recommended by `planning/PLAN.md` §6.

---

*Convention analysis: 2026-08-16*
