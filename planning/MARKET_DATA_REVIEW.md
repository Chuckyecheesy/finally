# Market Data Backend — Code Review

**Date:** 2026-08-15
**Scope:** `backend/app/market/` (8 modules) and `backend/tests/market/` (8 test files)
**Method:** Independent re-verification — full source read, `uv sync`, `uv build`,
full pytest run with coverage, `ruff check`/`format --check`, and a manual
10-ticker Cholesky sanity check. This supersedes `planning/archive/MARKET_DATA_REVIEW.md`
(2026-02-10), which reviewed an earlier state of the code; findings below note
where that review's issues have since been resolved.

---

## 1. Test Results

**142 tests collected, 142 passed, 0 failed.** (Prior review: 73 collected, 68 passed.)

```
uv run --extra dev pytest -v --cov=app --cov-report=term-missing
```

**Coverage: 98% overall** (prior review: 84%):

| Module | Coverage | Missing |
|---|---|---|
| models.py | 100% | |
| cache.py | 100% | |
| interface.py | 100% | |
| seed_prices.py | 100% | |
| factory.py | 100% | |
| __init__.py | 100% | |
| simulator.py | 98% | L149 (docstring line, not code), L271-272 (exception-log branch in `_run_loop`) |
| massive_client.py | 96% | L150-152 (`_poll_loop`'s `while True` body — only exercised by cancellation, not a live loop), L194 (`_fetch_snapshots` real network call) |
| stream.py | 94% | L40 (route decorator line), L89 (`CancelledError` log branch) |

The Massive tests no longer require the `massive` package to be absent-tolerant — it's a
listed core dependency, is installed, and all 34 `test_massive.py` cases pass directly
against fake model classes (not bare `MagicMock`), so a wrong attribute name (the bug
that shipped in an earlier pass, §3 below) would fail loudly rather than being silently
absorbed by a mock. This closes issue 3.2 from the prior review.

**Lint:** `ruff check app/ tests/` — clean, zero warnings. (Prior review flagged 5
unused-import warnings; all gone.)

**Format:** `ruff format --check` flags 4 test files as not matching the formatter's
preferred style (`test_cache.py`, `test_models.py`, `test_simulator.py`,
`test_simulator_source.py`). Cosmetic only, not enforced by `ruff check`, zero
functional impact. Not worth a fix cycle on its own.

**Build:** `uv sync --extra dev` and `uv build` both succeed cleanly, producing a
valid wheel. The `[tool.hatch.build.targets.wheel] packages = ["app"]` config is
present in `pyproject.toml` — the High-severity build blocker from the prior review
(3.1) is resolved.

---

## 2. Architecture Assessment

Confirmed against the actual source (not just the design docs): the subsystem is a
clean strategy-pattern implementation.

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBMSimulator (GBM + Cholesky-correlated moves)
└── MassiveDataSource    →  Polygon.io REST poller (massive package)
        │
        ▼
   PriceCache (thread-safe, in-memory, version-counted)
        │
        ▼
   SSE stream (create_stream_router) → frontend EventSource
```

**Strengths, verified by reading the code directly:**

- `PriceUpdate` is a proper `frozen=True, slots=True` dataclass — immutable, memory-efficient, safe to hand off mid-serialization.
- `PriceCache.update()` is the single write path; `previous_price` defaults to `price` on first write (correct "flat, no flash" behavior), and rounding happens in one place.
- `PriceCache.version` is read under the lock (`cache.py:67-71`) — uniformly thread-safe, not relying on CPython GIL atomicity. Confirms fix for prior issue 3.4/14.2.
- `stream.py`'s `create_stream_router()` builds a fresh `APIRouter` per call (`stream.py:26`) — no module-level router, no closure-over-stale-cache bug. Confirms fix for prior issue 3.6/14.3, and it's now regression-tested (`test_each_call_returns_an_independent_router`).
- `_generate_events` is correctly typed `-> AsyncGenerator[str, None]` (`stream.py:57`). Confirms fix for prior issue 3.3.
- `GBMSimulator.get_tickers()` is a public method (`simulator.py:140-142`); `SimulatorDataSource.get_tickers()` calls it rather than reaching into `_sim._tickers`. Confirms fix for prior issue 3.5.
- `massive_client.py` imports `RESTClient` and `SnapshotMarketType` at module level (no lazy import) — consistent with `massive` being declared a core dependency, and this is what makes `patch()`/mocking in tests reliable.
- `normalize_ticker()` lives once in `interface.py` and is applied by both `SimulatorDataSource.start/add_ticker/remove_ticker` and `MassiveDataSource.start/add_ticker/remove_ticker` — cache keys are canonical regardless of source or input casing. This is new since the prior review and is well tested (`test_interface.py::TestNormalizeTicker`, parametrized across whitespace/case/multi-dot tickers like `BRK.B`).
- The previously-open Massive timestamp bug (`.timestamp` attribute that doesn't exist on the real `LastTrade` model, silently swallowed by a bare `except AttributeError` and a `MagicMock`-based test that couldn't catch it) is fixed: `_extract_price`/`_extract_timestamp` use explicit `getattr`-based extraction with a `day.close` → `prev_day.close` fallback chain, and `_extract_timestamp` checks `sip_timestamp` → `participant_timestamp` → `trf_timestamp` in order. Verified by reading `massive_client.py:37-76` directly and cross-checking the corresponding tests in `test_massive.py` (`TestPriceExtraction`, `TestTimestampExtraction`), which use plain fake classes, not `MagicMock`.
- Both background loops (`SimulatorDataSource._run_loop`, `MassiveDataSource._poll_loop`/`_poll_once`) wrap their work in `try/except Exception`, log, and continue — a single bad tick or failed poll can't kill the long-running task.
- Fail-stale behavior for Massive is implemented as designed: a failed poll (`except Exception` around `asyncio.to_thread(self._fetch_snapshots)`) logs and returns without ever constructing a `SimulatorDataSource` as a fallback. There is no code path that could confuse the two sources.
- Manually verified: building a `GBMSimulator` with the full default 10-ticker set and stepping it 100 times succeeds without numerical error (Cholesky decomposition of the full correlation matrix is well-behaved) — see §4, this was an untested code path.

---

## 3. Issues Found

Nothing rises to High or Medium severity. Everything substantive from the prior
review (build config, Massive test fragility, SSE type annotation, cache lock,
router closures, `get_tickers` encapsulation, unused imports) is fixed and,
for the ones that were regressions waiting to happen, now has a dedicated
regression test. Remaining items are pre-existing "nice to have"s, none of
which block anything downstream.

### 3.1 No test exercises the full 10-ticker default correlation matrix (Severity: Low)

`test_simulator.py` never constructs a `GBMSimulator` with more than 2 tickers.
The Cholesky decomposition of the full 10x10 default correlation matrix (tech
0.6, finance 0.5, TSLA 0.3, cross-sector 0.3) is therefore only exercised at
runtime, never in CI. I confirmed by hand that it works correctly (§4), so this
is a coverage gap, not a bug — but it's exactly the kind of thing a future
change to `CORRELATION_GROUPS` or the correlation constants could silently
break (a non-positive-semi-definite matrix raises `LinAlgError` on
`np.linalg.cholesky`) without a test catching it. This was flagged in the prior
review (4.2) and remains open.

**Suggested fix:** one test —
`GBMSimulator(tickers=list(SEED_PRICES.keys()))` then `.step()` a few times and
assert no exception and all prices stay positive.

### 3.2 `ruff format` disagrees with 4 test files (Severity: Trivial)

`test_cache.py`, `test_models.py`, `test_simulator.py`, `test_simulator_source.py`
would be reformatted by `ruff format`. `ruff check` is clean (no lint rule
violations), so this is purely a formatter-style drift — not enforced by CI
unless `ruff format --check` is added to the pipeline. Cosmetic; fix opportunistically.

### 3.3 `MassiveDataSource.add_ticker` latency differs from the simulator (Severity: Informational, by design)

Documented behavior, not a bug: adding a ticker under Massive mode doesn't
populate the cache until the next scheduled poll (up to 15s on the free tier),
whereas the simulator seeds synchronously. This is called out explicitly in
`planning/MARKET_DATA_DESIGN.md` §8.4 and is a reasonable consequence of REST
polling. Flagging here only so whoever builds the watchlist endpoint (not yet
built) remembers that `cache.get_price()` can legitimately return `None` for a
few seconds after `POST /api/watchlist` under Massive mode, and the frontend/API
layer needs to tolerate that rather than treating it as an error.

---

## 4. Verification Notes

Ran directly, outside the test suite, to independently confirm the design docs'
claims rather than trust them at face value:

```
uv sync --extra dev        → resolves cleanly, no errors
uv build                   → wheel + sdist built successfully
uv run --extra dev pytest -v --cov=app --cov-report=term-missing
                            → 142 passed, 0 failed, 98% coverage
uv run --extra dev ruff check app/ tests/
                            → All checks passed!
uv run --extra dev ruff format --check app/ tests/
                            → 4 test files would reformat (cosmetic only)
python -c "GBMSimulator(tickers=list(SEED_PRICES.keys())); step() x100"
                            → succeeds, all 10 prices remain positive and reasonable
```

No discrepancies found between what `planning/MARKET_DATA_SUMMARY.md` and
`planning/MARKET_DATA_DESIGN.md` claim and what the code/tests actually do.

---

## 5. Verdict

The market data backend is in excellent shape and ready for the rest of the
backend to build on top of it. All issues from the original 2026-02-10 review
are resolved and regression-tested. No new High or Medium severity issues were
found in this pass.

**Should fix (low priority, non-blocking):**
1. Add one `GBMSimulator` test covering the full default 10-ticker set (§3.1).

**Nice to have:**
2. Run `ruff format` on the 4 flagged test files (§3.2).

**No action needed:**
3. The Massive `add_ticker` latency gap (§3.3) is intentional and already documented — it's a note for whoever builds the watchlist endpoint next, not a market-data defect.
