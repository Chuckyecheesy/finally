---
phase: 03-performance-hardening
plan: 01
subsystem: ui
tags: [react, hooks, performance, visibility-api, vitest]

# Dependency graph
requires:
  - phase: 02-test-coverage-expansion
    provides: stable frontend test suite (76 tests) to regress against
provides:
  - Visibility-gated 15s REST reconciliation poll in useTerminal
  - Test coverage (useTerminal.test.ts) proving stop/resume behavior on visibilitychange
affects: [03-02, 03-03, 04-dependency-upgrades]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Effect-scoped start/stop closures around a nullable timer ref, driven by a visibilitychange listener, to gate setInterval-based polling on document.visibilityState"

key-files:
  created: [frontend/src/hooks/useTerminal.test.ts]
  modified: [frontend/src/hooks/useTerminal.ts]

key-decisions:
  - "Kept refresh's signature and the 15_000ms interval constant untouched; only the effect scheduling refresh changed, per plan's interface constraint"
  - "start() is idempotent (no-op if timer already set) so the visibilitychange listener and the mount-time start() call can't double-schedule the interval"

patterns-established:
  - "Visibility-gated polling: local start/stop closures over a nullable timer variable, toggled by a visibilitychange listener, with mount-time start() skipped only when the tab is already hidden"

requirements-completed: [PERF-01]

duration: 20min
completed: 2026-08-16
---

# Phase 03 Plan 01: Visibility-Gated Reconciliation Polling Summary

**useTerminal's 15s REST reconciliation poll (`fetchPortfolio`/`fetchWatchlist`/`fetchHistory`) now stops entirely when the browser tab is backgrounded and resumes with an immediate refresh when it's foregrounded again.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-16T18:02:00Z
- **Completed:** 2026-08-16T18:22:26Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Rewrote `useTerminal`'s polling `useEffect` to gate the `setInterval` on `document.visibilityState`, stopping it on `visibilitychange` -> hidden and restarting (with an immediate `refresh()`) on `visibilitychange` -> visible
- Added `frontend/src/hooks/useTerminal.test.ts` with 3 behaviors (stays polling while visible, stops when hidden, resumes with immediate refresh when re-shown) using `vi.useFakeTimers()` and `renderHook`
- Confirmed RED (2 of 3 new tests failed) against the original unconditional-interval implementation before writing the fix
- Full frontend suite (79 tests: 76 baseline + 3 new) passes; `npm run lint` and `tsc --noEmit` both clean

## Task Commits

Each task was committed atomically (TDD RED then GREEN):

1. **Task 1 RED: add failing test for visibility-gated polling** - `7efaf72` (test)
2. **Task 1 GREEN: gate 15s reconciliation poll on tab visibility** - `403a03b` (feat)

## Files Created/Modified
- `frontend/src/hooks/useTerminal.test.ts` - New test file: 3 vitest behaviors covering visible/hidden/resume polling states, mocking `@/lib/api` and using fake timers
- `frontend/src/hooks/useTerminal.ts` - Polling effect rewritten with `start`/`stop` closures around a nullable timer, wired to a `visibilitychange` listener registered/removed in the effect

## Decisions Made
- Preserved `refresh`'s `useCallback` signature and the `15_000` interval constant exactly, touching only the scheduling effect, per the plan's interface note
- Made `start()` idempotent so the mount-time call and the visibilitychange-triggered call can never create two overlapping intervals

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The first `npm test` (full suite) run hit an environment-level vitest worker fetch timeout (`Timeout calling "fetch" with ["/@vite/env","web"]`) unrelated to any test logic — a transient sandboxing/IO hiccup in this run environment. Re-ran `npm test` and it completed cleanly with all 79 tests passing; no code change required.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PERF-01 closed; `useTerminal.ts`'s polling behavior is now the reference pattern for any future visibility-aware client polling in this codebase
- No blockers for 03-02/03-03

---
*Phase: 03-performance-hardening*
*Completed: 2026-08-16*

## Self-Check: PASSED

- FOUND: frontend/src/hooks/useTerminal.test.ts
- FOUND: frontend/src/hooks/useTerminal.ts
- FOUND: .planning/phases/03-performance-hardening/03-01-SUMMARY.md
- FOUND commit: 7efaf72 (test)
- FOUND commit: 403a03b (feat)
