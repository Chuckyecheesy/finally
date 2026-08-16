# Technology Stack

**Analysis Date:** 2026-08-16

## Languages

**Primary:**
- Python 3.12+ (backend) - `backend/app/`, `backend/tests/` — targets `py312` per `backend/pyproject.toml`; dev container runs 3.13
- TypeScript 5.7.3 (frontend) - `frontend/src/`

**Secondary:**
- SQL (embedded in Python strings) - `backend/app/db/schema.py` (SQLite schema/DDL)
- Bash / PowerShell - `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1`

## Runtime

**Environment:**
- Python 3.12+ (backend), managed by `uv`
- Node.js 20 (frontend build — `node:20-slim` in `Dockerfile` stage 1; also used by the Playwright test runner in `test/docker-compose.test.yml`)

**Package Manager:**
- Backend: `uv` (`backend/pyproject.toml`, `backend/uv.lock`) — lockfile present, `uv sync --locked` used in Docker build
- Frontend: `npm` (`frontend/package.json`, `frontend/package-lock.json`) — lockfile present, `npm ci` used in Docker build
- E2E tests: `npm` (`test/package.json`, `test/package-lock.json`)

## Frameworks

**Core:**
- FastAPI ≥0.115.0 - `backend/app/main.py` — REST API + SSE streaming + static file serving, single ASGI app
- Uvicorn `[standard]` ≥0.32.0 - ASGI server, entrypoint `uvicorn app.main:app` (see `Dockerfile` CMD)
- Next.js 15.5.23 (App Router) - `frontend/src/app/` — built with `output: "export"` for production (static export), served by FastAPI
- React 19.0.0 / React DOM 19.0.0 - `frontend/src/components/`

**Testing:**
- pytest ≥8.3.0 + pytest-asyncio ≥0.24.0 + pytest-cov ≥5.0.0 - `backend/tests/` (config in `backend/pyproject.toml` `[tool.pytest.ini_options]`, `asyncio_mode = "auto"`)
- Vitest 3.2.7 + @testing-library/react 16.2.0 + jsdom 26.0.0 - `frontend/src/**/*.test.tsx` (config: `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`)
- Playwright ^1.62.1 - `test/tests/` E2E suite, config `test/playwright.config.ts`, driven via `test/docker-compose.test.yml`

**Build/Dev:**
- Tailwind CSS ^4.3.3 (`@tailwindcss/postcss`) - `frontend/postcss.config.mjs`, `frontend/src/app/globals.css`
- ESLint 9.18.0 (flat config, `eslint-config-next` 15.5.23) - `frontend/eslint.config.mjs`
- Ruff ≥0.7.0 - `backend/pyproject.toml` `[tool.ruff]` (line-length 100, rules `E,F,I,N,W`, target `py312`)
- TypeScript compiler 5.7.3 (noEmit, strict mode) - `frontend/tsconfig.json`

## Key Dependencies

**Critical:**
- `litellm` ≥1.96.2 - `backend/app/llm/client.py` — routes chat completions through OpenRouter to Cerebras inference (`openrouter/openai/gpt-oss-120b`, structured output via `response_format`)
- `massive` ≥1.0.0 (Polygon.io Python SDK) - `backend/app/market/massive_client.py` — optional real market-data REST client
- `numpy` ≥2.0.0 - used by the GBM price simulator (`backend/app/market/simulator.py`)
- `pydantic` ≥2.12.5 - request/response schemas (`backend/app/api/schemas.py`, `backend/app/llm/schemas.py`)
- `recharts` 3.10.1 - `frontend/src/components/PnlChart.tsx`, `PriceChart.tsx`, `Heatmap.tsx` — canvas/SVG charting

**Infrastructure:**
- `rich` ≥13.0.0 - `backend/market_data_demo.py` (terminal dashboard demo, not part of the served app)
- Python stdlib `sqlite3` - `backend/app/db/connection.py` — no ORM; hand-written SQL via `sqlite3.Row`

## Configuration

**Environment:**
- `.env` file at project root (gitignored; `.env.example` committed) — loaded via `--env-file .env` in `docker-compose.yml` and the start scripts
- Variables: `OPENROUTER_API_KEY` (required for live LLM chat), `MASSIVE_API_KEY` (optional — presence toggles real market data vs. simulator, see `backend/app/market/factory.py`), `LLM_MOCK` (optional, `"true"` enables deterministic mock chat responses)
- `FINALLY_DB_PATH` env var overrides the SQLite file location (`backend/app/db/connection.py`); defaults to `<repo>/db/finally.db`, and is set to `/app/db/finally.db` inside the Docker image
- `.env` file existence noted only — contents not read/quoted here per security policy

**Build:**
- `frontend/next.config.ts` — conditional config: dev mode adds an `/api/*` rewrite proxy to `http://localhost:8000`; non-dev (build) mode sets `output: "export"` for the static export FastAPI serves
- `backend/pyproject.toml` — project metadata, dependency groups (`dev` extra), Ruff/pytest/coverage config
- `Dockerfile` — multi-stage build: Stage 1 `node:20-slim` builds the Next.js static export (`npm ci && npm run build`); Stage 2 `python:3.12-slim` installs backend deps via `uv sync --locked`, copies the frontend export into `/app/static`, exposes port 8000

## Platform Requirements

**Development:**
- Python 3.12+ with `uv` installed; run `uv sync --extra dev` in `backend/`
- Node 20+ with `npm` in `frontend/`
- Docker (for full-stack container build/run and E2E tests)

**Production:**
- Single Docker container, single port (8000), per `docker-compose.yml`
- SQLite database persisted via Docker named volume mounted at `/app/db` (host `./db/`)
- Deployable to any container platform (App Runner, Render, etc.) — no external service dependencies beyond OpenRouter/Massive APIs

---

*Stack analysis: 2026-08-16*
