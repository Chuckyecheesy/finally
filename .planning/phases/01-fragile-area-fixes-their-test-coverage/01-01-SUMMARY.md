---
phase: 01-fragile-area-fixes-their-test-coverage
plan: 01
subsystem: infra
tags: [fastapi, startup, error-handling, pytest]

# Dependency graph
requires: []
provides:
  - "create_app() raises RuntimeError (chained from ImportError) if app.llm.router cannot be imported, instead of silently booting without /api/chat"
  - "Test coverage for the chat-router import-failure path, its error-level log, the /api/chat mounted happy path, and all five _DeferredMarketSource methods' pre-startup RuntimeError"
affects: [01-02, backend-startup, api-app-factory]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-fast startup: a swallowed import for a now-mandatory subsystem raises RuntimeError instead of degrading to a partial app"

key-files:
  created: []
  modified:
    - backend/app/main.py
    - backend/tests/api/test_app.py

key-decisions:
  - "Chat-router import failure is fatal at app construction (FRAG-01) — aligns with STATE.md decision that a broken /api/chat should crash the process rather than 404 invisibly"
  - "Dropped inspect.signature-based keyword filtering in favor of a direct create_chat_router(price_cache=, market_source=) call, since the factory's signature is now stable and known"

patterns-established:
  - "Startup-mandatory subsystem imports: log at ERROR naming the module, then raise RuntimeError chained via `from exc` — detail travels through the exception chain/logs only, never into a response body"

requirements-completed: [FRAG-01, TEST-01]

duration: 15min
completed: 2026-08-16
---

# Phase 01 Plan 01: Fatal chat-router import failure + deferred-source test coverage Summary

**`_include_chat_router` now raises `RuntimeError` (chained from `ImportError`, logged at ERROR) instead of silently booting without `/api/chat`; `_DeferredMarketSource`'s pre-startup `RuntimeError` contract is now tested across all five interface methods.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-08-16T12:52:00Z (approx)
- **Completed:** 2026-08-16T13:07:04Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `create_app()` fails loudly (not silently) when `app.llm.router` can't be imported, closing the FRAG-01 gap identified in the codebase audit
- Removed the `inspect.signature`-based keyword filtering in `_include_chat_router`; the factory is now called directly with explicit keywords
- `backend/tests/api/test_app.py` grew from 6 to 10 tests, covering: the `/api/chat` happy path, the import-failure `RuntimeError` (with exception-chain assertion), the error-level log content, and all five `_DeferredMarketSource` methods (`start`, `stop`, `add_ticker`, `remove_ticker`, `get_tickers`) raising before startup

## Task Commits

Each task was committed atomically:

1. **Task 1: Make chat-router import failure fatal at app construction** - `b55ec3b` (feat)
2. **Task 2: Test the import-failure path and every deferred-source pre-startup method** - `8d48205` (test)

**Plan metadata:** pending (docs: complete plan — added by orchestrator/final commit step)

## Files Created/Modified
- `backend/app/main.py` - `_include_chat_router` raises `RuntimeError` (chained from `ImportError`, error-logged first) instead of warning-and-returning; dropped `import inspect` and the signature-filtering call in favor of an explicit-keyword call to `create_chat_router`
- `backend/tests/api/test_app.py` - Added `test_chat_route_is_mounted`, `test_chat_router_import_failure_raises_at_app_creation`, `test_chat_router_import_failure_is_logged_as_error`, `test_deferred_source_methods_all_raise_before_startup`; added `import logging`, `import sys`; updated module docstring

## Decisions Made
- Followed the plan exactly: message text is the fixed string naming `app.llm.router` only (no env values, file paths, or raw exception repr), per the plan's threat-model disposition (T-01-01, mitigate).
- No architectural changes needed; this was a straightforward hardening/testing change within one file plus its test file.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Worth noting for context: at agent spawn, this worktree's branch (`worktree-agent-af669e4f36e95d53f`) was pinned to an ancestor commit (`790abf5`) that predated the GSD-initialized `agent-teams` branch tip (`2a37c9d`), so `.planning/` and the current `backend/app/main.py` were not yet present in the worktree. Resolved with a safe fast-forward merge (`git merge --ff-only agent-teams`) before starting Task 1 — no rebase, no history rewrite, no destructive operation.

## Mutation check (acceptance criteria item)

Reasoned through rather than physically re-run: `test_chat_router_import_failure_raises_at_app_creation` asserts `pytest.raises(RuntimeError)` around `main.create_app()` with `app.llm.router` poisoned in `sys.modules`. If Task 1's `raise RuntimeError(...) from exc` were reverted to the old `logger.warning(...); return`, `create_app()` would return normally (no exception raised), so `pytest.raises(RuntimeError)` would fail with `Failed: DID NOT RAISE <class 'RuntimeError'>`. The test is a true, non-vacuous guard against that regression.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FRAG-01 and TEST-01 (this plan's scope) are closed; full backend suite is green at 270 tests (266 pre-existing + 4 new).
- 01-02 (the next plan in this phase) is unaffected by this plan's changes and can proceed independently.
- No blockers identified.

---
*Phase: 01-fragile-area-fixes-their-test-coverage*
*Completed: 2026-08-16*

## Self-Check: PASSED

- FOUND: backend/app/main.py
- FOUND: backend/tests/api/test_app.py
- FOUND: .planning/phases/01-fragile-area-fixes-their-test-coverage/01-01-SUMMARY.md
- FOUND: commit b55ec3b
- FOUND: commit 8d48205
