---
phase: 02-test-coverage-expansion
plan: 01
subsystem: testing
tags: [pytest, numpy, gbm-simulator, cholesky, correlation-matrix]

# Dependency graph
requires:
  - phase: 01-fragile-area-fixes-their-test-coverage
    provides: baseline of 274 backend + 41 frontend passing tests
provides:
  - "TestGBMSimulatorAtScale test class in backend/tests/market/test_simulator.py covering a 60-ticker (10 default + 50 synthetic) non-default watchlist"
  - "Verification that GBMSimulator's Cholesky factor correctly reconstructs the intended correlation matrix at scale, not just avoids raising"
  - "Verification that simulated prices stay strictly positive over 500 steps and after add/remove ticker churn at 60-ticker scale"
affects: [02-test-coverage-expansion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Independent reconstruction of the expected correlation matrix via GBMSimulator._pairwise_correlation for every ticker pair, then np.allclose against sim._cholesky @ sim._cholesky.T, as a stronger assertion than 'construction did not raise'"

key-files:
  created: []
  modified:
    - backend/tests/market/test_simulator.py

key-decisions:
  - "Reused the existing file's docstring/comment tone (see test_full_default_ticker_set_cholesky_is_well_behaved) for the new test class docstring"

patterns-established:
  - "Large-scale correlation-matrix well-behavedness check: reconstruct expected corr matrix from _pairwise_correlation, compare Cholesky-factor product via np.allclose, and independently assert PSD via np.linalg.eigvalsh"

requirements-completed: [TEST-02]

# Metrics
duration: 12min
completed: 2026-08-16
---

# Phase 2 Plan 1: GBM Simulator At-Scale Cholesky Stability Summary

**Added TestGBMSimulatorAtScale in backend/tests/market/test_simulator.py, proving the GBM simulator's Cholesky/correlation math stays well-behaved and prices stay positive for a 60-ticker non-default watchlist including add/remove churn.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-16T14:07:00Z
- **Completed:** 2026-08-16T14:19:03Z
- **Tasks:** 1 completed
- **Files modified:** 1

## Accomplishments
- Added `test_large_non_default_watchlist_cholesky_is_well_behaved`, which independently reconstructs the 60x60 expected correlation matrix from `GBMSimulator._pairwise_correlation` and asserts `np.allclose(sim._cholesky @ sim._cholesky.T, expected_corr, atol=1e-8)`, plus a positive-semi-definite eigenvalue check — proving the Cholesky factor truly reconstructs the intended correlation matrix, not merely that construction didn't raise `LinAlgError`.
- Added `test_large_watchlist_prices_stay_positive_over_many_steps`, stepping a 60-ticker simulator 500 times and asserting every generated price stays strictly positive and the tracked ticker set stays consistent.
- Added `test_cholesky_stable_after_add_remove_churn_at_scale`, adding 5 then removing 5 tickers on the 60-ticker simulator and confirming the Cholesky factor remains well-shaped and prices remain positive after the churn.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 50+ ticker Cholesky/correlation stability tests to test_simulator.py** - `b6a1f72` (test)

**Plan metadata:** (pending — see final commit below)

## Files Created/Modified
- `backend/tests/market/test_simulator.py` - Added `class TestGBMSimulatorAtScale` with three new test methods (60-ticker Cholesky reconstruction, price positivity at scale, churn stability); zero production code changes.

## Decisions Made
None - followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Worktree branch was found stale at spawn time (missing this phase's plan files and prior test files) and was self-healed via `git reset --hard` to the correct fresh-branch commit per the executor's `worktree_self_heal` instructions, before any commits were made on the branch — this is a harness/spawn issue, not a plan deviation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `backend/tests/market/test_simulator.py` now has 23 passing tests (20 pre-existing + 3 new); full backend suite is 277 passing (274 pre-existing + 3 new), confirmed via `uv run pytest`.
- `uv run --extra dev ruff check app/ tests/` passes with no findings.
- TEST-02 requirement satisfied; no blockers for the remaining Phase 2 plans (TEST-01, TEST-03, TEST-04).

---
*Phase: 02-test-coverage-expansion*
*Completed: 2026-08-16*

## Self-Check: PASSED

- FOUND: backend/tests/market/test_simulator.py
- FOUND: `class TestGBMSimulatorAtScale` present in file
- FOUND: commit b6a1f72 in git log
