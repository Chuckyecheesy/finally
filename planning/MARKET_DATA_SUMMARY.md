# Market Data Backend — Summary

**Status:** Complete, tested, reviewed, all issues resolved.

## What Was Built

A complete market data subsystem in `backend/app/market/` (8 modules, ~500 lines) providing live price simulation and real market data via a unified interface.

### Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Polygon.io REST poller (when MASSIVE_API_KEY set)
        │
        ▼
   PriceCache (thread-safe, in-memory)
        │
        ├──→ SSE stream endpoint (/api/stream/prices)
        ├──→ Portfolio valuation
        └──→ Trade execution
```

### Modules

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate` — immutable frozen dataclass (ticker, price, previous_price, timestamp, change, direction) |
| `interface.py` | `MarketDataSource` — abstract base class defining `start/stop/add_ticker/remove_ticker/get_tickers`; plus `normalize_ticker()`, the shared symbol-canonicalization helper both sources apply |
| `cache.py` | `PriceCache` — thread-safe price store with version counter for SSE change detection |
| `seed_prices.py` | Realistic seed prices, per-ticker GBM params (drift/volatility), correlation groups |
| `simulator.py` | `GBMSimulator` (Geometric Brownian Motion with Cholesky-correlated moves) + `SimulatorDataSource` |
| `massive_client.py` | `MassiveDataSource` — REST polling client for Polygon.io via the `massive` package, with `_extract_price` / `_extract_timestamp` handling sparse snapshots |
| `factory.py` | `create_market_data_source()` — selects simulator or Massive based on `MASSIVE_API_KEY` env var |
| `stream.py` | `create_stream_router()` — FastAPI SSE endpoint factory using version-based change detection |

### Key Design Decisions

- **Strategy pattern** — both data sources implement the same ABC; downstream code is source-agnostic
- **PriceCache as single point of truth** — producers write, consumers read; no direct coupling
- **GBM with correlated moves** — Cholesky decomposition of sector-based correlation matrix; tech stocks correlate at 0.6, finance at 0.5, cross-sector at 0.3
- **Random shock events** — ~0.1% chance per tick per ticker of a 2-5% move for visual drama
- **SSE over WebSockets** — simpler, one-way push, universal browser support

## Test Suite

**128 test functions** (more cases once parametrization expands) across 8
modules in `backend/tests/market/`.

| Module | Tests | Covers |
|--------|-------|--------|
| test_models.py | 12 | `PriceUpdate` fields, derived properties, JSON serializability, immutability |
| test_cache.py | 19 | read/write, direction, versioning, timestamp handling, thread safety |
| test_simulator.py | 19 | pure `GBMSimulator` math, correlation matrix, seeding |
| test_simulator_source.py | 16 | async lifecycle, cache seeding, ticker normalization |
| test_factory.py | 7 | `MASSIVE_API_KEY` selection logic |
| test_massive.py | 34 | price/timestamp extraction, poll cycle, failure modes |
| test_interface.py | 10 | `MarketDataSource` conformance for both impls, `normalize_ticker` |
| test_stream.py | 11 | SSE payload shape, change detection, disconnect, router factory |

## Code Review & Fixes Applied

An initial review identified 7 issues, all resolved:

1. **pyproject.toml build config** — added `[tool.hatch.build.targets.wheel] packages = ["app"]`
2. **Lazy imports removed** — `massive` is a core dependency; imports moved to top level
3. **SSE return type fixed** — `_generate_events` annotated as `AsyncGenerator[str, None]`
4. **Public `get_tickers()`** — added to `GBMSimulator` to avoid private attribute access
5. **Correlation constants cleaned up** — removed unused `DEFAULT_CORR`, consolidated into `CROSS_GROUP_CORR`
6. **Unused test imports removed** — `pytest`, `math`, `asyncio` cleaned from 4 test files
7. **Massive test mocks fixed** — `source._client` set in tests, patches target correct names

A second pass against the planning docs closed the three issues logged as open
in `MARKET_DATA_DESIGN.md` §14, plus two consistency gaps:

8. **Massive timestamp field** (was blocking all real-data use) — read
   `last_trade.sip_timestamp` and divide by `1e9`, not `.timestamp / 1000.0`.
   The old attribute doesn't exist on the real model, so every poll skipped
   every ticker and the cache never populated with a real API key. Extraction
   now lives in `_extract_price` / `_extract_timestamp`, with fallbacks to
   `day.close` / `prev_day.close` for symbols that haven't traded yet today.
9. **`PriceCache.version` now reads under the lock** — uniformly thread-safe
   rather than relying on GIL atomicity.
10. **`stream.py` router is per-call** — the module-level router double
    -registered `/prices` and made every route close over the last cache passed.
11. **Ticker normalization unified** — `normalize_ticker()` in `interface.py`,
    applied by both sources, so cache keys are canonical regardless of source
    or user input casing.
12. **Massive tests no longer use bare `MagicMock` snapshots** — a mock invents
    any attribute asked of it, which is exactly what hid issue 8. Tests now use
    plain fake classes mirroring the real `massive` models.

An independent re-review (`planning/MARKET_DATA_REVIEW.md`, 2026-08-15) confirmed
all of the above and found no new High/Medium issues, closing out its two
low-priority follow-ups:

13. **Full 10-ticker correlation matrix now covered by a test** —
    `test_simulator.py::test_full_default_ticker_set_cholesky_is_well_behaved`
    builds a `GBMSimulator` with the entire default ticker set and steps it
    100 times, asserting the Cholesky decomposition succeeds and all prices
    stay positive. Previously this was only verified manually, not in CI.
14. **`ruff format` drift fixed** — the 4 test files it flagged
    (`test_cache.py`, `test_models.py`, `test_simulator.py`,
    `test_simulator_source.py`) are now reformatted; `ruff format --check`
    is clean across the module.

## Demo

A Rich terminal demo is available at `backend/market_data_demo.py`:

```bash
cd backend
uv run market_data_demo.py
```

Displays a live-updating dashboard with all 10 tickers, sparklines, color-coded direction arrows, and an event log for notable price moves. Runs 60 seconds or until Ctrl+C.

## Usage for Downstream Code

```python
from app.market import PriceCache, create_market_data_source

# Startup
cache = PriceCache()
source = create_market_data_source(cache)  # Reads MASSIVE_API_KEY
await source.start(["AAPL", "GOOGL", "MSFT", ...])

# Read prices
update = cache.get("AAPL")          # PriceUpdate or None
price = cache.get_price("AAPL")     # float or None
all_prices = cache.get_all()        # dict[str, PriceUpdate]

# Dynamic watchlist
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```
