---
phase: 03-performance-hardening
plan: 03
subsystem: api
tags: [fastapi, query-params, pagination, vitest, pytest]

# Dependency graph
requires: []
provides:
  - "GET /api/portfolio/history bounded by a DEFAULT_HISTORY_LIMIT=500 default, with limit/since query params (limit capped 1-5000)"
  - "frontend fetchHistory(limit?) requesting a bounded default, overridable by callers"
affects: [portfolio-history, useTerminal]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FastAPI Query(..., ge=..., le=...) for bounding client-supplied pagination params before they reach the repository layer"
    - "Frontend default-parameter mirroring a backend constant so existing no-arg call sites pick up the bound automatically"

key-files:
  created:
    - frontend/src/lib/api.test.ts
  modified:
    - backend/app/api/portfolio.py
    - backend/tests/api/test_portfolio.py
    - frontend/src/lib/api.ts

key-decisions:
  - "DEFAULT_HISTORY_LIMIT=500 chosen to match on both backend and frontend, kept as a named constant in each file rather than shared across the language boundary"
  - "since remains a plain str query param forwarded to list_snapshots' existing string-comparison filtering, rather than parsed/validated as a datetime, per the plan's threat model disposition (accept — no new injection surface, malformed values just match no rows)"

patterns-established:
  - "Pagination bound pattern: FastAPI Query(ge=1, le=N) at the route layer, forwarded unchanged to an already-capable repository function"

requirements-completed: [PERF-03]

# Metrics
duration: 20min
completed: 2026-08-16
---

# Phase 3 Plan 3: Bound GET /api/portfolio/history Summary

**Added limit/since query params to GET /api/portfolio/history (default limit 500, capped 1-5000) and updated fetchHistory to request the bounded default, preventing an unbounded response as portfolio_snapshots grows over a long-running session.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-16T18:00:00Z (approx)
- **Completed:** 2026-08-16T18:25:12Z
- **Tasks:** 2
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments
- `GET /api/portfolio/history` now accepts `limit` (default `DEFAULT_HISTORY_LIMIT=500`, `ge=1, le=5000`) and `since` query params, forwarded to the already-capable `list_snapshots(user_id, since=since, limit=limit)` — no changes needed to `backend/app/db/snapshots.py`
- `frontend/src/lib/api.ts`'s `fetchHistory(limit = DEFAULT_HISTORY_LIMIT)` appends `?limit=...` to its request; `useTerminal.ts`'s existing no-arg call site is unaffected
- Three new backend tests (`test_history_is_bounded_by_default_limit_with_no_query_params`, `test_history_explicit_limit_caps_row_count_oldest_first`, `test_history_since_filters_inclusively`) and three new frontend tests (default limit, override, response-shape normalization preserved)

## Task Commits

Each task was committed atomically (TDD RED→GREEN within a single commit per task, since RED was verified interactively before the GREEN diff was staged):

1. **Task 1: Backend — bound GET /api/portfolio/history with limit/since query params** - `8636de4` (feat)
2. **Task 2: Frontend — fetchHistory requests a bounded default limit** - `12fcccc` (feat)

## Files Created/Modified
- `backend/app/api/portfolio.py` - `DEFAULT_HISTORY_LIMIT` constant; `get_history` now accepts `limit`/`since` `Query(...)` params, forwarded to `list_snapshots`
- `backend/tests/api/test_portfolio.py` - three new tests covering default bounding, explicit limit (oldest-first ordering preserved), and inclusive `since` filtering
- `frontend/src/lib/api.ts` - `DEFAULT_HISTORY_LIMIT = 500`; `fetchHistory(limit = DEFAULT_HISTORY_LIMIT)` builds `?limit=${limit}` into the request path
- `frontend/src/lib/api.test.ts` - new file; three tests stubbing `globalThis.fetch` to assert the default limit, an explicit override, and unchanged response normalization

## Decisions Made
- Kept `DEFAULT_HISTORY_LIMIT` as two independently-defined constants (backend Python, frontend TypeScript) with the same value (500) rather than introducing a shared config source — consistent with the codebase's existing pattern of no cross-language shared constants.
- Adjusted the plan's suggested test tickers: the plan's Test 2 example used `GOOGL`/`AMZN`, but the `client` fixture's `price_cache` only seeds `AAPL`/`MSFT` prices (`backend/tests/api/conftest.py`'s `SEEDED_PRICES`), so trades against unseeded tickers 404 and don't produce a snapshot. Used `AAPL`/`MSFT` repeats instead to reliably produce 4 snapshots — this is a same-behavior substitution, not a deviation from the task's intent.

## Deviations from Plan

None - plan executed exactly as written (aside from the test-ticker substitution noted above under Decisions Made, which was necessary for the test to pass against the existing fixture setup and does not change the behavior under test).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `GET /api/portfolio/history` is bounded; no further action needed for PERF-03.
- Full backend suite: 283 passed (280 baseline + 3 new). Full frontend suite: 79 passed (76 baseline + 3 new). `npx tsc --noEmit` and `npm run lint` both clean. `ruff check app/ tests/` clean.
- Manual verification: `curl "http://localhost:8000/api/portfolio/history?limit=5"` returns at most 5 rows (verified via TestClient, equivalent HTTP path); `curl "...?limit=99999"` returns 422 (verified).

---
*Phase: 03-performance-hardening*
*Completed: 2026-08-16*

## Self-Check: PASSED
