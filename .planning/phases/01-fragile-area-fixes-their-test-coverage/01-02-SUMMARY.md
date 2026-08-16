---
phase: 01-fragile-area-fixes-their-test-coverage
plan: 02
subsystem: api
tags: [fastapi, pydantic, react, typescript, portfolio-valuation]

# Dependency graph
requires: []
provides:
  - "PositionOut.stale boolean on GET /api/portfolio and POST /api/portfolio/trade"
  - "frontend Position.stale contract mirrored through api.ts normalization and useTerminal's live-price overlay"
affects: [frontend-positions-ui, portfolio-valuation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cache-miss valuation fallback (avg_cost substitution) now flagged explicitly via a boolean rather than being silently indistinguishable from a genuine break-even"

key-files:
  created: []
  modified:
    - backend/app/api/schemas.py
    - backend/app/api/portfolio.py
    - backend/tests/api/test_portfolio.py
    - frontend/src/lib/types.ts
    - frontend/src/lib/api.ts
    - frontend/src/hooks/useTerminal.ts
    - frontend/src/components/PositionsTable.test.tsx
    - .gitignore

key-decisions:
  - "Fixed .gitignore's bare `lib/` pattern (Python-template leftover) to `/lib/` (root-anchored) after discovering it had silently excluded all of frontend/src/lib/ (api.ts, types.ts, format.ts) from git tracking since inception"

patterns-established:
  - "Money/valuation fallbacks that could mask real state (e.g. avg_cost substitution) should carry an explicit boolean flag on the API contract rather than relying on callers to infer intent from a coincidental value"

requirements-completed: [FRAG-02]

# Metrics
duration: 25min
completed: 2026-08-16
---

# Phase 01 Plan 02: Stale Position Flag Summary

**`PositionOut.stale` boolean surfaces cache-miss avg_cost valuations distinctly from genuine break-even positions, mirrored end-to-end into the frontend `Position` contract.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed
- **Files modified:** 8 (7 planned + `.gitignore`)

## Accomplishments
- `GET /api/portfolio` and `POST /api/portfolio/trade` now emit `stale: bool` per position, true only when the price cache has no data for that ticker and the position was valued at `avg_cost`
- A genuine break-even position (real cached price equal to avg_cost) correctly reports `stale: false` — the discriminating case the requirement exists for
- Frontend `Position` type, `normalizePosition`, and `livePositions` (in `useTerminal`) carry the same contract; a live SSE price overlay always clears `stale`
- No rendering component or UI behavior touched — data/contract change only, per scope guard

## Task Commits

Each task was committed atomically:

1. **Task 1: Add PositionOut.stale and set it in build_portfolio, with tests** - `b3a552e` (feat)
2. **Task 2: Mirror stale into the frontend Position contract** - `6fc5baa` (feat)

## Files Created/Modified
- `backend/app/api/schemas.py` - `PositionOut.stale: bool = False`
- `backend/app/api/portfolio.py` - `build_portfolio` resolves `cached_price`/`stale` explicitly before falling back to `avg_cost`
- `backend/tests/api/test_portfolio.py` - 4 new tests: cached-price (not stale), cache-miss (stale), break-even-with-real-price (not stale), trade-response carries `stale`
- `frontend/src/lib/types.ts` - `Position.stale: boolean` (required)
- `frontend/src/lib/api.ts` - `normalizePosition` reads `raw.stale === true`
- `frontend/src/hooks/useTerminal.ts` - `livePositions` sets `stale: false` in the live-price branch
- `frontend/src/components/PositionsTable.test.tsx` - existing `Position` literals gain `stale: false`; 2 new tests for the `livePositions` stale-clearing/retention behavior
- `.gitignore` - anchored `lib/`/`lib64/` to repo root (`/lib/`, `/lib64/`) so the pattern stops matching `frontend/src/lib/`

## Decisions Made
- Followed the plan's exact field placement and comparison semantics (`stale=stale` in the `PositionOut(...)` construction, `raw.stale === true` strict comparison in `normalizePosition`)
- Fixed a pre-existing `.gitignore` bug (see Deviations) rather than working around it, since it directly blocked committing this task's required frontend changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `.gitignore`'s `lib/` pattern silently excluded `frontend/src/lib/` from git tracking**
- **Found during:** Task 2, when `git status` showed no diff for `frontend/src/lib/types.ts` and `api.ts` despite edits being present on disk
- **Issue:** `.gitignore` line 17 had a bare `lib/` entry (from the standard Python template, intended for `<project>/lib/` build output) that matches any directory named `lib` anywhere in the repo, including `frontend/src/lib/`. `git ls-files` confirmed `api.ts`, `types.ts`, and `format.ts` had never been tracked by git in this repo's history — this task's edits to `types.ts` and `api.ts` could not be committed at all without fixing this.
- **Fix:** Anchored the pattern to the repo root (`lib/` → `/lib/`, `lib64/` → `/lib64/`); confirmed no root-level or `backend/`-level `lib/` directory exists that the original pattern was protecting (Python venv is already covered by the separate `.venv` ignore rule). Added the three previously-untracked files to git.
- **Files modified:** `.gitignore`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/format.ts` (the latter added purely to restore tracking; its content was untouched by this plan)
- **Verification:** `git ls-files frontend/src/lib` now lists all three files; `git diff` correctly shows this plan's edits to `api.ts`/`types.ts`
- **Committed in:** `6fc5baa` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to complete the task as specified — the plan's file list explicitly names `frontend/src/lib/api.ts` and `types.ts` as files to modify, and those changes could not otherwise be committed. No scope creep beyond restoring git tracking for the `lib/` directory.

## Issues Encountered
None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FRAG-02 is closed; backend and frontend contracts for `stale` are consistent and tested
- `frontend/src/lib/` is now correctly tracked by git going forward — future edits to `api.ts`, `types.ts`, `format.ts` will show up in diffs and can be committed normally
- No blockers for subsequent phase-01 plans

---
*Phase: 01-fragile-area-fixes-their-test-coverage*
*Completed: 2026-08-16*

## Self-Check: PASSED

All created/modified files and both task commit hashes verified present.
