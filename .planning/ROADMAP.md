# Roadmap: FinAlly — Hardening Pass

## Overview

This milestone closes out every reliability, coverage, performance, and dependency-drift item surfaced by the codebase audit (`.planning/codebase/CONCERNS.md`), without changing user-facing behavior or regressing the 305 tests already passing. The four phases move from the two known fragile behaviors and their direct test coverage, through the remaining test-coverage gaps, into perf nits, and finish with the frontend dependency-version bump (isolated last since it carries the highest regression risk to the static-export build that the whole Docker architecture depends on).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Fragile Area Fixes & Their Test Coverage** - Chat-router import failures and stale-price P&L stop failing silently, backed by new tests for both paths
- [ ] **Phase 2: Test Coverage Expansion** - Close the simulator-scale, Massive-integration, and frontend-component test coverage gaps
- [ ] **Phase 3: Performance Hardening** - Visibility-gated polling, deduped snapshots, bounded history endpoint
- [ ] **Phase 4: Dependency Upgrades** - Next.js, TypeScript, ESLint, and React brought current, with static export re-verified

## Phase Details

### Phase 1: Fragile Area Fixes & Their Test Coverage
**Goal**: The two known fragile behaviors identified in the audit — a chat router that silently fails to mount, and a portfolio position that silently reports 0% P&L when priced at cost due to missing market data — are eliminated and directly covered by tests.
**Depends on**: Nothing (first phase)
**Requirements**: FRAG-01, FRAG-02, TEST-01
**Success Criteria** (what must be TRUE):
  1. Backend startup fails loudly (raises/logs an error, does not silently boot without `/api/chat`) if `app.llm.router` can't be imported
  2. `GET /api/portfolio` response includes a `stale: bool` field per position, true when the position is priced at `avg_cost` because the price cache has no data for that ticker
  3. `backend/tests/api/test_app.py` has passing tests covering `_DeferredMarketSource`'s pre-startup-access `RuntimeError` path and the chat-router import-failure path
  4. All 305 existing tests (266 backend + 39 frontend) still pass
**Plans**: TBD

### Phase 2: Test Coverage Expansion
**Goal**: The three remaining test-coverage gaps flagged in the audit — simulator behavior at scale, Massive-API integration, and untested frontend visual components — are closed so regressions in these areas fail at test time instead of only in production or via the slower E2E suite.
**Depends on**: Phase 1
**Requirements**: TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. A new backend test exercises GBM/Cholesky correlation math against a 50+ ticker, non-default watchlist and asserts the correlation matrix stays well-behaved and all generated prices remain positive
  2. A new realistically-mocked integration test exercises a full Massive API poll cycle feeding both the SSE price stream and portfolio valuation in one flow (beyond `massive_client.py`'s existing unit-level parsing tests)
  3. `Heatmap.tsx`, `PnlChart.tsx`, `PriceChart.tsx`, `Sparkline.tsx`, `TradeBar.tsx`, and `Panel.tsx` each have a passing colocated `*.test.tsx` file
  4. Full backend (`uv run pytest`) and frontend (`npm test`) suites pass with the new tests included
**Plans**: TBD

### Phase 3: Performance Hardening
**Goal**: The three perf nits flagged in the audit — an unthrottled background-tab poll, near-duplicate portfolio snapshots during active trading, and an unbounded P&L history response — are fixed.
**Depends on**: Phase 2
**Requirements**: PERF-01, PERF-02, PERF-03
**Success Criteria** (what must be TRUE):
  1. Backgrounding the browser tab (`document.visibilityState === "hidden"`) stops the 15s REST reconciliation poll in `useTerminal.ts`; foregrounding the tab resumes it
  2. A trade executed within a few seconds of the periodic 30s snapshot does not produce a near-duplicate `portfolio_snapshots` row
  3. `GET /api/portfolio/history` accepts a `limit`/time-range query parameter and returns a bounded result set instead of the full unbounded history
  4. All existing and newly added tests (Phase 1 + Phase 2 additions included) still pass
**Plans**: TBD

### Phase 4: Dependency Upgrades
**Goal**: Frontend dependencies are brought current (Next.js, TypeScript, ESLint, React), with the load-bearing static export re-verified to build cleanly after the Next.js major-version bump.
**Depends on**: Phase 3
**Requirements**: DEPS-01, DEPS-02, DEPS-03, DEPS-04
**Success Criteria** (what must be TRUE):
  1. `next` is upgraded to 16.x and `npm run build` (with `output: 'export'`) produces a working static export in `frontend/out/` with no build errors
  2. `typescript` is upgraded to 7.x and the project typechecks with no new type errors
  3. `eslint` is upgraded to 10.x and lint passes with no new errors
  4. `react`/`react-dom` are upgraded to 19.2.x and the full frontend test suite still passes
  5. The Docker image builds successfully end-to-end with the upgraded frontend, and the container serves `/api/health` and the static UI correctly
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Fragile Area Fixes & Their Test Coverage | 0/TBD | Not started | - |
| 2. Test Coverage Expansion | 0/TBD | Not started | - |
| 3. Performance Hardening | 0/TBD | Not started | - |
| 4. Dependency Upgrades | 0/TBD | Not started | - |
