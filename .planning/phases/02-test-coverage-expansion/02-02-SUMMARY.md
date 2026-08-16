---
phase: 02-test-coverage-expansion
plan: 02
subsystem: testing
tags: [pytest, massive-api, polygon, sse, portfolio, integration-test]

# Dependency graph
requires:
  - phase: 01-fragile-area-fixes-their-test-coverage
    provides: PositionOut.stale flag (FRAG-02) that this test's stale-fallback assertion depends on
provides:
  - Integration test proving one Massive poll cycle's cached output is the exact value both the SSE stream emits and portfolio valuation marks a position to market with
  - Coverage of the stale-fallback degradation path through the full poll -> cache -> valuation chain (not just build_portfolio in isolation)
affects: [test-coverage-expansion, dependency-drift]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Compose existing per-layer unit tests into a single integration test by driving _poll_once() then feeding the same PriceCache into _generate_events() and build_portfolio()"]

key-files:
  created: [backend/tests/market/test_massive_integration.py]
  modified: []

key-decisions:
  - "Reused FakeSnapshot/FakeLastTrade/_snapshot fakes from test_massive.py via direct import rather than redefining them, to keep the pinned Massive field contract single-sourced"
  - "Defined a local FakeRequest/FakeClient pair (not imported from test_stream.py) per the plan's interface note that test_stream.py's fakes are not a documented shared contract"

patterns-established: []

requirements-completed: [TEST-03]

# Metrics
duration: 12min
completed: 2026-08-16
---

# Phase 02 Plan 02: Massive Poll Integration Test Summary

**Integration test proving a single Massive API poll cycle's cached price reaches both the SSE stream payload and portfolio valuation identically, including the stale-fallback degradation path**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-16T14:07:00Z
- **Completed:** 2026-08-16T14:19:12Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- New `backend/tests/market/test_massive_integration.py` with `class TestMassivePollFeedsStreamAndPortfolio` containing three tests: SSE payload matches poll output, portfolio marks a held position to market from a poll, and a failed price extraction leaves the position correctly flagged `stale=True`
- Closes TEST-03 (test coverage gap: Massive poll cycle never previously tested end-to-end against the SSE stream and portfolio layers together)
- Full backend suite: 277 passed (up from 274), ruff clean, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the full Massive poll -> SSE stream + portfolio valuation integration test** - `b055ea6` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `backend/tests/market/test_massive_integration.py` - Three-test integration suite driving `MassiveDataSource._poll_once()` and feeding the resulting `PriceCache` into both `_generate_events` (SSE) and `build_portfolio` (valuation)

## Decisions Made
- Reused `FakeSnapshot`/`FakeLastTrade`/`_snapshot` from `test_massive.py` by direct import rather than reinventing MagicMocks, preserving the pinned Massive field contract
- Defined a local minimal `FakeRequest`/`FakeClient` pair rather than importing `test_stream.py`'s, per the plan's explicit guidance that it isn't a documented shared contract

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
TEST-03 closed. Remaining Phase 2 test-coverage items (TEST-01, TEST-02, TEST-04) are tracked in separate plans (02-01, 02-03, 02-04) per the phase's wave structure. No blockers for subsequent plans in this phase.

---
*Phase: 02-test-coverage-expansion*
*Completed: 2026-08-16*

## Self-Check: PASSED

- FOUND: backend/tests/market/test_massive_integration.py
- FOUND: .planning/phases/02-test-coverage-expansion/02-02-SUMMARY.md
- FOUND: b055ea6 (Task 1 commit)
