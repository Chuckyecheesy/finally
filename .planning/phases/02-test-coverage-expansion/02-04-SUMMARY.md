---
phase: 02-test-coverage-expansion
plan: 04
subsystem: testing
tags: [vitest, testing-library, recharts, react]

requires:
  - phase: 02-test-coverage-expansion
    provides: colocated frontend test conventions established in plans 02-01 through 02-03
provides:
  - Colocated Vitest tests for Heatmap.tsx, PnlChart.tsx, and PriceChart.tsx
  - Reusable pattern for mocking recharts' ResponsiveContainer under jsdom (clones children with explicit width/height)
affects: [test-coverage-expansion, frontend]

tech-stack:
  added: []
  patterns:
    - "vi.mock(\"recharts\", ...) overriding only ResponsiveContainer, cloning its child element with explicit width/height props so LineChart/AreaChart/Treemap render real SVG under jsdom (ResizeObserver stub never fires)"

key-files:
  created:
    - frontend/src/components/Heatmap.test.tsx
    - frontend/src/components/PnlChart.test.tsx
    - frontend/src/components/PriceChart.test.tsx
  modified: []

key-decisions:
  - "Recharts mock must clone the child element with explicit width/height props (not just wrap it in a fixed-size div) — real ResponsiveContainer injects width/height onto its child via cloneElement, and without that injection LineChart/AreaChart/Treemap render an empty recharts-wrapper with no SVG content."
  - "PriceChart price/percent assertions scoped to the Panel's <header> element via container.querySelector, since the Y-axis tick labels (e.g. '95.00') can collide with the header's formatted price text using screen.getByText."

patterns-established:
  - "Recharts component test scaffolding: mock ResponsiveContainer to clone+resize its child, then assert on real rendered SVG (e.g. path.recharts-line-curve stroke) rather than mocking the whole chart away."

requirements-completed: [TEST-04]

duration: 25min
completed: 2026-08-16
---

# Phase 02 Plan 04: Recharts Component Test Coverage Summary

**Colocated Vitest+RTL tests for Heatmap, PnlChart, and PriceChart using a child-cloning ResponsiveContainer mock so real Recharts SVG renders under jsdom**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-16T13:55:00Z
- **Completed:** 2026-08-16T14:20:42Z
- **Tasks:** 2
- **Files modified:** 3 (all new test files)

## Accomplishments
- `Heatmap.tsx` now has a passing test covering its empty-state text, quantity/price filtering (both must be positive), Treemap cell rendering (`role="listitem"`/`aria-label`), and the `onSelect` click callback
- `PnlChart.tsx` now has a passing test covering the <2-snapshot empty state and both rising (`var(--color-primary)`) and falling (`var(--color-down)`) line-stroke branches
- `PriceChart.tsx` now has a passing test covering both empty-state message variants (ticker selected vs. null), the header price/percent display, and both up/down session-change colorings
- Established a reusable `vi.mock("recharts", ...)` pattern that clones `ResponsiveContainer`'s child with explicit `width`/`height` props — required because real Recharts charts (`LineChart`, `AreaChart`, `Treemap`) only render their internal SVG when they receive concrete pixel dimensions, which the real `ResponsiveContainer` normally injects via `cloneElement` after a `ResizeObserver` callback that never fires under jsdom's stub

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Heatmap.test.tsx and PnlChart.test.tsx** - `a2cba45` (test)
2. **Task 2: Add PriceChart.test.tsx** - `3fed6c6` (test)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `frontend/src/components/Heatmap.test.tsx` - Empty-state, filtering, cell rendering, and click-callback coverage for the portfolio treemap
- `frontend/src/components/PnlChart.test.tsx` - Empty-state and rising/falling stroke-color coverage for the portfolio value line chart
- `frontend/src/components/PriceChart.test.tsx` - Empty-state, session-change calculation, and header price/percent coverage for the session price chart

