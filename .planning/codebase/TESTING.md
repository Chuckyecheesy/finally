# Testing Patterns

**Analysis Date:** 2026-08-16

## Test Framework

There are three distinct test suites in this repo, one per layer.

**Backend unit/integration (pytest):**
- Framework: `pytest>=8.3.0` with `pytest-asyncio>=0.24.0` and `pytest-cov>=5.0.0`
- Config: `backend/pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `python_files = ["test_*.py"]`, `asyncio_mode = "auto"` (async test functions don't need `@pytest.mark.asyncio`)
- Assertion style: plain `assert` + `pytest.approx()` for float comparisons

**Frontend unit/component (Vitest + React Testing Library):**
- Framework: `vitest@3.2.7`, `@testing-library/react@16.2.0`, `@testing-library/jest-dom@6.6.3`, `@testing-library/user-event@14.6.1`
- Config: `frontend/vitest.config.ts` — `environment: "jsdom"`, `globals: true`, `setupFiles: ["./vitest.setup.ts"]`, `include: ["src/**/*.test.{ts,tsx}"]`
- Path alias `@/*` mirrors `tsconfig.json` so imports work the same in tests as in app code

**E2E (Playwright):**
- Framework: `@playwright/test@^1.62.1`, isolated in `test/` with its own `package.json`
- Config: `test/playwright.config.ts` (not read in full here, but the suite is driven by `test/docker-compose.test.yml`, per `planning/PLAN.md` §12) — spins up the app container plus a Playwright container so browser dependencies stay out of the production image
- Runs against a real running app with `LLM_MOCK=true` for determinism (per `planning/PLAN.md` §12)

**Run Commands:**
```bash
# Backend
cd backend
uv run --extra dev pytest -v                # All tests
uv run --extra dev pytest --cov=app         # With coverage
uv run --extra dev ruff check app/ tests/   # Lint

# Frontend
cd frontend
npm run test         # vitest run (single pass)
npm run test:watch   # vitest (watch mode)
npm run lint         # eslint .

# E2E
cd test
npm run test          # playwright test
npm run test:headed   # playwright test --headed
npm run report         # playwright show-report
```

## Test File Organization

**Backend location:**
- Tests live in `backend/tests/`, mirroring the `backend/app/` package structure one-to-one: `tests/api/`, `tests/db/`, `tests/llm/`, `tests/market/` correspond to `app/api/`, `app/db/`, `app/llm/`, `app/market/`.
- Naming: `test_<module>.py` for each `<module>.py` (e.g. `app/db/portfolio.py` -> `tests/db/test_portfolio.py`).
- Each test subpackage has its own `conftest.py` scoped to that layer's fixtures (`tests/db/conftest.py`, `tests/api/conftest.py`, `tests/llm/conftest.py`), plus a root `tests/conftest.py` for shared fixtures.

**Frontend location:**
- Co-located: `Component.test.tsx` sits directly beside `Component.tsx` in `frontend/src/components/` and `frontend/src/hooks/` (e.g. `PriceCell.tsx` + `PriceCell.test.tsx`, `usePriceStream.ts` + `usePriceStream.test.ts`).

**E2E location:**
- Numbered, scenario-named spec files in `test/tests/`: `01-fresh-start.spec.ts`, `02-watchlist.spec.ts`, `03-trading.spec.ts`, `04-visualization.spec.ts`, `05-chat.spec.ts`, `06-sse-resilience.spec.ts` — numbering enforces a readable execution/reading order that follows the user journey in `planning/PLAN.md` §12.
- Shared helpers in `test/tests/helpers.ts` (locators, wait helpers, formatting helpers) — see Fixtures section below.

## Test Structure

**Backend (pytest, function-based, no classes):**
```python
"""Portfolio endpoints: valuation, trades, and history."""

import pytest
from app.db import DEFAULT_CASH_BALANCE

def buy(client, ticker="AAPL", quantity=10):
    return client.post(
        "/api/portfolio/trade",
        json={"ticker": ticker, "quantity": quantity, "side": "buy"},
    )

def test_buy_debits_cash_and_opens_position(client):
    response = buy(client, "AAPL", 10)
    assert response.status_code == 200
    ...
```
(`backend/tests/api/test_portfolio.py`)

- Module docstring states the file's overall scope in one line.
- Small local helper functions (like `buy()` above) reduce duplication within a test file instead of adding fixtures for simple request-building.
- Fixtures come from `conftest.py`, injected by name as test parameters (`client`, `price_cache`, `temp_db`).

**Frontend (Vitest + RTL, `describe`/`it`):**
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceCell } from "./PriceCell";

describe("PriceCell", () => {
  it("does not flash on first render", () => {
    render(<PriceCell value={190.5} />);
    const cell = screen.getByTestId("price-cell");
    expect(cell).toHaveTextContent("190.50");
    expect(cell.className).not.toMatch(/flash-/);
  });
  ...
});
```
(`frontend/src/components/PriceCell.test.tsx`)

- One `describe` block per component/hook, `it("does X", ...)` phrased as behavior statements.
- `render(...)` then `rerender(...)` (from RTL) is the standard way to test state transitions like the price-flash animation.
- `screen.getByTestId(...)` is the primary query strategy for elements without clear text/role; `data-testid="price-cell"` is set explicitly in the component for this purpose.

**E2E (Playwright, `test`/`test.describe`):**
```ts
import { expect, test } from "@playwright/test";
import { cashBalance, openApp, positionRow, ... } from "./helpers";

const TICKER = "MSFT";
test.describe.configure({ mode: "serial" }); // tests share state across the same page/app

test("buying shares debits cash and opens a position", async ({ page }) => {
  await openApp(page);
  const price = await waitForStreamingPrice(page, TICKER);
  ...
});
```
(`test/tests/03-trading.spec.ts`)

- `test.describe.configure({ mode: "serial" })` is used when a spec's tests intentionally build on each other's state (e.g. buy then sell then sell-remaining in `03-trading.spec.ts`).
- Locators favor ARIA roles/labels over CSS selectors (`page.getByRole("region", { name: "Watchlist" })`, `page.getByLabel("Ticker")`) — every `Panel` component renders `<section aria-label={title}>` specifically to support this (see comment in `test/tests/helpers.ts`).
- `page.waitForResponse(...)` is paired with the triggering `.click()` to avoid racing the UI against the network (see `trade()` and `sendChat()` helpers).

**Patterns:**
- Setup: pytest fixtures (`temp_db`, `client`, `price_cache`) inject fresh, isolated state per test; Playwright specs call `openApp(page)` at the start of each test to navigate and wait for the SSE connection.
- Teardown: Vitest's `vitest.setup.ts` runs `cleanup()` (RTL) and `vi.restoreAllMocks()` globally after every test via `afterEach` — individual test files don't need their own teardown.
- Assertion: pytest uses direct `assert` + `pytest.approx()` for money math; RTL uses `@testing-library/jest-dom` matchers (`toHaveTextContent`, `toHaveClass`); Playwright uses `expect(locator).toHaveText(...)` / `toBeVisible()` with generous timeouts for async UI (`{ timeout: 30_000 }` for SSE-dependent state).

## Mocking

**Backend — `unittest.mock`:**
```python
from unittest.mock import MagicMock, patch

with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
    ...
```
(`backend/tests/market/test_massive.py`)
- `patch.object` mocks the network-touching seam (`_fetch_snapshots`) of `MassiveDataSource` rather than mocking the HTTP client library directly — mock at the layer boundary the code owns, not at the third-party library.
- LLM tests avoid real network calls entirely by forcing mock mode: `backend/tests/llm/conftest.py` sets an **autouse** fixture `mock_mode` that does `monkeypatch.setenv(MOCK_ENV_VAR, "true")` for every test in the `llm` package — "so no test in this package can reach the network even if it forgets to opt in."
- A hand-built `FakeMarketSource(MarketDataSource)` test double (in `backend/tests/api/conftest.py`) implements the full `MarketDataSource` interface but just records lifecycle calls (`started`, `stopped`, `tickers`) instead of producing real prices — used so API tests exercise routes without a live background polling loop.

**Frontend — Vitest mocks:**
- `vi.restoreAllMocks()` runs globally after every test (`frontend/vitest.setup.ts`), so individual tests can freely use `vi.spyOn`/`vi.fn()` without needing explicit cleanup.
- `globalThis.ResizeObserver` is polyfilled once in `vitest.setup.ts` because Recharts' `ResponsiveContainer` needs it and jsdom doesn't provide it — a global environment shim rather than a per-test mock.

**What to Mock:**
- Backend: the network-touching boundary of an external integration (Massive API `_fetch_snapshots`), and the LLM call path (via `LLM_MOCK=true`, not a Python-level mock) — see LLM Mock Mode below.
- Frontend: browser APIs missing from jsdom (`ResizeObserver`); EventSource is not globally mocked, tested instead via the pure `parsePriceEvent()` function extracted from the hook.

**What NOT to Mock:**
- The SQLite database is never mocked — tests use a real, temporary SQLite file per test (`tmp_path / "finally.db"` via `monkeypatch.setenv(DB_PATH_ENV, ...)`, then `init_db()`). This exercises real SQL and real schema/seed behavior.
- `execute_trade()` and other repository functions are called directly, not mocked, in both DB-layer tests and API-layer tests — validation logic is exercised end-to-end through the real function.

## Fixtures and Factories

**Backend fixtures (pytest, per-package `conftest.py`):**
```python
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the repository at a fresh SQLite file and initialize it."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv(DB_PATH_ENV, str(path))
    init_db()
    return path
```
(`backend/tests/db/conftest.py`, duplicated with the same name/shape in `backend/tests/api/conftest.py` and `backend/tests/llm/conftest.py` — each package owns its own copy rather than sharing one; this is a deliberate isolation choice, not an oversight, so each test layer can evolve its fixture independently.)

- `price_cache` fixture seeds a real `PriceCache` instance with fixed prices (`{"AAPL": 100.0, "MSFT": 200.0}` in API tests) for deterministic trade-fill prices.
- `client` fixture (API tests) builds a bare `FastAPI()` app, registers only the routers under test, attaches `app.state.price_cache` / `app.state.market_source`, and wraps it in `TestClient(...)` — this avoids running the app's real lifespan/background tasks (which is separately tested in `tests/api/test_app.py`).

**Frontend test data:**
- No shared fixture/factory files observed; each test file inlines its own small mock props/data directly (e.g. `render(<PriceCell value={190.5} />)`).

**E2E "fixtures":** `test/tests/helpers.ts` acts as the shared factory/fixture layer — exports typed locator builders (`watchlistPanel`, `positionRow`), action helpers (`trade`, `sendChat`, `selectTicker`), wait helpers (`waitForStreamingPrice`, `waitForConnected`), and a parsing helper (`parseMoney`). New E2E specs are expected to compose from these rather than writing raw locators inline.

## Coverage

**Requirements:** No enforced minimum threshold found in CI config or `pyproject.toml`; `pytest-cov` is installed and configured (`[tool.coverage.run] source = ["app"]`, `omit = ["tests/*"]`) but no `fail_under` is set.

**View Coverage:**
```bash
cd backend
uv run --extra dev pytest --cov=app
```

## Test Types

**Unit Tests (backend):**
- Scope: pure logic — market data GBM math (`tests/market/test_simulator.py`), price cache (`tests/market/test_cache.py`), mock LLM trigger-phrase parsing (`tests/llm/test_mock.py`), Pydantic schema validation (`tests/llm/test_schemas.py`).

**Integration Tests (backend):**
- Scope: repository functions against a real (temp) SQLite database (`tests/db/*`), and API routes against a bare FastAPI app with a `TestClient` and fake/seeded dependencies (`tests/api/*`).

**Component Tests (frontend):**
- Scope: individual React components/hooks rendered in jsdom via RTL — covers rendering, user interaction, and derived UI state (price flashing, SSE event parsing) but not full-page integration.

**E2E Tests (Playwright, `test/`):**
- Scope: full user journeys against a real running Docker container — fresh start, watchlist CRUD, trading, visualization, AI chat (mocked), and SSE reconnection resilience (per `planning/PLAN.md` §12's six key scenarios, matching the six numbered spec files 1:1).

## Common Patterns

**Async Testing (backend):**
```python
# asyncio_mode = "auto" in pyproject.toml means async test functions
# just work without @pytest.mark.asyncio:
async def test_something(...):
    ...
```

**Async waiting (E2E):**
```ts
export async function waitForStreamingPrice(page: Page, ticker: string): Promise<number> {
  const cell = watchlistRow(page, ticker).getByTestId("price-cell");
  await expect(cell).not.toHaveText("—", { timeout: 30_000 });
  return Number.parseFloat(await cell.innerText());
}
```
(`test/tests/helpers.ts`) — SSE-dependent state is awaited with an explicit, generously-timed condition rather than a fixed sleep.

**Error Testing:**
```python
def test_buy_without_enough_cash_is_400(client):
    response = buy(client, "AAPL", 1000)
    assert response.status_code == 400
    assert "Insufficient cash" in response.json()["detail"]
```
(`backend/tests/api/test_portfolio.py`) — error tests assert both the HTTP status code and a substring of the `detail` message, not the full message text (keeps tests resilient to minor message rewording while still catching wrong-error-type bugs).

**Deterministic mock responder testing (LLM):**
```python
@pytest.mark.parametrize(
    ("message", "side", "quantity", "ticker"),
    [
        ("buy 10 AAPL", "buy", 10.0, "AAPL"),
        ("sell 2.5 TSLA", "sell", 2.5, "TSLA"),
        ...
    ],
)
def test_trade_phrases(message, side, quantity, ticker):
    response = generate_response(message, "ctx", [])
    ...
```
(`backend/tests/llm/test_mock.py`) — `pytest.mark.parametrize` is the standard way to cover many input variants of the same behavior; the mock responder's module docstring in `app/llm/mock.py` is documented as the authoritative list of trigger phrases, and this test file's parametrized cases are expected to stay in sync with it (per `backend/CLAUDE.md`: "E2E tests depend on them verbatim").

---

*Testing analysis: 2026-08-16*
