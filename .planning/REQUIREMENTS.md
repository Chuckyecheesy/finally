# Requirements: FinAlly — Hardening Pass

**Defined:** 2026-08-16
**Core Value:** The existing trading-workstation experience must keep working exactly as-is while every specific reliability, coverage, performance, and dependency risk identified in the codebase audit (`.planning/codebase/CONCERNS.md`) is closed out — without regressing the 305 passing tests.

## v1 Requirements

All requirements below are hardening fixes to the already-shipped v1 application (see PROJECT.md § Validated). No new user-facing features.

### Fragile Areas

- [ ] **FRAG-01**: `_include_chat_router` (`backend/app/main.py`) fails hard at startup if `app.llm.router` can't be imported, instead of silently logging a warning and booting without `/api/chat`
- [ ] **FRAG-02**: Portfolio API's `PositionOut` carries a `stale: bool` flag so the frontend can distinguish "priced at avg_cost because the price cache has no data" from a genuine break-even position

### Test Coverage

- [ ] **TEST-01**: Backend tests cover `_DeferredMarketSource`'s pre-startup-access `RuntimeError` path and the chat-router import-failure path in `backend/app/main.py`
- [ ] **TEST-02**: A GBM/Cholesky stability test exercises a large (50+), non-default ticker watchlist in `backend/app/market/simulator.py`, asserting the correlation matrix stays well-behaved and prices stay positive
- [ ] **TEST-03**: A realistically-mocked integration test exercises a full Massive API poll cycle feeding the SSE stream and portfolio valuation together (beyond `massive_client.py`'s existing unit-level parsing tests)
- [ ] **TEST-04**: Unit tests exist for `Heatmap.tsx`, `PnlChart.tsx`, `PriceChart.tsx`, `Sparkline.tsx`, `TradeBar.tsx`, and `Panel.tsx` (currently untested frontend components)

### Performance

- [ ] **PERF-01**: The frontend's 15s REST reconciliation poll (`useTerminal.ts`) is gated on `document.visibilityState` so a backgrounded tab stops polling
- [ ] **PERF-02**: Trade-triggered portfolio snapshots are debounced/deduped against the periodic 30s snapshot so active trading doesn't produce near-duplicate `portfolio_snapshots` rows
- [ ] **PERF-03**: `GET /api/portfolio/history` accepts a `limit`/time-range parameter so a long session's P&L chart data doesn't grow unbounded per request

### Dependency Drift

- [ ] **DEPS-01**: Next.js upgraded 15.5.23 → 16.x, with `output: 'export'` static export re-verified to build cleanly
- [ ] **DEPS-02**: TypeScript upgraded 5.7.3 → 7.x
- [ ] **DEPS-03**: ESLint upgraded 9.18.0 → 10.x
- [ ] **DEPS-04**: React and React-DOM upgraded 19.0.0 → 19.2.x

## v2 Requirements

None — this milestone is scoped tightly to the CONCERNS.md hardening backlog. Any new feature ideas surfaced during this work should be captured separately rather than folded in here.

## Out of Scope

| Feature | Reason |
|---------|--------|
| New user-facing features | This is a hardening-only milestone |
| Multi-user support / authentication | Explicitly deferred by PLAN.md's single-user design |
| Public-facing deployment hardening (rate limiting, auth) | Not requested; app remains local-single-user |
| Chat history retention/pruning UI | Flagged in CONCERNS.md as a future consideration, not urgent for this pass |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FRAG-01 | TBD | Pending |
| FRAG-02 | TBD | Pending |
| TEST-01 | TBD | Pending |
| TEST-02 | TBD | Pending |
| TEST-03 | TBD | Pending |
| TEST-04 | TBD | Pending |
| PERF-01 | TBD | Pending |
| PERF-02 | TBD | Pending |
| PERF-03 | TBD | Pending |
| DEPS-01 | TBD | Pending |
| DEPS-02 | TBD | Pending |
| DEPS-03 | TBD | Pending |
| DEPS-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0 (pending roadmap creation)
- Unmapped: 13 ⚠️

---
*Requirements defined: 2026-08-16*
*Last updated: 2026-08-16 after initial definition*