## Decisions Made
- The plan's suggested mock (`ResponsiveContainer` wrapping children in a fixed-size `<div>` without cloning) was insufficient in practice: the initial implementation left `LineChart`/`AreaChart`/`Treemap` with no `width`/`height` props, so Recharts rendered an empty `.recharts-wrapper` with no SVG children and all interaction/coloring assertions failed. Fixed by cloning the child element with explicit `width={600} height={400}` props, matching what the real `ResponsiveContainer` does internally via `cloneElement`. This is a same-task correction (Rule 1 — bug in the test code being written, not the plan's documented behavior), verified by re-running the test suite before proceeding.
- `PriceChart.test.tsx`'s price/percent assertions were scoped to `container.querySelector("header")` rather than global `screen.getByText(...)`, because the chart's own Y-axis tick labels (e.g., `"95.00"`) can render the same text as the header's formatted price/percent, causing `getByText` to throw a multiple-elements-found error. This is a corrected implementation of the plan's specified assertion strategy, not a scope change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Recharts ResponsiveContainer mock needed to clone+resize its child, not just wrap it**
- **Found during:** Task 1 (Heatmap.test.tsx / PnlChart.test.tsx), confirmed again in Task 2 (PriceChart.test.tsx)
- **Issue:** The interfaces block's suggested mock only wrapped `children` in a fixed-size `<div>`; real Recharts child components (`LineChart`, `AreaChart`, `Treemap`) require explicit `width`/`height` props passed directly to them (normally injected by the real `ResponsiveContainer` via `cloneElement`), so without that injection they rendered no SVG content and all four interaction/color-based assertions failed
- **Fix:** Updated the mock in all three test files to `cloneElement` the child with explicit `width={600} height={400}` props before rendering it inside the sized wrapper `<div>`
- **Files modified:** frontend/src/components/Heatmap.test.tsx, frontend/src/components/PnlChart.test.tsx, frontend/src/components/PriceChart.test.tsx
- **Verification:** `npm test -- Heatmap.test.tsx PnlChart.test.tsx PriceChart.test.tsx` — all 13 new tests pass; full `npm test` — 54/54 passing
- **Committed in:** a2cba45 (Task 1), 3fed6c6 (Task 2)

**2. [Rule 1 - Bug] PriceChart price/percent text collided with chart Y-axis tick labels**
- **Found during:** Task 2 (PriceChart.test.tsx)
- **Issue:** `screen.getByText("95.00")` matched both the header's formatted price span and a Y-axis tick label rendering the same numeric string, throwing a multiple-elements-found error
- **Fix:** Scoped the assertion to `container.querySelector("header")` and asserted `toHaveTextContent`/`.tnum:last-child` within that scope instead of a global text query
- **Files modified:** frontend/src/components/PriceChart.test.tsx
- **Verification:** `npm test -- PriceChart.test.tsx` — all 5 tests pass
- **Committed in:** 3fed6c6 (Task 2)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in the test scaffolding being authored, not the production components)
**Impact on plan:** Both fixes were necessary for the tests to actually exercise the intended behavior rather than passing vacuously against unrendered charts. No scope creep — zero production code was touched.

## Issues Encountered
None beyond the two auto-fixed deviations above, both resolved within the same task before committing.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TEST-04 is now fully closed: all six previously-untested frontend components (`Heatmap`, `PnlChart`, `PriceChart` in this plan; `Sparkline`, `TradeBar`, `Panel` in plans 02-01 through 02-03) have colocated passing test coverage
- Full frontend suite: 54/54 tests passing (9 test files) — no regressions introduced
- No blockers for subsequent phases

---
*Phase: 02-test-coverage-expansion*
*Completed: 2026-08-16*

## Self-Check: PASSED

All created files verified present (Heatmap.test.tsx, PnlChart.test.tsx, PriceChart.test.tsx, this SUMMARY.md). Both task commits (a2cba45, 3fed6c6) verified present in `git log`.
