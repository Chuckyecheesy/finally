# FinAlly — Hardening Pass

## What This Is

FinAlly is an AI-powered trading workstation (Bloomberg-terminal-style UI, simulated portfolio, LLM chat copilot) built as a capstone project for an agentic AI coding course. The full v1 application — live market data streaming, portfolio/trading, watchlist management, AI chat with auto-executed trades, and the terminal frontend — is already built and passing its test suite (266 backend + 39 frontend tests). This GSD milestone is a **hardening pass**: fixing known fragile areas, closing test coverage gaps, resolving perf nits, and clearing dependency drift — all surfaced by an independent codebase audit (`.planning/codebase/CONCERNS.md`). No new user-facing features are in scope.

## Core Value

The existing trading-workstation experience must keep working exactly as-is while every specific reliability, coverage, performance, and dependency risk identified in the codebase audit is closed out — without regressing the 305 passing tests.

## Requirements

### Validated

- ✓ Live market data streaming (simulator + Massive/Polygon.io) via SSE — `backend/app/market/`
- ✓ Portfolio management: market-order buy/sell, positions, P&L — `backend/app/db/portfolio.py`, `backend/app/api/portfolio.py`
- ✓ Watchlist CRUD — `backend/app/api/watchlist.py`, `backend/app/db/watchlist.py`
- ✓ AI chat assistant with auto-executed trades/watchlist changes (LiteLLM → OpenRouter/Cerebras, structured output) — `backend/app/llm/`
- ✓ Terminal frontend: watchlist, price chart, heatmap, P&L chart, positions table, trade bar, chat panel — `frontend/src/components/`
- ✓ SQLite persistence with lazy schema init and seed data — `backend/app/db/`
- ✓ Single-container Docker deployment (Next.js static export served by FastAPI)
- ✓ Unit test suites: 266 backend (pytest), 39 frontend (Vitest + RTL); Playwright E2E suite in `test/`

### Active

**Fragile areas**
- [ ] FRAG-01: `_include_chat_router` in `backend/app/main.py` fails hard (not a silently-logged warning) if `app.llm.router` can't be imported, since the LLM module is now complete and a swallowed import should not degrade `/api/chat` invisibly
- [ ] FRAG-02: `PositionOut` (portfolio API) carries a `stale: bool` flag so the frontend can distinguish "priced at avg_cost because no market data" from a genuine break-even position, instead of silently reporting 0% P&L

**Test coverage gaps**
- [ ] TEST-01: Add coverage for `_DeferredMarketSource`'s pre-startup-access `RuntimeError` path and the chat-router import-failure path in `backend/app/main.py`
- [ ] TEST-02: Add a GBM/Cholesky stability test exercising a large (50+), non-default ticker watchlist in `backend/app/market/simulator.py`
- [ ] TEST-03: Add a realistically-mocked integration test exercising a full Massive API poll cycle feeding the SSE stream and portfolio valuation together (not just `massive_client.py` unit-level parsing)
- [ ] TEST-04: Add unit tests for the currently-untested frontend components: `Heatmap.tsx`, `PnlChart.tsx`, `PriceChart.tsx`, `Sparkline.tsx`, `TradeBar.tsx`, `Panel.tsx`

**Perf nits**
- [ ] PERF-01: Gate the frontend's 15s REST reconciliation poll (`useTerminal.ts`) on `document.visibilityState` so a backgrounded tab stops polling
- [ ] PERF-02: Debounce/dedupe trade-triggered portfolio snapshots that land within a few seconds of the periodic 30s snapshot, to avoid near-duplicate `portfolio_snapshots` rows during active trading
- [ ] PERF-03: Add a `limit`/time-range parameter to `GET /api/portfolio/history` so the P&L chart's data doesn't grow unbounded per request over a long session

**Dependency drift**
- [ ] DEPS-01: Upgrade Next.js 15.5.23 → 16.x; re-verify `output: 'export'` static export still builds cleanly (load-bearing for the single-container Docker architecture)
- [ ] DEPS-02: Upgrade TypeScript 5.7.3 → 7.x
- [ ] DEPS-03: Upgrade ESLint 9.18.0 → 10.x
- [ ] DEPS-04: Upgrade React/React-DOM 19.0.0 → 19.2.x

### Out of Scope

- New user-facing features — this is a hardening-only milestone, not a feature milestone
- Multi-user support / authentication — explicitly deferred by PLAN.md's single-user design; not revisited here
- Public-facing deployment hardening (rate limiting, auth for a public endpoint) — not requested; app remains local-single-user
- Chat history retention/pruning UI — flagged in CONCERNS.md as a future consideration, not urgent enough for this pass

## Context

- This is a brownfield GSD initialization: the app was built prior to GSD adoption (see git history predating the `Start of GSD process` commit), then a 4-agent codebase mapping pass (`.planning/codebase/`) produced `STACK.md`, `ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, and `CONCERNS.md` — the last of which is the direct source for every requirement above.
- Verified during this session: `uv run pytest` → 266 passed; `npm test` → 39 passed; the FastAPI backend boots and serves `/api/health` and `/api/watchlist` correctly.
- Security hygiene fixed during this session (separate from the Active scope above): a live OpenRouter key that had leaked into `.env.example`'s working tree was moved to a gitignored `.env` and the placeholder restored; `db/finally.db` was untracked from git (per PLAN.md §4, only `.gitkeep` should be committed at that path).
- The `agent-teams` git branch (current branch) has diverged substantially from `origin/main` — it carries the full application build plus the GSD tooling install, none of which is on `main` yet. Push/PR strategy for that divergence is still an open decision, deliberately deferred by the user during this session.

## Constraints

- **Regression safety**: All 305 existing tests (266 backend + 39 frontend) must continue passing after every change in this milestone; the Playwright E2E suite in `test/` should also be re-run before considering the milestone done.
- **Static export criticality**: `frontend/next.config.ts`'s `output: 'export'` must keep working after the Next.js major-version bump — this is the single point where a regression would silently break the production Docker image, per `.planning/codebase/CONCERNS.md`.
- **No new features**: Changes in this milestone are fixes/hardening only, scoped strictly to the items above.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Treat existing app as brownfield "Validated", scope this milestone to CONCERNS.md hardening items only | The app is already functionally complete and tested; re-running greenfield questioning/research would be redundant given the codebase audit already surfaced concrete, specific issues | — Pending |
| Chat-router import failure becomes a hard failure at startup (FRAG-01) | LLM module is complete; a silently-swallowed import failure degrades `/api/chat` to an invisible 404 instead of a loud startup error | — Pending |
| Dependency upgrades target latest majors (Next 16, TS 7, ESLint 10, React 19.2), not just patches | User scoped "dependency drift" as in-scope without narrowing to patch-only; static export re-verification is called out as a required check alongside the Next.js bump | — Pending |
| Push/PR strategy for the `agent-teams` branch's large divergence from `main` is deferred | User explicitly asked to proceed straight to project docs instead of deciding branch/PR strategy now | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-16 after initialization*
