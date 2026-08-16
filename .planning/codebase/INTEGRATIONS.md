# External Integrations

**Analysis Date:** 2026-08-16

## APIs & External Services

**LLM Inference:**
- OpenRouter (routing) → Cerebras (inference provider) - `backend/app/llm/client.py`
  - SDK/Client: `litellm.completion()`, model string `openrouter/openai/gpt-oss-120b`, `extra_body={"provider": {"order": ["cerebras"]}}`
  - Auth: `OPENROUTER_API_KEY` env var (read implicitly by LiteLLM/OpenRouter conventions; not directly referenced in `client.py`)
  - Structured output: `response_format=LLMStructuredResponse` (Pydantic model, `backend/app/llm/schemas.py`)
  - Failure handling: `generate_response()` never raises — network/provider/parse failures degrade to an apology message with no trade actions (see docstring in `backend/app/llm/client.py`)
  - Mock mode: when `LLM_MOCK=true`, `backend/app/llm/mock.py` serves deterministic canned responses instead of calling OpenRouter (used by E2E tests and offline dev)

**Market Data:**
- Massive (Polygon.io) REST API - `backend/app/market/massive_client.py`
  - SDK/Client: `massive.RESTClient` (`massive` PyPI package ≥1.0.0)
  - Auth: `MASSIVE_API_KEY` env var — presence/absence selects this client vs. the built-in simulator (`backend/app/market/factory.py`)
  - Endpoint used: `GET /v2/snapshot/locale/us/markets/stocks/tickers` via `client.get_snapshot_all(market_type=SnapshotMarketType.STOCKS, tickers=...)`
  - Polling model (not streaming): default interval 15s (free tier, 5 req/min); poll loop in `MassiveDataSource._poll_loop`
  - Failure handling: a failed poll is logged and retried on the next interval — no fallback to the simulator, cache simply goes stale for affected tickers (`backend/app/market/massive_client.py`, `_poll_once`)
  - If `MASSIVE_API_KEY` is unset/empty, `SimulatorDataSource` (`backend/app/market/simulator.py`) generates prices in-process via GBM — no external network calls

## Data Storage

**Databases:**
- SQLite (file-based, single-user) - `backend/app/db/connection.py`
  - Connection: `FINALLY_DB_PATH` env var overrides path; default `<repo>/db/finally.db`; Docker sets `FINALLY_DB_PATH=/app/db/finally.db`
  - Client: Python stdlib `sqlite3` — no ORM; `WAL` journal mode, `busy_timeout=5000ms`, connections opened per unit of work (`get_connection()` context manager)
  - Schema/DDL: `backend/app/db/schema.py`; lazy init + seed at FastAPI startup via `init_db()` (`backend/app/db/init_db.py`, called from `backend/app/main.py` lifespan)
  - Tables: `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages` (all scoped by `user_id`, hardcoded `"default"`)

**File Storage:**
- Local filesystem only — SQLite file persisted via Docker named volume (`./db:/app/db` in `docker-compose.yml`); no object storage (S3, GCS, etc.)

**Caching:**
- In-process, in-memory `PriceCache` - `backend/app/market/cache.py` — thread-safe latest-price store written by the market data source and read by the SSE stream endpoint; not a distributed cache (Redis, Memcached not used)

## Authentication & Identity

**Auth Provider:**
- None — single-user application by design. All DB rows carry `user_id = "default"` (see `backend/app/db/models.py` / repository modules) to allow future multi-user support without schema migration, but no login/session/auth flow currently exists (per `planning/PLAN.md` §2, §7)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry/Bugsnag/etc. integration found)

**Logs:**
- Python stdlib `logging` module used throughout backend (e.g., `backend/app/main.py`, `backend/app/market/massive_client.py`, `backend/app/llm/client.py`) — logs to stdout/stderr, no external log aggregation service

## CI/CD & Deployment

**Hosting:**
- Single Docker container, port 8000 (`Dockerfile`, `docker-compose.yml`) — designed to be portable to any container platform (AWS App Runner, Render, etc.) per `planning/PLAN.md` §11; no deploy/`terraform` config currently present in the repo

**CI Pipeline:**
- GitHub Actions - `.github/workflows/`
  - `claude-code-review.yml`-style workflow: runs Anthropic's `claude-code-action` code review plugin on PR events (uses `ANTHROPIC_API_KEY` secret)
  - A second workflow triggers Claude Code on `@claude` mentions in issues/PR comments/reviews (uses `ANTHROPIC_API_KEY` secret, `contents: write` permission)
  - No build/test/deploy CI pipeline detected (no workflow runs `pytest`, `npm test`, or `docker build` for verification)

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY` — required for live LLM chat functionality (`.env.example`)

**Optional env vars:**
- `MASSIVE_API_KEY` — enables real market data via Massive/Polygon.io; empty/unset uses the built-in simulator
- `LLM_MOCK` — `"true"` enables deterministic mock chat responses (used by E2E tests, set in `test/docker-compose.test.yml`)
- `FINALLY_DB_PATH` — overrides SQLite file location (used by tests and Docker)

**Secrets location:**
- `.env` file at project root, gitignored; `.env.example` committed as a template (contents of `.env`/`.env.example` not reproduced here beyond variable names, per security policy)
- GitHub Actions secret: `ANTHROPIC_API_KEY` (for Claude Code review/assistant workflows only — unrelated to the app's runtime secrets)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None (LLM and Massive API calls are synchronous request/response, not webhook-based)

---

*Integration audit: 2026-08-16*
